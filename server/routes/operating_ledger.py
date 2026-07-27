"""Trusted operating ledger routes for the real single-store flow."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from models.operating_ledger import OperatingLedger, today


router = APIRouter(prefix="/projects", tags=["operating-ledger"])


class FactPatch(BaseModel):
    fact_type: str | None = None
    date: str | None = None
    amount: float | None = None
    platform: str | None = None
    account_location: str | None = None
    business_owner: str | None = None
    confidence: str | None = None
    review_status: str | None = None
    title: str | None = None
    description: str | None = None
    period_start: str | None = None
    period_end: str | None = None
    metadata: dict[str, Any] | None = None


class MarkFactRequest(BaseModel):
    action: str = Field(..., description="former_owner_collected / former_owner_transfer / platform_unsettled / refund / purchase / non_operating / defer")


class CaptureFactImportRequest(BaseModel):
    file_name: str = ""
    source_type: str
    fields: list[dict[str, Any]] = Field(default_factory=list)
    structured_artifact: dict[str, Any] = Field(default_factory=dict)
    raw_text: str = ""
    evidence_image_url: str = ""


@router.get("/{project_id}/operating-ledger")
async def get_operating_ledger(project_id: str):
    ledger = OperatingLedger.load(project_id)
    return ledger.to_dict()


@router.post("/{project_id}/operating-ledger/seed")
async def seed_operating_ledger(project_id: str):
    ledger = OperatingLedger(project_id)
    ledger.seed_real_store()
    ledger.save()
    return {"success": True, "ledger": ledger.to_dict()}


@router.get("/{project_id}/business-facts")
async def list_business_facts(project_id: str, review_status: str | None = Query(None)):
    ledger = OperatingLedger.load(project_id)
    return {"facts": ledger.list_facts(review_status=review_status), "total": len(ledger.list_facts(review_status=review_status))}


@router.patch("/{project_id}/business-facts/{fact_id}")
async def update_business_fact(project_id: str, fact_id: str, patch: FactPatch):
    ledger = OperatingLedger.load(project_id)
    try:
      fact = ledger.update_fact(fact_id, patch.model_dump(exclude_unset=True))
    except KeyError as exc:
      raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"success": True, "fact": fact}


@router.post("/{project_id}/business-facts/{fact_id}/confirm")
async def confirm_business_fact(project_id: str, fact_id: str):
    ledger = OperatingLedger.load(project_id)
    try:
        result = ledger.confirm_fact(fact_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"success": True, **result}


@router.post("/{project_id}/business-facts/{fact_id}/reject")
async def reject_business_fact(project_id: str, fact_id: str):
    ledger = OperatingLedger.load(project_id)
    try:
        fact = ledger.reject_fact(fact_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"success": True, "fact": fact}


@router.post("/{project_id}/business-facts/{fact_id}/mark")
async def mark_business_fact(project_id: str, fact_id: str, req: MarkFactRequest):
    ledger = OperatingLedger.load(project_id)
    try:
        fact = ledger.mark_fact(fact_id, req.action)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True, "fact": fact}


@router.post("/{project_id}/business-facts/from-capture")
async def create_business_facts_from_capture(project_id: str, req: CaptureFactImportRequest):
    ledger = OperatingLedger.load(project_id)
    result = ledger.ingest_capture_artifact(
        source_type=req.source_type,
        fields=req.fields,
        structured_artifact=req.structured_artifact,
        file_name=req.file_name,
        raw_text=req.raw_text,
        evidence_image_url=req.evidence_image_url,
    )
    return {"success": True, **result}


@router.get("/{project_id}/money-view")
async def get_money_view(project_id: str, date: str | None = Query(None)):
    ledger = OperatingLedger.load(project_id)
    return ledger.money_view(date=date)


@router.get("/{project_id}/platform-reconciliations")
async def get_platform_reconciliations(
    project_id: str,
    start: str | None = Query(None),
    end: str | None = Query(None),
):
    """渠道对账明细；仅用于核对和资金追踪，不重复计入主营业收入。"""
    ledger = OperatingLedger.load(project_id)
    return ledger.reconciliation_view(start=start, end=end)


@router.get("/{project_id}/cash-flow")
async def get_cash_flow(
    project_id: str,
    start: str | None = Query(None),
    end: str | None = Query(None),
):
    """现金流视图；缺少现金输入时返回未知，不用 0 伪造余额。"""
    ledger = OperatingLedger.load(project_id)
    return ledger.cash_flow_view(start=start, end=end)


@router.get("/{project_id}/first-stage-inventory")
async def get_first_stage_inventory(project_id: str, date: str | None = Query(None)):
    ledger = OperatingLedger.load(project_id)
    return ledger.inventory_view(date=date)


@router.get("/{project_id}/today-operating-card")
async def get_today_operating_card(project_id: str, date: str | None = Query(None)):
    ledger = OperatingLedger.load(project_id)
    return ledger.today_card(date=date or today())


@router.get("/{project_id}/cost-question")
async def answer_cost_question(project_id: str, question: str = Query("一盒 6 粒章鱼烧成本是多少？")):
    ledger = OperatingLedger.load(project_id)
    return ledger.cost_question(question)


@router.get("/{project_id}/daily-close-check")
async def get_daily_close_check(project_id: str, date: str | None = Query(None)):
    ledger = OperatingLedger.load(project_id)
    return ledger.daily_close_check(date=date)


@router.get("/{project_id}/daily-review-check")
async def get_daily_review_check(project_id: str, date: str | None = Query(None)):
    ledger = OperatingLedger.load(project_id)
    return ledger.daily_close_check(date=date)
