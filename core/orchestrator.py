#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""工具编排器：对外提供更高级的工具选择和参数构建逻辑。

当前实现中，工具编排逻辑主要在 ToolSelectorNode 和 ToolExecutorNode 中完成。
本模块提供辅助函数和可扩展的编排策略。
"""

from __future__ import annotations

from typing import Any, Dict, List

from models.state import AgentState, TurnState
from tools.registry import ToolRegistry


def suggest_tools(
    registry: ToolRegistry,
    intent: str,
    profile: Dict[str, Any],
    already_used: List[str] = None,
) -> List[str]:
    """根据意图和画像推荐工具列表。

    这是 ToolSelectorNode 的辅助函数，提供更灵活的编排策略。
    """
    already_used = already_used or []
    selected = registry.select_for_intent(
        intent=intent,
        profile=profile,
        exclude=["rag_search"] + already_used,
        max_tools=2,
    )
    return [t.meta.name for t in selected]


def build_tool_params(
    tool_name: str,
    profile: Dict[str, Any],
    user_input: str,
    intent: str,
) -> Dict[str, Any]:
    """为指定工具构建调用参数。

    根据工具类型和用户画像生成适配的参数字典。
    """
    if tool_name == "amap_site_analysis":
        return {
            "address": profile.get("具体地址", profile.get("商圈", "")),
            "city": profile.get("城市", ""),
            "category": profile.get("品类", "早餐"),
            "radius": 1000,
        }
    elif tool_name == "finance_calculator":
        return {"profile": profile}
    else:
        return {"query": user_input, "profile": profile}
