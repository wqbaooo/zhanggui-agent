#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""联网搜索工具：支持多个搜索后端，优先使用免费方案。

支持的搜索后端：
- DuckDuckGo（免费，无需API key，需安装 duckduckgo-search）
- Serper（付费，Google搜索API，需 SERPER_API_KEY）
- Tavily（付费，专为AI设计，需 TAVILY_API_KEY）

返回格式：List[Evidence] 与RAG结果一致，可直接融入证据流。
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote_plus
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

from models.state import Evidence
from tools.base import BaseTool, ToolMeta, ToolResult

logger = logging.getLogger(__name__)


# 智能触发关键词
SEARCH_TRIGGERS = [
    "最新", "今年", "2026", "最近", "现在", "目前",
    "政策", "法规", "趋势", "行情", "市场",
    "品牌", "加盟", "连锁", "网红",
    "搜索", "查一下", "帮我查", "搜一下",
    "新闻", "资讯", "动态", "热点",
    "多少钱", "价格", "费用", "多少",
]


@dataclass
class SearchResult:
    """搜索结果条目。"""
    title: str
    snippet: str
    url: str
    source: str  # "duckduckgo" / "serper" / "tavily"
    published_date: Optional[str] = None


class WebSearchTool(BaseTool):
    """联网搜索工具。"""

    meta = ToolMeta(
        name="web_search",
        description="联网搜索最新信息，获取实时市场数据、政策法规、品牌资讯等",
        applicable_intents=["*"],  # 所有意图都可能需要
        required_profile_fields=[],  # 无前置要求
        priority=90,  # 高优先级，仅次于RAG
    )

    def __init__(self):
        self._backend = None
        self._serper_key = None
        self._tavily_key = None

    def _ensure_config(self):
        """懒加载配置。"""
        if self._backend is not None:
            return

        import os
        self._serper_key = os.getenv("SERPER_API_KEY", "")
        self._tavily_key = os.getenv("TAVILY_API_KEY", "")

        # 选择后端：DuckDuckGo > Serper > Tavily
        # 注意：DuckDuckGo不需要key，但需要安装duckduckgo-search包
        try:
            from duckduckgo_search import DDGS
            self._backend = "duckduckgo"
            logger.info("搜索后端: DuckDuckGo (免费)")
        except ImportError:
            if self._serper_key:
                self._backend = "serper"
                logger.info("搜索后端: Serper (Google)")
            elif self._tavily_key:
                self._backend = "tavily"
                logger.info("搜索后端: Tavily")
            else:
                self._backend = "none"
                logger.warning("无可用搜索后端，请安装 duckduckgo-search 或配置 SERPER_API_KEY/TAVILY_API_KEY")

    def available(self) -> bool:
        """检查是否有可用的搜索后端。"""
        self._ensure_config()
        return self._backend != "none"

    def validate_params(self, params: Dict[str, Any]) -> Tuple[bool, str]:
        """校验参数。"""
        if not params.get("query"):
            return False, "缺少搜索查询参数"
        return True, ""

    def execute(self, params: Dict[str, Any]) -> ToolResult:
        """执行搜索。

        params:
            query: str - 搜索查询
            max_results: int - 最多返回结果数（默认5）
        """
        self._ensure_config()

        query = params.get("query", "")
        max_results = params.get("max_results", 5)

        if not query:
            return ToolResult(success=False, error="搜索查询为空")

        if self._backend == "none":
            return ToolResult(success=False, error="无可用搜索后端")

        try:
            results = self._search(query, max_results)

            # 转换为Evidence格式
            evidence_list = []
            for i, result in enumerate(results):
                evidence = Evidence(
                    id=f"web_{hash(result.url) % 10000:04d}",
                    source="联网搜索",
                    title=result.title,
                    text=f"{result.snippet}\n来源: {result.url}",
                    score=0.8 - i * 0.05,  # 按顺序递减分数
                    status="usable",
                    source_type="web_search",
                )
                evidence_list.append(evidence)

            return ToolResult(
                success=True,
                data=evidence_list,
                metadata={
                    "backend": self._backend,
                    "query": query,
                    "total_results": len(evidence_list),
                },
            )

        except Exception as exc:
            logger.error("搜索失败: %s", exc)
            return ToolResult(success=False, error=str(exc))

    def _search(self, query: str, max_results: int) -> List[SearchResult]:
        """根据后端执行搜索。"""
        if self._backend == "duckduckgo":
            return self._search_duckduckgo(query, max_results)
        elif self._backend == "serper":
            return self._search_serper(query, max_results)
        elif self._backend == "tavily":
            return self._search_tavily(query, max_results)
        return []

    def _search_duckduckgo(self, query: str, max_results: int) -> List[SearchResult]:
        """DuckDuckGo搜索（带超时和重试）。"""
        import signal
        from duckduckgo_search import DDGS
        import time

        results = []
        max_retries = 1  # 减少重试次数，避免卡死
        
        for attempt in range(max_retries):
            try:
                ddgs = DDGS(timeout=8)  # 8秒超时
                # 优先搜索中文结果
                for r in ddgs.text(query, max_results=max_results, region='cn-zh'):
                    results.append(SearchResult(
                        title=r.get("title", ""),
                        snippet=r.get("body", ""),
                        url=r.get("href", ""),
                        source="duckduckgo",
                    ))
                if results:
                    return results
                # 无结果，尝试 fallback
                logger.info("DuckDuckGo 返回空结果，尝试备用方案")
                return self._search_duckduckgo_fallback(query, max_results)
            except Exception as exc:
                if "Ratelimit" in str(exc) and attempt < max_retries - 1:
                    wait_time = 2
                    logger.warning("DuckDuckGo 速率限制，%d秒后重试...", wait_time)
                    time.sleep(wait_time)
                    continue
                logger.warning("DuckDuckGo API 失败: %s，尝试备用方案", exc)
                return self._search_duckduckgo_fallback(query, max_results)

        return results

    def _search_duckduckgo_fallback(self, query: str, max_results: int) -> List[SearchResult]:
        """DuckDuckGo备用搜索方案（使用HTML解析）。"""
        import re
        from html.parser import HTMLParser

        results = []
        encoded_query = quote_plus(query)
        url = f"https://html.duckduckgo.com/html/?q={encoded_query}"

        try:
            req = Request(url, headers={
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            })
            with urlopen(req, timeout=10) as response:
                html = response.read().decode('utf-8')

            # 简单解析HTML提取搜索结果
            # 提取标题和链接
            title_pattern = r'class="result__a"[^>]*href="([^"]*)"[^>]*>(.*?)</a>'
            snippet_pattern = r'class="result__snippet"[^>]*>(.*?)</(?:a|td|div)'

            titles = re.findall(title_pattern, html, re.DOTALL)
            snippets = re.findall(snippet_pattern, html, re.DOTALL)

            for i, (url, title) in enumerate(titles[:max_results]):
                # 清理HTML标签
                title = re.sub(r'<[^>]+>', '', title).strip()
                snippet = re.sub(r'<[^>]+>', '', snippets[i]).strip() if i < len(snippets) else ""

                if title:
                    results.append(SearchResult(
                        title=title,
                        snippet=snippet,
                        url=url,
                        source="duckduckgo",
                    ))

        except Exception as exc:
            logger.error("DuckDuckGo 备用搜索失败: %s", exc)

        return results

    def _search_serper(self, query: str, max_results: int) -> List[SearchResult]:
        """Serper (Google) 搜索。"""
        url = "https://google.serper.dev/search"
        headers = {
            "X-API-KEY": self._serper_key,
            "Content-Type": "application/json",
        }
        payload = json.dumps({
            "q": query,
            "gl": "cn",  # 中国地区
            "hl": "zh-cn",  # 中文界面
            "num": max_results,
        }).encode("utf-8")

        req = Request(url, data=payload, headers=headers, method="POST")
        with urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        results = []
        for item in data.get("organic", [])[:max_results]:
            results.append(SearchResult(
                title=item.get("title", ""),
                snippet=item.get("snippet", ""),
                url=item.get("link", ""),
                source="serper",
            ))

        return results

    def _search_tavily(self, query: str, max_results: int) -> List[SearchResult]:
        """Tavily搜索。"""
        url = "https://api.tavily.com/search"
        headers = {
            "Content-Type": "application/json",
        }
        payload = json.dumps({
            "api_key": self._tavily_key,
            "query": query,
            "max_results": max_results,
            "include_answer": False,
            "include_raw_content": False,
        }).encode("utf-8")

        req = Request(url, data=payload, headers=headers, method="POST")
        with urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        results = []
        for item in data.get("results", [])[:max_results]:
            results.append(SearchResult(
                title=item.get("title", ""),
                snippet=item.get("content", ""),
                url=item.get("url", ""),
                source="tavily",
            ))

        return results


def should_search(user_input: str, intent: str) -> bool:
    """判断是否需要联网搜索。

    智能触发条件：
    1. 用户输入包含搜索触发关键词
    2. 意图是营销运营或开店规划（通常需要最新信息）
    3. 用户明确要求搜索
    """
    # 检查触发关键词
    for trigger in SEARCH_TRIGGERS:
        if trigger in user_input:
            return True

    # 检查意图
    if intent in ["营销运营", "开店规划"]:
        # 这些意图通常需要最新信息
        return True

    # 检查是否明确要求搜索
    search_keywords = ["搜索", "查一下", "帮我查", "搜一下", "网上", "线上"]
    for keyword in search_keywords:
        if keyword in user_input:
            return True

    return False
