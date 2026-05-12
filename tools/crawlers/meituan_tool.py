#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""美团/大众点评竞品数据工具。

通过联网搜索间接获取美团和大众点评上的竞品数据，
包括评分分布、价格带、热门品类、用户评价关键词。

注意：本工具不直接爬取美团/点评页面（违反ToS），
而是通过搜索引擎聚合公开可见的商家信息。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from tools.base import BaseTool, ToolMeta, ToolResult
from tools.web_search_tool import WebSearchTool


@dataclass
class CompetitorInfo:
    """竞品商家信息。"""
    name: str = ""
    category: str = ""
    avg_price: str = ""         # 人均消费
    rating: str = ""            # 评分
    review_count: str = ""      # 评论数
    address: str = ""
    source: str = ""            # 数据来源
    highlights: List[str] = field(default_factory=list)


class MeituanCompetitionTool(BaseTool):
    """美团/大众点评竞品分析工具——基于搜索的竞争情报收集。"""

    meta = ToolMeta(
        name="meituan_competition",
        description="搜索美团/大众点评上的竞品数据：同品类商家数量、评分分布、价格带、热门评价",
        applicable_intents=["选址诊断", "选品决策", "开店规划"],
        required_profile_fields=["城市"],
        optional_profile_fields=["区县", "品类"],
        priority=75,
    )

    def __init__(self):
        self._web_search = None
        self._results_cache: Dict[str, Any] = {}

    def _get_web_search(self) -> WebSearchTool:
        if self._web_search is None:
            self._web_search = WebSearchTool()
        return self._web_search

    def available(self) -> bool:
        return self._get_web_search().available()

    def validate_params(self, params: Dict[str, Any]) -> Tuple[bool, str]:
        if not params.get("city"):
            return False, "缺少城市参数"
        return True, ""

    def execute(self, params: Dict[str, Any]) -> ToolResult:
        """搜索美团/点评竞品数据。

        params:
            city: str - 城市名
            category: str - 品类（如 '早餐'）
            district: str - 区县（可选）
            keywords: str - 额外搜索关键词（可选）
        """
        city = params.get("city", "")
        category = params.get("category", "餐饮")
        district = params.get("district", "")
        extra_kw = params.get("keywords", "")

        web = self._get_web_search()
        location = f"{city}{district}" if district else city

        queries = [
            f"{location} {category} 美团 评分 人气",
            f"{location} {category} 大众点评 推荐 排行",
            f"{location} {category} 人均消费 价格 热门",
        ]

        results = []
        for q in queries:
            try:
                sr = web.execute({"query": q, "max_results": 3})
                if sr.success and sr.data:
                    results.extend(sr.data)
            except Exception:
                continue

        if not results:
            return ToolResult(
                success=False,
                error=f"未找到 {location} 的 {category} 相关美团/点评数据",
            )

        # 解析搜索结果
        competitors = self._parse_competitors(results, category)
        analysis = self._analyze_competition(competitors)

        return ToolResult(
            success=True,
            data={
                "location": location,
                "category": category,
                "competitors": [self._comp_to_dict(c) for c in competitors[:15]],
                "analysis": analysis,
                "search_queries": queries,
                "total_results": len(results),
                "note": "数据来自搜索引擎聚合，非美团/点评官方API。建议结合实地调研验证。",
            },
            metadata={"city": city, "category": category, "district": district},
        )

    def _parse_competitors(self, search_results: List[Any], category: str) -> List[CompetitorInfo]:
        """从搜索结果中提取竞品信息。"""
        competitors = []
        for ev in search_results:
            text = getattr(ev, 'text', getattr(ev, 'snippet', str(ev)))
            title = getattr(ev, 'title', '')
            source = getattr(ev, 'source', getattr(ev, 'url', ''))

            # 提取商家名、评分、价格
            name_match = re.search(r'([\u4e00-\u9fa5]{2,10}(?:店|馆|坊|屋|吧|厅|堂))', title + text)
            rating_match = re.search(r'([\d.]+)\s*分', text)
            price_match = re.search(r'人均[：:]?\s*[¥￥]?(\d+)', text)
            review_match = re.search(r'(\d+)\s*(?:条评论|条评价)', text)

            comp = CompetitorInfo(
                name=name_match.group(1) if name_match else (title[:30] if title else "未知"),
                category=category,
                avg_price=f"¥{price_match.group(1)}" if price_match else "",
                rating=rating_match.group(1) if rating_match else "",
                review_count=review_match.group(1) if review_match else "",
                source=source[:80] if source else "",
            )

            # 提取亮点关键词
            highlights = []
            for kw in ["环境好", "服务好", "味道好", "性价比高", "人多", "排队",
                        "干净", "便宜", "好吃", "正宗", "网红", "老店"]:
                if kw in text:
                    highlights.append(kw)
            comp.highlights = highlights[:5]

            competitors.append(comp)

        # 按名称去重
        seen = set()
        deduped = []
        for c in competitors:
            if c.name in seen:
                continue
            seen.add(c.name)
            deduped.append(c)

        return deduped

    def _analyze_competition(self, competitors: List[CompetitorInfo]) -> Dict[str, Any]:
        """分析竞品格局。"""
        if not competitors:
            return {"message": "暂无足够数据进行分析"}

        ratings = []
        prices = []
        highlights_count: Dict[str, int] = {}

        for c in competitors:
            if c.rating:
                try:
                    ratings.append(float(c.rating))
                except ValueError:
                    pass
            if c.avg_price:
                try:
                    prices.append(int(re.sub(r'\D', '', c.avg_price)))
                except ValueError:
                    pass
            for h in c.highlights:
                highlights_count[h] = highlights_count.get(h, 0) + 1

        avg_rating = sum(ratings) / len(ratings) if ratings else 0
        avg_price = sum(prices) / len(prices) if prices else 0

        # 价格带分布
        price_bands = {"低价(≤15)": 0, "中价(16-30)": 0, "高价(>30)": 0}
        for p in prices:
            if p <= 15:
                price_bands["低价(≤15)"] += 1
            elif p <= 30:
                price_bands["中价(16-30)"] += 1
            else:
                price_bands["高价(>30)"] += 1

        # 市场饱和度评估
        total_count = len(competitors)
        if total_count > 20:
            saturation = "高竞争——同品类商家密集，差异化是关键"
        elif total_count > 8:
            saturation = "中度竞争——有空间但需找准定位"
        else:
            saturation = "竞争较低——可能为蓝海市场，但需验证需求"

        return {
            "total_competitors_found": total_count,
            "avg_rating": round(avg_rating, 1),
            "avg_price": int(avg_price) if avg_price else "N/A",
            "price_distribution": price_bands,
            "top_highlights": dict(sorted(highlights_count.items(), key=lambda x: x[1], reverse=True)[:8]),
            "market_saturation": saturation,
            "differentiation_tips": (
                "建议关注：价格缺口（当前市场均价" + str(int(avg_price)) + "元）" +
                "、评分落差（均分" + str(round(avg_rating, 1)) + "分）" +
                "、评价高频词（" + "/".join([k for k, v in sorted(highlights_count.items(), key=lambda x: x[1], reverse=True)[:3]]) + "）"
            ) if competitors else "",
        }

    @staticmethod
    def _comp_to_dict(comp: CompetitorInfo) -> Dict[str, Any]:
        return {
            "name": comp.name,
            "category": comp.category,
            "avg_price": comp.avg_price,
            "rating": comp.rating,
            "review_count": comp.review_count,
            "highlights": comp.highlights,
            "source": comp.source,
        }
