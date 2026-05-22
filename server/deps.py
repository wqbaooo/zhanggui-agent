#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""依赖注入：Agent 实例管理、session 工厂。"""

from __future__ import annotations

import logging
import uuid
from typing import Dict

from main import 开店Agent

logger = logging.getLogger(__name__)

_sessions: Dict[str, 开店Agent] = {}


def get_agent(project_id: str = "") -> 开店Agent:
    """获取或创建 Agent 实例。

    按 project_id 隔离会话。空 project_id 使用临时会话。
    """
    key = project_id or f"anon_{uuid.uuid4().hex[:8]}"
    if key not in _sessions:
        _sessions[key] = 开店Agent(project_id=project_id if project_id else None)
        logger.info("Agent 实例已创建: project=%s", project_id or "anonymous")
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
