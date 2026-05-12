#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SHOULD_ASK 决策门：判断是继续处理还是先追问用户补充信息。"""

from __future__ import annotations

from core.state_machine import ASK_USER, NodeResult
from models.state import AgentState, TurnState


# 各意图下的必需字段（缺失时强制追问）
BLOCKING_FIELDS = {
    "选址诊断": ["城市"],
    "选品决策": ["城市"],
    "财务测算": ["品类", "预算"],
    "风险控制": ["品类"],
}

# 追问话术模板
QUESTION_TEMPLATES = {
    "城市": "你打算在哪个城市/区域开店？",
    "品类": "准备做什么品类？（早餐、粉面、小吃、饮品、快餐...）",
    "预算": "总预算大概多少？（含转让费、装修、设备、首批物料、备用金）",
    "经营方式": "打算自营还是加盟？",
    "具体地址": "有没有看中的具体铺位地址？",
    "月租金": "月租金大概多少？",
    "店铺面积": "店铺面积多大？",
}


class ShouldAskNode:
    """决策门：判断信息是否足够继续，还是需要追问。"""

    name = "should_ask"

    def execute(self, agent_state: AgentState, turn_state: TurnState) -> NodeResult:
        intent = turn_state.classified_intent
        missing = agent_state.get_missing_fields(intent)

        # 如果是补充信息类意图，直接继续处理
        if intent == "补充信息":
            return NodeResult(
                next_node="retrieve_evidence",
                log_summary="补充信息意图，直接继续",
                decision="continue(补充信息)",
            )

        # 检查是否有阻断性缺失（必须先问）
        blocking = BLOCKING_FIELDS.get(intent, [])
        blocking_missing = [f for f in blocking if f in missing]

        # 决策逻辑
        should_ask = False
        questions: list[str] = []

        # ─── 阻断性缺失：第一轮且缺少关键信息时追问 ───
        # 放宽条件：只在第一轮且阻断性字段缺失时追问
        if blocking_missing and agent_state.turn_count == 0:
            should_ask = True
            questions = [QUESTION_TEMPLATES.get(f, f"请提供: {f}") for f in blocking_missing[:2]]
        # 第一轮且画像几乎为空 → 追问基本信息（但最多2个问题，不要拦死）
        elif agent_state.profile_completeness < 0.2 and agent_state.turn_count == 0:
            should_ask = False  # 不阻断，改为非阻塞追问
            priority_fields = ["城市", "品类", "预算"]
            questions = [
                QUESTION_TEMPLATES.get(f, f"请提供: {f}")
                for f in priority_fields if f in missing
            ][:2]
            agent_state.pending_questions = questions

        if should_ask and questions:
            agent_state.pending_questions = questions
            turn_state.output_mode = "ask_user"
            return NodeResult(
                next_node=ASK_USER,
                log_summary=f"追问: {questions}",
                decision=f"ask_user(missing={blocking_missing or missing[:3]})",
            )

        # 信息足够（或非第一轮），继续处理
        # 即使有缺失字段，也可以在回复末尾附带追问
        if missing:
            non_blocking_questions = [
                QUESTION_TEMPLATES.get(f, f"请补充: {f}")
                for f in missing[:2]
            ]
            agent_state.pending_questions = non_blocking_questions

        return NodeResult(
            next_node="retrieve_evidence",
            log_summary=f"continue, completeness={agent_state.profile_completeness:.1f}",
            decision=f"continue(completeness={agent_state.profile_completeness:.1f})",
        )
