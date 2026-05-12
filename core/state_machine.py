#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""状态机引擎：节点注册、转移规则、执行循环。"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional, Protocol

from models.state import AgentState, NodeLog, TurnState

logger = logging.getLogger(__name__)


# 特殊节点名（终态）
END = "__END__"
ASK_USER = "__ASK_USER__"


class Node(Protocol):
    """状态机节点协议。所有节点必须实现此接口。"""

    @property
    def name(self) -> str: ...

    def execute(
        self, agent_state: AgentState, turn_state: TurnState
    ) -> "NodeResult": ...


class NodeResult:
    """节点执行结果。"""

    def __init__(
        self,
        next_node: str,
        updates: Optional[Dict[str, Any]] = None,
        log_summary: str = "",
        decision: str = "",
    ):
        self.next_node = next_node
        self.updates = updates or {}
        self.log_summary = log_summary
        self.decision = decision


class StateMachine:
    """轻量状态机引擎。

    支持：
    - 节点注册
    - 线性和分支转移
    - 最大步数保护（防无限循环）
    - 执行审计日志
    """

    def __init__(self, max_steps: int = 15):
        self._nodes: Dict[str, Node] = {}
        self._start_node: str = ""
        self._max_steps = max_steps

    def register(self, node: Node):
        """注册一个节点。"""
        self._nodes[node.name] = node

    def set_start(self, node_name: str):
        """设置起始节点。"""
        if node_name not in self._nodes:
            raise ValueError(f"起始节点 '{node_name}' 未注册")
        self._start_node = node_name

    def run(self, agent_state: AgentState, turn_state: TurnState) -> TurnState:
        """执行状态机，从起始节点开始，直到到达终态或超出步数。

        返回更新后的 TurnState（含 node_trace）。
        """
        if not self._start_node:
            raise RuntimeError("未设置起始节点")

        current_node_name = self._start_node
        steps = 0

        while steps < self._max_steps:
            if current_node_name in (END, ASK_USER):
                turn_state.output_mode = (
                    "ask_user" if current_node_name == ASK_USER else "full_response"
                )
                break

            node = self._nodes.get(current_node_name)
            if node is None:
                logger.error("节点 '%s' 未找到，终止执行", current_node_name)
                break

            # 执行节点
            log_entry = NodeLog(node_name=node.name, started_at=time.time())
            try:
                result = node.execute(agent_state, turn_state)
            except Exception as exc:
                logger.error("节点 '%s' 执行异常: %s", node.name, exc)
                log_entry.ended_at = time.time()
                log_entry.outputs_summary = f"ERROR: {exc}"
                turn_state.node_trace.append(log_entry)
                break

            log_entry.ended_at = time.time()
            log_entry.outputs_summary = result.log_summary
            log_entry.decision = result.decision
            turn_state.node_trace.append(log_entry)

            # 应用更新
            self._apply_updates(result.updates, agent_state, turn_state)

            # 转移到下一个节点
            current_node_name = result.next_node
            steps += 1

        if steps >= self._max_steps:
            logger.warning("状态机超出最大步数(%d)，强制终止", self._max_steps)
            turn_state.output_mode = "full_response"

        return turn_state

    def _apply_updates(
        self,
        updates: Dict[str, Any],
        agent_state: AgentState,
        turn_state: TurnState,
    ):
        """将节点结果中的 updates 应用到状态上。"""
        for key, value in updates.items():
            # turn_state 字段优先
            if hasattr(turn_state, key):
                setattr(turn_state, key, value)
            elif hasattr(agent_state, key):
                setattr(agent_state, key, value)

    @property
    def registered_nodes(self) -> List[str]:
        return list(self._nodes.keys())
