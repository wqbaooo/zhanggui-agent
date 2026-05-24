#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""依赖注入：Agent 实例管理、session 工厂。"""

from __future__ import annotations

import logging
import time as _time
import uuid
from typing import Dict

from main import 开店Agent

logger = logging.getLogger(__name__)

_sessions: Dict[str, 开店Agent] = {}
_sessions_last_access: Dict[str, float] = {}
_SESSION_TTL = 1800  # 30 分钟


def _cleanup():
    now = _time.time()
    expired = [k for k, t in _sessions_last_access.items() if now - t > _SESSION_TTL]
    for k in expired:
        _sessions.pop(k, None)
        _sessions_last_access.pop(k, None)
    if expired:
        logger.info("清理 %d 个过期 Agent 会话", len(expired))


def get_agent(project_id: str = "", session_id: str = "") -> 开店Agent:
    """获取或创建 Agent 实例。

    session_id 优先：同一 session_id 复用同一实例（跨轮次记忆）。
    project_id 降级：用于项目级别的会话隔离。
    """
    _cleanup()
    key = session_id or project_id or f"anon_{uuid.uuid4().hex[:8]}"
    if key not in _sessions:
        _sessions[key] = 开店Agent(project_id=project_id if project_id else None)
        logger.info("Agent 实例已创建: session=%s project=%s", session_id or "auto", project_id or "anonymous")
    _sessions_last_access[key] = _time.time()
    return _sessions[key]


def reset_agent(project_id: str = "") -> bool:
    """重置指定项目的 Agent 会话。"""
    key = project_id or ""
    if key in _sessions:
        _sessions[key].reset_conversation()
        return True
    for k in list(_sessions.keys()):
        if k.startswith(key):
            _sessions[k].reset_conversation()
            return True
    return False
