#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Legacy session compatibility layer.

The current product path uses the LangGraph agent and the FastAPI project
routes. This module keeps the old ``Session`` import usable for CLI fallback
and historical tests without depending on the removed ``nodes/`` pipeline.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from models.project import ProjectMemory
from models.schemas import AssistantResponse
from models.state import AgentState, ProfileField, TurnState
from tools.rag_tool import RagTool

DEFAULT_PROJECT_ID = "xinyu-hengtai-dakou"


class Session:
    """Small deterministic fallback for the retired node-based session."""

    def __init__(self, project_id: Optional[str] = None):
        self.agent_state = AgentState(project_id=project_id or DEFAULT_PROJECT_ID)
        self._load_project_profile()

    def process_turn(self, user_input: str, context: Optional[Dict[str, Any]] = None) -> TurnState:
        """Process one turn without network or LLM dependencies."""
        turn = TurnState(user_input=user_input, assistant_context=context)
        self.agent_state.turn_count += 1
        self.agent_state.conversation_history.append({"role": "user", "content": user_input})

        response = self._build_response(user_input)
        turn.classified_intent = "store_operations"
        turn.output_mode = "full_response"
        turn.response_text = response.response_text
        turn.structured_output = response.to_dict()

        self.agent_state.conversation_history.append(
            {"role": "assistant", "content": turn.response_text}
        )
        return turn

    def get_response(self, user_input: str) -> str:
        return self.process_turn(user_input).response_text

    def get_structured_response(self, user_input: str) -> Dict[str, Any]:
        return self.process_turn(user_input).structured_output

    def audit_sources(self) -> Dict[str, Any]:
        """Return RAG audit data when the local index is available."""
        rag_tool = RagTool()
        if not rag_tool.available():
            return {"chunks": 0, "available": False}
        return rag_tool.audit()

    def reset(self):
        project_id = self.agent_state.project_id
        self.agent_state = AgentState(project_id=project_id)
        self._load_project_profile()

    def _load_project_profile(self):
        memory = ProjectMemory.load(self.agent_state.project_id) if self.agent_state.project_id else None
        if not memory or not memory.profile:
            return
        for key, value in memory.profile.items():
            self.agent_state.profile[key] = ProfileField(
                value=value,
                confidence="confirmed",
                source_turn=0,
            )
        self.agent_state._recalculate_completeness()

    @staticmethod
    def _build_response(user_input: str) -> AssistantResponse:
        summary = (
            "已按新余恒太城五楼大口章鱼烧的单店经营口径处理。"
            "当前优先补齐真实营业、SKU、库存、用工和平台数据，再生成日报、周报和风险提醒。"
        )
        return AssistantResponse(
            decision="needs_more_data",
            summary=summary,
            facts=[
                "服务对象限定为新余恒太城五楼大口章鱼烧。",
                "默认项目数据目录为 project_data/xinyu-hengtai-dakou/。",
            ],
            assumptions=["未接入实时平台授权时，平台经营数据以导入文件或本地记录为准。"],
            risks=[
                {
                    "level": "medium",
                    "message": "缺少连续经营数据时，SKU 预测和工资核算只能作为试算。",
                }
            ],
            next_actions=[
                "导入最近 7 天营业日报。",
                "核对 SKU 销量、库存损耗和缺货记录。",
                "核对员工班次、工时、提成和临时调整。",
                "生成本周经营复盘草稿。",
            ],
            questions_for_user=[
                "今天营业额、订单数和差评数是多少？",
                "哪些 SKU 售罄、滞销或损耗异常？",
                "今天实际到岗人员和工时是多少？",
            ],
            memory_updates={"last_user_input": user_input},
            response_text=summary,
        )
