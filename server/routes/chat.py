#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""对话路由 — POST /api/chat (SSE 流式)。"""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from server.deps import get_agent
from core.agent_runtime import runtime_status
from models.agent_sessions import AgentSessionStore
from server.schemas import AgentSessionCreate, ChatRequest
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
    project_id = req.project_id or "xinyu-hengtai-dakou"
    store = AgentSessionStore.for_project(project_id)
    selected_runtime = runtime_status()["selected"]
    session_id = store.ensure_session(
        project_id,
        req.session_id,
        scope=req.scope,
        runtime=selected_runtime,
    )
    store.append_message(
        session_id,
        "user",
        req.message,
        message_id=req.client_message_id,
    )
    agent = get_agent(project_id, session_id)
    try:
        import asyncio
        response = await asyncio.wait_for(
            asyncio.to_thread(agent.get_response, req.message),
            timeout=90
        )
        metadata = agent.get_run_metadata()
        store.append_message(session_id, "assistant", str(response), metadata=metadata)
        return {
            "response": response,
            "session_id": session_id,
            "meta": metadata,
        }
    except asyncio.TimeoutError:
        logger.warning("同步对话超时")
        store.append_message(
            session_id,
            "assistant",
            "处理超过 90 秒，已停止等待。你可以继续重试。",
            status="failed",
            metadata={"error": "timeout"},
        )
        raise HTTPException(status_code=504, detail="请求处理超时，请简化问题或稍后重试")
    except Exception as exc:
        logger.exception("同步对话失败")
        store.append_message(
            session_id,
            "assistant",
            "这次没有处理完成，服务暂时不可用。",
            status="failed",
            metadata={"error": type(exc).__name__},
        )
        raise HTTPException(status_code=500, detail="服务暂不可用，请稍后重试")


@router.get("/projects/{project_id}/agent/sessions")
async def list_agent_sessions(project_id: str, scope: str = "master", limit: int = 50):
    sessions = AgentSessionStore.for_project(project_id).list_sessions(
        project_id,
        scope=scope,
        limit=limit,
    )
    return {"sessions": sessions}


@router.post("/projects/{project_id}/agent/sessions")
async def create_agent_session(project_id: str, req: AgentSessionCreate):
    store = AgentSessionStore.for_project(project_id)
    session_id = store.ensure_session(
        project_id,
        req.id,
        scope=req.scope,
        title=req.title,
        runtime=runtime_status()["selected"],
    )
    if req.messages:
        store.import_session(
            project_id,
            session_id,
            req.title,
            req.messages,
            scope=req.scope,
        )
    return {"session": store.get_session(project_id, session_id)}


@router.get("/projects/{project_id}/agent/sessions/{session_id}")
async def get_agent_session(project_id: str, session_id: str):
    session = AgentSessionStore.for_project(project_id).get_session(project_id, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="对话不存在")
    return {"session": session}


@router.delete("/projects/{project_id}/agent/sessions/{session_id}")
async def archive_agent_session(project_id: str, session_id: str):
    archived = AgentSessionStore.for_project(project_id).archive_session(project_id, session_id)
    if not archived:
        raise HTTPException(status_code=404, detail="对话不存在")
    return {"success": True}


@router.get("/agent/runtime")
async def get_agent_runtime_status():
    """Expose real runtime state; never label Hermes active when it is offline."""
    return runtime_status()
