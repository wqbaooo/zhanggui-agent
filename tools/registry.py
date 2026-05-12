#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""工具注册表：管理所有可用工具的发现和选择。"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from tools.base import BaseTool, ToolMeta

logger = logging.getLogger(__name__)


class ToolRegistry:
    """工具注册与发现中心。"""

    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}

    def register(self, tool: BaseTool):
        """注册一个工具实例。"""
        self._tools[tool.meta.name] = tool
        logger.debug("工具已注册: %s", tool.meta.name)

    def get(self, name: str) -> Optional[BaseTool]:
        """按名称获取工具。"""
        return self._tools.get(name)

    def list_available(self) -> List[BaseTool]:
        """列出当前可用的工具。"""
        return [t for t in self._tools.values() if t.available()]

    def select_for_intent(
        self,
        intent: str,
        profile: Dict[str, Any],
        exclude: Optional[List[str]] = None,
        max_tools: int = 3,
    ) -> List[BaseTool]:
        """根据意图和画像选择合适的工具。

        Args:
            intent: 当前意图
            profile: 当前画像字段字典
            exclude: 排除的工具名列表（如已在本轮调用过）
            max_tools: 最多选择几个工具

        Returns:
            按优先级排序的工具列表
        """
        exclude_set = set(exclude or [])
        profile_keys = set(profile.keys())
        candidates: List[BaseTool] = []

        for tool in self._tools.values():
            # 跳过不可用或已排除的
            if not tool.available() or tool.meta.name in exclude_set:
                continue

            # 检查意图匹配
            if intent not in tool.meta.applicable_intents and "*" not in tool.meta.applicable_intents:
                continue

            # 检查必需字段
            required = set(tool.meta.required_profile_fields)
            if not required.issubset(profile_keys):
                continue

            candidates.append(tool)

        # 按优先级排序（高优先级在前）
        candidates.sort(key=lambda t: t.meta.priority, reverse=True)
        return candidates[:max_tools]

    @property
    def tool_names(self) -> List[str]:
        return list(self._tools.keys())


# 全局注册表实例
registry = ToolRegistry()
