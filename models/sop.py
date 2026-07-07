#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SOP 文档库：标准作业流程的版本化管理和训练关联。"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from config import PROJECT_DATA_DIR
from models.json_store import atomic_write_json, load_json

SOP_CATEGORIES = [
    "产品制作",
    "备料",
    "开店",
    "营业中",
    "外卖",
    "打烊",
    "卫生",
    "检查",
    "培训",
    "异常处理",
]

SOP_SOURCES = [
    "总部资料",
    "南昌经验",
    "现场流程",
    "异常复盘",
    "卫生标准",
    "老板口述",
    "其他",
]


@dataclass
class SopStep:
    """SOP 单个步骤。"""
    order: int = 0
    title: str = ""
    description: str = ""
    tools: List[str] = field(default_factory=list)
    time_estimate: str = ""
    is_critical: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SopStep":
        return cls(**{key: data.get(key, default) for key, default in {
            "order": 0, "title": "", "description": "", "tools": [],
            "time_estimate": "", "is_critical": False,
        }.items()})


@dataclass
class SopDocument:
    """一份标准作业流程文档。"""
    id: str = ""
    category: str = "产品制作"
    title: str = ""
    version: int = 1
    status: str = "草稿"
    source: str = ""
    description: str = ""
    steps: List[Dict[str, Any]] = field(default_factory=list)
    related_sku_ids: List[str] = field(default_factory=list)
    related_training_skills: List[str] = field(default_factory=list)
    last_reviewed: str = ""
    review_cycle_days: int = 90
    notes: str = ""
    created_at: float = 0.0
    updated_at: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SopDocument":
        defaults = {
            "id": "", "category": "产品制作", "title": "", "version": 1,
            "status": "草稿", "source": "", "description": "", "steps": [],
            "related_sku_ids": [], "related_training_skills": [],
            "last_reviewed": "", "review_cycle_days": 90, "notes": "",
            "created_at": 0.0, "updated_at": 0.0,
        }
        return cls(**{key: data.get(key, default) for key, default in defaults.items()})


@dataclass
class SopLibrary:
    """SOP 文档库，管理该项目的全部 SOP。"""
    project_id: str
    documents: List[Dict[str, Any]] = field(default_factory=list)
    updated_at: float = field(default_factory=time.time)

    @property
    def data_file(self) -> Path:
        return PROJECT_DATA_DIR / self.project_id / "sops.json"

    def save(self):
        self.updated_at = time.time()
        self.data_file.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_json(self.data_file, asdict(self))

    @classmethod
    def load(cls, project_id: str) -> Optional["SopLibrary"]:
        path = PROJECT_DATA_DIR / project_id / "sops.json"
        if not path.exists():
            return None
        data = load_json(path)
        return cls(**data) if data is not None else None

    @classmethod
    def create(cls, project_id: str) -> "SopLibrary":
        library = cls(project_id=project_id)
        library.save()
        return library

    def _next_id(self) -> str:
        now = int(time.time() * 1000)
        return f"sop-{now}-{len(self.documents)}"

    def add(self, doc: SopDocument) -> SopDocument:
        now = time.time()
        if not doc.id:
            doc.id = self._next_id()
        doc.created_at = now
        doc.updated_at = now
        doc.version = 1
        self.documents.append(doc.to_dict())
        self.save()
        return doc

    def get(self, doc_id: str) -> Optional[Dict[str, Any]]:
        for doc in self.documents:
            if doc.get("id") == doc_id:
                return doc
        return None

    def update(self, doc_id: str, patch: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        for i, doc in enumerate(self.documents):
            if doc.get("id") == doc_id:
                if patch.get("bump_version"):
                    patch.pop("bump_version", None)
                    patch["version"] = int(doc.get("version", 1)) + 1
                patch["updated_at"] = time.time()
                self.documents[i].update({k: v for k, v in patch.items() if v is not None})
                self.save()
                return self.documents[i]
        return None

    def delete(self, doc_id: str) -> bool:
        before = len(self.documents)
        self.documents = [d for d in self.documents if d.get("id") != doc_id]
        if len(self.documents) < before:
            self.save()
            return True
        return False

    def by_category(self, category: str) -> List[Dict[str, Any]]:
        return [d for d in self.documents if d.get("category") == category]

    def by_status(self, status: str) -> List[Dict[str, Any]]:
        return [d for d in self.documents if d.get("status") == status]

    def stale(self, days: int = 90) -> List[Dict[str, Any]]:
        """找出超过 review_cycle 未复核的 SOP。"""
        from datetime import datetime
        now = datetime.now()
        result = []
        for doc in self.documents:
            reviewed = doc.get("last_reviewed", "")
            cycle = int(doc.get("review_cycle_days", 90))
            if not reviewed:
                result.append(doc)
                continue
            try:
                last = datetime.strptime(reviewed, "%Y-%m-%d")
                if (now - last).days > cycle:
                    result.append(doc)
            except ValueError:
                result.append(doc)
        return result

    def search(self, keyword: str) -> List[Dict[str, Any]]:
        kw = keyword.lower()
        return [
            d for d in self.documents
            if kw in json.dumps(d, ensure_ascii=False).lower()
        ]

    def categories_summary(self) -> Dict[str, Any]:
        cats: Dict[str, int] = {}
        statuses: Dict[str, int] = {}
        for doc in self.documents:
            cat = doc.get("category", "其他")
            cats[cat] = cats.get(cat, 0) + 1
            st = doc.get("status", "草稿")
            statuses[st] = statuses.get(st, 0) + 1
        return {
            "total": len(self.documents),
            "by_category": cats,
            "by_status": statuses,
            "stale": len(self.stale()),
        }
