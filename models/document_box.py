#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""门店资料箱：合同、证照、供应商协议、检查报告等文档归档模型。"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from config import PROJECT_DATA_DIR
from models.json_store import atomic_write_json, load_json

DOCUMENT_TYPES = [
    "租赁合同",
    "加盟合同",
    "供应商协议",
    "营业执照",
    "食品经营许可",
    "健康证",
    "卫生检查报告",
    "消防检查",
    "转让协议",
    "设备采购合同",
    "装修合同",
    "劳动合同",
    "保险单据",
    "水电账单",
    "税务凭证",
    "总部通知",
    "其他",
]


@dataclass
class StoreDocument:
    """单份门店资料档案。"""
    id: str = ""
    title: str = ""
    doc_type: str = "其他"
    tags: List[str] = field(default_factory=list)
    source: str = ""
    file_ref: str = ""
    status: str = "原始"
    parties: List[str] = field(default_factory=list)
    sign_date: str = ""
    expiry_date: str = ""
    key_terms: List[str] = field(default_factory=list)
    extracted_fields: Dict[str, Any] = field(default_factory=dict)
    risk_flags: List[str] = field(default_factory=list)
    related_to: Dict[str, str] = field(default_factory=dict)
    notes: str = ""
    created_at: float = 0.0
    updated_at: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StoreDocument":
        return cls(**{key: data.get(key, default) for key, default in {
            "id": "", "title": "", "doc_type": "其他", "tags": [], "source": "",
            "file_ref": "", "status": "原始", "parties": [], "sign_date": "",
            "expiry_date": "", "key_terms": [], "extracted_fields": {},
            "risk_flags": [], "related_to": {}, "notes": "", "created_at": 0.0,
            "updated_at": 0.0,
        }.items()})


@dataclass
class DocumentBox:
    """门店资料箱，管理该项目的全部文档档案。"""
    project_id: str
    documents: List[Dict[str, Any]] = field(default_factory=list)
    updated_at: float = field(default_factory=time.time)

    @property
    def data_file(self) -> Path:
        return PROJECT_DATA_DIR / self.project_id / "documents.json"

    def save(self):
        self.updated_at = time.time()
        self.data_file.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_json(self.data_file, asdict(self))

    @classmethod
    def load(cls, project_id: str) -> Optional["DocumentBox"]:
        path = PROJECT_DATA_DIR / project_id / "documents.json"
        if not path.exists():
            return None
        data = load_json(path)
        return cls(**data) if data is not None else None

    @classmethod
    def create(cls, project_id: str) -> "DocumentBox":
        box = cls(project_id=project_id)
        box.save()
        return box

    def _next_id(self) -> str:
        now = int(time.time() * 1000)
        count = len(self.documents)
        return f"doc-{now}-{count}"

    def add(self, doc: StoreDocument) -> StoreDocument:
        now = time.time()
        if not doc.id:
            doc.id = self._next_id()
        doc.created_at = now
        doc.updated_at = now
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

    def by_type(self, doc_type: str) -> List[Dict[str, Any]]:
        return [d for d in self.documents if d.get("doc_type") == doc_type]

    def by_entity(self, entity_type: str, entity_id: str) -> List[Dict[str, Any]]:
        return [
            d for d in self.documents
            if d.get("related_to", {}).get("entity_type") == entity_type
            and d.get("related_to", {}).get("entity_id") == entity_id
        ]

    def expiring_soon(self, days: int = 30) -> List[Dict[str, Any]]:
        now = time.time()
        cutoff = now + days * 86400
        result = []
        for doc in self.documents:
            expiry = doc.get("expiry_date", "")
            if expiry:
                try:
                    from datetime import datetime
                    expiry_ts = datetime.strptime(expiry, "%Y-%m-%d").timestamp()
                    if now <= expiry_ts <= cutoff:
                        result.append(doc)
                except ValueError:
                    pass
        return result

    def search(self, keyword: str) -> List[Dict[str, Any]]:
        kw = keyword.lower()
        result = []
        for doc in self.documents:
            text = json.dumps(doc, ensure_ascii=False).lower()
            if kw in text:
                result.append(doc)
        return result

    def summary(self) -> Dict[str, Any]:
        types: Dict[str, int] = {}
        for doc in self.documents:
            t = doc.get("doc_type", "其他")
            types[t] = types.get(t, 0) + 1
        return {
            "total": len(self.documents),
            "by_type": types,
            "expiring_soon": len(self.expiring_soon()),
        }
