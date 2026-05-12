#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""会话管理器：管理多轮对话生命周期、画像合并、状态机调度。"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from core.llm_client import LLMClient
from core.state_machine import StateMachine
from models.project import ProjectMemory
from models.schemas import AssistantResponse
from models.state import AgentState, TurnState
from nodes.evidence_retriever import EvidenceRetrieverNode
from nodes.intent_classifier import IntentClassifierNode
from nodes.memory_writer import MemoryWriterNode
from nodes.profile_collector import ProfileCollectorNode
from nodes.response_synthesizer import ResponseSynthesizerNode
from nodes.risk_diagnoser import RiskDiagnoserNode
from nodes.should_ask import ShouldAskNode
from nodes.tool_executor import ToolExecutorNode, ToolSelectorNode
from tools.amap_tool import AmapSiteTool
from tools.finance_tool import FinanceTool
from tools.rag_tool import RagTool
from tools.registry import ToolRegistry
from tools.vector_search_tool import VectorSearchTool
from tools.web_search_tool import WebSearchTool

logger = logging.getLogger(__name__)


class Session:
    """对话会话管理器。

    管理一个完整的对话会话：
    - 维护 AgentState（跨轮次）
    - 每轮创建 TurnState
    - 构建并运行状态机
    """

    def __init__(self, project_id: Optional[str] = None):
        self.llm = LLMClient()
        self.agent_state = AgentState(project_id=project_id)

        # 如果有项目档案，加载画像
        if project_id:
            memory = ProjectMemory.load(project_id)
            if memory and memory.profile:
                from models.state import ProfileField
                for k, v in memory.profile.items():
                    self.agent_state.profile[k] = ProfileField(
                        value=v, confidence="confirmed", source_turn=0
                    )
                self.agent_state._recalculate_completeness()

        # 初始化工具注册表
        self.registry = ToolRegistry()
        self._register_tools()

        # 构建状态机
        self.machine = self._build_machine()

    def process_turn(self, user_input: str, context: Optional[Dict[str, Any]] = None) -> TurnState:
        """处理一轮对话。

        Args:
            user_input: 用户输入文本
            context: 可选的总助理传入上下文

        Returns:
            完成的 TurnState（含 response_text 和 structured_output）
        """
        turn_state = TurnState(user_input=user_input, assistant_context=context)

        # 运行状态机
        self.machine.run(self.agent_state, turn_state)

        return turn_state

    def get_response(self, user_input: str) -> str:
        """简化接口：输入文本，返回回复文本。"""
        turn = self.process_turn(user_input)
        return turn.response_text

    def get_structured_response(self, user_input: str) -> Dict[str, Any]:
        """总助理接口：输入文本，返回结构化JSON。"""
        turn = self.process_turn(user_input)
        return turn.structured_output

    def audit_sources(self) -> Dict[str, Any]:
        """审计知识库状态。"""
        rag_tool = self.registry.get("rag_search")
        if rag_tool and isinstance(rag_tool, RagTool):
            result = rag_tool.audit()
            print(f"[DEBUG] Audit result: {result}")
            return result
        return {}

    def reset(self):
        """重置会话状态。"""
        project_id = self.agent_state.project_id
        self.agent_state = AgentState(project_id=project_id)

    def _register_tools(self):
        """注册所有可用工具。"""
        # 向量语义检索（优先，替代BM25）
        vector_search = VectorSearchTool()
        if vector_search.available():
            self.registry.register(vector_search)

        # BM25 RAG（向量不可用时降级）
        self.registry.register(RagTool())

        # 联网搜索（需要后端可用）
        web_search = WebSearchTool()
        if web_search.available():
            self.registry.register(web_search)

        # 高德地图（需要 API key）
        amap = AmapSiteTool()
        if amap.available():
            self.registry.register(amap)

        # 财务测算（总是可用）
        self.registry.register(FinanceTool())

    def _build_machine(self) -> StateMachine:
        """构建状态机，注册所有节点。"""
        machine = StateMachine(max_steps=12)

        # 获取工具实例
        rag_tool = self.registry.get("rag_search")
        web_search_tool = self.registry.get("web_search")
        vector_search_tool = self.registry.get("vector_search")

        # 注册节点
        machine.register(IntentClassifierNode(self.llm))
        machine.register(ProfileCollectorNode(self.llm))
        machine.register(ShouldAskNode())
        machine.register(EvidenceRetrieverNode(rag_tool, web_search_tool, vector_search_tool))
        machine.register(ToolSelectorNode(self.registry))
        machine.register(ToolExecutorNode(self.registry))
        machine.register(RiskDiagnoserNode(self.llm))
        machine.register(ResponseSynthesizerNode(self.llm))
        machine.register(MemoryWriterNode())

        # 设置起始节点
        machine.set_start("classify_intent")

        return machine
