#!/usr/bin/env python3
"""Alpha Testing — 观察层。记录使用 friction，自动生成报告。"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Literal
from enum import Enum

FEEDBACK_DIR = Path(__file__).resolve().parent.parent / "project_data" / "alpha"


class FeedbackType(str, Enum):
    UX = "ux"
    WORKFLOW = "workflow"
    COGNITION = "cognition"
    BLOCKER = "blocker"
    MISSING = "missing_feature"
    FAKE = "fake_requirement"
    HIGH_VALUE = "high_value"
    LOW_VALUE = "low_value"


class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class AlphaFeedback:
    """一条 Alpha 观察记录"""
    id: str = ""
    type: FeedbackType = FeedbackType.UX
    severity: Severity = Severity.MEDIUM
    context: str = ""       # 在哪里遇到的
    notes: str = ""         # 具体描述
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()
        if not self.id:
            self.id = f"fb_{datetime.now().strftime('%H%M%S')}"

    def to_dict(self):
        return asdict(self)


class AlphaStore:
    """Alpha 反馈存储"""

    def __init__(self, case_id: str = "default"):
        self.case_id = case_id
        self.dir = FEEDBACK_DIR / case_id
        self.dir.mkdir(parents=True, exist_ok=True)
        self.file = self.dir / "feedback.json"

    def _load(self) -> List[dict]:
        if not self.file.exists():
            return []
        try:
            return json.loads(self.file.read_text(encoding="utf-8"))
        except Exception:
            return []

    def _save(self, items: List[dict]):
        self.file.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")

    def record(self, fb: AlphaFeedback) -> AlphaFeedback:
        items = self._load()
        items.append(fb.to_dict())
        self._save(items)
        return fb

    def list_all(self) -> List[AlphaFeedback]:
        items = self._load()
        result = []
        for d in items:
            try:
                fb = AlphaFeedback(
                    id=d.get("id", ""),
                    type=FeedbackType(d.get("type", "ux")),
                    severity=Severity(d.get("severity", "medium")),
                    context=d.get("context", ""),
                    notes=d.get("notes", ""),
                    timestamp=d.get("timestamp", ""),
                )
                result.append(fb)
            except Exception:
                continue
        return result

    def clear(self):
        self._save([])


class AlphaReport:
    """自动生成 Alpha 测试报告"""

    def __init__(self, store: AlphaStore):
        self.store = store

    def generate(self) -> dict:
        feedbacks = self.store.list_all()
        if not feedbacks:
            return {"status": "no_data", "message": "还没有观察记录。开始使用后记录 friction。"}

        by_type: dict[str, list] = {}
        by_severity: dict[str, int] = {"low": 0, "medium": 0, "high": 0}
        for fb in feedbacks:
            t = fb.type.value
            if t not in by_type:
                by_type[t] = []
            by_type[t].append(fb)
            by_severity[fb.severity.value] += 1

        return {
            "total": len(feedbacks),
            "by_severity": by_severity,
            "by_type": {k: len(v) for k, v in by_type.items()},
            "top_friction": self._top_friction(feedbacks),
            "sections": {
                "体验问题": [fb.notes for fb in by_type.get("ux", [])],
                "认知负担": [fb.notes for fb in by_type.get("cognition", [])],
                "假流程": [fb.notes for fb in by_type.get("fake_requirement", [])],
                "缺失能力": [fb.notes for fb in by_type.get("missing_feature", [])],
                "高价值功能": [fb.notes for fb in by_type.get("high_value", [])],
                "低价值功能": [fb.notes for fb in by_type.get("low_value", [])],
                "录入负担": [fb.notes for fb in by_type.get("workflow", []) if "录入" in fb.notes or "负担" in fb.notes or "懒得" in fb.notes],
            },
            "generated_at": datetime.now().isoformat(),
        }

    def _top_friction(self, feedbacks: List[AlphaFeedback]) -> list:
        high = [fb for fb in feedbacks if fb.severity == Severity.HIGH]
        high.sort(key=lambda f: f.timestamp, reverse=True)
        return [{"type": fb.type.value, "notes": fb.notes, "context": fb.context} for fb in high[:10]]
