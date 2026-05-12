#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ProjectMemory：项目档案持久化模型。"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from config import PROJECT_DATA_DIR


@dataclass
class ProjectMemory:
    """独立于会话的项目档案，支持跨会话持久化。"""
    project_id: str
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    profile: Dict[str, Any] = field(default_factory=dict)
    candidate_sites: List[Dict[str, Any]] = field(default_factory=list)
    financial_models: List[Dict[str, Any]] = field(default_factory=list)
    field_observations: List[Dict[str, Any]] = field(default_factory=list)
    risk_register: List[Dict[str, Any]] = field(default_factory=list)
    decisions_log: List[Dict[str, Any]] = field(default_factory=list)
    artifacts: List[Dict[str, str]] = field(default_factory=list)

    @property
    def data_dir(self) -> Path:
        return PROJECT_DATA_DIR / self.project_id

    def save(self):
        """持久化到磁盘。"""
        self.updated_at = time.time()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        path = self.data_dir / "memory.json"
        path.write_text(
            json.dumps(asdict(self), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    @classmethod
    def load(cls, project_id: str) -> Optional["ProjectMemory"]:
        """从磁盘加载，不存在返回 None。"""
        path = PROJECT_DATA_DIR / project_id / "memory.json"
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return cls(**data)
        except Exception:
            return None

    @classmethod
    def create(cls, project_id: str) -> "ProjectMemory":
        """创建新项目档案。"""
        memory = cls(project_id=project_id)
        memory.save()
        return memory

    def update_profile(self, profile_dict: Dict[str, Any]):
        """更新项目画像。"""
        self.profile.update(profile_dict)
        self.save()

    def add_site(self, site_data: Dict[str, Any]):
        """添加候选铺位。"""
        site_data["added_at"] = time.time()
        self.candidate_sites.append(site_data)
        self.save()

    def add_financial_model(self, model_data: Dict[str, Any]):
        """添加财务测算版本。"""
        model_data["created_at"] = time.time()
        self.financial_models.append(model_data)
        self.save()

    def add_decision(self, decision: Dict[str, Any]):
        """记录决策。"""
        decision["timestamp"] = time.time()
        self.decisions_log.append(decision)
        self.save()
