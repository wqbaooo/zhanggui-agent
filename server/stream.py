#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""LangGraph astream_events → SSE 事件转换器。

将 LangGraph 的流式事件映射为 Vercel AI SDK 兼容的 SSE stream parts。
"""

from __future__ import annotations

import json
import logging
from typing import Any, AsyncGenerator, Dict

logger = logging.getLogger(__name__)


async def stream_agent_response(
    user_message: str,
    session_id: str,
    project_id: str = "",
) -> AsyncGenerator[str, None]:
    """流式执行 Agent 并生成 SSE 事件。

    Yields:
        SSE 格式的字符串，每行一个事件。
        事件类型: text-delta, tool-input-start, tool-output-available,
                  reasoning-delta, finish
    """
    from core.readiness import build_readiness_overlay
    from graph.agent import build_agent
    from graph.state import get_state
    from langchain_core.messages import HumanMessage

    agent = build_agent()
    config = {"configurable": {"thread_id": session_id}}
    state = get_state(session_id)

    messages = list(state.messages) if state.messages else []
    messages.append(HumanMessage(content=user_message))

    yield _sse("start-step", {})

    emitted_text = ""

    try:
        async for event in agent.astream_events(
            {"messages": messages, "profile": state.profile},
            config=config,
            version="v2",
        ):
            kind = event.get("event", "")

            if kind == "on_chat_model_stream":
                chunk = event.get("data", {}).get("chunk", None)
                if chunk and hasattr(chunk, "content") and chunk.content:
                    text = chunk.content
                    if isinstance(text, str) and text:
                        emitted_text += text
                        yield _sse("text-delta", text)

                if chunk and hasattr(chunk, "tool_call_chunks") and chunk.tool_call_chunks:
                    for tc in chunk.tool_call_chunks:
                        if tc.get("name"):
                            yield _sse("tool-input-start", {
                                "toolName": tc["name"],
                                "toolCallId": tc.get("id", ""),
                            })
                        if tc.get("args"):
                            yield _sse("tool-input-delta", {
                                "toolCallId": tc.get("id", ""),
                                "argsTextDelta": tc["args"],
                            })

            elif kind == "on_tool_end":
                output = event.get("data", {}).get("output", "")
                tool_name = event.get("name", "unknown")
                yield _sse("tool-output-available", {
                    "toolCallId": event.get("run_id", ""),
                    "toolName": tool_name,
                    "output": str(output)[:2000],
                })

    except Exception as exc:
        logger.error("Agent stream error: %s", exc)
        yield _sse("text-delta", f"\n\n抱歉，处理时出现问题：{exc}")

    overlay = build_readiness_overlay(user_message)
    if overlay and "项目审查补齐：新手加盟最低闭环" not in emitted_text:
        yield _sse("text-delta", "\n\n---\n\n" + overlay)

    yield _sse("finish-step", {})
    yield _sse("finish", {})


def _sse(event_type: str, data: Any) -> str:
    """格式化单个 SSE 事件。

    Vercel AI SDK stream protocol:
    - text-delta: 直接传字符串
    - 其他类型: JSON 序列化对象
    """
    if isinstance(data, str):
        return f"0:{json.dumps(data)}\n"
    return f"2:{json.dumps([data])}\n"
