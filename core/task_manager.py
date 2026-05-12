#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""项目管理器：任务跟踪、里程碑、进度管理。"""

import json, os, uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional

tz_cn = timezone(timedelta(hours=8))


class Task:
    def __init__(self, description: str, phase: str, priority: str = "medium",
                 deadline_days: int = 7, depends_on: List[str] = None):
        self.id = f"TASK_{uuid.uuid4().hex[:6].upper()}"
        self.description = description
        self.phase = phase
        self.priority = priority
        self.status = "pending"
        self.created = datetime.now(tz_cn).isoformat()
        self.deadline = (datetime.now(tz_cn) + timedelta(days=deadline_days)).isoformat()
        self.depends_on = depends_on or []
        self.completed_at = None

    def to_dict(self):
        return {
            "id": self.id, "description": self.description, "phase": self.phase,
            "priority": self.priority, "status": self.status, "created": self.created,
            "deadline": self.deadline, "depends_on": self.depends_on,
            "completed_at": self.completed_at,
        }


class Milestone:
    def __init__(self, name: str, phase: str, completion_criteria: List[str]):
        self.name = name
        self.phase = phase
        self.completion_criteria = completion_criteria
        self.achieved = False
        self.achieved_at = None

    def to_dict(self):
        return {
            "name": self.name, "phase": self.phase,
            "completion_criteria": self.completion_criteria,
            "achieved": self.achieved, "achieved_at": self.achieved_at,
        }


class ProjectMemory:
    def __init__(self, project_id: str = None):
        self.project_id = project_id or f"PROJ_{uuid.uuid4().hex[:8].upper()}"
        self.tasks: List[Task] = []
        self.milestones: List[Milestone] = []
        self.profile: Dict = {}
        self.current_phase = "想法验证"
        self.created = datetime.now(tz_cn).isoformat()
        self._storage_dir = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "project_archives"
        )
        self._load()

    def _file_path(self):
        return os.path.join(self._storage_dir, f"{self.project_id}.json")

    def _load(self):
        fp = self._file_path()
        if os.path.exists(fp):
            try:
                with open(fp) as f:
                    data = json.load(f)
                self.profile = data.get("profile", {})
                self.current_phase = data.get("current_phase", "想法验证")
                self.tasks = []
                for td in data.get("tasks", []):
                    t = Task(td["description"], td.get("phase", ""), td.get("priority", "medium"))
                    t.id = td.get("id", t.id)
                    t.status = td.get("status", "pending")
                    t.created = td.get("created", t.created)
                    t.deadline = td.get("deadline", t.deadline)
                    t.depends_on = td.get("depends_on", [])
                    t.completed_at = td.get("completed_at")
                    self.tasks.append(t)
                self.milestones = []
                for md in data.get("milestones", []):
                    m = Milestone(md["name"], md.get("phase", ""), md.get("completion_criteria", []))
                    m.achieved = md.get("achieved", False)
                    m.achieved_at = md.get("achieved_at")
                    self.milestones.append(m)
            except Exception:
                pass

    def save(self):
        os.makedirs(self._storage_dir, exist_ok=True)
        with open(self._file_path(), "w") as f:
            json.dump({
                "project_id": self.project_id,
                "profile": self.profile,
                "current_phase": self.current_phase,
                "created": self.created,
                "tasks": [t.to_dict() for t in self.tasks],
                "milestones": [m.to_dict() for m in self.milestones],
            }, f, ensure_ascii=False, indent=2)

    def add_task(self, description: str, phase: str = "", priority: str = "medium",
                 deadline_days: int = 7) -> Task:
        t = Task(description, phase or self.current_phase, priority, deadline_days)
        self.tasks.append(t)
        self.save()
        return t

    def update_task(self, task_id: str, status: str = None, description: str = None):
        for t in self.tasks:
            if t.id == task_id:
                if status:
                    t.status = status
                    if status == "completed":
                        t.completed_at = datetime.now(tz_cn).isoformat()
                if description:
                    t.description = description
                self.save()
                return t
        return None

    def get_tasks(self, phase: str = None, status: str = None) -> List[Task]:
        result = self.tasks
        if phase:
            result = [t for t in result if t.phase == phase]
        if status:
            result = [t for t in result if t.status == status]
        return sorted(result, key=lambda t: t.priority_rank(), reverse=True)

    def priority_rank(self, task):
        return {"high": 3, "medium": 2, "low": 1}.get(task.priority, 1)

    def stats(self) -> Dict:
        total = len(self.tasks)
        completed = sum(1 for t in self.tasks if t.status == "completed")
        in_progress = sum(1 for t in self.tasks if t.status == "in_progress")
        pending = sum(1 for t in self.tasks if t.status == "pending")
        return {
            "total": total, "completed": completed, "in_progress": in_progress,
            "pending": pending, "completion_pct": round(completed * 100 / total, 1) if total else 0,
            "current_phase": self.current_phase,
        }

    def add_default_milestones(self, phases: List[str]):
        default_milestones = {
            "想法验证": ["完成品类分析", "完成财务可行性测算", "完成人格评估", "Go/No-Go决策"],
            "选址筹备": ["完成商圈扫描", "完成竞品调研", "候选铺位≥3个", "选址决策"],
            "开店执行": ["证照办理完成", "装修验收", "设备采购到位", "人员到位", "供应链就绪"],
            "运营增长": ["开业活动执行", "日成本监控建立", "首月盈亏分析", "会员体系上线"],
        }
        for phase in phases:
            if phase not in [m.name for m in self.milestones]:
                criteria = default_milestones.get(phase, ["完成本阶段所有任务"])
                m = Milestone(phase, phase, criteria)
                self.milestones.append(m)
        self.save()

    def check_milestone(self, phase: str) -> bool:
        for m in self.milestones:
            if m.name == phase and not m.achieved:
                phase_tasks = self.get_tasks(phase=phase)
                if all(t.status == "completed" for t in phase_tasks):
                    m.achieved = True
                    m.achieved_at = datetime.now(tz_cn).isoformat()
                    self.save()
                    return True
        return False
