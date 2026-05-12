#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""意图分类节点：识别用户意图，支持LLM辅助和规则降级。"""

from __future__ import annotations

from typing import Any, Dict

from core.llm_client import LLMClient
from core.state_machine import NodeResult
from models.state import AgentState, TurnState


INTENT_KEYWORDS = {
    "开店规划": ["规划", "方案", "计划", "怎么开", "准备开", "想开店", "能不能做", "可不可行", "可行性", "评估"],
    "选址诊断": ["选址", "商圈", "商铺", "位置", "地段", "客流", "动线", "铺位", "门面"],
    "选品决策": ["选品", "品类", "项目", "做什么", "什么品类"],
    "财务测算": ["成本", "利润", "租金", "回本", "投产", "流水", "盈亏", "预算多少"],
    "风险控制": ["风险", "避坑", "合同", "转让", "亏", "防骗", "加盟骗"],
    "营销运营": ["运营", "营销", "推广", "抖音", "团购", "开业活动", "引流"],
}

LLM_PROMPT_TEMPLATE = """你是一个餐饮开店意图分类器。根据用户输入，判断其主要意图。

可选意图：
- 开店规划: 用户想了解完整开店流程或方案可行性
- 选址诊断: 用户有具体地址/商圈，想评估选址
- 选品决策: 用户在纠结做什么品类
- 财务测算: 用户问成本、利润、回本
- 风险控制: 用户问避坑、合同、加盟防骗
- 营销运营: 用户问开业、推广、平台运营
- 补充信息: 用户在回答之前Agent的追问
- 通用咨询: 以上都不匹配

上下文：
- 上一轮意图：{last_intent}
- 对话轮次：{turn_count}
- 已有画像字段：{profile_keys}

用户输入：{user_input}

只输出意图标签，不要解释。"""


class IntentClassifierNode:
    """意图分类节点。"""

    name = "classify_intent"

    def __init__(self, llm: LLMClient):
        self.llm = llm

    def execute(self, agent_state: AgentState, turn_state: TurnState) -> NodeResult:
        user_input = turn_state.user_input

        # 特殊处理：如果上一轮是追问模式，且本轮输入很短，可能是补充信息
        if (
            agent_state.turn_count > 0
            and agent_state.pending_questions
            and len(user_input) < 50
        ):
            intent = "补充信息"
            return NodeResult(
                next_node="collect_profile",
                updates={"classified_intent": intent},
                log_summary=f"intent={intent}(短回复补充)",
                decision="补充信息（检测到上轮追问+短回复）",
            )

        # LLM分类 + 规则降级
        intent, used_llm = self._classify(user_input, agent_state)

        return NodeResult(
            next_node="collect_profile",
            updates={"classified_intent": intent},
            log_summary=f"intent={intent}, llm={used_llm}",
        )

    def _classify(self, user_input: str, agent_state: AgentState) -> tuple[str, bool]:
        """分类意图，返回 (intent, used_llm)。"""
        # 尝试LLM
        if self.llm.available():
            prompt = LLM_PROMPT_TEMPLATE.format(
                last_intent=agent_state.intents_history[-1] if agent_state.intents_history else "无",
                turn_count=agent_state.turn_count,
                profile_keys=", ".join(agent_state.profile.keys()) or "无",
                user_input=user_input,
            )
            result = self.llm.call(prompt, max_tokens=30, temperature=0.1)
            if result:
                # 验证返回的意图是否合法
                result = result.strip().replace('"', '').replace("'", "")
                valid_intents = list(INTENT_KEYWORDS.keys()) + ["补充信息", "通用咨询"]
                for valid in valid_intents:
                    if valid in result:
                        return valid, True

        # 降级到规则
        return self._rule_classify(user_input), False

    @staticmethod
    def _rule_classify(text: str) -> str:
        """基于关键词的规则分类。"""
        for intent, keywords in INTENT_KEYWORDS.items():
            if any(kw in text for kw in keywords):
                return intent
        return "通用咨询"
