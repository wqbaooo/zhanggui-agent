#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""工时工资模型：员工档案、考勤记录、工资计算。"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from config import PROJECT_DATA_DIR
from models.json_store import atomic_write_json, load_json


@dataclass
class StaffMember:
    """员工档案。"""
    id: str = ""
    name: str = ""
    role: str = "员工"
    phone: str = ""
    health_cert_expiry: str = ""
    skills: List[str] = field(default_factory=list)
    hourly_wage: float = 0.0
    monthly_base: float = 0.0
    pay_type: str = "auto"
    standard_monthly_work_days: int = 26
    overtime_multiplier: float = 1.5
    hire_date: str = ""
    status: str = "在岗"
    notes: str = ""
    created_at: float = 0.0
    updated_at: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StaffMember":
        defaults = {
            "id": "", "name": "", "role": "员工", "phone": "",
            "health_cert_expiry": "", "skills": [], "hourly_wage": 0.0,
            "monthly_base": 0.0, "pay_type": "auto",
            "standard_monthly_work_days": 26, "overtime_multiplier": 1.5,
            "hire_date": "", "status": "在岗",
            "notes": "", "created_at": 0.0, "updated_at": 0.0,
        }
        return cls(**{key: data.get(key, default) for key, default in defaults.items()})


@dataclass
class WorkRecord:
    """单日工时记录。"""
    id: str = ""
    staff_id: str = ""
    date: str = ""
    shift: str = "全天"
    hours: float = 0.0
    overtime_hours: float = 0.0
    notes: str = ""
    created_at: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorkRecord":
        defaults = {
            "id": "", "staff_id": "", "date": "", "shift": "全天",
            "hours": 0.0, "overtime_hours": 0.0, "notes": "",
            "created_at": 0.0,
        }
        return cls(**{key: data.get(key, default) for key, default in defaults.items()})


@dataclass
class LaborTracking:
    """工时工资管理：员工 + 考勤 + 工资核算。"""
    project_id: str
    staff: List[Dict[str, Any]] = field(default_factory=list)
    work_records: List[Dict[str, Any]] = field(default_factory=list)
    updated_at: float = field(default_factory=time.time)

    @property
    def data_file(self) -> Path:
        return PROJECT_DATA_DIR / self.project_id / "labor.json"

    def save(self):
        self.updated_at = time.time()
        self.data_file.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_json(self.data_file, asdict(self))

    @classmethod
    def load(cls, project_id: str) -> Optional["LaborTracking"]:
        path = PROJECT_DATA_DIR / project_id / "labor.json"
        if not path.exists():
            return None
        data = load_json(path)
        return cls(**data) if data is not None else None

    @classmethod
    def create(cls, project_id: str) -> "LaborTracking":
        tracking = cls(project_id=project_id)
        tracking.save()
        return tracking

    def _next_id(self, prefix: str) -> str:
        now = int(time.time() * 1000)
        items = self.staff if prefix == "staff" else self.work_records
        return f"{prefix}-{now}-{len(items)}"

    def add_staff(self, member: StaffMember) -> StaffMember:
        now = time.time()
        if not member.id:
            member.id = self._next_id("staff")
        member.created_at = now
        member.updated_at = now
        self.staff.append(member.to_dict())
        self.save()
        return member

    def get_staff(self, staff_id: str) -> Optional[Dict[str, Any]]:
        for s in self.staff:
            if s.get("id") == staff_id:
                return s
        return None

    def update_staff(self, staff_id: str, patch: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        for i, s in enumerate(self.staff):
            if s.get("id") == staff_id:
                patch["updated_at"] = time.time()
                self.staff[i].update({k: v for k, v in patch.items() if v is not None})
                self.save()
                return self.staff[i]
        return None

    def delete_staff(self, staff_id: str) -> bool:
        before = len(self.staff)
        self.staff = [s for s in self.staff if s.get("id") != staff_id]
        if len(self.staff) < before:
            self.save()
            return True
        return False

    def record_work(self, record: WorkRecord) -> WorkRecord:
        now = time.time()
        if not record.id:
            record.id = self._next_id("work")
        record.created_at = now

        # 同人同天覆盖旧记录
        self.work_records = [
            r for r in self.work_records
            if not (r.get("staff_id") == record.staff_id and r.get("date") == record.date)
        ]
        self.work_records.append(record.to_dict())
        self.save()
        return record

    def get_work_records(self, staff_id: Optional[str] = None, date_from: str = "", date_to: str = "", limit: int = 60) -> List[Dict[str, Any]]:
        records = self.work_records
        if staff_id:
            records = [r for r in records if r.get("staff_id") == staff_id]
        if date_from:
            records = [r for r in records if r.get("date", "") >= date_from]
        if date_to:
            records = [r for r in records if r.get("date", "") <= date_to]
        records = sorted(records, key=lambda r: r.get("date", ""), reverse=True)
        return records[:limit]

    def monthly_wage(self, staff_id: str, year_month: str) -> Dict[str, Any]:
        """计算某员工某月工资。"""
        member = self.get_staff(staff_id)
        if not member:
            raise KeyError(f"staff {staff_id} not found")

        records = self.get_work_records(
            staff_id=staff_id,
            date_from=f"{year_month}-01",
            date_to=f"{year_month}-31",
            limit=366,
        )

        total_hours = sum(float(r.get("hours", 0)) for r in records)
        total_overtime = sum(float(r.get("overtime_hours", 0)) for r in records)
        hourly_wage = float(member.get("hourly_wage", 0))
        monthly_base = float(member.get("monthly_base", 0))
        pay_type = member.get("pay_type", "auto")
        if pay_type == "auto":
            pay_type = "monthly" if monthly_base > 0 else "hourly"
        standard_days = max(int(member.get("standard_monthly_work_days", 26) or 26), 1)
        overtime_multiplier = max(float(member.get("overtime_multiplier", 1.5) or 1.5), 1)
        work_days = len(records)

        attendance_ratio = min(work_days / standard_days, 1.0)
        effective_hourly_wage = hourly_wage
        if effective_hourly_wage <= 0 and monthly_base > 0:
            effective_hourly_wage = monthly_base / (standard_days * 8)

        regular_pay = 0.0
        base_pay = 0.0
        cost_basis = "attendance"
        if pay_type == "owner":
            base_pay = monthly_base
            attendance_ratio = 1.0
            cost_basis = "owner_opportunity_cost"
        elif pay_type == "monthly":
            base_pay = monthly_base * attendance_ratio
        else:
            regular_pay = hourly_wage * total_hours

        overtime_pay = total_overtime * effective_hourly_wage * overtime_multiplier
        total_wage = base_pay + regular_pay + overtime_pay

        return {
            "staff_id": staff_id,
            "staff_name": member.get("name"),
            "year_month": year_month,
            "work_days": work_days,
            "total_hours": round(total_hours, 1),
            "total_overtime": round(total_overtime, 1),
            "hourly_wage": round(hourly_wage, 2),
            "monthly_base": round(monthly_base, 2),
            "pay_type": pay_type,
            "standard_monthly_work_days": standard_days,
            "attendance_ratio": round(attendance_ratio, 4),
            "regular_pay": round(regular_pay, 2),
            "base_pay": round(base_pay, 2),
            "overtime_pay": round(overtime_pay, 2),
            "cost_basis": cost_basis,
            "total_wage": round(total_wage, 2),
            "records": records,
        }

    def wage_summary(self, year_month: str) -> Dict[str, Any]:
        """整店月度工资汇总。"""
        staff_wages = []
        total = 0.0
        for s in self.staff:
            if s.get("status") != "在岗":
                continue
            try:
                wage = self.monthly_wage(s["id"], year_month)
                staff_wages.append(wage)
                total += wage["total_wage"]
            except KeyError:
                pass
        return {
            "year_month": year_month,
            "staff_count": len(staff_wages),
            "total_wage": round(total, 2),
            "breakdown": staff_wages,
        }

    def efficiency(self, total_revenue: float, total_orders: int) -> Dict[str, Any]:
        """人工效率指标：人效、单均人工、人工率。"""
        staff_count = sum(1 for s in self.staff if s.get("status") == "在岗")
        if staff_count == 0:
            return {"staff_count": 0, "revenue_per_staff": 0, "labor_per_order": 0, "labor_cost_rate": 0}
        revenue_per_staff = round(total_revenue / staff_count, 2)
        labor_per_order = round(
            sum(float(s.get("monthly_base", 0) or s.get("hourly_wage", 0) * 8 * 26)
                for s in self.staff if s.get("status") == "在岗")
            / max(total_orders, 1), 2
        )
        total_labor = sum(
            float(s.get("monthly_base", 0) or s.get("hourly_wage", 0) * 8 * 26)
            for s in self.staff if s.get("status") == "在岗"
        )
        labor_cost_rate = round(total_labor / max(total_revenue, 1), 4)
        return {
            "staff_count": staff_count,
            "revenue_per_staff": revenue_per_staff,
            "labor_per_order": labor_per_order,
            "labor_cost_rate": labor_cost_rate,
            "total_labor_estimate": round(total_labor, 2),
        }

    def health_cert_alerts(self, days: int = 30) -> List[Dict[str, Any]]:
        """健康证即将到期提醒。"""
        from datetime import datetime
        today = datetime.now()
        cutoff = today.timestamp() + days * 86400
        alerts = []
        for s in self.staff:
            expiry = s.get("health_cert_expiry", "")
            if not expiry:
                continue
            try:
                expiry_ts = datetime.strptime(expiry, "%Y-%m-%d").timestamp()
                if today.timestamp() <= expiry_ts <= cutoff:
                    remaining = int((expiry_ts - today.timestamp()) / 86400)
                    alerts.append({
                        "staff_id": s.get("id"),
                        "name": s.get("name"),
                        "expiry_date": expiry,
                        "days_remaining": max(0, remaining),
                    })
            except ValueError:
                pass
        return sorted(alerts, key=lambda a: a["days_remaining"])
