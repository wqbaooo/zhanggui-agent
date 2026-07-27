#!/usr/bin/env python3
"""周报/月报路由：经营复盘报告的生成与查询。"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from models.labor import LaborTracking
from models.finance_ledger import FinanceLedger
from models.project import ProjectMemory
from models.reports import ReportArchive
from models.sku import SkuCatalog

router = APIRouter(prefix="/projects", tags=["reports"])


def _archive(pid: str) -> ReportArchive:
    a = ReportArchive.load(pid)
    return a if a is not None else ReportArchive.create(pid)


@router.get("/{project_id}/reports")
async def list_reports(project_id: str, report_type: Optional[str] = Query(None), limit: int = Query(12, ge=1, le=50)):
    reports = _archive(project_id).list_reports(report_type=report_type, limit=limit)
    return {"reports": reports, "count": len(reports)}


@router.get("/{project_id}/reports/{report_id}")
async def get_report(project_id: str, report_id: str):
    r = _archive(project_id).get(report_id)
    if r is None:
        raise HTTPException(status_code=404, detail="report not found")
    return {"report": r}


@router.post("/{project_id}/reports/generate")
async def generate_report(project_id: str, report_type: str = Query("weekly", description="daily、weekly 或 monthly")):
    if report_type not in ("daily", "weekly", "monthly"):
        raise HTTPException(status_code=400, detail="report_type must be daily, weekly or monthly")

    archive = _archive(project_id)
    finance = FinanceLedger.for_project(project_id)
    start, end, _, _ = archive.finance_period(report_type)
    readiness = finance.finance_overview(project_id, start, end)
    if readiness.get("profit_status") != "confirmed":
        missing_inputs = list(readiness.get("missing_inputs", []))
        if not readiness.get("sales_days"):
            missing_inputs.insert(0, "daily_sales")
        raise HTTPException(
            status_code=409,
            detail="营收/成本数据尚未完整确认，暂不发布正式利润报告；缺少：" + "、".join(missing_inputs),
        )
    report = archive.generate_from_finance(report_type, finance)
    return {"success": True, "report": report.to_dict()}
