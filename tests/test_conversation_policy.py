from core.conversation_policy import plan_conversation_turn
from main import 掌柜Agent


def test_greeting_is_a_lightweight_conversation_without_business_context():
    plan = plan_conversation_turn("你好")

    assert plan.intent == "social"
    assert plan.load_business_context is False
    assert plan.allowed_tools == ()
    assert plan.direct_reply == "你好，老板。今天想先看店里的哪件事？"


def test_acknowledgement_does_not_restart_a_store_report():
    plan = plan_conversation_turn("好的，谢谢")

    assert plan.intent == "social"
    assert plan.load_business_context is False
    assert plan.allowed_tools == ()
    assert "不客气" in (plan.direct_reply or "")


def test_finance_question_loads_only_finance_capabilities():
    plan = plan_conversation_turn("这个月实际赚了多少钱？")

    assert plan.intent == "business_question"
    assert plan.load_business_context is True
    assert plan.allowed_tools == ("finance",)
    assert plan.direct_reply is None


def test_recording_request_is_an_action_not_a_generic_report():
    plan = plan_conversation_turn("帮我记一笔今天买章鱼粉的进货支出")

    assert plan.intent == "business_action"
    assert plan.load_business_context is True
    assert set(plan.allowed_tools) == {"finance", "inventory"}


def test_agent_greeting_never_calls_reasoning_runtime_or_trusted_chain(monkeypatch):
    agent = 掌柜Agent.__new__(掌柜Agent)
    agent._project_id = "xinyu-hengtai-dakou"
    agent._last_domain_context = {}
    agent._last_answer_guardrail = []
    agent._last_answer_source = "not_run"
    agent._last_runtime_provider = None
    agent._last_runtime_model = None
    agent._runtime_fallback_reason = None
    agent._reasoning_runtime = object()
    agent._use_langgraph = True

    monkeypatch.setattr(
        agent,
        "_trusted_runtime_response",
        lambda _message: (_ for _ in ()).throw(AssertionError("trusted chain should not run")),
    )

    assert agent.get_response("你好") == "你好，老板。今天想先看店里的哪件事？"
    metadata = agent.get_run_metadata()
    assert metadata["answer_source"] == "conversation_policy"
    assert metadata["domains"] == []
    assert metadata["intent"] == "social"


def test_runtime_failure_is_disclosed_in_metadata(monkeypatch):
    class BrokenRuntime:
        provider = "hermes"

        def get_response(self, _message, _context):
            raise RuntimeError("connection refused")

    agent = 掌柜Agent.__new__(掌柜Agent)
    agent._project_id = "xinyu-hengtai-dakou"
    agent._last_domain_context = {}
    agent._last_answer_guardrail = []
    agent._last_answer_source = "not_run"
    agent._last_runtime_provider = None
    agent._last_runtime_model = None
    agent._runtime_fallback_reason = None
    agent._reasoning_runtime = BrokenRuntime()
    agent._use_langgraph = True
    monkeypatch.setattr(agent, "_trusted_runtime_response", lambda _message: "可信链回答")

    assert agent.get_response("库存还缺哪些信息？") == "可信链回答"
    metadata = agent.get_run_metadata()
    assert metadata["answer_source"] == "runtime_fallback"
    assert metadata["requested_runtime"] == "hermes"
    assert metadata["runtime_fallback"] is True
    assert "connection refused" in metadata["runtime_fallback_reason"]
