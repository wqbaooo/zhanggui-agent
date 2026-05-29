#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from core.readiness import (
    build_readiness_overlay,
    build_readiness_structured,
    detect_readiness_case,
    merge_readiness_overlay,
)
from main import _build_enhanced_message, 开店Agent


USER_CASE = (
    "我即将去江西新余开店，我之前没有开店相关的经验，也不会算账、营销、做主播ip。"
    "我加盟的是南昌的一个品牌叫大口章鱼烧，我想请问能否为我解决？"
)


def test_detects_first_time_franchise_case():
    case = detect_readiness_case(USER_CASE)

    assert case.applies is True
    assert case.city == "新余"
    assert case.brand == "大口章鱼烧"
    assert case.category == "章鱼烧"


def test_overlay_contains_minimum_execution_loop():
    overlay = build_readiness_overlay(USER_CASE)

    assert "Needs More Data" in overlay
    assert "加盟尽调" in overlay
    assert "财务测算" in overlay
    assert "新余选址" in overlay
    assert "不依赖个人主播 IP" in overlay
    assert "加盟后的生命周期" in overlay
    assert "外卖运营账" in overlay
    assert "止损预警账" in overlay
    assert "7 个信息" in overlay


def test_structured_response_has_risks_and_actions():
    structured = build_readiness_structured(USER_CASE)

    assert structured["decision"] == "needs_more_data"
    assert structured["memory_updates"]["城市"] == "新余"
    assert structured["memory_updates"]["品牌"] == "大口章鱼烧"
    assert len(structured["risks"]) >= 3
    assert len(structured["next_actions"]) >= 4
    assert len(structured["questions_for_user"]) >= 4
    assert any("经营看板" in action for action in structured["next_actions"])
    assert any("外卖" in question for question in structured["questions_for_user"])


def test_overlay_is_idempotent():
    once = merge_readiness_overlay(USER_CASE, "基础回答")
    twice = merge_readiness_overlay(USER_CASE, once)

    assert once == twice


def test_structured_response_merges_readiness_without_llm(monkeypatch):
    monkeypatch.setattr("main._langgraph_available", lambda: False)
    monkeypatch.setattr("core.session.Session.get_structured_response", lambda self, text: {
        "response_text": "基础结构化回答",
        "decision": "conditional_go",
        "facts": ["base fact"],
        "assumptions": [],
        "risks": [],
        "scores": {
            "site": None,
            "finance": None,
            "category_fit": None,
            "execution_difficulty": None,
        },
        "next_actions": [],
        "questions_for_user": [],
        "sources": [],
        "artifacts": [],
        "memory_updates": {},
    })

    response = 开店Agent().get_structured_response(USER_CASE)

    assert response["decision"] == "needs_more_data"
    assert response["memory_updates"]["品牌"] == "大口章鱼烧"
    assert any(risk["level"] == "critical" for risk in response["risks"])
    assert "项目审查补齐：新手加盟最低闭环" in response["response_text"]


def test_enhanced_message_keeps_context_compatible_with_readiness():
    message = _build_enhanced_message(
        user_message=USER_CASE,
        context={"city": "新余", "category": "章鱼烧"},
        task_type="risk_review",
    )

    structured = build_readiness_structured(message)

    assert structured["decision"] == "needs_more_data"
    assert structured["memory_updates"]["城市"] == "新余"
