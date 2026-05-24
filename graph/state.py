#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""LangGraph状态定义：GraphState。"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Annotated, Any, Dict, List, Optional

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langgraph.graph.message import add_messages

from models.plan import Plan


@dataclass
class GraphState:
    """LangGraph全局状态。
    
    这是Agent的"记忆+上下文+工作区"，所有节点读写这个状态。
    messages 字段使用 add_messages reducer，支持节点追加消息而非覆盖。
    """
    
    # ============ 用户输入 ============
    user_input: str = ""  # 当前用户输入
    messages: Annotated[List[BaseMessage], add_messages] = field(default_factory=list)  # 对话历史（LangChain格式）
    
    # ============ 画像（跨轮次累积） ============
    profile: Dict[str, Any] = field(default_factory=dict)  # 城市/品类/预算/经验/经营方式
    profile_completeness: float = 0.0  # 画像完整度 0-1
    missing_fields: List[str] = field(default_factory=list)  # 缺失的关键字段
    
    # ============ 计划（核心新增） ============
    plan: Optional[Plan] = None  # 开店主计划
    current_task_id: Optional[str] = None  # 当前正在执行的任务
    task_results: Dict[str, Any] = field(default_factory=dict)  # 任务执行结果
    
    # ============ 推理（ReAct） ============
    thought: str = ""  # 当前思考
    action: str = ""  # 当前行动（工具调用）
    action_input: Dict[str, Any] = field(default_factory=dict)  # 行动参数
    observation: str = ""  # 观察结果（工具返回）
    reflection: str = ""  # 反思：结果评估、风险识别
    
    # ============ 证据（检索结果） ============
    evidence: List[Any] = field(default_factory=list)  # 检索到的证据
    evidence_sources: List[str] = field(default_factory=list)  # 证据来源标签
    
    # ============ 风险 ============
    risks: List[Dict[str, Any]] = field(default_factory=list)  # 识别的风险
    risk_level: str = "low"  # low / medium / high / critical
    
    # ============ 输出 ============
    response: str = ""  # 给用户看的自然语言回复
    structured_output: Dict[str, Any] = field(default_factory=dict)  # 结构化输出
    decision: str = "needs_more_data"  # go / no_go / needs_more_data / conditional_go
    
    # ============ 人机交互（中断） ============
    interrupt_reason: Optional[str] = None  # 中断原因
    options: List[str] = field(default_factory=list)  # 选项（让用户选择）
    needs_human_input: bool = False  # 是否需要人工输入
    next_question: str = ""  # 下一步要问用户的问题
    
    # ============ 元数据 ============
    session_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    turn_count: int = 0
    current_phase: str = "initial"  # initial / planning / executing / reflecting / interrupted
    
    def add_message(self, role: str, content: str):
        """添加消息到对话历史。"""
        if role == "human":
            self.messages.append(HumanMessage(content=content))
        elif role == "ai":
            self.messages.append(AIMessage(content=content))
    
    def get_profile_str(self) -> str:
        """获取画像的文本描述。"""
        if not self.profile:
            return "暂无画像信息"
        parts = []
        for key, value in self.profile.items():
            parts.append(f"{key}: {value}")
        return "\n".join(parts)
    
    def update_profile(self, new_fields: Dict[str, Any]):
        """更新画像字段。"""
        self.profile.update(new_fields)
        # 重新计算完整度
        core_fields = ["城市", "品类", "预算", "经营方式", "店铺状态"]
        filled = sum(1 for f in core_fields if f in self.profile)
        self.profile_completeness = filled / len(core_fields)
    
    def to_interrupt_dict(self) -> Dict[str, Any]:
        """转换为中断状态字典（用于前端展示）。"""
        return {
            "interrupt_reason": self.interrupt_reason,
            "options": self.options,
            "next_question": self.next_question,
            "plan": self.plan.to_dict() if self.plan else None,
            "current_phase": self.current_phase,
            "progress": self.plan.progress_percentage() if self.plan else 0,
        }


# 全局状态实例（用于单会话）
import time as _time
_state_instances: Dict[str, GraphState] = {}
_state_last_access: Dict[str, float] = {}
_SESSION_TTL = 1800  # 30 分钟无活动自动清理


def _cleanup_expired():
    """清理过期会话，防止内存泄漏。"""
    now = _time.time()
    expired = [k for k, t in _state_last_access.items() if now - t > _SESSION_TTL]
    for k in expired:
        _state_instances.pop(k, None)
        _state_last_access.pop(k, None)
    if expired:
        logger = __import__("logging").getLogger(__name__)
        logger.info("清理 %d 个过期会话", len(expired))


def get_state(session_id: str) -> GraphState:
    """获取或创建状态实例。"""
    _cleanup_expired()
    if session_id not in _state_instances:
        _state_instances[session_id] = GraphState(session_id=session_id)
    _state_last_access[session_id] = _time.time()
    return _state_instances[session_id]


def clear_state(session_id: str):
    """清除状态实例。"""
    _state_instances.pop(session_id, None)
    _state_last_access.pop(session_id, None)
