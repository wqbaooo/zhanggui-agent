#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""风险诊断节点：基于画像、证据和工具结果综合判断风险。"""

from __future__ import annotations

from typing import List

from core.llm_client import LLMClient
from core.state_machine import NodeResult
from models.state import AgentState, RiskFlag, TurnState


RISK_RULES = [
    {
        "trigger": ["加盟"],
        "risk": "加盟项目需要先验证供应链、合同退出条款、真实门店盈利，不能只看总部样板。",
        "severity": "high",
    },
    {
        "trigger": ["转让", "接店", "接手"],
        "risk": "转让店重点核查原店闭店原因、房东是否认可转让、设备折价和隐性债务。",
        "severity": "high",
    },
    {
        "trigger": ["地铁口", "路过", "人很多", "人流大"],
        "risk": "高人流不等于有效客流，需看停留意愿、消费场景和进店转化率。",
        "severity": "medium",
    },
    {
        "trigger": ["商场", "mall", "购物中心"],
        "risk": "商场店需要评估：扣点/租金模式、营业时间限制、装修补贴条件、同层竞品。",
        "severity": "medium",
    },
    {
        "trigger": ["借钱", "贷款", "借贷", "全部积蓄"],
        "risk": "高杠杆创业风险极大，建议预留至少6个月备用金，不能把退路封死。",
        "severity": "critical",
    },
]

LLM_PROMPT_TEMPLATE = """你是一个拥有 15 年经验的餐饮投资顾问。请扮演“红队”角色，对用户的开店计划进行对抗性审查。

用户画像：{profile}
意图：{intent}
工具分析结果摘要：{tool_summary}
证据摘要：{evidence_summary}

请列出 2-4 个最关键的风险点或思维盲点。重点关注：
1. **隐性成本**：如证照办理、邻里关系处理、季节性波动等。
2. **逻辑矛盾**：如预算与选址的不匹配、品类与客群的冲突。
3. **市场陷阱**：如平台扣点变化、竞品恶性竞争等。

格式要求：
- [严重程度:high/medium/low] 风险描述（请用客观、专业的第三方口吻）

只列风险，不要解释或给建议。"""


class RiskDiagnoserNode:
    """风险诊断节点。"""

    name = "diagnose_risks"

    def __init__(self, llm: LLMClient):
        self.llm = llm

    def execute(self, agent_state: AgentState, turn_state: TurnState) -> NodeResult:
        user_input = turn_state.user_input
        profile = agent_state.get_profile_dict()

        # 规则诊断
        rule_risks = self._rule_diagnose(user_input, agent_state, turn_state)

        # LLM诊断（可选）
        llm_risks: List[RiskFlag] = []
        used_llm = False
        if self.llm.available() and turn_state.retrieved_evidence:
            llm_risks, used_llm = self._llm_diagnose(agent_state, turn_state)

        # 合并风险（去重）
        all_risks = rule_risks + llm_risks
        seen_desc = set()
        deduped: List[RiskFlag] = []
        for risk in all_risks:
            short = risk.description[:30]
            if short not in seen_desc:
                seen_desc.add(short)
                deduped.append(risk)

        # 更新状态
        agent_state.risk_flags = deduped
        turn_state.diagnosed_risks = [r.description for r in deduped]

        return NodeResult(
            next_node="synthesize_response",
            log_summary=f"risks={len(deduped)}, llm={used_llm}",
        )

    def _rule_diagnose(self, user_input: str, agent_state: AgentState, turn_state: TurnState) -> List[RiskFlag]:
        """基于规则的风险检测。"""
        risks: List[RiskFlag] = []
        text = user_input.lower()

        for rule in RISK_RULES:
            if any(trigger in text for trigger in rule["trigger"]):
                risks.append(RiskFlag(
                    description=rule["risk"],
                    severity=rule["severity"],
                    source="rule",
                ))

        # 视频未转写警告
        if turn_state.retrieved_evidence:
            video_usable = any(
                e.status in ("transcribed", "usable") and e.source_type == "video"
                for e in turn_state.retrieved_evidence
            )
            if not video_usable:
                has_video_ref = any(e.source_type == "video" for e in turn_state.retrieved_evidence)
                if has_video_ref:
                    risks.append(RiskFlag(
                        description="视频库目前以标题索引为主，内容需转写后才能作为强证据。",
                        severity="low",
                        source="rule",
                    ))

        # 财务工具结果中的风险
        finance_data = turn_state.tool_outputs.get("finance_calculator", {})
        if finance_data.get("success") and finance_data.get("data"):
            scenarios = finance_data["data"].get("三档测算", {})
            conservative = scenarios.get("保守", {})
            if isinstance(conservative.get("月净利"), (int, float)) and conservative["月净利"] <= 0:
                risks.append(RiskFlag(
                    description="保守测算下月净利为负，项目存在较大亏损风险。",
                    severity="critical",
                    source="tool",
                ))

        return risks

    def _llm_diagnose(self, agent_state: AgentState, turn_state: TurnState) -> tuple[List[RiskFlag], bool]:
        """LLM辅助风险诊断。"""
        profile = agent_state.get_profile_dict()
        evidence_summary = "\n".join(
            f"- {e.source}/{e.title}: {e.content[:100]}"
            for e in turn_state.retrieved_evidence[:5]
        )
        tool_summary = ""
        for name, output in turn_state.tool_outputs.items():
            if output.get("success"):
                tool_summary += f"- {name}: 执行成功\n"

        prompt = LLM_PROMPT_TEMPLATE.format(
            profile=profile,
            intent=turn_state.classified_intent,
            tool_summary=tool_summary or "无",
            evidence_summary=evidence_summary or "无",
        )

        result = self.llm.call(prompt, max_tokens=400, temperature=0.3)
        if not result:
            return [], False

        # 解析LLM输出
        risks: List[RiskFlag] = []
        for line in result.strip().splitlines():
            line = line.strip().lstrip("- ")
            if not line:
                continue
            severity = "medium"
            if "[high]" in line.lower() or "[严重程度:high]" in line.lower():
                severity = "high"
                line = line.replace("[high]", "").replace("[严重程度:high]", "").strip()
            elif "[low]" in line.lower() or "[严重程度:low]" in line.lower():
                severity = "low"
                line = line.replace("[low]", "").replace("[严重程度:low]", "").strip()
            elif "[critical]" in line.lower():
                severity = "critical"
                line = line.replace("[critical]", "").strip()
            else:
                line = line.replace("[medium]", "").replace("[严重程度:medium]", "").strip()

            if line:
                risks.append(RiskFlag(description=line, severity=severity, source="llm"))

        return risks[:4], True
