#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""RAG检索工具：包装现有 rag_engine.py。"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List

# 确保能导入项目根目录的 rag_engine
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import DEFAULT_KB_PATH, DEFAULT_DOCUMENT_KB_DIR, DEFAULT_RAG_INDEX_PATH, DEFAULT_VIDEO_KB_DIR
from models.state import Evidence
from rag_engine import RagIndex
from tools.base import BaseTool, ToolMeta, ToolResult


class RagTool(BaseTool):
    """知识库检索工具，基于BM25混合检索。"""

    meta = ToolMeta(
        name="rag_search",
        description="从核心知识库、PDF文档、视频转写中检索相关知识片段",
        applicable_intents=["*"],  # 所有意图都可以用
        required_profile_fields=[],  # 无前置要求
        priority=100,  # 最高优先级，总是被选中
    )

    def __init__(self):
        self._index: RagIndex | None = None
        self._knowledge_hub = None

    def _ensure_loaded(self):
        """懒加载知识索引。"""
        if self._index is not None:
            return
        self._index = RagIndex.load(DEFAULT_RAG_INDEX_PATH)
        print(f"[DEBUG] RAG Index loaded: {len(self._index.chunks)} chunks")

    def available(self) -> bool:
        return DEFAULT_RAG_INDEX_PATH.exists()

    def execute(self, params: Dict[str, Any]) -> ToolResult:
        """执行检索。

        params:
            query: str - 检索查询
            limit: int - 最多返回条数（默认8）
            source_types: List[str] - 可选，过滤来源类型
        """
        self._ensure_loaded()
        if not self._index or not self._index.chunks:
            return ToolResult(success=False, error="RAG索引为空或未加载")

        query = params.get("query", "")
        limit = params.get("limit", 8)
        source_types = params.get("source_types")

        if not query:
            return ToolResult(success=False, error="检索查询为空")

        hits = self._index.search(
            query, limit=limit, source_types=source_types, include_unusable=True
        )

        evidence_list: List[Evidence] = [
            Evidence(
                id=hit.chunk.id,
                source=self._source_label(hit.chunk.source_type),
                title=hit.chunk.title,
                text=hit.chunk.text,
                score=hit.score,
                status=hit.chunk.status,
                source_type=hit.chunk.source_type,
            )
            for hit in hits
        ]

        return ToolResult(
            success=True,
            data=evidence_list,
            metadata={
                "total_hits": len(hits),
                "query": query,
            },
        )

    def audit(self) -> Dict[str, Any]:
        """审计知识库状态。"""
        self._ensure_loaded()
        if not self._index:
            return {"chunks": 0}
        return self._index.audit()

    @staticmethod
    def _source_label(source_type: str) -> str:
        return {
            "core_markdown": "核心知识库",
            "document": "文档知识库",
            "video": "视频课程",
        }.get(source_type, source_type)
