#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Case intelligence rules for restaurant opening decisions.

This module does not scrape or store external cases. It defines the first
small contract for turning real store cases, franchisee experience, and
investor-style judgment into agent behavior.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List

from core.case_repository import RestaurantCase, load_default_repository


THEORY_EXPOSITION_TERMS = (
    "经济学告诉你",
    "消费学告诉你",
    "根据价格弹性理论",
    "根据消费者行为理论",
    "根据某某论文",
)


ROLE_WEIGHTS: Dict[str, int] = {
    "legal_or_regulatory": 100,
    "verified_store_data": 95,
    "super_franchisee": 85,
    "operator": 80,
    "single_store_owner": 75,
    "investor": 70,
    "platform_operator": 65,
    "brand_claim": 25,
    "influencer_content": 20,
}


@dataclass(frozen=True)
class CaseContext:
    """Detected business context used to choose case perspectives."""

    mode: str = ""
    category: str = ""
    location_type: str = ""
    city_tier: str = ""
    staffing_model: str = ""
    signals: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class CaseRule:
    """A reusable case-derived operating rule."""

    name: str
    applies_to: List[str]
    warning_signal: str
    agent_rule: str
    preferred_roles: List[str]


CASE_RULES: List[CaseRule] = [
    CaseRule(
        name="owner_operator_vs_hired_staff",
        applies_to=["加盟", "小吃", "商场", "档口", "低客单"],
        warning_signal="营业额看起来不低，但请人后净利很薄",
        agent_rule="必须把老板亲自守店模型和请人模型分开算；不能只看营业额。",
        preferred_roles=["verified_store_data", "single_store_owner", "super_franchisee"],
    ),
    CaseRule(
        name="franchise_constraint_first",
        applies_to=["加盟", "品牌", "总部", "原料", "合同"],
        warning_signal="总部规则不清楚，却直接给自营式运营建议",
        agent_rule="先确认加盟约束：能否改价格、能否加品类、是否强制采购、外卖活动是否需总部批准。",
        preferred_roles=["legal_or_regulatory", "super_franchisee", "operator"],
    ),
    CaseRule(
        name="single_store_replicability",
        applies_to=["扩店", "投资", "超级加盟商", "多店"],
        warning_signal="利润主要来自老板本人不拿工资或超长时间守店",
        agent_rule="如果离开老板本人仍不能正现金流，只能算自雇店，不能按投资型门店判断。",
        preferred_roles=["super_franchisee", "investor", "verified_store_data"],
    ),
    CaseRule(
        name="platform_margin_erosion",
        applies_to=["外卖", "满减", "平台", "团购"],
        warning_signal="单量上升但利润没有上升",
        agent_rule="外卖和团购必须单独算扣点、满减、包装、配送和核销后的单均利润。",
        preferred_roles=["platform_operator", "operator", "verified_store_data"],
    ),
    CaseRule(
        name="mall_food_court_fit",
        applies_to=["商场", "美食城", "档口", "小吃"],
        warning_signal="商场有流量，但品类不匹配或转化弱",
        agent_rule="商场档口优先看高峰时段转化、出餐速度、客单价和同层竞品，不只看总人流。",
        preferred_roles=["operator", "single_store_owner", "verified_store_data"],
    ),
]


def detect_case_context(text: str) -> CaseContext:
    """Extract coarse case context from a user message."""
    normalized = text or ""
    signals: List[str] = []

    mode = "加盟" if any(k in normalized for k in ("加盟", "总部", "品牌")) else ""
    if mode:
        signals.append("franchise")

    category = _first_match(normalized, ("章鱼烧", "小吃", "早餐", "奶茶", "咖啡", "烧烤", "快餐"))
    if category:
        signals.append(f"category:{category}")

    location_type = _first_match(normalized, ("商场", "美食城", "档口", "社区", "学校", "街边", "夜市"))
    if location_type:
        signals.append(f"location:{location_type}")

    city_tier = "低线城市" if any(k in normalized for k in ("县城", "三四线", "新余", "乡镇")) else ""
    if city_tier:
        signals.append("lower_tier_city")

    staffing_model = ""
    if any(k in normalized for k in ("请人", "员工", "两个人", "人工")):
        staffing_model = "请人模型"
        signals.append("hired_staff")
    if any(k in normalized for k in ("亲自", "自己守", "老板守店")):
        staffing_model = "老板亲自守店"
        signals.append("owner_operator")

    return CaseContext(
        mode=mode,
        category=category,
        location_type=location_type,
        city_tier=city_tier,
        staffing_model=staffing_model,
        signals=signals,
    )


def matching_case_rules(text: str) -> List[CaseRule]:
    """Return case rules whose trigger terms appear in the message."""
    normalized = text or ""
    scored: List[tuple[int, CaseRule]] = []
    for rule in CASE_RULES:
        score = sum(1 for term in rule.applies_to if term and term in normalized)
        if score:
            role_bonus = max(ROLE_WEIGHTS.get(role, 0) for role in rule.preferred_roles)
            scored.append((score * 1000 + role_bonus, rule))
    return [rule for _, rule in sorted(scored, key=lambda item: item[0], reverse=True)]


def build_case_intelligence_guidance(text: str) -> str:
    """Build internal prompt guidance for the current user message."""
    rules = matching_case_rules(text)
    similar_cases = find_similar_external_cases(text, limit=3)
    if not rules and not similar_cases:
        return ""

    context = detect_case_context(text)
    lines = [
        "## 案例智能判断层（内部使用，不要作为理论课输出）",
        "优先把真实门店样本、加盟商复盘、超级加盟商经验和投资人视角转成动作建议。",
        "默认不要展示理论名词、学科标签或论文出处；除非用户追问依据。",
    ]
    if context.signals:
        lines.append(f"识别到的经营场景: {', '.join(context.signals)}")
    if rules:
        lines.append("本轮优先应用这些经验规则:")
    for rule in rules[:4]:
        lines.append(f"- {rule.name}: {rule.agent_rule}")
    if similar_cases:
        lines.append("可借鉴的外部案例规则（内部权重，不要直接堆案例给用户）:")
        for case in similar_cases:
            role = case.source_role or "unknown"
            confidence = case.confidence or "medium"
            lines.append(f"- {case.case_id} [{role}/{confidence}]: {case.agent_rule}")
    lines.append("回答必须落到：结论、关键数字/缺失数据、下一步动作、止损线。")
    return "\n".join(lines)


def find_similar_external_cases(text: str, limit: int = 3) -> List[RestaurantCase]:
    """Return similar structured external cases for prompt grounding."""
    context = detect_case_context(text)
    filters = {
        "mode": context.mode,
        "category": context.category,
        "location_type": context.location_type,
        "city_tier": context.city_tier,
        "staffing_model": context.staffing_model,
    }
    try:
        return load_default_repository().search(text, filters=filters, limit=limit)
    except Exception:
        return []


def should_split_owner_operator_model(text: str) -> bool:
    """Whether the agent must compare owner-operated and hired-staff economics."""
    normalized = text or ""
    return any(k in normalized for k in ("请人", "员工", "人工", "老板不在", "亲自守店", "自己守"))


def has_theory_exposition(text: str) -> bool:
    """Detect user-facing theory exposition that should be avoided by default."""
    return any(term in (text or "") for term in THEORY_EXPOSITION_TERMS)


def _first_match(text: str, candidates: tuple[str, ...]) -> str:
    for candidate in candidates:
        if candidate in text:
            return candidate
    return ""
