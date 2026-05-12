#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""核心数据模型：AgentState（跨轮次）、TurnState（单轮）、Evidence等。"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ProfileField:
    """画像字段，带置信度和来源轮次。"""
    value: Any
    confidence: str = "confirmed"  # confirmed | inferred | unclear
    source_turn: int = 0


@dataclass
class Evidence:
    """检索到的证据片段。"""
    id: str = ""               # 唯一标识，用于引用
    source: str = ""           # "核心知识库" | "文档知识库" | "视频课程"
    title: str = ""
    text: str = ""             # 内容文本
    score: float = 0.0         # 相关度得分
    status: str = "usable"     # usable | transcribed | title_index_only | needs_ocr
    source_type: str = ""      # core_markdown | document | video_transcript


@dataclass
class RiskFlag:
    """风险标记，带严重等级。"""
    description: str
    severity: str = "medium"  # low | medium | high | critical
    source: str = "rule"      # rule | llm | tool


@dataclass
class Decision:
    """阶段性决策记录。"""
    turn: int
    decision_type: str  # go | no_go | needs_more_data | conditional_go
    summary: str
    evidence_refs: List[str] = field(default_factory=list)


@dataclass
class NodeLog:
    """节点执行日志，用于审计。"""
    node_name: str
    started_at: float = 0.0
    ended_at: float = 0.0
    inputs_summary: str = ""
    outputs_summary: str = ""
    decision: str = ""        # 决策门的选择记录
    llm_used: bool = False
    llm_fallback: bool = False

    @property
    def duration_ms(self) -> float:
        return (self.ended_at - self.started_at) * 1000


@dataclass
class AgentState:
    """跨轮次累积的会话状态。"""
    session_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    project_id: Optional[str] = None
    turn_count: int = 0
    current_phase: str = "画像建立"  # 画像建立 | 想法验证 | 选址 | 财务 | 执行
    profile: Dict[str, ProfileField] = field(default_factory=dict)
    profile_completeness: float = 0.0
    intents_history: List[str] = field(default_factory=list)
    evidence_pool: List[Evidence] = field(default_factory=list)
    risk_flags: List[RiskFlag] = field(default_factory=list)
    tool_results: Dict[str, Any] = field(default_factory=dict)
    pending_questions: List[str] = field(default_factory=list)
    decisions: List[Decision] = field(default_factory=list)
    conversation_history: List[Dict[str, str]] = field(default_factory=list)

    def merge_profile(self, delta: Dict[str, Any], turn: int):
        """将新一轮提取的画像字段合并到已有画像。

        规则：
        - confirmed 字段不被 inferred 覆盖
        - 已有 confirmed 字段被新的 confirmed 值覆盖（用户改主意）
        """
        for key, value in delta.items():
            if isinstance(value, ProfileField):
                new_field = value
            else:
                new_field = ProfileField(value=value, confidence="confirmed", source_turn=turn)

            existing = self.profile.get(key)
            if existing is None:
                self.profile[key] = new_field
            elif new_field.confidence == "confirmed":
                self.profile[key] = new_field
            elif existing.confidence != "confirmed":
                self.profile[key] = new_field

        self._recalculate_completeness()

    def get_profile_dict(self) -> Dict[str, Any]:
        """返回画像的纯值字典（不含元信息）。"""
        return {k: v.value for k, v in self.profile.items()}

    def get_missing_fields(self, intent: str) -> List[str]:
        """根据意图计算缺失的关键字段。"""
        base_fields = ["城市", "品类", "预算", "经营方式"]
        if intent in ("选址诊断", "财务测算"):
            base_fields += ["店铺面积", "月租金"]
        if intent == "选址诊断":
            base_fields += ["具体地址"]

        existing_keys = set(self.profile.keys())
        return [f for f in base_fields if f not in existing_keys]

    def _recalculate_completeness(self):
        """重新计算画像完整度。"""
        core_fields = ["城市", "品类", "预算", "经营方式", "店铺状态"]
        if not core_fields:
            self.profile_completeness = 0.0
            return
        filled = sum(1 for f in core_fields if f in self.profile)
        self.profile_completeness = filled / len(core_fields)


@dataclass
class TurnState:
    """单轮处理上下文，用完即归档。"""
    turn_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    user_input: str = ""
    assistant_context: Optional[Dict[str, Any]] = None  # 总助理传入的上下文
    classified_intent: str = ""
    intent_confidence: float = 1.0
    extracted_profile_delta: Dict[str, Any] = field(default_factory=dict)
    selected_tools: List[str] = field(default_factory=list)
    tool_outputs: Dict[str, Any] = field(default_factory=dict)
    retrieved_evidence: List[Evidence] = field(default_factory=list)
    diagnosed_risks: List[str] = field(default_factory=list)
    response_text: str = ""
    structured_output: Dict[str, Any] = field(default_factory=dict)
    node_trace: List[NodeLog] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)
    output_mode: str = "ask_user"  # ask_user | full_response

    def to_log_dict(self) -> Dict[str, Any]:
        """序列化为可写入 jsonl 的字典。"""
        return {
            "turn_id": self.turn_id,
            "user_input": self.user_input,
            "intent": self.classified_intent,
            "profile_delta": self.extracted_profile_delta,
            "tools_used": self.selected_tools,
            "evidence_count": len(self.retrieved_evidence),
            "risks": self.diagnosed_risks,
            "output_mode": self.output_mode,
            "node_trace": [
                {"node": log.node_name, "ms": log.duration_ms, "llm": log.llm_used}
                for log in self.node_trace
            ],
            "timestamp": self.timestamp,
        }
