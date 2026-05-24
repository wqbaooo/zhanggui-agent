#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""对话路由 — POST /api/chat (SSE 流式)。"""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from server.deps import get_agent
from server.schemas import ChatRequest
from server.stream import stream_agent_response

logger = logging.getLogger(__name__)

router = APIRouter(tags=["chat"])


@router.post("/chat")
async def chat_endpoint(req: ChatRequest):
    """流式对话端点。

    返回 SSE 流，兼容 Vercel AI SDK useChat 协议。
    """
    session_id = req.session_id or f"sess_{uuid.uuid4().hex[:12]}"

    async def event_generator():
        async for event in stream_agent_response(
            user_message=req.message,
            session_id=session_id,
            project_id=req.project_id or "",
        ):
            yield event

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "X-Session-Id": session_id,
        },
    )


@router.post("/chat/sync")
async def chat_sync(req: ChatRequest):
    """同步对话端点（非流式，用于调试和简单调用）。"""
    agent = get_agent(req.project_id)
    try:
        response = agent.get_response(req.message)
        return {"response": response, "session_id": req.session_id or "sync"}
    except Exception as exc:
        logger.exception("同步对话失败")
        raise HTTPException(status_code=500, detail="服务暂不可用，请稍后重试")
