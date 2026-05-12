#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""工具选择和执行节点。"""

from __future__ import annotations

from typing import Any, Dict

from core.state_machine import NodeResult
from models.state import AgentState, TurnState
from tools.registry import ToolRegistry


class ToolSelectorNode:
    """工具选择节点：根据意图和画像决定调用哪些工具。"""

    name = "select_tools"

    def __init__(self, registry: ToolRegistry):
        self.registry = registry

    def execute(self, agent_state: AgentState, turn_state: TurnState) -> NodeResult:
        intent = turn_state.classified_intent
        profile = agent_state.get_profile_dict()

        # RAG 总是在 evidence_retriever 中已调用，这里选其他工具
        selected = self.registry.select_for_intent(
            intent=intent,
            profile=profile,
            exclude=["rag_search"],  # RAG已在上一步执行
            max_tools=2,
        )

        tool_names = [t.meta.name for t in selected]
        turn_state.selected_tools = tool_names

        if not tool_names:
            # 无额外工具可调用，跳过执行直接诊断
            return NodeResult(
                next_node="diagnose_risks",
                log_summary="no_extra_tools",
            )

        return NodeResult(
            next_node="execute_tools",
            log_summary=f"selected={tool_names}",
        )


class ToolExecutorNode:
    """工具执行节点：执行选中的工具并收集结果。"""

    name = "execute_tools"

    def __init__(self, registry: ToolRegistry):
        self.registry = registry

    def execute(self, agent_state: AgentState, turn_state: TurnState) -> NodeResult:
        profile = agent_state.get_profile_dict()
        tool_outputs: Dict[str, Any] = {}

        for tool_name in turn_state.selected_tools:
            tool = self.registry.get(tool_name)
            if not tool:
                continue

            # 构建工具参数
            params = self._build_params(tool_name, profile, turn_state.user_input)

            # 校验
            valid, err = tool.validate_params(params)
            if not valid:
                tool_outputs[tool_name] = {"success": False, "error": err}
                continue

            # 执行
            result = tool.execute(params)
            tool_outputs[tool_name] = {
                "success": result.success,
                "data": result.data,
                "error": result.error,
                "metadata": result.metadata,
            }

            # 缓存到全局状态
            if result.success:
                agent_state.tool_results[tool_name] = result.data

        turn_state.tool_outputs = tool_outputs

        return NodeResult(
            next_node="diagnose_risks",
            log_summary=f"executed={list(tool_outputs.keys())}, success={sum(1 for v in tool_outputs.values() if v.get('success'))}",
        )

    def _build_params(self, tool_name: str, profile: Dict[str, Any], user_input: str) -> Dict[str, Any]:
        """根据工具名和画像构建调用参数。"""
        if tool_name == "amap_site_analysis":
            return {
                "address": profile.get("具体地址", ""),
                "city": profile.get("城市", ""),
                "category": profile.get("品类", "早餐"),
                "radius": 1000,
            }
        elif tool_name == "finance_calculator":
            return {"profile": profile}
        else:
            return {"query": user_input, "profile": profile}
