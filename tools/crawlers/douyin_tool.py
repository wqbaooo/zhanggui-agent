#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""抖音本地生活数据工具。

通过联网搜索间接获取抖音上的本地生活内容数据，
包括热门视频趋势、达人探店情况、本地话题热度。

注意：不直接爬取抖音页面，而是通过搜索引擎聚合公开可见的内容信息。
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from tools.base import BaseTool, ToolMeta, ToolResult
from tools.web_search_tool import WebSearchTool


@dataclass
class LocalTrend:
    """本地热点/趋势项。"""
    keyword: str = ""
    mention_count: int = 0
    sentiment: str = ""  # positive/negative/neutral
    sample_content: str = ""


class DouyinLocalTool(BaseTool):
    """抖音本地生活数据分析工具。"""

    meta = ToolMeta(
        name="douyin_local",
        description="搜索抖音本地生活热点：同城热门品类、达人探店趋势、本地话题热度、用户偏好",
        applicable_intents=["营销运营", "选品决策", "开店规划", "通用咨询"],
        required_profile_fields=["城市"],
        optional_profile_fields=["品类", "区县"],
        priority=70,
    )

    def __init__(self):
        self._web_search = None

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
        """搜索抖音本地生活数据。

        params:
            city: str - 城市名
            category: str - 品类（如 '早餐'）
            district: str - 区县（可选）
        """
        city = params.get("city", "")
        category = params.get("category", "")
        district = params.get("district", "")

        web = self._get_web_search()
        location = f"{city}{district}" if district else city

        # 多个搜索角度
        queries = []
        if category:
            queries.append(f"{location} {category} 抖音 探店 网红")
            queries.append(f"{location} {category} 抖音 热门 排行")
        else:
            queries.append(f"{location} 餐饮 抖音 探店 热门")
            queries.append(f"{location} 美食 抖音 本地生活 探店")

        queries.append(f"{location} 抖音同城 美食 热度")
        queries.append(f"{location} 达人探店 推荐 餐饮")

        results = []
        for q in queries[:4]:  # 限制为4个查询
            try:
                sr = web.execute({"query": q, "max_results": 3})
                if sr.success and sr.data:
                    results.extend(sr.data)
            except Exception:
                continue

        if not results:
            return ToolResult(
                success=False,
                error=f"未找到 {location} 相关抖音本地生活数据",
            )

        # 分析结果
        trends = self._extract_trends(results, category)
        content_analysis = self._analyze_content(results)

        return ToolResult(
            success=True,
            data={
                "location": location,
                "category": category or "全部",
                "trends": [{"keyword": t.keyword, "mentions": t.mention_count,
                            "sentiment": t.sentiment, "sample": t.sample_content[:100]}
                           for t in trends[:10]],
                "content_analysis": content_analysis,
                "marketing_tips": self._generate_marketing_tips(trends, content_analysis, city, category),
                "note": "数据来自搜索引擎聚合，非抖音官方API。建议结合抖音App内搜索验证。",
            },
            metadata={"city": city, "category": category},
        )

    def _extract_trends(self, search_results: List[Any], category: str) -> List[LocalTrend]:
        """从搜索结果中提取本地趋势关键词。"""
        all_text = ""
        for ev in search_results:
            text = getattr(ev, 'text', getattr(ev, 'snippet', str(ev)))
            all_text += text + " "

        # 提取品类关键词
        category_keywords = [
            "早餐", "午餐", "晚餐", "小吃", "奶茶", "咖啡", "烧烤", "火锅",
            "面馆", "快餐", "烘焙", "甜品", "麻辣烫", "炸鸡", "汉堡",
            "牛杂", "肠粉", "烧饼", "馄饨", "包子", "粉面", "卤味",
            "冰粉", "凉皮", "煎饼", "糖水", "汤粉", "拌面",
        ]

        # 提取话题趋势
        trend_keywords = [
            "排队", "网红店", "打卡", "探店", "新店", "老店",
            "便宜", "性价比", "人均", "套餐", "团购", "优惠",
            "环境好", "装修", "拍照", "氛围", "深夜", "夜宵",
        ]

        word_counts = Counter()
        for kw in category_keywords + trend_keywords:
            count = all_text.count(kw)
            if count > 0:
                word_counts[kw] = count

        # 构建趋势列表
        trends = []
        for kw, count in word_counts.most_common(15):
            # 简单情感判断
            sentiment = "neutral"
            pos_words = ["好吃", "推荐", "赞", "排队", "网红", "人气"]
            neg_words = ["贵", "难吃", "差评", "踩雷"]
            context_start = max(0, all_text.find(kw) - 30)
            context = all_text[context_start:context_start + 80]
            if any(w in context for w in pos_words):
                sentiment = "positive"
            elif any(w in context for w in neg_words):
                sentiment = "negative"

            trends.append(LocalTrend(
                keyword=kw,
                mention_count=count,
                sentiment=sentiment,
                sample_content=context.strip()[:100],
            ))

        return trends

    def _analyze_content(self, search_results: List[Any]) -> Dict[str, Any]:
        """分析内容特征。"""
        # 统计内容来源类型
        sources = Counter()
        total_text = ""
        for ev in search_results:
            src = getattr(ev, 'source', getattr(ev, 'url', ''))
            text = getattr(ev, 'text', getattr(ev, 'snippet', str(ev)))
            total_text += text + " "

            if 'douyin.com' in src:
                sources['抖音'] += 1
            elif 'dianping.com' in src or 'meituan.com' in src:
                sources['美团/点评'] += 1
            elif 'xiaohongshu.com' in src:
                sources['小红书'] += 1
            elif 'zhihu.com' in src:
                sources['知乎'] += 1
            elif 'baidu.com' in src:
                sources['百度'] += 1
            else:
                sources['其他'] += 1

        # 内容热度指标
        hot_signals = []
        if "排队" in total_text:
            hot_signals.append("部分店铺有排队现象")
        if "网红" in total_text or "打卡" in total_text:
            hot_signals.append("存在网红打卡效应")
        if "探店" in total_text:
            hot_signals.append("有达人探店内容覆盖")
        if "新店" in total_text:
            hot_signals.append("近期有新增店铺")

        return {
            "source_distribution": dict(sources.most_common()),
            "total_results": len(search_results),
            "hot_signals": hot_signals,
            "content_freshness": "搜索快照，时效性取决于搜索引擎缓存",
        }

    def _generate_marketing_tips(
        self,
        trends: List[LocalTrend],
        analysis: Dict[str, Any],
        city: str,
        category: str,
    ) -> str:
        """基于趋势分析生成营销建议。"""
        tips = []
        hot_signals = analysis.get("hot_signals", [])

        if "有达人探店内容覆盖" in hot_signals:
            tips.append(f"抖音上已有{city}的{category or '餐饮'}探店内容，建议策划差异化探店活动")
        if "存在网红打卡效应" in hot_signals:
            tips.append(f"本地存在网红打卡文化，可考虑打造视觉记忆点（装修/摆盘/包装）")
        if "有达人探店内容覆盖" not in hot_signals:
            tips.append(f"{city}该品类抖音内容较少——可能是蓝海机会，建议主动邀请本地达人探店")

        # 基于品类关键词建议
        trend_kw = [t.keyword for t in trends[:5]]
        if category and category in trend_kw:
            tips.append(f"'{category}'在本地有一定热度，可借助已有热度做内容")
        elif category:
            tips.append(f"'{category}'在本地搜索热度较低，需从0开始教育市场——做差异化内容")

        return "\n".join(f"- {t}" for t in tips) if tips else "暂无足够数据生成营销建议"
