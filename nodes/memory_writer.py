#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""记忆写入节点：更新AgentState、归档TurnState、持久化ProjectMemory。"""

from __future__ import annotations

import json
from pathlib import Path

from config import PROJECT_DATA_DIR
from core.state_machine import END, NodeResult
from models.state import AgentState, TurnState


class MemoryWriterNode:
    """记忆写入节点（状态机最后一步）。"""

    name = "write_memory"

    def execute(self, agent_state: AgentState, turn_state: TurnState) -> NodeResult:
        # 1. 更新 AgentState 的意图历史
        if turn_state.classified_intent:
            agent_state.intents_history.append(turn_state.classified_intent)

        # 2. 更新对话历史
        agent_state.conversation_history.append({
            "role": "user",
            "content": turn_state.user_input,
        })
        agent_state.conversation_history.append({
            "role": "agent",
            "content": turn_state.response_text,
        })

        # 3. 增加轮次计数
        agent_state.turn_count += 1

        # 4. 归档 TurnState 到 turns.jsonl（如果有 project_id）
        if agent_state.project_id:
            self._archive_turn(agent_state.project_id, turn_state)

        return NodeResult(
            next_node=END,
            log_summary=f"turn={agent_state.turn_count}, history_len={len(agent_state.conversation_history)}",
        )

    def _archive_turn(self, project_id: str, turn_state: TurnState):
        """将 TurnState 追加写入 turns.jsonl。"""
        turns_dir = PROJECT_DATA_DIR / project_id
        turns_dir.mkdir(parents=True, exist_ok=True)
        turns_file = turns_dir / "turns.jsonl"

        log_dict = turn_state.to_log_dict()
        with open(turns_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_dict, ensure_ascii=False) + "\n")
