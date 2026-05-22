#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""请求/响应 Pydantic 模型。"""

from __future__ import annotations

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., description="用户消息")
    session_id: Optional[str] = Field(None, description="会话 ID，空则创建新会话")
    project_id: Optional[str] = Field(None, description="项目 ID")
    context: Dict[str, Any] = Field(default_factory=dict, description="注入的上下文（城市/品类/预算等）")


class ChatResponse(BaseModel):
    response: str = Field(..., description="Agent 回复文本")
    session_id: str = Field(..., description="会话 ID")


class AuditResponse(BaseModel):
    chunks: int
    by_type: Dict[str, int]
    by_status: Dict[str, int]


class HealthResponse(BaseModel):
    status: str
    service: str
