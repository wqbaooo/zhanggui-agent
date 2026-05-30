#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""总助理接口格式：AssistantRequest / AssistantResponse。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class AssistantRequest:
    """总助理调用掌柜Agent的输入格式。"""
    skill_name: str = "store_opening_agent"
    task_type: str = "general"  # profile|site_eval|finance|permit|marketing|risk_review
    project_id: Optional[str] = None
    user_message: str = ""
    context: Dict[str, Any] = field(default_factory=dict)
    attachments: List[Dict[str, str]] = field(default_factory=list)
    output_requirements: Dict[str, Any] = field(default_factory=lambda: {
        "format": "chat",
        "need_sources": True,
        "need_next_actions": True,
    })

    def to_dict(self) -> Dict[str, Any]:
        return {
            "skill_name": self.skill_name,
            "task_type": self.task_type,
            "project_id": self.project_id,
            "user_message": self.user_message,
            "context": self.context,
            "attachments": self.attachments,
            "output_requirements": self.output_requirements,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AssistantRequest":
        return cls(
            skill_name=data.get("skill_name", "store_opening_agent"),
            task_type=data.get("task_type", "general"),
            project_id=data.get("project_id"),
            user_message=data.get("user_message", ""),
            context=data.get("context", {}),
            attachments=data.get("attachments", []),
            output_requirements=data.get("output_requirements", {}),
        )


@dataclass
class AssistantResponse:
    """掌柜Agent返回给总助理的标准输出格式。"""
    decision: str = "needs_more_data"  # go | no_go | needs_more_data | conditional_go
    summary: str = ""
    facts: List[str] = field(default_factory=list)
    assumptions: List[str] = field(default_factory=list)
    risks: List[Dict[str, str]] = field(default_factory=list)
    scores: Dict[str, Optional[int]] = field(default_factory=lambda: {
        "site": None,
        "finance": None,
        "category_fit": None,
        "execution_difficulty": None,
    })
    next_actions: List[str] = field(default_factory=list)
    questions_for_user: List[str] = field(default_factory=list)
    sources: List[Dict[str, str]] = field(default_factory=list)
    artifacts: List[Dict[str, str]] = field(default_factory=list)
    memory_updates: Dict[str, Any] = field(default_factory=dict)
    response_text: str = ""  # 给人看的自然语言版本

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision": self.decision,
            "summary": self.summary,
            "facts": self.facts,
            "assumptions": self.assumptions,
            "risks": self.risks,
            "scores": self.scores,
            "next_actions": self.next_actions,
            "questions_for_user": self.questions_for_user,
            "sources": self.sources,
            "artifacts": self.artifacts,
            "memory_updates": self.memory_updates,
            "response_text": self.response_text,
        }
