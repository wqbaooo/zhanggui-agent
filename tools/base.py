#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""工具基类和 ToolMeta 定义。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class ToolMeta:
    """工具元信息，用于注册和编排。"""
    name: str
    description: str
    applicable_intents: List[str]       # 适用哪些意图
    required_profile_fields: List[str]  # 调用前必须有哪些画像字段
    optional_profile_fields: List[str] = field(default_factory=list)
    priority: int = 50                  # 同意图下的优先级（越高越先）
    cooldown: int = 0                   # 同一会话中调用间隔（轮次）


@dataclass
class ToolResult:
    """工具执行结果。"""
    success: bool
    data: Any = None
    error: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


class BaseTool:
    """所有工具的基类。"""

    meta: ToolMeta

    def available(self) -> bool:
        """该工具是否可用（如API key存在）。"""
        return True

    def validate_params(self, params: Dict[str, Any]) -> Tuple[bool, str]:
        """校验调用参数是否合法。返回 (valid, error_msg)。"""
        return True, ""

    def execute(self, params: Dict[str, Any]) -> ToolResult:
        """执行工具，返回结果。"""
        raise NotImplementedError
