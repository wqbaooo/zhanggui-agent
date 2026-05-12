#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""向量化检索工具（分片版）：支持按 category 路由检索。

基于 Sentence-BERT + Faiss 的语义检索，支持分片索引按需加载。
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from models.state import Evidence
from tools.base import BaseTool, ToolMeta, ToolResult

logger = logging.getLogger(__name__)

VECTOR_DIR = Path("knowledge_base/vector_store")
SHARDED_DIR = Path("knowledge_base/vector_store_sharded")

# 阶段 → 索引目录映射
CATEGORY_MAP = {
    "想法验证": "创业1.0",
    "选址": "选址指南",
    "财务": "创业2.0",
    "执行": "创业2.0",
    "运营": "同城引流",
    "通用": "global",
}


class VectorSearchTool(BaseTool):
    """向量化语义检索工具（支持分片索引）。"""

    meta = ToolMeta(
        name="vector_search",
        description="基于语义相似度的知识库检索（替代BM25，解决OOV问题）",
        applicable_intents=["*"],
        required_profile_fields=[],
        priority=95,
    )

    def __init__(self):
        self._model = None
        self._shards: Dict[str, Dict] = {}  # category -> {index, texts, metadata}
        self._global_loaded = False

    # ------------------------------------------------------------------
    # 模型加载（只加载一次）
    # ------------------------------------------------------------------
    def _load_model(self):
        if self._model is not None:
            return
        try:
            from sentence_transformers import SentenceTransformer
            logger.info("加载向量化模型...")
            self._model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
        except Exception as exc:
            logger.error("加载模型失败: %s", exc)
            raise

    # ------------------------------------------------------------------
    # 分片索引加载（按需）
    # ------------------------------------------------------------------
    def _load_shard(self, category: str) -> Optional[Dict]:
        """加载指定 category 的索引，返回 {index, texts, metadata}。"""
        if category in self._shards:
            return self._shards[category]

        shard_dir = SHARDED_DIR / category
        if not (shard_dir / "index.faiss").exists():
            return None

        try:
            import faiss
            logger.info("加载分片索引: %s", category)
            index = faiss.read_index(str(shard_dir / "index.faiss"))
            with open(shard_dir / "metadata.json", "r", encoding="utf-8") as f:
                data = json.load(f)
            shard = {"index": index, "texts": data["texts"], "metadata": data["metadata"]}
            self._shards[category] = shard
            return shard
        except Exception as exc:
            logger.error("加载分片索引失败 [%s]: %s", category, exc)
            return None

    # ------------------------------------------------------------------
    # 全局索引加载（兼容旧版）
    # ------------------------------------------------------------------
    def _load_global(self) -> Optional[Dict]:
        if self._global_loaded:
            return self._shards.get("global")
        if not (VECTOR_DIR / "index.faiss").exists():
            return None
        try:
            import faiss
            logger.info("加载全局向量索引...")
            index = faiss.read_index(str(VECTOR_DIR / "index.faiss"))
            with open(VECTOR_DIR / "metadata.json", "r", encoding="utf-8") as f:
                data = json.load(f)
            shard = {"index": index, "texts": data["texts"], "metadata": data["metadata"]}
            self._shards["global"] = shard
            self._global_loaded = True
            return shard
        except Exception as exc:
            logger.error("加载全局索引失败: %s", exc)
            return None

    # ------------------------------------------------------------------
    # 公共接口
    # ------------------------------------------------------------------
    def available(self) -> bool:
        return (SHARDED_DIR.exists() and any(SHARDED_DIR.iterdir())) or (VECTOR_DIR / "index.faiss").exists()

    def execute(self, params: Dict[str, Any]) -> ToolResult:
        """执行语义检索。

        params:
            query: str - 检索查询
            limit: int - 最多返回条数（默认5）
            category: str - 阶段/分类（默认全局检索）
        """
        query = params.get("query", "")
        limit = params.get("limit", 5)
        category = params.get("category", "")

        if not query:
            return ToolResult(success=False, error="检索查询为空")

        try:
            self._load_model()
            import faiss
            import numpy as np
        except Exception as exc:
            return ToolResult(success=False, error=f"依赖未安装: {exc}")

        # 路由到对应分片
        shard = None
        if category:
            mapped = CATEGORY_MAP.get(category, category)
            shard = self._load_shard(mapped)
        if shard is None:
            shard = self._load_global()
        if shard is None:
            return ToolResult(success=False, error="无可用索引")

        # 向量化 + 搜索
        query_embedding = self._model.encode([query])
        query_embedding = np.array(query_embedding).astype("float32")
        faiss.normalize_L2(query_embedding)

        scores, indices = shard["index"].search(query_embedding, limit * 2)

        evidence_list = []
        seen_sources = set()

        for score, idx in zip(scores[0], indices[0]):
            if idx < 0 or idx >= len(shard["texts"]):
                continue

            text = shard["texts"][idx]
            meta = shard["metadata"][idx]

            source = meta.get("source", f"idx_{idx}")
            if source in seen_sources:
                continue
            seen_sources.add(source)

            ev_type = meta.get("type", "知识")
            title = f"[{ev_type}] {source}"

            evidence = Evidence(
                id=f"vec_{idx:04d}",
                source="向量知识库",
                title=title,
                text=text[:500],
                score=float(score),
                status="usable",
                source_type="vector_search",
            )
            evidence_list.append(evidence)

            if len(evidence_list) >= limit:
                break

        return ToolResult(
            success=True,
            data=evidence_list,
            metadata={"total_hits": len(evidence_list), "query": query, "category": category or "global"},
        )

    def search_similar(self, query: str, limit: int = 5, category: str = "") -> List[Tuple[str, float, Dict]]:
        """返回原始检索结果（用于调试）。"""
        result = self.execute({"query": query, "limit": limit, "category": category})
        if not result.success or not result.data:
            return []
        return [(ev.text, ev.score, {"source": ev.title}) for ev in result.data]
