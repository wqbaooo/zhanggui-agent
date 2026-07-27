#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""工时工资路由：员工档案、考勤记录、工资核算。"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from models.labor import LaborTracking, StaffMember, WorkRecord
from models.project import ProjectMemory
from server.schemas import (
    StaffCreate,
    StaffUpdate,
    WorkRecordCreate,
    WorkRecordListParams,
)

router = APIRouter(prefix="/projects", tags=["labor"])


def _tracking(project_id: str) -> LaborTracking:
    tracking = LaborTracking.load(project_id)
    if tracking is None:
        tracking = LaborTracking.create(project_id)
    return tracking


# ── 员工档案 ──

@router.get("/{project_id}/labor/staff")
async def list_staff(project_id: str):
    tracking = _tracking(project_id)
    alerts = tracking.health_cert_alerts()
    return {
        "staff": tracking.staff,
        "count": len(tracking.staff),
        "health_cert_alerts": alerts,
    }


@router.post("/{project_id}/labor/staff")
async def create_staff(project_id: str, req: StaffCreate):
    tracking = _tracking(project_id)
    member = StaffMember(
        name=req.name,
        role=req.role,
        phone=req.phone,
        health_cert_expiry=req.health_cert_expiry or "",
        skills=req.skills,
        hourly_wage=req.hourly_wage,
        monthly_base=req.monthly_base,
        pay_type=req.pay_type,
        standard_monthly_work_days=req.standard_monthly_work_days,
        overtime_multiplier=req.overtime_multiplier,
        overtime_hourly_rate=req.overtime_hourly_rate,
        hire_date=req.hire_date or "",
        status="在岗",
        notes=req.notes,
    )
    saved = tracking.add_staff(member)
    return {"success": True, "staff": saved.to_dict()}


@router.get("/{project_id}/labor/staff/{staff_id}")
async def get_staff(project_id: str, staff_id: str):
    tracking = _tracking(project_id)
    member = tracking.get_staff(staff_id)
    if member is None:
        raise HTTPException(status_code=404, detail="staff not found")
    return {"staff": member}


@router.patch("/{project_id}/labor/staff/{staff_id}")
async def update_staff(project_id: str, staff_id: str, req: StaffUpdate):
    tracking = _tracking(project_id)
    payload = req.model_dump(exclude_unset=True) if hasattr(req, "model_dump") else req.dict(exclude_unset=True)
    updated = tracking.update_staff(staff_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail="staff not found")
    return {"success": True, "staff": updated}


@router.delete("/{project_id}/labor/staff/{staff_id}")
async def delete_staff(project_id: str, staff_id: str):
    tracking = _tracking(project_id)
    if not tracking.delete_staff(staff_id):
        raise HTTPException(status_code=404, detail="staff not found")
    return {"success": True}


# ── 工时记录 ──

@router.get("/{project_id}/labor/records")
async def list_work_records(
    project_id: str,
    staff_id: Optional[str] = Query(None, description="按员工筛选"),
    date_from: str = Query("", description="起始日期 YYYY-MM-DD"),
    date_to: str = Query("", description="截止日期 YYYY-MM-DD"),
    limit: int = Query(60, ge=1, le=366),
):
    tracking = _tracking(project_id)
    records = tracking.get_work_records(
        staff_id=staff_id, date_from=date_from, date_to=date_to, limit=limit,
    )
    return {"records": records, "count": len(records)}


@router.post("/{project_id}/labor/records")
async def create_work_record(project_id: str, req: WorkRecordCreate):
    tracking = _tracking(project_id)
    if tracking.get_staff(req.staff_id) is None:
        raise HTTPException(status_code=404, detail="staff not found")
    record = WorkRecord(
        staff_id=req.staff_id,
        date=req.date,
        shift=req.shift,
        hours=req.hours,
        overtime_hours=req.overtime_hours,
        notes=req.notes,
    )
    saved = tracking.record_work(record)
    return {"success": True, "record": saved.to_dict()}


# ── 工资核算 ──

@router.get("/{project_id}/labor/wages")
async def get_wage_summary(project_id: str, year_month: str = Query(..., description="YYYY-MM 格式")):
    _validate_year_month(year_month)
    tracking = _tracking(project_id)
    try:
        summary = tracking.wage_summary(year_month)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return summary


@router.get("/{project_id}/labor/wages/{staff_id}")
async def get_staff_wage(project_id: str, staff_id: str, year_month: str = Query(..., description="YYYY-MM 格式")):
    _validate_year_month(year_month)
    tracking = _tracking(project_id)
    try:
        wage = tracking.monthly_wage(staff_id, year_month)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return wage


@router.post("/{project_id}/labor/wages/finalize")
async def finalize_wages(project_id: str, year_month: str = Query(..., description="YYYY-MM 格式")):
    """确认月工资，并按当月已有经营日均摊写入人工成本。"""
    _validate_year_month(year_month)
    tracking = _tracking(project_id)
    summary = tracking.wage_summary(year_month)
    memory = ProjectMemory.load(project_id) or ProjectMemory.create(project_id)
    entries = [
        entry for entry in memory.daily_operations
        if str(entry.get("date", "")).startswith(f"{year_month}-")
    ]
    if not entries:
        raise HTTPException(status_code=400, detail="该月没有经营记录，无法分摊人工成本")

    total_wage = float(summary["total_wage"])
    daily = round(total_wage / len(entries), 2)
    allocated = 0.0
    for index, entry in enumerate(entries):
        amount = round(total_wage - allocated, 2) if index == len(entries) - 1 else daily
        entry["labor"] = amount
        allocated += amount

    memory.profile["monthly_labor"] = round(total_wage, 2)
    memory.profile["monthly_labor_period"] = year_month
    memory.add_capture_audit_log({
        "source_type": "labor_calculation",
        "file_name": "",
        "capture_kind": "operation",
        "recognized_fields": [
            {"key": "year_month", "value": year_month},
            {"key": "total_wage", "value": round(total_wage, 2)},
            {"key": "operation_days", "value": len(entries)},
        ],
        "human_modified_fields": [],
        "review_status": "written",
        "write_target": "daily_operations.labor",
    })
    return {
        "success": True,
        **summary,
        "operation_days": len(entries),
        "daily_labor_allocated": daily,
    }


@router.get("/{project_id}/labor/efficiency")
async def get_labor_efficiency(project_id: str, revenue: float = Query(0, description="期间总营收"), orders: int = Query(0, description="期间总订单数")):
    tracking = _tracking(project_id)
    return tracking.efficiency(revenue, orders)


def _validate_year_month(year_month: str) -> None:
    from datetime import datetime
    try:
        datetime.strptime(year_month, "%Y-%m")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="year_month must use YYYY-MM format") from exc
