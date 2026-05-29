#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Operational philosophy guidance for the restaurant-opening agent.

The agent should use philosophical methods as internal decision discipline,
not as user-facing theory exposition.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List


PHILOSOPHY_EXPOSITION_TERMS = (
    "马克思主义告诉你",
    "毛泽东思想告诉你",
    "苏格拉底认为",
    "根据矛盾论",
    "根据实践论",
)


@dataclass(frozen=True)
class PhilosophyPrinciple:
    name: str
    trigger_terms: tuple[str, ...]
    internal_method: str
    user_facing_behavior: str


PRINCIPLES: List[PhilosophyPrinciple] = [
    PhilosophyPrinciple(
        name="socratic_questioning",
        trigger_terms=("不确定", "不知道", "想问", "能不能", "靠谱吗", "怎么判断"),
        internal_method="先找缺失前提，再用结构化问题逼近关键事实。",
        user_facing_behavior="少问开放题，多给 A/B/C 选项和为什么要问。",
    ),
    PhilosophyPrinciple(
        name="primary_contradiction",
        trigger_terms=("转租", "加盟", "选址", "亏", "利润", "人工", "租金", "外卖"),
        internal_method="先识别当前阶段的主要矛盾，避免把次要问题讲成重点。",
        user_facing_behavior="直接指出最卡成败的一两个变量，例如租金、人工、总部约束或客流转化。",
    ),
    PhilosophyPrinciple(
        name="practice_to_knowledge_to_practice",
        trigger_terms=("试营业", "运营", "复盘", "数据", "营销", "活动", "菜单"),
        internal_method="把判断放回实践检验：假设、动作、数据、复盘、再调整。",
        user_facing_behavior="给出小实验、观察周期、记录字段和止损线。",
    ),
    PhilosophyPrinciple(
        name="concrete_analysis",
        trigger_terms=("商场", "美食城", "县城", "新余", "品牌", "品类", "档口"),
        internal_method="具体问题具体分析，不能把别的城市、别的品牌、别的地段经验直接套用。",
        user_facing_behavior="要求用户补地段、品牌约束、客群、竞品和真实流水，而不是泛泛建议。",
    ),
    PhilosophyPrinciple(
        name="from_customers_to_customers",
        trigger_terms=("顾客", "复购", "差评", "口味", "排队", "人流", "转化"),
        internal_method="从真实顾客行为中来，到产品、价格、动线和服务改造中去。",
        user_facing_behavior="优先看顾客买不买、为什么不买、买完回不回来。",
    ),
]


def matching_principles(text: str) -> List[PhilosophyPrinciple]:
    """Return operational principles relevant to the message."""
    normalized = text or ""
    scored: List[tuple[int, PhilosophyPrinciple]] = []
    for principle in PRINCIPLES:
        score = sum(1 for term in principle.trigger_terms if term in normalized)
        if score:
            scored.append((score, principle))
    return [principle for _, principle in sorted(scored, key=lambda item: item[0], reverse=True)]


def build_philosophy_guidance(text: str) -> str:
    """Build internal guidance for applying philosophy as business judgment."""
    principles = matching_principles(text)
    if not principles:
        return ""

    lines = [
        "## 经营哲学方法层（内部使用，不要讲成哲学课）",
        "把苏格拉底追问、矛盾分析、实践检验、具体问题具体分析内化成判断动作。",
        "默认不要展示哲学名词或政治思想标签；只输出经营结论、验证动作和复盘标准。",
        "本轮优先使用:",
    ]
    for principle in principles[:3]:
        lines.append(f"- {principle.name}: {principle.internal_method} 输出方式: {principle.user_facing_behavior}")
    return "\n".join(lines)


def has_philosophy_exposition(text: str) -> bool:
    """Detect user-facing philosophy exposition that should be avoided by default."""
    return any(term in (text or "") for term in PHILOSOPHY_EXPOSITION_TERMS)
