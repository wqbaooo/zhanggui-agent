#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""高德地图工具：包装现有 amap_tool.py，适配工具注册表接口。

支持两级分析：
- 精确选址：有具体地址 → analyze_site（周边竞品+聚客点）
- 区域扫描：只有城市/区县 → analyze_town（区域POI密度+竞争格局）
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import AMAP_WEBSERVICE_KEY
from tools.base import BaseTool, ToolMeta, ToolResult

# 延迟导入原始 amap_tool 避免初始化时报错
_amap_module = None


def _get_amap_tool():
    global _amap_module
    if _amap_module is None:
        import amap_tool as _mod
        _amap_module = _mod
    return _amap_module


class AmapSiteTool(BaseTool):
    """高德地图选址分析工具——支持精确选址和区域扫描两级分析。"""

    meta = ToolMeta(
        name="amap_site_analysis",
        description="基于高德地图分析商圈：精确选址（周边竞品/聚客点/交通设施）或区域扫描（县/乡镇POI密度/竞争格局）",
        applicable_intents=["选址诊断", "开店规划"],
        required_profile_fields=["城市"],
        optional_profile_fields=["具体地址", "区县", "品类"],
        priority=80,
    )

    def available(self) -> bool:
        return bool(AMAP_WEBSERVICE_KEY)

    def validate_params(self, params: Dict[str, Any]) -> Tuple[bool, str]:
        profile = params.get("profile", {})
        if not profile.get("城市"):
            return False, "至少需要城市信息"
        return True, ""

    def execute(self, params: Dict[str, Any]) -> ToolResult:
        """执行选址分析——智能选择分析模式。

        params 支持两种模式：
        
        模式A - 精确选址（有具体地址）：
            profile: {城市, 具体地址, 品类, 搜索半径}
        
        模式B - 区域扫描（只有城市/区县）：
            profile: {城市, 区县, 乡镇, 品类}
        """
        profile = params.get("profile", {})
        city = profile.get("城市", "")
        category = profile.get("品类", "早餐")
        address = profile.get("具体地址", "")
        county = profile.get("区县", "")
        town = profile.get("乡镇", "")
        radius = params.get("radius", 1000)

        if not city:
            return ToolResult(success=False, error="缺少城市信息")

        try:
            mod = _get_amap_tool()
            tool_instance = mod.AmapTool(key=AMAP_WEBSERVICE_KEY)

            if address:
                # 模式A：精确选址分析
                result = tool_instance.analyze_site(
                    address=address,
                    category=category,
                    city=city,
                    radius=radius,
                )
                return ToolResult(
                    success=True,
                    data=result,
                    metadata={"mode": "site_analysis", "address": address, "category": category},
                )
            else:
                # 模式B：区域扫描分析
                result = tool_instance.analyze_town(
                    city=city,
                    county=county,
                    town=town,
                    category=category,
                )
                return ToolResult(
                    success=True,
                    data=result,
                    metadata={"mode": "town_analysis", "city": city, "county": county, "town": town},
                )
        except Exception as exc:
            return ToolResult(success=False, error=str(exc))
