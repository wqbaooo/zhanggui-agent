from pathlib import Path

from fastapi.testclient import TestClient

import config
import models.project as project_model
from core.finance_agent import READ_ONLY_TOOLS, FinanceAgentPlan, _deterministic_answer, answer_finance_question
from core.finance_intelligence import build_finance_agent_insights
from core.finance_runtime import FinanceAgentRuntime
from core.finance_skills import READ_ONLY_FINANCE_SKILLS
from core.finance_answers import answer_finance_question as answer_owner_finance_question
from models.finance_ledger import FinanceLedger
from models.agent_sessions import AgentSessionStore
from server.main import app


PROJECT_ID = "finance-agent-store"


def _ledger(tmp_path: Path, monkeypatch) -> FinanceLedger:
    monkeypatch.setattr(config, "PROJECT_DATA_DIR", tmp_path)
    monkeypatch.setattr(project_model, "PROJECT_DATA_DIR", tmp_path)
    ledger = FinanceLedger.for_project(PROJECT_ID)
    ledger.ensure_store(PROJECT_ID, "财务Agent测试店", "2026-07-01")
    ledger.record_merchant_net_sale(
        PROJECT_ID,
        business_date="2026-07-01",
        channel="客如云",
        amount_minor=10_000,
        source_basis="测试",
        evidence_status="confirmed",
        settlement_state="store_account_received",
    )
    ledger.create_bookkeeping_record(
        store_id=PROJECT_ID,
        transaction_date="2026-07-02",
        direction="outflow",
        amount_minor=2_205,
        transaction_kind="operating_expense",
        business_scope="store",
        category_code="6003",
        category_name="水电燃气",
        account_key="store-icbc",
        counter_account_key=None,
        counterparty="电力公司",
        summary="电费",
        source_type="manual",
        source_reference="test-electricity",
        confidence="confirmed",
        status="posted",
    )
    return ledger


def test_exact_missing_days_question_returns_date_coverage_not_profit_inputs(tmp_path, monkeypatch):
    ledger = _ledger(tmp_path, monkeypatch)
    response = answer_finance_question(
        ledger,
        PROJECT_ID,
        "我还有哪些天的账单没有录入 是空缺的 不完整的",
        "2026-07-01",
        "2026-07-04",
        use_model=False,
    )

    assert response["intent"] == "date_coverage"
    assert "07月03日至07月04日" in response["answer"]
    assert "07月02日" in response["answer"]
    assert "食材成本" not in response["answer"]
    assert "daily_close" not in str(response)
    assert [item["step"] for item in response["execution_trace"]] == [
        "理解问题", "核对财务事实", "一致性检查",
    ]


def test_missing_days_answer_is_conclusion_first_and_scannable():
    answer = _deterministic_answer(
        FinanceAgentPlan("date_coverage", ("finance_date_coverage",), "逐日核对"),
        [{
            "tool": "finance_date_coverage",
            "empty_days": ["2026-07-22", "2026-07-23"],
            "activity_without_sales": ["2026-07-20"],
            "platform_only_days": ["2026-07-13", "2026-07-14"],
            "open_close_days": ["2026-07-01"],
        }],
        "2026-07-27",
    )

    assert answer.startswith("**核对结论**")
    assert "共 **6 天**存在待补项" in answer
    assert "- **完全空缺**：07月22日至07月23日" in answer
    assert "- **缺营业收入**：07月20日" in answer
    assert "**建议先补**" in answer


def test_master_agent_routes_missing_days_to_date_coverage(tmp_path, monkeypatch):
    ledger = _ledger(tmp_path, monkeypatch)
    monkeypatch.setattr(FinanceLedger, "for_project", classmethod(lambda cls, project_id: ledger))

    answer = answer_owner_finance_question("我还有哪些天的账单没有录入？", PROJECT_ID)

    assert answer is not None
    assert answer.startswith("**核对结论**")
    assert "**完全空缺**" in answer
    assert "当前缺口" not in answer


def test_model_selects_read_only_tool_and_bad_answer_falls_back_to_facts(tmp_path, monkeypatch):
    ledger = _ledger(tmp_path, monkeypatch)

    class FakeGateway:
        route = type("Route", (), {"provider": "deepseek", "model": "deepseek-chat"})()

        def __init__(self):
            self.calls = 0

        def json_completion(self, system, user, *, max_tokens):
            self.calls += 1
            if self.calls == 1:
                return {"intent": "date_coverage", "tools": ["finance_date_coverage"], "period_interpretation": "逐日核对"}
            return {"answer": "只缺7月4日。"}

    response = answer_finance_question(
        ledger, PROJECT_ID, "哪些天没录", "2026-07-01", "2026-07-04", gateway_factory=FakeGateway,
    )

    assert response["agent"]["mode"] == "模型规划"
    assert response["agent"]["model_used"] is True
    assert "07月03日至07月04日" in response["answer"]
    assert response["agent"]["fallback_reason"] == "模型回答未通过事实完整性校验"


def test_unknown_model_tool_is_rejected_and_never_executed(tmp_path, monkeypatch):
    ledger = _ledger(tmp_path, monkeypatch)

    class BadGateway:
        def json_completion(self, system, user, *, max_tokens):
            return {"intent": "write", "tools": ["delete_ledger"], "period_interpretation": "删除"}

    response = answer_finance_question(
        ledger, PROJECT_ID, "哪些天没录", "2026-07-01", "2026-07-04", gateway_factory=BadGateway,
    )

    assert "delete_ledger" not in READ_ONLY_TOOLS
    assert response["agent"]["mode"] == "规则兜底"
    assert "越权工具" in response["agent"]["fallback_reason"]
    assert "07月03日至07月04日" in response["answer"]


def test_finance_skills_are_read_only_and_exposed_after_use(tmp_path, monkeypatch):
    ledger = _ledger(tmp_path, monkeypatch)
    assert all(skill.risk_level == "read_only" for skill in READ_ONLY_FINANCE_SKILLS)

    response = answer_finance_question(
        ledger, PROJECT_ID, "哪些天没录", "2026-07-01", "2026-07-04", use_model=False,
    )

    assert response["skills_used"][0]["name"] == "daily-ledger-completeness"
    assert response["skills_used"][0]["tool"] == "finance_date_coverage"


def test_finance_query_api_exposes_agent_trace_without_calling_network(tmp_path, monkeypatch):
    _ledger(tmp_path, monkeypatch)
    response = TestClient(app).post(
        f"/api/projects/{PROJECT_ID}/finance/query",
        json={"query": "我还有哪些天的账单没有录入 是空缺的 不完整的", "start": "2026-07-01", "end": "2026-07-04"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["intent"] == "date_coverage"
    assert body["execution_trace"][-1]["step"] == "一致性检查"
    assert body["sources"][0]["label"] == "专业资金台账"


def test_finance_runtime_treats_greeting_as_conversation_and_persists_scope(tmp_path, monkeypatch):
    ledger = _ledger(tmp_path, monkeypatch)
    store = AgentSessionStore(tmp_path / "agent.sqlite3")
    result = FinanceAgentRuntime(ledger, store).run(
        PROJECT_ID, "你好", "2026-07-01", "2026-07-04", use_model=False,
    )

    assert result["intent"] == "social"
    assert result["conversation_mode"] == "social"
    assert result["metrics"] == []
    assert result["execution_trace"] == []
    session = store.get_session(PROJECT_ID, result["session_id"])
    assert session is not None and session["scope"] == "finance"
    assert [item["role"] for item in session["messages"]] == ["user", "assistant"]


def test_finance_runtime_identity_question_uses_model_conversation_without_ledger(tmp_path, monkeypatch):
    ledger = _ledger(tmp_path, monkeypatch)
    store = AgentSessionStore(tmp_path / "agent.sqlite3")

    class DialogueGateway:
        route = type("Route", (), {"provider": "deepseek", "model": "deepseek-v4-pro"})()

        def json_completion(self, system, user, *, max_tokens):
            assert "conversation" in system
            assert "你是谁" in user
            return {
                "mode": "conversation",
                "reply": "我是这家店的财务 Agent，负责把每笔钱的来源、位置和用途理清楚。",
            }

    result = FinanceAgentRuntime(ledger, store, gateway_factory=DialogueGateway).run(
        PROJECT_ID, "你是谁", "2026-07-01", "2026-07-04", use_model=True,
    )

    assert result["intent"] == "conversation"
    assert result["conversation_mode"] == "social"
    assert result["metrics"] == []
    assert result["execution_trace"] == []
    assert result["agent"]["provider"] == "deepseek"
    assert result["agent"]["model_used"] is True
    assert store.get_preference_profile(PROJECT_ID, scope="finance") == []


def test_finance_runtime_accepts_model_led_finance_analysis_without_keyword_guard(tmp_path, monkeypatch):
    ledger = _ledger(tmp_path, monkeypatch)
    store = AgentSessionStore(tmp_path / "agent.sqlite3")

    class AnalysisGateway:
        route = type("Route", (), {"provider": "deepseek", "model": "deepseek-v4-pro"})()

        def __init__(self):
            self.calls = 0

        def json_completion(self, system, user, *, max_tokens):
            self.calls += 1
            if "判断当前话语" in system:
                return {
                    "mode": "finance_question",
                    "goal": "综合分析所选期间财务情况",
                    "reply": "",
                }
            if "规划器" in system:
                return {
                    "intent": "comprehensive_analysis",
                    "tools": [
                        "finance_metric_summary",
                        "finance_funds_status",
                        "finance_profit_readiness",
                    ],
                    "period_interpretation": "综合分析所选期间",
                }
            return {"answer": "**财务结论**\n\n当前收入已有记录，但成本资料仍不完整，暂不能确认真实净利润。"}

    result = FinanceAgentRuntime(ledger, store, gateway_factory=AnalysisGateway).run(
        PROJECT_ID,
        "你能不能帮我专业的分析一下我的财务情况吗",
        "2026-07-01",
        "2026-07-04",
        use_model=True,
    )

    assert result["conversation_mode"] == "finance"
    assert result["intent"] == "comprehensive_analysis"
    assert result["turn_route"] == "model"
    assert result["execution_trace"]
    assert "负责收入" not in result["answer"]
    assert {item["metric_code"] for item in result["metrics"]} >= {
        "revenue", "operating_net_profit", "former_owner_receivable",
    }


def test_finance_runtime_uses_history_for_vague_analysis_follow_up(tmp_path, monkeypatch):
    ledger = _ledger(tmp_path, monkeypatch)
    store = AgentSessionStore(tmp_path / "agent.sqlite3")

    class ContextGateway:
        route = type("Route", (), {"provider": "deepseek", "model": "deepseek-v4-pro"})()

        def json_completion(self, system, user, *, max_tokens):
            if "判断当前话语" in system:
                assert "专业分析一下我的财务情况" in user
                assert "那你帮我分析一下啊" in user
                return {"mode": "finance_question", "goal": "延续上一轮财务分析请求", "reply": ""}
            if "规划器" in system:
                return {
                    "intent": "comprehensive_analysis",
                    "tools": ["finance_metric_summary", "finance_profit_readiness"],
                    "period_interpretation": "延续上一轮，综合分析所选期间",
                }
            return {"answer": "**财务结论**\n\n收入已记录；成本缺口未补齐前，真实净利润仍待核算。"}

    session_id = store.ensure_session(PROJECT_ID, None, scope="finance", title="财务分析")
    store.append_message(session_id, "user", "你能不能帮我专业分析一下我的财务情况吗")
    store.append_message(session_id, "assistant", "可以，我会结合台账做综合分析。")

    result = FinanceAgentRuntime(ledger, store, gateway_factory=ContextGateway).run(
        PROJECT_ID,
        "那你帮我分析一下啊",
        "2026-07-01",
        "2026-07-04",
        session_id=session_id,
        use_model=True,
    )

    assert result["conversation_mode"] == "finance"
    assert result["execution_trace"]
    assert "财务 Agent，负责" not in result["answer"]


def test_finance_runtime_never_executes_write_from_conversation_route(tmp_path, monkeypatch):
    ledger = _ledger(tmp_path, monkeypatch)
    store = AgentSessionStore(tmp_path / "agent.sqlite3")

    class WriteGateway:
        route = type("Route", (), {"provider": "deepseek", "model": "deepseek-v4-pro"})()

        def json_completion(self, system, user, *, max_tokens):
            return {
                "mode": "finance_action",
                "goal": "删除一笔账",
                "reply": "我可以先定位并整理成待确认操作；没有你的确认，不会删除正式台账。",
            }

    result = FinanceAgentRuntime(ledger, store, gateway_factory=WriteGateway).run(
        PROJECT_ID, "把昨天那笔电费删掉", "2026-07-01", "2026-07-04", use_model=True,
    )

    assert result["conversation_mode"] == "finance_action"
    assert result["execution_plan"]["status"] != "completed"
    assert result["execution_trace"][-1]["detail"] == "正式台账尚未写入"
    assert len(ledger.list_bookkeeping_records(PROJECT_ID)) == 1


def test_finance_runtime_queues_cross_domain_work_through_master(tmp_path, monkeypatch):
    ledger = _ledger(tmp_path, monkeypatch)
    store = AgentSessionStore(tmp_path / "agent.sqlite3")

    class CrossModuleGateway:
        route = type("Route", (), {"provider": "deepseek", "model": "deepseek-v4-pro"})()

        def json_completion(self, system, user, *, max_tokens):
            return {
                "mode": "cross_module",
                "goal": "核对库存损耗对成本的影响",
                "target_agent": "inventory",
                "reply": "这需要先由库存 Agent 核对实盘与耗用事实，再回到财务核算成本。",
            }

    result = FinanceAgentRuntime(
        ledger, store, gateway_factory=CrossModuleGateway,
    ).run(
        PROJECT_ID, "帮我核对库存损耗对成本的影响", "2026-07-01", "2026-07-04",
        use_model=True,
    )

    assert result["handoff"]["status"] == "queued_for_master"
    assert result["handoff"]["coordinator_agent"] == "master"
    queued = store.list_handoffs(PROJECT_ID, status="queued_for_master")
    assert len(queued) == 1
    assert queued[0]["source_agent"] == "finance"
    assert queued[0]["target_agent"] == "inventory"


def test_finance_runtime_builds_then_confirms_real_execution_plan(tmp_path, monkeypatch):
    ledger = _ledger(tmp_path, monkeypatch)
    ledger.upsert_fund_account(
        PROJECT_ID,
        account_key="agent-store-icbc",
        name="工商银行店铺账户",
        account_kind="bank",
        owner_kind="store",
        is_store_controlled=True,
        institution="工商银行",
        effective_from="2026-07-01",
    )
    store = AgentSessionStore(tmp_path / "agent.sqlite3")

    class ActionGateway:
        route = type("Route", (), {"provider": "deepseek", "model": "deepseek-v4-pro"})()

        def json_completion(self, system, user, *, max_tokens):
            return {
                "mode": "finance_action",
                "goal": "记录店铺电费",
                "reply": "",
            }

    records_before = len(ledger.list_bookkeeping_records(PROJECT_ID))
    draft = FinanceAgentRuntime(ledger, store, gateway_factory=ActionGateway).run(
        PROJECT_ID,
        "昨天店铺电费花了22.05元，用工商银行卡",
        "2026-07-01",
        "2026-07-04",
        use_model=True,
    )

    assert draft["conversation_mode"] == "finance_action"
    assert draft["execution_plan"]["status"] == "awaiting_confirmation"
    assert len(ledger.list_bookkeeping_records(PROJECT_ID)) == records_before

    completed = FinanceAgentRuntime(ledger, store, gateway_factory=ActionGateway).run(
        PROJECT_ID,
        "确认执行",
        "2026-07-01",
        "2026-07-04",
        session_id=draft["session_id"],
        use_model=True,
    )

    assert completed["conversation_mode"] == "finance_action_completed"
    assert completed["execution_plan"]["status"] == "completed"
    assert len(ledger.list_bookkeeping_records(PROJECT_ID)) == records_before + 1


def test_finance_runtime_identity_fallback_never_defaults_to_revenue(tmp_path, monkeypatch):
    ledger = _ledger(tmp_path, monkeypatch)
    store = AgentSessionStore(tmp_path / "agent.sqlite3")
    result = FinanceAgentRuntime(ledger, store).run(
        PROJECT_ID, "你是谁", "2026-07-01", "2026-07-04", use_model=False,
    )

    assert result["intent"] == "conversation"
    assert "财务 Agent" in result["answer"]
    assert "营业收入为" not in result["answer"]
    assert result["metrics"] == []


def test_finance_runtime_unknown_language_asks_for_clarification_not_metrics(tmp_path, monkeypatch):
    ledger = _ledger(tmp_path, monkeypatch)
    store = AgentSessionStore(tmp_path / "agent.sqlite3")
    result = FinanceAgentRuntime(ledger, store).run(
        PROJECT_ID, "你觉得呢", "2026-07-01", "2026-07-04", use_model=False,
    )

    assert result["conversation_mode"] == "social"
    assert result["metrics"] == []
    assert "继续直接说" in result["answer"]


def test_finance_runtime_learns_only_explicit_topic_interest(tmp_path, monkeypatch):
    ledger = _ledger(tmp_path, monkeypatch)
    store = AgentSessionStore(tmp_path / "agent.sqlite3")
    result = FinanceAgentRuntime(ledger, store).run(
        PROJECT_ID, "哪些钱还没到店铺工商银行？", "2026-07-01", "2026-07-04", use_model=False,
    )

    assert result["learned_topic"] == "funds_settlement"
    assert store.get_preference_profile(PROJECT_ID, scope="finance")[0]["topic"] == "funds_settlement"


def test_daily_finance_insights_are_fact_backed_and_preference_ranked(tmp_path, monkeypatch):
    ledger = _ledger(tmp_path, monkeypatch)
    result = build_finance_agent_insights(
        ledger, PROJECT_ID, "2026-07-04",
        [{"topic": "daily_completeness", "count": 3, "last_seen_at": "2026-07-04T10:00:00+08:00"}],
    )

    assert result["schema_version"] == "finance_agent_insights_v1"
    assert result["agent"]["scope"] == "finance"
    assert result["daily_brief"]["items"][0]["topic"] == "daily_completeness"
    assert result["daily_brief"]["items"][0]["preference_boosted"] is True


def test_finance_query_api_greeting_does_not_generate_report(tmp_path, monkeypatch):
    _ledger(tmp_path, monkeypatch)
    response = TestClient(app).post(
        f"/api/projects/{PROJECT_ID}/finance/query",
        json={"query": "你好", "start": "2026-07-01", "end": "2026-07-04"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["conversation_mode"] == "social"
    assert body["metrics"] == []
    assert body["agent"]["scope"] == "finance"


def test_finance_query_api_identity_does_not_generate_revenue_report(tmp_path, monkeypatch):
    _ledger(tmp_path, monkeypatch)
    response = TestClient(app).post(
        f"/api/projects/{PROJECT_ID}/finance/query",
        json={"query": "你是谁", "start": "2026-07-01", "end": "2026-07-04"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["intent"] == "conversation"
    assert body["metrics"] == []
    assert "财务 Agent" in body["answer"]
    assert "营业收入为" not in body["answer"]
