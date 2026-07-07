#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from core.case_intelligence import (
    build_case_intelligence_guidance,
    detect_case_context,
    has_theory_exposition,
    matching_case_rules,
    should_split_owner_operator_model,
)
from graph.prompts import RESEARCH_SYSTEM_PROMPT, SYSTEM_PROMPT


STORE_CASE = (
    "我接手新余恒太城美食城档口，加盟大口章鱼烧。"
    "原老板不在店，请两个人人工太高，我准备亲自守店。"
)


def test_detects_franchise_mall_food_court_context():
    context = detect_case_context(STORE_CASE)

    assert context.mode == "加盟"
    assert context.category == "章鱼烧"
    assert context.location_type == "美食城"
    assert context.city_tier == "低线城市"
    assert "hired_staff" in context.signals


def test_matches_owner_operator_and_franchise_rules():
    rules = matching_case_rules(STORE_CASE)
    names = [rule.name for rule in rules]

    assert "owner_operator_vs_hired_staff" in names
    assert "franchise_constraint_first" in names
    assert "mall_food_court_fit" in names


def test_case_guidance_prioritizes_actions_not_theory():
    guidance = build_case_intelligence_guidance(STORE_CASE)

    assert "案例智能判断层" in guidance
    assert "老板亲自守店模型和请人模型分开算" in guidance
    assert "结论、关键数字/缺失数据、下一步动作、止损线" in guidance
    assert not has_theory_exposition(guidance)


def test_owner_operator_split_required_for_staffing_cases():
    assert should_split_owner_operator_model(STORE_CASE) is True
    assert should_split_owner_operator_model("我想了解开业证照办理") is False


def test_prompt_contract_internalizes_theory_and_cases():
    assert "不是当前门店事实" in RESEARCH_SYSTEM_PROMPT
    assert "检查项、数据缺口、风险阈值和下一步动作" in RESEARCH_SYSTEM_PROMPT
    assert "新余恒太城五楼大口章鱼烧" in SYSTEM_PROMPT
    assert "真实经营资料持续入库" in SYSTEM_PROMPT
    assert "不推荐加盟品牌" in SYSTEM_PROMPT
