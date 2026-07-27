from pathlib import Path

from fastapi.testclient import TestClient

import config
import models.project as project_model
from core.finance_agent import READ_ONLY_TOOLS, FinanceAgentPlan, _deterministic_answer, answer_finance_question
from core.finance_answers import answer_finance_question as answer_owner_finance_question
from models.finance_ledger import FinanceLedger
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
