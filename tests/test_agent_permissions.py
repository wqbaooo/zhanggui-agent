from core.agent_permissions import (
    DEFAULT_PROJECT_ID,
    authorize_tool_call,
    enforce_project_scope,
)
from graph.agent import _guard_tool_calls
from langchain_core.messages import AIMessage


def test_read_tools_do_not_require_confirmation():
    decision = authorize_tool_call(
        "get_financial_context",
        {"project_id": DEFAULT_PROJECT_ID},
        "帮我看看今天的钱在哪里",
    )
    assert decision.allowed is True
    assert decision.required_level == 0


def test_confirm_fact_requires_current_user_confirmation():
    denied = authorize_tool_call(
        "confirm_fact",
        {"fact_id": "fact-1", "project_id": DEFAULT_PROJECT_ID},
        "帮我看一下这条",
    )
    allowed = authorize_tool_call(
        "confirm_fact",
        {"fact_id": "fact-1", "project_id": DEFAULT_PROJECT_ID},
        "确认入账",
        recent_context="事实详情：fact-1",
    )
    assert denied.allowed is False
    assert allowed.allowed is True


def test_finance_plan_execution_requires_visible_plan_and_explicit_confirmation():
    args = {
        "plan_id": "finance-plan:xinyu-hengtai-dakou:abc123",
        "project_id": DEFAULT_PROJECT_ID,
    }
    assert authorize_tool_call(
        "execute_finance_plan",
        args,
        "帮我处理一下",
        recent_context="finance-plan:xinyu-hengtai-dakou:abc123",
    ).allowed is False
    assert authorize_tool_call(
        "execute_finance_plan",
        args,
        "确认执行",
        recent_context="没有展示方案编号",
    ).allowed is False
    assert authorize_tool_call(
        "execute_finance_plan",
        args,
        "确认执行",
        recent_context="方案 finance-plan:xinyu-hengtai-dakou:abc123，收入影响为0",
    ).allowed is True


def test_amount_change_requires_matching_explicit_amount():
    args = {
        "fact_id": "fact-1",
        "new_amount": 1268.5,
        "project_id": DEFAULT_PROJECT_ID,
    }
    assert authorize_tool_call("modify_fact_amount", args, "这笔金额不对").allowed is False
    assert authorize_tool_call("modify_fact_amount", args, "金额改成 1,200").allowed is False
    assert authorize_tool_call(
        "modify_fact_amount",
        args,
        "金额改成 1,268.50",
        recent_context="事实详情：fact-1",
    ).allowed is True


def test_mark_fact_confirmation_must_match_action():
    args = {
        "fact_id": "fact-1",
        "action": "former_owner_collected",
        "project_id": DEFAULT_PROJECT_ID,
    }
    assert authorize_tool_call("mark_fact", args, "标记为退款").allowed is False
    assert authorize_tool_call(
        "mark_fact",
        args,
        "这笔是前老板代收",
        recent_context="事实详情：fact-1",
    ).allowed is True


def test_other_projects_are_rejected():
    try:
        enforce_project_scope("demo-store")
    except PermissionError as exc:
        assert DEFAULT_PROJECT_ID in str(exc)
    else:
        raise AssertionError("other project should be rejected")


def test_unknown_or_external_action_is_denied():
    decision = authorize_tool_call(
        "pay_supplier",
        {"amount": 1000, "project_id": DEFAULT_PROJECT_ID},
        "付给供应商",
    )
    assert decision.allowed is False
    assert decision.required_level == 4


def test_graph_guard_removes_unauthorized_mutation_call():
    response = AIMessage(
        content="",
        tool_calls=[{
            "name": "confirm_fact",
            "args": {"fact_id": "fact-1", "project_id": DEFAULT_PROJECT_ID},
            "id": "call-1",
            "type": "tool_call",
        }],
    )
    guarded = _guard_tool_calls(response, "帮我看看这条")
    assert guarded.tool_calls == []
    assert "明确关联这条事实" in str(guarded.content)


def test_graph_guard_keeps_authorized_mutation_call():
    response = AIMessage(
        content="",
        tool_calls=[{
            "name": "confirm_fact",
            "args": {"fact_id": "fact-1", "project_id": DEFAULT_PROJECT_ID},
            "id": "call-1",
            "type": "tool_call",
        }],
    )
    guarded = _guard_tool_calls(response, "确认入账", "事实详情：fact-1")
    assert guarded.tool_calls == response.tool_calls


def test_confirmation_cannot_mutate_a_different_fact():
    decision = authorize_tool_call(
        "confirm_fact",
        {"fact_id": "fact-2", "project_id": DEFAULT_PROJECT_ID},
        "确认入账",
        recent_context="事实详情：fact-1",
    )
    assert decision.allowed is False
