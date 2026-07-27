#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""可信 Agent 回复 → SSE 事件转换器。

流式与同步端点共用同一个 Agent 编排入口，避免绕过门店事实、
确定性财务回答、多轮领域上下文和回答守卫。
"""

from __future__ import annotations

import json
import logging
import asyncio
from typing import Any, AsyncGenerator

logger = logging.getLogger(__name__)


async def stream_agent_response(
    user_message: str,
    session_id: str,
    project_id: str = "",
) -> AsyncGenerator[str, None]:
    """通过统一可信 Agent 链生成 SSE 事件。

    Yields:
        SSE 格式的字符串，每行一个事件。
        事件类型: text-delta, finish
    """
    from server.deps import get_agent
    from models.agent_sessions import AgentSessionStore

    resolved_project = project_id or "xinyu-hengtai-dakou"
    store = AgentSessionStore.for_project(resolved_project)
    store.ensure_session(resolved_project, session_id, runtime="stream")
    store.append_message(session_id, "user", user_message)

    yield _sse("start-step", {})

    rendered_response = ""
    metadata: dict[str, Any] = {}
    try:
        agent = get_agent(resolved_project, session_id)
        response = await asyncio.wait_for(
            asyncio.to_thread(agent.get_response, user_message),
            timeout=90,
        )
        rendered_response = str(response)
        metadata = agent.get_run_metadata()
        for chunk in _chunk_text(str(response)):
            yield _sse("text-delta", chunk)
    except asyncio.TimeoutError:
        logger.warning("Agent stream timed out: session=%s", session_id)
        rendered_response = "处理超过 90 秒，请简化问题后重试。"
        metadata = {"error": "timeout"}
        yield _sse("text-delta", rendered_response)
    except Exception:
        logger.exception("Agent stream failed: session=%s", session_id)
        rendered_response = "服务暂时不可用，请稍后重试。"
        metadata = {"error": "runtime_failure"}
        yield _sse("text-delta", rendered_response)

    store.append_message(
        session_id,
        "assistant",
        rendered_response,
        status="failed" if metadata.get("error") else "complete",
        metadata=metadata,
    )

    yield _sse("finish-step", {})
    yield _sse("finish", {})


def _chunk_text(text: str, size: int = 96) -> list[str]:
    """Split a trusted complete answer into stable SSE text deltas."""
    return [text[index:index + size] for index in range(0, len(text), size)] or [""]


def _sse(event_type: str, data: Any) -> str:
    """格式化单个 SSE 事件。

    Vercel AI SDK stream protocol:
    - text-delta: 直接传字符串
    - 其他类型: JSON 序列化对象
    """
    if isinstance(data, str):
        return f"0:{json.dumps(data)}\n"
    return f"2:{json.dumps([data])}\n"
