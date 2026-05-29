#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from core.philosophy import (
    build_philosophy_guidance,
    has_philosophy_exposition,
    matching_principles,
)
from graph.prompts import SYSTEM_PROMPT


STORE_OPERATION_CASE = (
    "我接手新余恒太城美食城加盟章鱼烧档口，"
    "现在担心人工、租金、外卖和营销，想知道怎么试营业复盘。"
)


def test_matches_operational_philosophy_principles():
    names = [principle.name for principle in matching_principles(STORE_OPERATION_CASE)]

    assert "primary_contradiction" in names
    assert "practice_to_knowledge_to_practice" in names
    assert "concrete_analysis" in names


def test_philosophy_guidance_is_internal_and_action_oriented():
    guidance = build_philosophy_guidance(STORE_OPERATION_CASE)

    assert "经营哲学方法层" in guidance
    assert "主要矛盾" in guidance
    assert "观察周期" in guidance or "记录字段" in guidance
    assert not has_philosophy_exposition(guidance)


def test_system_prompt_has_philosophy_without_user_facing_preaching():
    assert "经营哲学方法层" in SYSTEM_PROMPT
    assert "苏格拉底追问" in SYSTEM_PROMPT
    assert "主要矛盾分析" in SYSTEM_PROMPT
    assert "实践检验" in SYSTEM_PROMPT
    assert "默认不要写" in SYSTEM_PROMPT


def test_detects_bad_philosophy_exposition():
    assert has_philosophy_exposition("根据矛盾论，你这个店的主要矛盾是人工")
    assert not has_philosophy_exposition("你现在最卡成败的是人工和租金，先拆两个模型算。")
