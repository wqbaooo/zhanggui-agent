#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Structured restaurant case repository and similarity search."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from config import KNOWLEDGE_BASE_DIR


DEFAULT_CASE_PATH = KNOWLEDGE_BASE_DIR / "cases" / "structured_cases.json"


@dataclass
class RestaurantCase:
    case_id: str
    title: str
    source_role: str
    case_type: str
    city_tier: str = ""
    location_type: str = ""
    category: str = ""
    mode: str = ""
    scale: str = ""
    failure_reason: List[str] = field(default_factory=list)
    success_pattern: List[str] = field(default_factory=list)
    warning_signal: List[str] = field(default_factory=list)
    agent_rule: str = ""
    source_url: str = ""
    confidence: str = "medium"
    notes: str = ""

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RestaurantCase":
        allowed = cls.__dataclass_fields__.keys()
        clean = {k: v for k, v in data.items() if k in allowed}
        return cls(**clean)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class CaseRepository:
    def __init__(self, path: Path = DEFAULT_CASE_PATH):
        self.path = path
        self.cases: List[RestaurantCase] = []
        self.load()

    def load(self):
        if not self.path.exists():
            self.cases = []
            return
        data = json.loads(self.path.read_text(encoding="utf-8"))
        self.cases = [RestaurantCase.from_dict(item) for item in data]

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps([case.to_dict() for case in self.cases], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def upsert(self, case: RestaurantCase):
        self.cases = [old for old in self.cases if old.case_id != case.case_id]
        self.cases.append(case)
        self.save()

    def search(self, query: str = "", filters: Optional[Dict[str, str]] = None, limit: int = 5) -> List[RestaurantCase]:
        filters = filters or {}
        scored: List[tuple[int, RestaurantCase]] = []
        for case in self.cases:
            score = _score_case(case, query, filters)
            if score > 0:
                scored.append((score, case))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [case for _, case in scored[:limit]]


def load_default_repository() -> CaseRepository:
    return CaseRepository()


def _score_case(case: RestaurantCase, query: str, filters: Dict[str, str]) -> int:
    score = 0
    haystack = " ".join([
        case.title,
        case.source_role,
        case.case_type,
        case.city_tier,
        case.location_type,
        case.category,
        case.mode,
        case.scale,
        " ".join(case.failure_reason),
        " ".join(case.success_pattern),
        " ".join(case.warning_signal),
        case.agent_rule,
        case.notes,
    ])

    for value in filters.values():
        if value and value in haystack:
            score += 5
    for token in _tokenize(query):
        if token in haystack:
            score += 2
    if case.confidence == "high":
        score += 2
    if case.source_role in {"legal_or_regulatory", "verified_store_data", "super_franchisee"}:
        score += 2
    return score


def _tokenize(text: str) -> List[str]:
    tokens = []
    for token in ["加盟", "商场", "美食城", "档口", "小吃", "人工", "租金", "外卖", "闭店", "转租", "总部", "超级加盟商", "投资人"]:
        if token in text:
            tokens.append(token)
    return tokens
