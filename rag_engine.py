#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""轻量 RAG 引擎。

V1 先用标准库实现可审计的混合检索：关键词覆盖 + BM25。
后续可以在不改 Agent 上层接口的情况下替换成向量库。
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_INDEX_PATH = PROJECT_ROOT / "knowledge_base" / "rag_index.json"


@dataclass
class RagChunk:
    id: str
    source_type: str
    source_path: str
    title: str
    text: str
    metadata: Dict[str, Any]
    status: str = "usable"


@dataclass
class RagHit:
    chunk: RagChunk
    score: float
    reasons: List[str]


class RagIndex:
    def __init__(self, chunks: Optional[List[RagChunk]] = None):
        self.chunks = chunks or []
        self._doc_tokens: List[List[str]] = []
        self._doc_freq: Counter[str] = Counter()
        self._avgdl = 0.0
        self._prepared = False

    def add(self, chunk: RagChunk):
        self.chunks.append(chunk)
        self._prepared = False

    def save(self, path: Path = DEFAULT_INDEX_PATH):
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"chunks": [asdict(chunk) for chunk in self.chunks]}
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: Path = DEFAULT_INDEX_PATH) -> "RagIndex":
        if not path.exists():
            return cls([])
        payload = json.loads(path.read_text(encoding="utf-8"))
        return cls([RagChunk(**item) for item in payload.get("chunks", [])])

    def search(
        self,
        query: str,
        limit: int = 8,
        source_types: Optional[Iterable[str]] = None,
        include_unusable: bool = False,
    ) -> List[RagHit]:
        self._prepare()
        query_tokens = tokenize(query)
        if not query_tokens:
            return []
        source_type_set = set(source_types) if source_types else None
        hits: List[RagHit] = []
        for idx, chunk in enumerate(self.chunks):
            if source_type_set and chunk.source_type not in source_type_set:
                continue
            if not include_unusable and chunk.status != "usable":
                continue
            score, reasons = self._score(idx, chunk, query_tokens)
            if score > 0:
                hits.append(RagHit(chunk=chunk, score=score, reasons=reasons))
        return sorted(hits, key=lambda hit: hit.score, reverse=True)[:limit]

    def audit(self) -> Dict[str, Any]:
        by_type: Dict[str, int] = {}
        by_status: Dict[str, int] = {}
        for chunk in self.chunks:
            by_type[chunk.source_type] = by_type.get(chunk.source_type, 0) + 1
            by_status[chunk.status] = by_status.get(chunk.status, 0) + 1
        return {"chunks": len(self.chunks), "by_type": by_type, "by_status": by_status}

    def _prepare(self):
        if self._prepared:
            return
        self._doc_tokens = []
        self._doc_freq = Counter()
        total_len = 0
        for chunk in self.chunks:
            tokens = tokenize(f"{chunk.title}\n{chunk.text}")
            self._doc_tokens.append(tokens)
            total_len += len(tokens)
            self._doc_freq.update(set(tokens))
        self._avgdl = total_len / len(self._doc_tokens) if self._doc_tokens else 0.0
        self._prepared = True

    def _score(self, idx: int, chunk: RagChunk, query_tokens: List[str]) -> tuple[float, List[str]]:
        tokens = self._doc_tokens[idx]
        if not tokens:
            return 0.0, []
        counts = Counter(tokens)
        doc_len = len(tokens)
        k1 = 1.5
        b = 0.75
        score = 0.0
        reasons = []
        for token in query_tokens:
            tf = counts.get(token, 0)
            if not tf:
                continue
            df = self._doc_freq.get(token, 0)
            idf = math.log(1 + (len(self.chunks) - df + 0.5) / (df + 0.5))
            denom = tf + k1 * (1 - b + b * doc_len / (self._avgdl or 1))
            score += idf * (tf * (k1 + 1) / denom)
            reasons.append(token)

        # 标题匹配加权
        title = chunk.title.lower()
        exact_boost = 0.0
        for token in query_tokens:
            if token in title:
                exact_boost += 1.5
        
        # 状态加权：优先返回已转写或可用的内容
        status_boost = 1.0
        if chunk.status == "usable":
            status_boost = 1.5
        elif chunk.status == "title_index_only":
            status_boost = 0.3
            
        # 元数据标签匹配加权
        tags = chunk.metadata.get("topic_tags", [])
        tag_match = sum(1 for t in tags if any(q in t for q in query_tokens))
        tag_boost = tag_match * 2.0

        final_score = (score + exact_boost + tag_boost) * status_boost
        return final_score, reasons[:8]


def tokenize(text: str) -> List[str]:
    text = text.lower()
    chinese_terms = [
        "开店", "创业", "餐饮", "选址", "商圈", "商铺", "铺位", "客流", "动线", "聚客",
        "地铁", "学校", "社区", "写字楼", "医院", "商场", "菜场", "竞品",
        "选品", "品类", "小吃", "早餐", "粉面", "快餐", "饮品", "外卖", "堂食",
        "成本", "利润", "毛利", "租金", "人力", "水电", "包材", "投产", "回本", "现金流",
        "加盟", "自营", "合伙", "转让", "合同", "装修", "设备", "证照", "许可证",
        "风险", "避坑", "止损", "营销", "推广", "抖音", "小红书", "美团", "饿了么", "团购",
    ]
    tokens: List[str] = []
    for term in chinese_terms:
        if term in text:
            tokens.extend([term] * text.count(term))
    tokens.extend(re.findall(r"[a-z0-9_]{2,}", text))
    tokens.extend(re.findall(r"\d+(?:\.\d+)?%?", text))
    return tokens


def chunk_text(text: str, size: int = 900, overlap: int = 120) -> List[str]:
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        chunks.append(text[start:end])
        if end == len(text):
            break
        start = max(start + 1, end - overlap)
    return chunks
