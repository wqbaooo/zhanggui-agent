#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""响应综合节点：将所有分析结果综合为最终输出（text + structured JSON）。"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from core.llm_client import LLMClient
from core.state_machine import END, NodeResult
from models.schemas import AssistantResponse
from models.state import AgentState, Evidence, RiskFlag, TurnState


LLM_SYSTEM_MSG = "你是一位拥有 15 年经验的独立餐饮创业顾问。你的风格务实、客观、保守。请基于提供的行业参考依据和用户画像，给出具备整体性思考的专业建议。严禁提及任何特定讲师或课程名称。"

LLM_PROMPT_TEMPLATE = """基于以下信息，为用户生成一个简洁、实用的回答。

User question：{user_input}
意图：{intent}
画像：{profile}
缺失字段：{missing_fields}
风险信号：{risks}
工具分析结果：{tool_results}
证据：
{evidence}

要求：
1. 先给阶段性判断（能继续/需暂停/有风险）
2. 列出核心发现（事实为主，标注假设）
3. 给2-4条具体可执行的下一步行动
4. 如果信息不足，明确说需要什么
5. 如有追问需补充，在末尾自然带出

不要重复用户已知信息，聚焦于新洞察和可操作建议。"""


class ResponseSynthesizerNode:
    """响应综合节点。"""

    name = "synthesize_response"

    def __init__(self, llm: LLMClient):
        self.llm = llm

    def execute(self, agent_state: AgentState, turn_state: TurnState) -> NodeResult:
        # 如果是追问模式，构建追问回复
        if turn_state.output_mode == "ask_user":
            text = self._build_ask_response(agent_state, turn_state)
            structured = self._build_structured(agent_state, turn_state, text)
            turn_state.response_text = text
            turn_state.structured_output = structured.to_dict()
            return NodeResult(
                next_node="write_memory",
                log_summary="output_mode=ask_user",
            )

        # 完整回复模式：LLM综合 + 规则降级
        text, used_llm = self._synthesize(agent_state, turn_state)
        structured = self._build_structured(agent_state, turn_state, text)

        turn_state.response_text = text
        turn_state.structured_output = structured.to_dict()

        return NodeResult(
            next_node="write_memory",
            log_summary=f"output_mode=full, llm={used_llm}, len={len(text)}",
        )

    def _synthesize(self, agent_state: AgentState, turn_state: TurnState) -> tuple[str, bool]:
        """综合生成回复文本。"""
        # 尝试LLM
        if self.llm.available():
            prompt = self._build_llm_prompt(agent_state, turn_state)
            result = self.llm.call(
                prompt,
                system_msg=LLM_SYSTEM_MSG,
                temperature=0.3,
                max_tokens=2000,
            )
            if result:
                # 附加追问
                if agent_state.pending_questions:
                    result += "\n\n---\n顺便想确认几个信息：\n"
                    for q in agent_state.pending_questions[:2]:
                        result += f"- {q}\n"
                return result, True

        # 降级到模板
        return self._template_response(agent_state, turn_state), False

    def _build_llm_prompt(self, agent_state: AgentState, turn_state: TurnState) -> str:
        """构建LLM综合提示词，强化证据ID映射。"""
        evidence_text = "\n".join(
            f"[Ref: {e.id}] ({e.source_type}) {e.title}: {e.text[:250]}"
            for i, e in enumerate(turn_state.retrieved_evidence[:6], 1)
        )

        tool_results_text = ""
        for name, output in turn_state.tool_outputs.items():
            if output.get("success"):
                data = output.get("data", {})
                if isinstance(data, dict):
                    # 简化输出
                    tool_results_text += f"\n{name}:\n"
                    for k, v in list(data.items())[:8]:
                        tool_results_text += f"  {k}: {v}\n"

        return LLM_PROMPT_TEMPLATE.format(
            user_input=turn_state.user_input,
            intent=turn_state.classified_intent,
            profile=agent_state.get_profile_dict(),
            missing_fields=", ".join(agent_state.get_missing_fields(turn_state.classified_intent)),
            risks="; ".join(r.description for r in agent_state.risk_flags[:5]),
            tool_results=tool_results_text or "无",
            evidence=evidence_text or "无相关证据",
        )

    def _template_response(self, agent_state: AgentState, turn_state: TurnState) -> str:
        """本地模板填充（LLM不可用时的降级方案），保持专业顾问口吻。"""
        intent = turn_state.classified_intent
        profile = agent_state.get_profile_dict()
        lines = []

        # 1. 阶段性诊断
        lines.append("## 阶段性诊断")
        if agent_state.profile_completeness < 0.4:
            lines.append("当前信息不足以做出精准判断，建议先补齐核心画像字段。")
        else:
            lines.append("基于现有信息，该项目存在明显的风险点，需要进一步验证。")
        lines.append("")

        # 2. 核心洞察与建议
        lines.append("## 核心洞察")
        lines += self._intent_advice(intent)
        lines.append("")

        # 3. 风险提示（红队测试）
        if agent_state.risk_flags:
            lines.append("## 风险提示")
            for risk in agent_state.risk_flags[:5]:
                severity_mark = {"critical": "!!!", "high": "!!", "medium": "!", "low": ""}.get(risk.severity, "")
                lines.append(f"- {severity_mark} {risk.description}")
            lines.append("")

        # 4. 下一步行动
        lines.append("## 下一步行动")
        actions = self._next_actions(intent, agent_state)
        for i, action in enumerate(actions, 1):
            lines.append(f"{i}. {action}")
        lines.append("")

        # 5. 证据参考（客观引用）
        if turn_state.retrieved_evidence:
            lines.append("## 行业参考依据")
            for e in turn_state.retrieved_evidence[:4]:
                if e.status == "usable":
                    snippet = re.sub(r"\s+", " ", e.text)[:120]
                    lines.append(f"- [Ref: {e.id}] {e.source}/{e.title}: {snippet}")

        return "\n".join(lines)

    def _build_ask_response(self, agent_state: AgentState, turn_state: TurnState) -> str:
        """构建追问回复。"""
        # 【调试用】如果已经手动注入了画像，则跳过追问，直接进入模板回复
        if agent_state.profile_completeness >= 0.4:
            return self._template_response(agent_state, turn_state)
            
        lines = ["我来帮你规划，先了解几个关键信息：", ""]
        for q in agent_state.pending_questions[:3]:
            lines.append(f"- {q}")
        lines.append("")
        lines.append("有了这些信息，我能给出更有针对性的建议。")
        return "\n".join(lines)

    def _build_structured(self, agent_state: AgentState, turn_state: TurnState, text: str) -> AssistantResponse:
        """构建总助理标准输出。"""
        response = AssistantResponse()
        response.response_text = text
        response.summary = text[:200] if text else ""

        # decision
        if turn_state.output_mode == "ask_user":
            response.decision = "needs_more_data"
        elif any(r.severity == "critical" for r in agent_state.risk_flags):
            response.decision = "no_go"
        elif agent_state.profile_completeness >= 0.6 and not any(r.severity in ("critical", "high") for r in agent_state.risk_flags):
            response.decision = "conditional_go"
        else:
            response.decision = "needs_more_data"

        # risks
        response.risks = [
            {"description": r.description, "severity": r.severity}
            for r in agent_state.risk_flags
        ]

        # questions
        response.questions_for_user = agent_state.pending_questions

        # sources
        response.sources = [
            {"source": e.source, "title": e.title, "status": e.status}
            for e in turn_state.retrieved_evidence[:5]
        ]

        # next_actions
        response.next_actions = self._next_actions(turn_state.classified_intent, agent_state)

        # memory_updates
        if turn_state.extracted_profile_delta:
            response.memory_updates["profile_delta"] = turn_state.extracted_profile_delta

        return response

    @staticmethod
    def _intent_advice(intent: str) -> List[str]:
        """根据意图给出方向性专业建议（去元描述化）。"""
        advice_map = {
            "开店规划": [
                '- 商业逻辑起点：从“谁在什么场景下为什么复购”开始，而非单纯考虑“开什么店”。',
                '- 方案拆解：建议将计划拆分为选品、选址、财务模型、开业获客四个模块同步推进。',
                '- 预算策略：若启动资金有限，优先考虑低装修、低人工、刚需高频的小店模型。',
            ],
            "选址诊断": [
                '- 选址核心：关注目标客群的有效动线与消费场景，而非单纯的总人流量。',
                '- 硬件硬伤排查：优先确认明火/排烟/消防/转让权/租期等不可逆条件。',
                '- 收益倒推：月营业额需覆盖租金、人力、食材及平台费用后仍有正向现金流。',
            ],
            "财务测算": [
                '- 保守原则：使用保守模型测算生存底线，避免使用乐观模型评估盈利上限。',
                '- 关键指标：重点核算日单量、客单价、毛利率与回本周期的敏感性关系。',
            ],
            "风险控制": [
                '- 加盟审查：必须验证供应链稳定性、真实门店盈利数据及合同退出条款。',
                '- 转让核查：重点调查原店闭店真相、房东态度及是否存在隐性债务。',
            ],
        }
        return advice_map.get(intent, [
            "- 建议结合具体开店画像进行深度分析，以确保建议的针对性。",
            "- 优先执行可验证的实地调研动作，以数据支撑决策。",
        ])

    @staticmethod
    def _next_actions(intent: str, agent_state: AgentState) -> List[str]:
        """根据意图和状态生成下一步行动。"""
        actions = []
        profile = agent_state.get_profile_dict()

        if agent_state.profile_completeness < 0.4:
            actions.append("补齐开店画像：城市/商圈、品类、预算、经营方式、是否已有铺位。")

        if intent == "选址诊断":
            if "具体地址" not in profile:
                actions.append("确定1-3个候选铺位地址，我来帮你做地图+竞品分析。")
            actions.append("实地蹲点：工作日和周末各覆盖早中晚高峰，记录30分钟有效客流。")
            actions.append("拍门头、动线、左右邻铺、对面街景照片。")
        elif intent == "财务测算":
            actions.append("确认月租金、面积、预估客单价和日单量。")
            actions.append("列出初始投入明细：转让费、装修、设备、物料、备用金。")
        elif intent == "营销运营":
            actions.append("开业前准备：团购品设计、达人名单、3条同城短视频脚本。")
        else:
            actions.append("做两轮实地蹲点：工作日和周末各覆盖早中晚。")
            actions.append("列500米内竞品表：品类、价格带、排队情况、外卖销量。")

        actions.append("做保守财务模型：日单量×客单价×毛利率 vs 月固定成本。")
        return actions[:5]
