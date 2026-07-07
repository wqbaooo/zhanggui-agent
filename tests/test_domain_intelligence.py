from core.domain_intelligence import (
    build_domain_context,
    context_for_prompt,
    render_grounded_fallback,
    route_domains,
    validate_grounded_answer,
)
from models.labor import LaborTracking
from models.project import ProjectMemory
from models.sku import SkuCatalog
from models.sop import SopLibrary


PROJECT_ID = "xinyu-hengtai-dakou"


def test_delivery_material_question_queries_rules_hq_catalog_and_inventory():
    context = build_domain_context(PROJECT_ID, "我准备买外卖的东西，你推荐一下")

    assert context["route"]["domains"] == ["procurement"]
    report = context["reports"][0]
    assert report["domain"] == "procurement_inventory"
    assert any("订书机" in item for item in report["professional_guidance"])
    assert any(item["fact"] == "总部目录匹配物料" for item in report["known_facts"])
    assert any(item["fact"] == "本店已记录库存" for item in report["known_facts"])
    assert context["response_contract"]["relationship"].startswith("用户是门店老板")


def test_hq_mapped_local_supplier_is_reported_as_conflict():
    context = build_domain_context(PROJECT_ID, "外卖袋还能不能从本地买平替")

    report = context["reports"][0]
    assert context["status"] == "conflict"
    assert any(item["type"] == "supplier_policy_conflict" for item in report["conflicts"])
    assert any("不得推荐本地平替" in rule for rule in context["response_contract"]["rules"])


def test_labor_question_uses_labor_module():
    context = build_domain_context(PROJECT_ID, "这个月员工工资和加班怎么算")

    assert context["route"]["domains"] == ["labor"]
    assert context["reports"][0]["domain"] == "labor"
    assert any(item["fact"] == "在岗员工" for item in context["reports"][0]["known_facts"])


def test_finance_and_channel_question_fans_out_to_both_domains():
    context = build_domain_context(PROJECT_ID, "最近外卖平台到底赚不赚钱，利润怎么样")

    assert set(context["route"]["domains"]) == {"finance", "channel"}
    assert {report["domain"] for report in context["reports"]} == {"finance", "channel"}


def test_sop_and_risk_question_uses_both_domains():
    context = build_domain_context(PROJECT_ID, "员工打烊卫生和食品安全应该按什么流程")

    assert set(context["route"]["domains"]) == {"sop", "risk"}
    assert {report["domain"] for report in context["reports"]} == {"sop", "risk"}


def test_unknown_question_keeps_general_store_context():
    context = build_domain_context(PROJECT_ID, "你怎么看这件事")

    assert context["route"]["domains"] == ["general"]
    assert context["reports"][0]["domain"] == "general"


def test_missing_data_becomes_question_gap_not_fake_fact(monkeypatch):
    monkeypatch.setattr(ProjectMemory, "load", classmethod(lambda cls, project_id: None))
    monkeypatch.setattr(SkuCatalog, "load", classmethod(lambda cls, project_id: None))
    monkeypatch.setattr(LaborTracking, "load", classmethod(lambda cls, project_id: None))
    monkeypatch.setattr(SopLibrary, "load", classmethod(lambda cls, project_id: None))

    context = build_domain_context("missing-store", "库存和员工工资怎么样")

    assert context["status"] == "needs_input"
    assert any(report["gaps"] for report in context["reports"])
    assert all(
        report["known_facts"] == []
        for report in context["reports"]
    )


def test_router_supports_multi_domain_turns():
    assert set(route_domains("看一下外卖库存和员工排班")) == {
        "inventory",
        "labor",
    }


def test_prompt_context_is_compact_but_keeps_rules_and_conflicts():
    context = build_domain_context(PROJECT_ID, "外卖袋还能不能从本地买平替")
    compact = context_for_prompt(context)

    encoded = str(compact)
    assert len(encoded) < 7000
    assert compact["reports"][0]["hard_rules"]
    assert compact["reports"][0]["conflicts"]
    assert compact["response_contract"]["relationship"].startswith("用户是门店老板")


def test_grounded_fallback_answers_delivery_material_question_without_roleplay():
    context = context_for_prompt(
        build_domain_context(PROJECT_ID, "我准备买外卖的东西，你推荐一下")
    )

    answer = render_grounded_fallback("我准备买外卖的东西，你推荐一下", context)

    assert "订书机" in answer
    assert "总部目录内食材、包装和耗材禁止自行采购平替" in answer
    assert "总部订货目录中查到" in answer
    assert "门店SKU库存中查到" in answer
    assert "顾客" not in answer
    assert "味道" not in answer


def test_follow_up_inherits_previous_delivery_material_scope():
    first = build_domain_context(PROJECT_ID, "我准备买外卖的东西，你推荐一下")
    follow_up = build_domain_context(
        PROJECT_ID,
        "刚才那些里面哪些必须总部买",
        previous_context=first,
    )

    report = follow_up["reports"][0]
    hq_items = next(
        fact["items"]
        for fact in report["known_facts"]
        if fact["fact"] == "总部目录匹配物料"
    )
    assert follow_up["route"]["domains"] == ["procurement"]
    assert any("外卖" in item["name"] for item in hq_items)


def test_channel_profit_does_not_claim_store_profit_is_channel_profit():
    context = build_domain_context(PROJECT_ID, "外卖平台到底赚不赚钱，利润怎么样")
    channel = next(report for report in context["reports"] if report["domain"] == "channel")

    assert any("不能确认外卖渠道单独净利润" in gap for gap in channel["gaps"])


def test_finance_fallback_uses_owner_readable_metric_labels():
    context = context_for_prompt(
        build_domain_context(PROJECT_ID, "最近利润怎么样")
    )
    answer = render_grounded_fallback("最近利润怎么样", context)

    assert "全店净利润" in answer
    assert "net_profit" not in answer


def test_multi_domain_fallback_deduplicates_shared_operation_summary():
    context = context_for_prompt(
        build_domain_context(PROJECT_ID, "外卖平台到底赚不赚钱，利润怎么样")
    )
    answer = render_grounded_fallback("外卖平台到底赚不赚钱，利润怎么样", context)

    assert answer.count("本店已记录：") == 1
    assert "不能证明外卖渠道单独赚钱" in answer


def test_sop_fallback_returns_real_operating_steps():
    context = context_for_prompt(
        build_domain_context(PROJECT_ID, "员工打烊卫生和食品安全应该按什么流程")
    )
    answer = render_grounded_fallback(
        "员工打烊卫生和食品安全应该按什么流程",
        context,
    )

    assert "每日打烊复核" in answer
    assert "复核出餐区卫生" in answer


def test_guardrail_rejects_unknown_procurement_permission_and_fake_zero_stock():
    context = build_domain_context(PROJECT_ID, "我准备买外卖的东西，你推荐一下")
    answer = "订书机总部一般不管控，可以放心买。外卖无纺布袋库存为0。"

    issues = validate_grounded_answer(answer, context)

    assert "把未知采购权限表述为允许" in issues
    assert "把总部目录占位表述为真实零库存" in issues


def test_guardrail_rejects_conditional_local_purchase_after_hard_rule():
    context = build_domain_context(PROJECT_ID, "哪些外卖物料需要总部买")
    answer = "总部物料禁止平替。如果可以本地买，我再推荐本地渠道。"

    assert validate_grounded_answer(answer, context) == ["把未知采购权限表述为允许"]
