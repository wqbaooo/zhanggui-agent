#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""财务测算路由 — POST /api/finance。

⚠️ 已废弃：此端点为筹备期口径（投资回本测算），与当前单店经营 Agent 口径冲突。
当前产品定位为"AI 单店经营 Agent"（参见 AGENTS.md），不应再使用此端点。
保留路由仅为向后兼容，新功能请使用 /api/analyze 或 /api/reports 端点。
"""

from __future__ import annotations

import hashlib
import logging
import mimetypes
import threading
from datetime import datetime, timedelta
from io import BytesIO
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

import config
from core.finance_intake import parse_finance_file
from core.finance_text_intake import parse_finance_text
from core.finance_execution import FinanceExecutionService
from core.finance_categories import finance_category_catalog, find_finance_category
from core.finance_agent import answer_finance_question
from core.platform_report_intake import parse_platform_report
from core.xlsx_export import FinanceSheet, Formula, build_finance_workbook
from models.finance_ledger import FinanceLedger, FinanceMigrationError, money_to_minor
from models.store_facts import StoreFactBook


def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")

logger = logging.getLogger(__name__)

router = APIRouter(tags=["finance"])

_ledger_cache: dict[str, FinanceLedger] = {}
_ledger_cache_lock = threading.Lock()


def _ledger(project_id: str) -> FinanceLedger:
    """Initialize one ledger per database path, then reuse its lightweight handle.

    The finance page loads several read endpoints in parallel. Re-running schema
    checks, workflow synchronization and legacy migration in every request makes
    otherwise read-only page loads contend for SQLite writes during startup.
    """
    cache_key = str((config.PROJECT_DATA_DIR / project_id / "finance.db").resolve())
    cached = _ledger_cache.get(cache_key)
    if cached is not None:
        return cached
    with _ledger_cache_lock:
        cached = _ledger_cache.get(cache_key)
        if cached is None:
            cached = FinanceLedger.for_project(project_id)
            _ledger_cache[cache_key] = cached
        return cached


class ExpenseRequest(BaseModel):
    date: str = Field(default_factory=_today)
    category_code: str
    amount: float = Field(..., gt=0)
    reference: str
    paid_from: Optional[str] = Field(None, pattern="^(1001|1002)$")
    description: str = ""


class DailyCloseRequest(BaseModel):
    counted_cash: Optional[float] = Field(None, ge=0)
    reserve_cash: float = Field(500, ge=0)
    merchant_net_confirmed: bool = False
    fund_locations_reviewed: bool = False
    outflows_reviewed: bool = False
    food_cost: Optional[float] = Field(None, ge=0)
    packaging_cost: Optional[float] = Field(None, ge=0)
    overtime_hours: Optional[float] = Field(None, ge=0, le=24)
    rent: Optional[float] = Field(None, ge=0)
    utility: Optional[float] = Field(None, ge=0)
    other_cost: Optional[float] = Field(None, ge=0)


class JournalEntryLine(BaseModel):
    account_code: str = Field(..., pattern="^\\d{4}$")
    debit_minor: int = Field(0, ge=0)
    credit_minor: int = Field(0, ge=0)


class JournalEntryRequest(BaseModel):
    entry_date: str = Field(default_factory=_today)
    description: str = ""
    lines: list[JournalEntryLine]


class CapitalEventRequest(BaseModel):
    date: str = Field(default_factory=_today)
    event_type: str = Field(..., pattern="^(owner_investment|owner_draw|loan_in|loan_repayment|equipment_purchase|deposit_payment)$")
    amount: float = Field(..., gt=0)
    reference: str
    money_account: str = Field("1002", pattern="^(1001|1002)$")
    description: str = ""


class FinancialTargetRequest(BaseModel):
    target_type: str = Field(..., pattern="^(monthly_profit|minimum_cash|revenue)$")
    period_start: str
    period_end: str
    amount: float = Field(..., ge=0)


class ReopenDailyCloseRequest(BaseModel):
    reason: str = Field(..., min_length=2)


class SettlementReceiptRequest(BaseModel):
    date: str = Field(default_factory=_today)
    amount: float = Field(..., gt=0)
    reference: str = Field(..., min_length=2)
    source: str = Field(..., pattern="^(platform|former_owner)$")


class MerchantNetSaleRequest(BaseModel):
    business_date: str = Field(default_factory=_today)
    channel: str = Field(..., min_length=1)
    amount: float = Field(..., ge=0)
    reference_gross: float | None = Field(None, ge=0)
    source_basis: str = Field(..., min_length=2)
    evidence_status: str = Field(..., pattern="^(confirmed|keruyun_only|manual|missing|permission_blocked)$")
    settlement_state: str = Field(..., pattern="^(merchant_net_confirmed|wallet_credited|bound_bank_received|former_owner_received|former_owner_pending_transfer|store_account_received|unknown|disputed)$")
    current_fund_account_id: str | None = None
    evidence_reference: str | None = None
    notes: str | None = None


class DailyRevenueItemRequest(BaseModel):
    channel: str = Field(..., min_length=1)
    status: str = Field(..., pattern="^(recorded|confirmed_zero|not_available)$")
    amount: float | None = Field(None, ge=0)
    notes: str | None = None


class DailyRevenueBatchRequest(BaseModel):
    items: list[DailyRevenueItemRequest] = Field(..., min_length=1, max_length=7)


class FundAccountRequest(BaseModel):
    account_key: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    account_kind: str = Field(..., pattern="^(cash|bank|platform_wallet|payment_wallet|clearing)$")
    owner_kind: str = Field(..., pattern="^(store|owner|former_owner|platform|unknown)$")
    is_store_controlled: bool = False
    institution: str | None = None
    masked_number: str | None = None
    opening_balance: float = 0
    effective_from: str | None = None
    effective_to: str | None = None
    status: str = Field("active", pattern="^(active|planned|retired|unknown)$")


class FundMovementRequest(BaseModel):
    occurred_on: str = Field(default_factory=_today)
    amount: float = Field(..., gt=0)
    movement_type: str = Field(..., min_length=2)
    from_fund_account_id: str | None = None
    to_fund_account_id: str | None = None
    business_scope: str = Field("store", pattern="^(store|personal|mixed|unknown)$")
    purpose: str = Field(..., min_length=1)
    counterparty: str | None = None
    evidence_reference: str | None = None
    status: str = Field("confirmed", pattern="^(expected|confirmed|reconciled|void)$")
    reference: str = Field(..., min_length=2)
    notes: str | None = None


class DebtRequest(BaseModel):
    debt_key: str = Field(..., min_length=1)
    lender: str = Field(..., min_length=1)
    principal: float = Field(..., gt=0)
    received_on: str
    due_on: str | None = None
    annual_rate_decimal: str | None = None
    status: str = Field("active", pattern="^(active|settled|disputed|unknown)$")
    notes: str | None = None


class EvidenceVoucherRequest(BaseModel):
    voucher_key: str = Field(..., min_length=1)
    business_date: str | None = None
    evidence_type: str = Field(..., min_length=2)
    channel: str | None = None
    amount: float | None = Field(None, ge=0)
    source_sheet: str | None = None
    source_cell: str | None = None
    original_filename: str = Field(..., min_length=1)
    original_path: str = Field(..., min_length=1)
    sha256: str = Field(..., min_length=6)
    status: str = Field(..., pattern="^(confirmed|pending|permission_blocked|unmatched|duplicate)$")
    notes: str | None = None


class DebtAllocationRequest(BaseModel):
    allocation_key: str = Field(..., min_length=1)
    purpose: str = Field(..., min_length=1)
    amount: float = Field(..., gt=0)
    classification: str = Field(..., min_length=2)
    evidence_reference: str | None = None
    notes: str | None = None


class BookkeepingRecordRequest(BaseModel):
    transaction_date: str = Field(default_factory=_today)
    transaction_time: str | None = None
    direction: str = Field(..., pattern="^(inflow|outflow|transfer)$")
    amount: float = Field(..., gt=0)
    transaction_kind: str = Field(..., min_length=2)
    business_scope: str = Field(..., pattern="^(store|personal|mixed|unknown)$")
    category_code: str | None = Field(None, pattern="^\\d{4}$")
    category_name: str = Field(..., min_length=1)
    business_category_key: str | None = None
    account_key: str | None = None
    counter_account_key: str | None = None
    counterparty: str | None = None
    summary: str | None = None
    source_reference: str = Field(..., min_length=2)
    voucher_id: str | None = None


class BookkeepingReviewRequest(BaseModel):
    transaction_kind: str = Field(..., min_length=2)
    business_scope: str = Field(..., pattern="^(store|personal|mixed|unknown)$")
    category_code: str | None = Field(None, pattern="^\\d{4}$")
    category_name: str = Field(..., min_length=1)
    business_category_key: str | None = None
    account_key: str | None = None
    counter_account_key: str | None = None
    counterparty: str | None = None
    summary: str | None = None


class BookkeepingCorrectionRequest(BaseModel):
    business_category_key: str = Field(..., min_length=2)
    reason: str = Field(..., min_length=4)
    corrected_by: str = Field("owner", min_length=2)
    correction_key: str = Field(..., min_length=4)


class CashPlanItemRequest(BaseModel):
    due_date: str
    flow_type: str = Field(..., pattern="^(expected_inflow|required_outflow)$")
    amount: float = Field(..., gt=0)
    category: str = Field(..., min_length=1)
    counterparty: str | None = None
    priority: str = Field(..., pattern="^(must_pay|expected|optional)$")
    source_reference: str = Field(..., min_length=2)
    notes: str | None = None


class ReconciliationMatchRequest(BaseModel):
    target_type: str = Field(..., pattern="^(merchant_net_sale|fund_movement)$")
    target_id: str = Field(..., min_length=2)
    matched_amount: float = Field(..., gt=0)
    notes: str | None = None


class FinanceExecutionPreviewRequest(BaseModel):
    event_type: str = Field(..., min_length=2)
    transaction_date: str
    amount: float | None = Field(None, gt=0)
    amount_minor: int | None = Field(None, gt=0)
    account_key: str | None = None
    current_account_key: str | None = None
    channel: str | None = None
    settlement_state: str | None = None
    category_code: str | None = None
    category_name: str | None = None
    counterparty: str | None = None
    source_basis: str | None = None
    source_reference: str = Field(..., min_length=2)
    evidence_reference: str | None = None
    business_period_start: str | None = None
    business_period_end: str | None = None
    platforms: list[str] | None = None
    notes: str | None = None


class FinanceExecutionConfirmRequest(BaseModel):
    confirmed: bool
    confirmed_by: str = Field("owner", min_length=1)


class FinanceTextParseRequest(BaseModel):
    text: str = Field(..., min_length=2, max_length=1000)


class PlatformCollectionBindingRequest(BaseModel):
    platform: str = Field(..., min_length=1)
    collector_account_key: str = Field(..., min_length=1)
    destination_account_key: str | None = None
    collector_owner_kind: str = Field(
        ..., pattern="^(store|owner|former_owner|platform|unknown)$"
    )
    settlement_rule: str | None = None
    settlement_delay_days: int | None = Field(None, ge=0, le=60)
    settlement_day_basis: str | None = Field(None, pattern="^(calendar_day|working_day)$")
    settlement_rule_status: str = Field("unknown", pattern="^(confirmed|unknown)$")
    settlement_rule_source: str | None = None
    settlement_delay_target: str = Field("bound_bank", pattern="^(bound_bank|platform_wallet)$")
    withdrawal_mode: str = Field("automatic", pattern="^(automatic|manual)$")
    effective_from: str
    effective_to: str | None = None
    status: str = Field("active", pattern="^(active|planned|retired|unknown)$")
    notes: str | None = None


class PlatformBoundCardTransferRequest(BaseModel):
    transfer_date: str = Field(default_factory=_today)
    amount: float = Field(..., gt=0)
    arrival_period_start: str
    arrival_period_end: str
    source_reference: str = Field(..., min_length=2)
    evidence_reference: str | None = None


INTAKE_RECORD_TYPES: dict[str, dict[str, str | None]] = {
    "platform_settlement": {"direction": "inflow", "kind": "platform_settlement", "scope": "store", "code": None, "name": "平台结算到账"},
    "former_owner_transfer": {"direction": "inflow", "kind": "former_owner_transfer", "scope": "store", "code": "1013", "name": "前老板转回代收款"},
    "inventory_purchase": {"direction": "outflow", "kind": "inventory_purchase", "scope": "store", "code": "1401", "name": "原材料库存"},
    "operating_expense": {"direction": "outflow", "kind": "operating_expense", "scope": "store", "code": "6005", "name": "店铺经营支出"},
    "personal_spending": {"direction": "outflow", "kind": "personal_spending", "scope": "personal", "code": None, "name": "个人消费"},
    "owner_investment": {"direction": "inflow", "kind": "owner_investment", "scope": "store", "code": "3001", "name": "老板投入"},
    "owner_draw": {"direction": "outflow", "kind": "owner_draw", "scope": "store", "code": "3002", "name": "老板取用"},
    "loan_in": {"direction": "inflow", "kind": "loan_in", "scope": "store", "code": "2003", "name": "借款到账"},
    "loan_repayment": {"direction": "outflow", "kind": "loan_repayment", "scope": "store", "code": "2003", "name": "偿还借款本金"},
}


async def _save_finance_intake_voucher(
    project_id: str,
    ledger: FinanceLedger,
    *,
    file: UploadFile | None,
    business_date: str,
    amount_minor: int,
    fact_type: str,
    channel: str | None,
    notes: str | None,
) -> dict[str, Any] | None:
    if file is None:
        return None
    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=400, detail="凭证文件为空")
    if len(contents) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="单张财务凭证不能超过10MB")
    digest = hashlib.sha256(contents).hexdigest()
    suffix = Path(file.filename or "凭证").suffix.lower() or ".bin"
    relative_path = Path("documents") / "evidence" / "finance-intake" / business_date[:7] / f"{digest[:20]}{suffix}"
    destination = config.PROJECT_DATA_DIR / project_id / relative_path
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not destination.exists():
        destination.write_bytes(contents)
    voucher_id = ledger.register_evidence_voucher(
        project_id,
        voucher_key=f"finance-intake:{digest}",
        business_date=business_date,
        evidence_type=fact_type,
        channel=channel,
        amount_minor=amount_minor,
        original_filename=file.filename or "财务凭证",
        original_path=str(relative_path),
        sha256=digest,
        status="pending",
        notes=notes,
    )
    return next(item for item in ledger.list_evidence_vouchers(project_id, business_date, business_date) if item["id"] == voucher_id)


def _save_platform_report_voucher(
    project_id: str,
    ledger: FinanceLedger,
    *,
    filename: str,
    contents: bytes,
    report: dict[str, Any],
) -> tuple[str, str]:
    digest = hashlib.sha256(contents).hexdigest()
    suffix = Path(filename).suffix.lower() or ".bin"
    business_date = str(report.get("period_end") or report.get("period_start") or _today())
    relative_path = (
        Path("documents")
        / "evidence"
        / "platform-reports"
        / business_date[:7]
        / f"{digest[:20]}{suffix}"
    )
    destination = config.PROJECT_DATA_DIR / project_id / relative_path
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not destination.exists():
        destination.write_bytes(contents)
    summary = report.get("summary") or {}
    amount_minor = (
        summary.get("merchant_net_minor")
        if report.get("report_type") == "keruyun_daily_brief"
        else summary.get("wallet_credit_minor")
    )
    voucher_id = ledger.register_evidence_voucher(
        project_id,
        voucher_key=f"platform-report:{digest}",
        business_date=business_date,
        evidence_type=str(report["report_type"]),
        channel=str(report["source_platform"]),
        amount_minor=int(amount_minor or 0),
        original_filename=filename,
        original_path=str(relative_path),
        sha256=digest,
        status="confirmed",
        notes=(
            f"官方报表；期间 {report.get('period_start') or '未知'} 至 "
            f"{report.get('period_end') or '未知'}；原件按哈希去重保存"
        ),
    )
    return voucher_id, digest


def _fund_account_map(ledger: FinanceLedger, project_id: str) -> dict[str, dict[str, Any]]:
    return {str(item["account_key"]): item for item in ledger.list_fund_accounts(project_id)}


@router.get("/projects/{project_id}/finance/overview")
async def finance_overview(project_id: str, start: str | None = None, end: str | None = None):
    return _ledger(project_id).finance_overview(project_id, start, end)


@router.get("/projects/{project_id}/finance/analytics")
async def finance_analytics(project_id: str, start: str | None = None, end: str | None = None):
    ledger = _ledger(project_id)
    first, last = ledger.period_bounds(project_id)
    period_end = end or last or _today()
    period_start = start or (f"{period_end[:7]}-01" if period_end else first)
    if not period_start:
        period_start = period_end
    try:
        return ledger.finance_analytics(project_id, period_start, period_end)
    except FinanceMigrationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/projects/{project_id}/finance/operating-facts")
async def finance_operating_facts(project_id: str):
    book = StoreFactBook.load(project_id)
    return {
        "project_id": project_id,
        "finance": book.finance_summary(),
        "product_sales": book.product_sales_summary(),
        "packaging_estimate": book.packaging_estimate(),
        "inventory_policy": book.inventory_policy,
        "operational_forms": book.operational_forms,
        "supplier_invoices": book.supplier_invoices,
    }


@router.post("/projects/{project_id}/finance/expenses")
async def create_finance_expense(project_id: str, req: ExpenseRequest):
    try:
        entry_id = _ledger(project_id).record_expense(
            project_id, req.date, req.category_code, money_to_minor(req.amount),
            req.reference, req.paid_from, req.description,
        )
        return {"success": True, "entry_id": entry_id}
    except FinanceMigrationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/projects/{project_id}/finance/daily-close/{date}")
async def get_finance_daily_close(project_id: str, date: str):
    return _ledger(project_id).daily_close(project_id, date)


@router.post("/projects/{project_id}/finance/daily-close/{date}")
async def save_finance_daily_close(project_id: str, date: str, req: DailyCloseRequest):
    payload = {
        "counted_cash_minor": money_to_minor(req.counted_cash) if req.counted_cash is not None else None,
        "reserve_cash_minor": money_to_minor(req.reserve_cash),
        "merchant_net_confirmed": req.merchant_net_confirmed,
        "fund_locations_reviewed": req.fund_locations_reviewed,
        "outflows_reviewed": req.outflows_reviewed,
        "food_cost_minor": money_to_minor(req.food_cost) if req.food_cost is not None else None,
        "packaging_cost_minor": money_to_minor(req.packaging_cost) if req.packaging_cost is not None else None,
        "overtime_hours": req.overtime_hours,
        "rent_minor": money_to_minor(req.rent) if req.rent is not None else None,
        "utility_minor": money_to_minor(req.utility) if req.utility is not None else None,
        "other_cost_minor": money_to_minor(req.other_cost) if req.other_cost is not None else None,
    }
    try:
        ledger = _ledger(project_id)
        result = ledger.save_daily_close(project_id, date, payload)
        generated_reports: list[str] = []
        if result.get("status") == "closed":
            from models.reports import ReportArchive

            archive = ReportArchive.load(project_id) or ReportArchive.create(project_id)
            for report_type in ("daily", "weekly", "monthly"):
                try:
                    archive.generate_from_finance(report_type, ledger)
                    generated_reports.append(report_type)
                except ValueError:
                    # The report remains blocked until all facts in its period
                    # are confirmed; later closes retry it idempotently.
                    continue
        return {**result, "generated_reports": generated_reports}
    except FinanceMigrationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/projects/{project_id}/finance/daily-close/{date}/reopen")
async def reopen_finance_daily_close(project_id: str, date: str, req: ReopenDailyCloseRequest):
    try:
        return _ledger(project_id).reopen_daily_close(project_id, date, req.reason)
    except FinanceMigrationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/projects/{project_id}/finance/alerts")
async def finance_alerts(project_id: str, start: str | None = None, end: str | None = None):
    return {"alerts": _ledger(project_id).alerts(project_id, start, end)}


@router.get("/projects/{project_id}/finance/statements/profit-and-loss")
async def get_profit_and_loss(project_id: str, start: str | None = None, end: str | None = None):
    ledger = _ledger(project_id)
    first, last = ledger.period_bounds(project_id)
    start, end = start or first, end or last
    if not start or not end:
        return {"error": "暂无数据"}
    return ledger.profit_and_loss(project_id, start, end)


@router.get("/projects/{project_id}/finance/statements/balance-sheet")
async def get_balance_sheet(project_id: str, as_of: str | None = None):
    ledger = _ledger(project_id)
    _, last = ledger.period_bounds(project_id)
    as_of = as_of or last
    if not as_of:
        return {"error": "暂无数据"}
    return ledger.balance_sheet(project_id, as_of)


@router.get("/projects/{project_id}/finance/statements/cash-flow")
async def get_cash_flow(project_id: str, start: str | None = None, end: str | None = None):
    ledger = _ledger(project_id)
    first, last = ledger.period_bounds(project_id)
    start, end = start or first, end or last
    if not start or not end:
        return {"error": "暂无数据"}
    return ledger.cash_flow(project_id, start, end)


@router.get("/projects/{project_id}/finance/metrics")
async def list_finance_metrics():
    return {"metrics": _ledger("xinyu-hengtai-dakou").list_metrics()}


@router.get("/projects/{project_id}/finance/metrics/{metric_code}")
async def get_finance_metric(project_id: str, metric_code: str, start: str | None = None, end: str | None = None):
    ledger = _ledger(project_id)
    first, last = ledger.period_bounds(project_id)
    start, end = start or first, end or last
    if not start or not end:
        return {"error": "暂无数据"}
    return ledger.get_metric(project_id, metric_code, start, end)


@router.get("/projects/{project_id}/finance/reconciliation/platforms")
async def reconcile_platforms(project_id: str, start: str | None = None, end: str | None = None):
    ledger = _ledger(project_id)
    first, last = ledger.period_bounds(project_id)
    start, end = start or first, end or last
    if not start or not end:
        return {"error": "暂无数据"}
    return ledger.reconcile_platforms(project_id, start, end)


@router.get("/projects/{project_id}/finance/reconciliation/cash")
async def reconcile_cash(project_id: str, date: str):
    return _ledger(project_id).reconcile_cash(project_id, date)


@router.get("/projects/{project_id}/finance/reconciliation/receivables")
async def reconcile_receivables(project_id: str, start: str | None = None, end: str | None = None):
    ledger = _ledger(project_id)
    first, last = ledger.period_bounds(project_id)
    start, end = start or first, end or last
    if not start or not end:
        return {"error": "暂无数据"}
    return ledger.reconcile_receivables(project_id, start, end)


@router.post("/projects/{project_id}/finance/settlements/confirm")
async def confirm_finance_settlement(project_id: str, req: SettlementReceiptRequest):
    """Confirm bank arrival; this clears receivables and never adds revenue again."""
    ledger = _ledger(project_id)
    try:
        amount_minor = money_to_minor(req.amount)
        if req.source == "former_owner":
            entry_id = ledger.record_former_owner_transfer(project_id, req.date, amount_minor, req.reference)
        else:
            entry_id = ledger.record_platform_settlement(project_id, req.date, amount_minor, req.reference)
        return {"success": True, "entry_id": entry_id, "revenue_impact_minor": 0, "amount_minor": amount_minor}
    except FinanceMigrationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/projects/{project_id}/finance/merchant-net-sales")
async def list_merchant_net_sales(project_id: str, start: str, end: str):
    ledger = _ledger(project_id)
    return {
        "period_start": start,
        "period_end": end,
        "total_minor": ledger.merchant_net_total(project_id, start, end),
        "rows": ledger.merchant_net_sales(project_id, start, end),
    }


@router.post("/projects/{project_id}/finance/merchant-net-sales")
async def create_merchant_net_sale(project_id: str, req: MerchantNetSaleRequest):
    ledger = _ledger(project_id)
    try:
        record_id = ledger.record_merchant_net_sale(
            project_id,
            business_date=req.business_date,
            channel=req.channel,
            amount_minor=money_to_minor(req.amount),
            reference_gross_minor=money_to_minor(req.reference_gross) if req.reference_gross is not None else None,
            source_basis=req.source_basis,
            evidence_status=req.evidence_status,
            settlement_state=req.settlement_state,
            current_fund_account_id=req.current_fund_account_id,
            evidence_reference=req.evidence_reference,
            notes=req.notes,
        )
        return {"success": True, "record_id": record_id}
    except FinanceMigrationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/projects/{project_id}/finance/daily-revenue-checklist")
async def get_daily_revenue_checklist(project_id: str, start: str, end: str):
    try:
        return _ledger(project_id).daily_revenue_checklist(project_id, start, end)
    except FinanceMigrationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/projects/{project_id}/finance/daily-revenue/{business_date}")
async def save_daily_revenue(
    project_id: str, business_date: str, req: DailyRevenueBatchRequest,
):
    try:
        items = [
            {
                "channel": item.channel,
                "status": item.status,
                "amount_minor": money_to_minor(item.amount) if item.amount is not None else None,
                "notes": item.notes,
            }
            for item in req.items
        ]
        return _ledger(project_id).save_daily_revenue_entries(
            project_id, business_date, items,
        )
    except FinanceMigrationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/projects/{project_id}/finance/fund-accounts")
async def list_fund_accounts(project_id: str, as_of: str | None = None):
    ledger = _ledger(project_id)
    return {
        "accounts": ledger.list_fund_accounts(project_id),
        "positions": ledger.fund_positions(project_id, as_of or _today()),
    }


@router.post("/projects/{project_id}/finance/fund-accounts")
async def create_fund_account(project_id: str, req: FundAccountRequest):
    account_id = _ledger(project_id).upsert_fund_account(
        project_id,
        account_key=req.account_key,
        name=req.name,
        account_kind=req.account_kind,
        owner_kind=req.owner_kind,
        is_store_controlled=req.is_store_controlled,
        institution=req.institution,
        masked_number=req.masked_number,
        opening_balance_minor=money_to_minor(req.opening_balance),
        effective_from=req.effective_from,
        effective_to=req.effective_to,
        status=req.status,
    )
    return {"success": True, "account_id": account_id}


@router.get("/projects/{project_id}/finance/fund-movements")
async def list_fund_movements(project_id: str, start: str, end: str):
    return {"rows": _ledger(project_id).list_fund_movements(project_id, start, end)}


@router.post("/projects/{project_id}/finance/fund-movements")
async def create_fund_movement(project_id: str, req: FundMovementRequest):
    try:
        movement_id = _ledger(project_id).record_fund_movement(
            project_id,
            occurred_on=req.occurred_on,
            amount_minor=money_to_minor(req.amount),
            movement_type=req.movement_type,
            from_fund_account_id=req.from_fund_account_id,
            to_fund_account_id=req.to_fund_account_id,
            business_scope=req.business_scope,
            purpose=req.purpose,
            counterparty=req.counterparty,
            evidence_reference=req.evidence_reference,
            status=req.status,
            reference=req.reference,
            notes=req.notes,
        )
        return {"success": True, "movement_id": movement_id}
    except FinanceMigrationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/projects/{project_id}/finance/bookkeeping")
async def list_bookkeeping_records(
    project_id: str,
    start: str | None = None,
    end: str | None = None,
    status: str | None = None,
):
    return {"rows": _ledger(project_id).list_bookkeeping_records(project_id, start, end, status)}


@router.get("/projects/{project_id}/finance/categories")
async def get_finance_categories(project_id: str):
    """Return the one category contract used by intake, ledger and exports."""
    _ledger(project_id).ensure_store(project_id, project_id, _today())
    return finance_category_catalog()


@router.post("/projects/{project_id}/finance/bookkeeping")
async def create_bookkeeping_record(project_id: str, req: BookkeepingRecordRequest):
    try:
        category = find_finance_category(req.business_category_key)
        if req.business_category_key and not category:
            raise FinanceMigrationError("所选财务分类不存在，请刷新分类后重试")
        record_id = _ledger(project_id).create_bookkeeping_record(
            project_id,
            transaction_date=req.transaction_date,
            transaction_time=req.transaction_time,
            direction=str(category["direction"]) if category else req.direction,
            amount_minor=money_to_minor(req.amount),
            transaction_kind=str(category["transaction_kind"]) if category else req.transaction_kind,
            business_scope=str(category["business_scope"]) if category else req.business_scope,
            category_code=category["account_code"] if category else req.category_code,
            category_name=str(category["name"]) if category else req.category_name,
            business_category_key=str(category["key"]) if category else None,
            business_category_group=str(category["group_name"]) if category else None,
            account_key=req.account_key,
            counter_account_key=req.counter_account_key,
            counterparty=req.counterparty,
            summary=req.summary,
            source_type="manual",
            source_reference=req.source_reference,
            voucher_id=req.voucher_id,
            confidence="confirmed",
        )
        return {"success": True, "record": _ledger(project_id).get_bookkeeping_record(project_id, record_id)}
    except FinanceMigrationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.patch("/projects/{project_id}/finance/bookkeeping/{record_id}")
async def review_bookkeeping_record(project_id: str, record_id: str, req: BookkeepingReviewRequest):
    try:
        category = find_finance_category(req.business_category_key)
        if req.business_category_key and not category:
            raise FinanceMigrationError("所选财务分类不存在，请刷新分类后重试")
        record = _ledger(project_id).update_bookkeeping_record(
            project_id,
            record_id,
            transaction_kind=str(category["transaction_kind"]) if category else req.transaction_kind,
            business_scope=str(category["business_scope"]) if category else req.business_scope,
            category_code=category["account_code"] if category else req.category_code,
            category_name=str(category["name"]) if category else req.category_name,
            business_category_key=str(category["key"]) if category else None,
            business_category_group=str(category["group_name"]) if category else None,
            account_key=req.account_key,
            counter_account_key=req.counter_account_key,
            counterparty=req.counterparty,
            summary=req.summary,
        )
        return {"success": True, "record": record}
    except FinanceMigrationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/projects/{project_id}/finance/bookkeeping/{record_id}/confirm")
async def confirm_bookkeeping_record(project_id: str, record_id: str):
    try:
        return {"success": True, "record": _ledger(project_id).confirm_bookkeeping_record(project_id, record_id)}
    except FinanceMigrationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/projects/{project_id}/finance/bookkeeping/{record_id}/correct-classification")
async def correct_bookkeeping_classification(
    project_id: str, record_id: str, req: BookkeepingCorrectionRequest
):
    """Correct a posted classification while preserving before/after evidence."""
    try:
        result = _ledger(project_id).correct_posted_bookkeeping_classification(
            project_id,
            record_id,
            business_category_key=req.business_category_key,
            reason=req.reason,
            corrected_by=req.corrected_by,
            correction_key=req.correction_key,
        )
        return {"success": True, **result}
    except FinanceMigrationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/projects/{project_id}/finance/execution-plans/preview")
async def preview_finance_execution_plan(
    project_id: str, req: FinanceExecutionPreviewRequest
):
    payload = req.model_dump()
    payload["amount_minor"] = (
        int(req.amount_minor)
        if req.amount_minor is not None
        else money_to_minor(req.amount)
    )
    try:
        plan = FinanceExecutionService(_ledger(project_id)).preview(project_id, payload)
        return {"success": True, "plan": plan}
    except FinanceMigrationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/projects/{project_id}/finance/intake/parse-text")
async def parse_finance_intake_text(project_id: str, req: FinanceTextParseRequest):
    ledger = _ledger(project_id)
    return parse_finance_text(
        req.text,
        today=_today(),
        accounts=ledger.list_fund_accounts(project_id),
    )


@router.get("/projects/{project_id}/finance/platform-collection-bindings")
async def list_platform_collection_bindings(
    project_id: str, on_date: str | None = None
):
    return {
        "rows": _ledger(project_id).list_platform_collection_bindings(
            project_id, on_date
        )
    }


@router.post("/projects/{project_id}/finance/platform-collection-bindings")
async def save_platform_collection_binding(
    project_id: str, req: PlatformCollectionBindingRequest
):
    try:
        row = _ledger(project_id).upsert_platform_collection_binding(
            project_id, **req.model_dump()
        )
        return {"success": True, "binding": row}
    except (FinanceMigrationError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/projects/{project_id}/finance/platform-arrivals")
async def list_platform_arrivals(
    project_id: str, arrival_period_start: str, arrival_period_end: str
):
    try:
        return _ledger(project_id).platform_arrival_candidates(
            project_id,
            arrival_period_start=arrival_period_start,
            arrival_period_end=arrival_period_end,
        )
    except (FinanceMigrationError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/projects/{project_id}/finance/platform-bound-card-transfers/match")
async def match_platform_bound_card_transfer(
    project_id: str, req: PlatformBoundCardTransferRequest
):
    try:
        return _ledger(project_id).match_platform_bound_card_transfer(
            project_id,
            transfer_date=req.transfer_date,
            amount_minor=money_to_minor(req.amount),
            arrival_period_start=req.arrival_period_start,
            arrival_period_end=req.arrival_period_end,
            source_reference=req.source_reference,
            evidence_reference=req.evidence_reference,
        )
    except (FinanceMigrationError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/projects/{project_id}/finance/execution-plans")
async def list_finance_execution_plans(
    project_id: str,
    status: str | None = None,
    limit: int = 100,
):
    statuses = [item.strip() for item in (status or "").split(",") if item.strip()]
    return {
        "rows": _ledger(project_id).list_execution_plans(
            project_id, statuses=statuses, limit=limit
        )
    }


@router.get("/projects/{project_id}/finance/execution-plans/{plan_id:path}")
async def get_finance_execution_plan(project_id: str, plan_id: str):
    try:
        return {
            "success": True,
            "plan": _ledger(project_id).get_execution_plan(project_id, plan_id),
        }
    except FinanceMigrationError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/projects/{project_id}/finance/execution-plans/{plan_id:path}/confirm")
async def confirm_finance_execution_plan(
    project_id: str, plan_id: str, req: FinanceExecutionConfirmRequest
):
    if not req.confirmed:
        raise HTTPException(status_code=422, detail="必须明确确认后才能执行财务写入")
    try:
        plan = FinanceExecutionService(_ledger(project_id)).execute(
            project_id, plan_id, confirmed_by=req.confirmed_by
        )
        return {"success": True, "plan": plan}
    except FinanceMigrationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/projects/{project_id}/finance/intake")
async def create_finance_intake(
    project_id: str,
    fact_type: str = Form(...),
    business_date: str = Form(...),
    amount: float = Form(...),
    account_key: str | None = Form(None),
    counter_account_key: str | None = Form(None),
    current_account_key: str | None = Form(None),
    channel: str | None = Form(None),
    settlement_state: str | None = Form(None),
    category_code: str | None = Form(None),
    category_name: str | None = Form(None),
    business_category_key: str | None = Form(None),
    counterparty: str | None = Form(None),
    source_basis: str = Form("手工录入"),
    business_period_start: str | None = Form(None),
    business_period_end: str | None = Form(None),
    platforms: str | None = Form(None),
    notes: str | None = Form(None),
    file: UploadFile | None = File(None),
):
    """Create one finance fact from a screenshot or manual entry.

    A source file is immutable evidence.  The user-selected fact type decides
    whether it becomes daily merchant net sales or a reviewable money record;
    a bank receipt can therefore never silently become a second sales record.
    """
    try:
        amount_minor = money_to_minor(amount)
    except Exception as exc:
        raise HTTPException(status_code=422, detail="金额必须是大于0的数字") from exc
    if amount_minor <= 0:
        raise HTTPException(status_code=422, detail="金额必须大于0")
    try:
        datetime.strptime(business_date, "%Y-%m-%d")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="日期必须是 YYYY-MM-DD") from exc

    ledger = _ledger(project_id)
    voucher = await _save_finance_intake_voucher(
        project_id, ledger, file=file, business_date=business_date,
        amount_minor=amount_minor, fact_type=fact_type, channel=channel, notes=notes,
    )
    voucher_id = voucher["id"] if voucher else None
    source_reference = voucher_id or f"finance-intake:{project_id}:{fact_type}:{business_date}:{amount_minor}:{source_basis}"

    plan = FinanceExecutionService(ledger).preview(
        project_id,
        {
            "event_type": fact_type,
            "transaction_date": business_date,
            "amount_minor": amount_minor,
            "account_key": account_key,
            "counter_account_key": counter_account_key,
            "current_account_key": current_account_key,
            "channel": channel,
            "settlement_state": settlement_state,
            "category_code": category_code,
            "category_name": category_name,
            "business_category_key": business_category_key,
            "counterparty": counterparty,
            "source_basis": source_basis,
            "source_reference": source_reference,
            "evidence_reference": voucher_id,
            "business_period_start": business_period_start,
            "business_period_end": business_period_end,
            "platforms": [
                item.strip() for item in (platforms or "").split(",") if item.strip()
            ] or None,
            "notes": notes,
        },
    )
    return {
        "success": True,
        "kind": fact_type,
        "plan": plan,
        "voucher": voucher,
    }


@router.post("/projects/{project_id}/finance/report-imports/preview")
async def preview_platform_report(
    project_id: str,
    file: UploadFile = File(...),
):
    """Read an official platform report without changing the ledger."""
    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=400, detail="报表文件为空")
    if len(contents) > 25 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="报表文件不能超过25MB")
    try:
        report = parse_platform_report(file.filename or "官方报表", contents)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"success": True, "project_id": project_id, "report": report}


@router.post("/projects/{project_id}/finance/report-imports/confirm")
async def confirm_platform_report(
    project_id: str,
    file: UploadFile = File(...),
    wallet_account_key: str | None = Form(None),
    destination_account_key: str | None = Form(None),
):
    """Archive and classify an official report after deterministic validation."""
    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=400, detail="报表文件为空")
    if len(contents) > 25 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="报表文件不能超过25MB")
    try:
        report = parse_platform_report(file.filename or "官方报表", contents)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if not report.get("can_confirm"):
        warnings = "、".join(str(item) for item in report.get("warnings") or [])
        raise HTTPException(status_code=422, detail=f"报表校验未通过：{warnings or '缺少必要字段'}")

    ledger = _ledger(project_id)
    business_date = str(report.get("period_end") or report.get("period_start") or _today())
    ledger.ensure_store(project_id, str(report.get("store_name") or project_id), business_date)
    accounts = _fund_account_map(ledger, project_id)

    if report["report_type"] == "meituan_balance_statement":
        if not wallet_account_key or wallet_account_key not in accounts:
            raise HTTPException(status_code=422, detail="请选择已登记的美团平台钱包")
        if not destination_account_key or destination_account_key not in accounts:
            raise HTTPException(status_code=422, detail="请选择提现实际到达的账户")

    voucher_id, digest = _save_platform_report_voucher(
        project_id,
        ledger,
        filename=file.filename or "官方报表",
        contents=contents,
        report=report,
    )

    if report["report_type"] == "keruyun_daily_brief":
        report_date = str(report["period_end"])
        summary = report["summary"]
        merchant_net_minor = int(summary["merchant_net_minor"])
        existing_revenue = ledger.revenue_total(project_id, report_date, report_date)
        if existing_revenue and existing_revenue != merchant_net_minor:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"{report_date} 已有营业收入 {existing_revenue / 100:.2f} 元，"
                    f"与本报表 {merchant_net_minor / 100:.2f} 元不一致；请先复核原账"
                ),
            )
        payment_methods = [
            {
                "method": item["method"],
                "amount": int(item["amount_minor"]) / 100,
            }
            for item in report["payment_methods"]
        ]
        posted = ledger.record_confirmed_daily_revenue(
            project_id,
            {
                "date": report_date,
                "actual_revenue": merchant_net_minor / 100,
                "payment_methods": payment_methods,
                "source_basis": "客如云营业简报·营业统计与支付统计交叉校验",
            },
        )
        cash_account = next(
            (item for item in accounts.values() if item.get("account_kind") == "cash"),
            None,
        )
        channel_record_ids: list[str] = []
        for item in report["payment_methods"]:
            method = str(item["method"])
            if method == "现金":
                settlement_state = "store_account_received"
                current_account_id = cash_account["id"] if cash_account else None
            elif method in {"美团外卖", "淘宝闪购餐饮", "抖音团购券", "美团团购券", "京东外卖", "京东秒送"}:
                settlement_state = "wallet_credited"
                current_account_id = None
            else:
                settlement_state = "merchant_net_confirmed"
                current_account_id = None
            channel_record_ids.append(
                ledger.record_merchant_net_sale(
                    project_id,
                    business_date=report_date,
                    channel=method,
                    amount_minor=int(item["amount_minor"]),
                    source_basis="客如云营业简报·支付统计",
                    evidence_status="confirmed",
                    settlement_state=settlement_state,
                    current_fund_account_id=current_account_id,
                    evidence_reference=voucher_id,
                    notes="渠道净收款；到账与平台提现另行对账，不重复确认收入",
                )
            )
        return {
            "success": True,
            "report_type": report["report_type"],
            "voucher_id": voucher_id,
            "posted": posted,
            "merchant_net_minor": merchant_net_minor,
            "revenue_impact_minor": merchant_net_minor if posted else 0,
            "channel_record_ids": channel_record_ids,
        }

    record_ids: list[str] = []
    for row in report["rows"]:
        signed_amount_minor = int(row["signed_amount_minor"])
        if not signed_amount_minor:
            continue
        event_type = str(row["event_type"])
        if event_type == "wallet_credit":
            direction = "inflow"
            transaction_kind = "platform_settlement"
            category_code = None
            category_name = "美团平台钱包账单"
            account_key = wallet_account_key
            counter_account_key = None
        elif event_type == "wallet_withdrawal":
            direction = "transfer"
            transaction_kind = "account_transfer"
            category_code = None
            category_name = "美团钱包提现"
            account_key = wallet_account_key
            counter_account_key = destination_account_key
        elif event_type == "promotion_fee":
            direction = "outflow"
            transaction_kind = "operating_expense"
            category_code = "5004"
            category_name = "活动与推广"
            account_key = wallet_account_key
            counter_account_key = None
        else:
            raise HTTPException(status_code=422, detail="存在未识别的钱包流水，不能自动生成账目")
        source_reference = f"{digest}:{row['source_sheet']}:{row['reference']}"
        record_ids.append(
            ledger.create_bookkeeping_record(
                project_id,
                transaction_date=str(row["occurred_on"]),
                direction=direction,
                amount_minor=abs(signed_amount_minor),
                transaction_kind=transaction_kind,
                business_scope="store",
                category_code=category_code,
                category_name=category_name,
                account_key=account_key,
                counter_account_key=counter_account_key,
                counterparty="美团",
                summary=str(row["transaction_type"]),
                source_type=str(report["report_type"]),
                source_reference=source_reference,
                voucher_id=voucher_id,
                confidence="high",
                classification_reason=(
                    "平台钱包入账或提现只改变资金位置，不增加营业收入"
                    if event_type != "promotion_fee"
                    else "美团推广费流水，待人工确认后计入活动与推广"
                ),
                raw_data=row,
                status="needs_review",
            )
        )
    return {
        "success": True,
        "report_type": report["report_type"],
        "voucher_id": voucher_id,
        "created_record_count": len(record_ids),
        "record_ids": record_ids,
        "revenue_impact_minor": 0,
    }


@router.post("/projects/{project_id}/finance/imports")
async def import_finance_statement(
    project_id: str,
    account_key: str = Form(...),
    source_type: str = Form("bank_statement"),
    file: UploadFile = File(...),
):
    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=400, detail="账单文件为空")
    if len(contents) > 25 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="账单文件不能超过25MB")
    ledger = _ledger(project_id)
    accounts = {item["account_key"]: item for item in ledger.list_fund_accounts(project_id)}
    account = accounts.get(account_key)
    if not account:
        raise HTTPException(status_code=422, detail="请先在资金账户中登记这张账单所属账户")
    try:
        parsed = parse_finance_file(
            file.filename or "账单",
            file.content_type or "application/octet-stream",
            contents,
            account_owner_kind=str(account["owner_kind"]),
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    digest = hashlib.sha256(contents).hexdigest()
    suffix = Path(file.filename or "账单").suffix.lower() or ".bin"
    month = min(item["transaction_date"] for item in parsed["transactions"])[:7]
    project_dir = config.PROJECT_DATA_DIR / project_id
    relative_path = Path("documents") / "evidence" / "finance-imports" / month / f"{digest[:20]}{suffix}"
    destination = project_dir / relative_path
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not destination.exists():
        destination.write_bytes(contents)
    first_date = min(item["transaction_date"] for item in parsed["transactions"])
    voucher_id = ledger.register_evidence_voucher(
        project_id,
        voucher_key=f"finance-import:{digest}:{account_key}",
        business_date=first_date,
        evidence_type=source_type,
        original_filename=file.filename or "账单",
        original_path=str(relative_path),
        sha256=digest,
        status="pending",
        channel=account.get("institution") or account.get("name"),
        notes=f"账单导入，共{parsed['row_count']}笔；收入{parsed['inflow_minor']}分，支出{parsed['outflow_minor']}分",
    )
    batch_id = ledger.create_import_batch(
        project_id,
        source_type=source_type,
        account_key=account_key,
        original_filename=file.filename or "账单",
        original_path=str(relative_path),
        sha256=digest,
        row_count=parsed["row_count"],
        inflow_minor=parsed["inflow_minor"],
        outflow_minor=parsed["outflow_minor"],
        opening_balance_minor=parsed["opening_balance_minor"],
        closing_balance_minor=parsed["closing_balance_minor"],
        status="needs_review",
    )
    record_ids = []
    for transaction in parsed["transactions"]:
        record_ids.append(ledger.create_bookkeeping_record(
            project_id,
            transaction_date=transaction["transaction_date"],
            transaction_time=transaction.get("transaction_time"),
            direction=transaction["direction"],
            amount_minor=transaction["amount_minor"],
            transaction_kind=transaction["transaction_kind"],
            business_scope=transaction["business_scope"],
            category_code=transaction.get("category_code"),
            category_name=transaction["category_name"],
            account_key=account_key,
            counterparty=transaction.get("counterparty"),
            summary=transaction.get("summary"),
            source_type=source_type,
            source_reference=f"{batch_id}:{transaction['source_reference']}",
            voucher_id=voucher_id,
            import_batch_id=batch_id,
            confidence=transaction["confidence"],
            classification_reason=transaction["classification_reason"],
            raw_data=transaction.get("raw_data") or {},
            status="needs_review",
        ))
    return {
        "success": True,
        "batch_id": batch_id,
        "voucher_id": voucher_id,
        "record_ids": record_ids,
        **{key: parsed[key] for key in ("row_count", "inflow_minor", "outflow_minor", "opening_balance_minor", "closing_balance_minor")},
    }


@router.get("/projects/{project_id}/finance/imports")
async def list_finance_imports(project_id: str):
    return {"rows": _ledger(project_id).list_import_batches(project_id)}


@router.get("/projects/{project_id}/finance/daily-snapshot")
async def get_daily_finance_snapshot(project_id: str, date: str):
    try:
        return _ledger(project_id).daily_finance_snapshot(project_id, date)
    except FinanceMigrationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/projects/{project_id}/finance/period-snapshot")
async def get_period_finance_snapshot(project_id: str, start: str, end: str):
    try:
        return _ledger(project_id).period_finance_snapshot(project_id, start, end)
    except FinanceMigrationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/projects/{project_id}/finance/cash-forecast")
async def get_cash_chain_forecast(
    project_id: str,
    as_of: str | None = None,
    safety_reserve: float | None = None,
):
    try:
        return _ledger(project_id).cash_chain_forecast(
            project_id,
            as_of or _today(),
            safety_reserve_minor=money_to_minor(safety_reserve) if safety_reserve is not None else None,
        )
    except (FinanceMigrationError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/projects/{project_id}/finance/cash-plan")
async def create_cash_plan_item(project_id: str, req: CashPlanItemRequest):
    try:
        item_id = _ledger(project_id).create_cash_plan_item(
            project_id,
            due_date=req.due_date,
            flow_type=req.flow_type,
            amount_minor=money_to_minor(req.amount),
            category=req.category,
            counterparty=req.counterparty,
            priority=req.priority,
            source_reference=req.source_reference,
            notes=req.notes,
        )
        return {"success": True, "item_id": item_id}
    except FinanceMigrationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/projects/{project_id}/finance/reconciliation/queue")
async def get_reconciliation_queue(project_id: str, start: str | None = None, end: str | None = None):
    return {"rows": _ledger(project_id).reconciliation_queue(project_id, start, end)}


@router.post("/projects/{project_id}/finance/reconciliation/{record_id}/match")
async def match_reconciliation_record(project_id: str, record_id: str, req: ReconciliationMatchRequest):
    try:
        record = _ledger(project_id).match_reconciliation(
            project_id,
            record_id,
            target_type=req.target_type,
            target_id=req.target_id,
            matched_amount_minor=money_to_minor(req.matched_amount),
            notes=req.notes,
        )
        return {"success": True, "record": record}
    except FinanceMigrationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/projects/{project_id}/finance/debts")
async def list_debts(project_id: str):
    return _ledger(project_id).debt_summary(project_id)


@router.post("/projects/{project_id}/finance/debts")
async def create_debt(project_id: str, req: DebtRequest):
    debt_id = _ledger(project_id).record_debt(
        project_id,
        debt_key=req.debt_key,
        lender=req.lender,
        principal_minor=money_to_minor(req.principal),
        received_on=req.received_on,
        due_on=req.due_on,
        annual_rate_decimal=req.annual_rate_decimal,
        status=req.status,
        notes=req.notes,
    )
    return {"success": True, "debt_id": debt_id}


@router.post("/projects/{project_id}/finance/debts/{debt_id}/allocations")
async def create_debt_allocation(project_id: str, debt_id: str, req: DebtAllocationRequest):
    try:
        allocation_id = _ledger(project_id).record_debt_allocation(
            project_id,
            debt_id=debt_id,
            allocation_key=req.allocation_key,
            purpose=req.purpose,
            amount_minor=money_to_minor(req.amount),
            classification=req.classification,
            evidence_reference=req.evidence_reference,
            notes=req.notes,
        )
        return {"success": True, "allocation_id": allocation_id}
    except FinanceMigrationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/projects/{project_id}/finance/evidence-vouchers")
async def list_evidence_vouchers(project_id: str, start: str | None = None, end: str | None = None):
    return {"rows": _ledger(project_id).list_evidence_vouchers(project_id, start, end)}


@router.post("/projects/{project_id}/finance/evidence-vouchers")
async def create_evidence_voucher(project_id: str, req: EvidenceVoucherRequest):
    voucher_id = _ledger(project_id).register_evidence_voucher(
        project_id,
        voucher_key=req.voucher_key,
        business_date=req.business_date,
        evidence_type=req.evidence_type,
        channel=req.channel,
        amount_minor=money_to_minor(req.amount) if req.amount is not None else None,
        source_sheet=req.source_sheet,
        source_cell=req.source_cell,
        original_filename=req.original_filename,
        original_path=req.original_path,
        sha256=req.sha256,
        status=req.status,
        notes=req.notes,
    )
    return {"success": True, "voucher_id": voucher_id}


@router.get("/projects/{project_id}/finance/evidence-vouchers/{voucher_id}/file")
async def get_evidence_voucher_file(project_id: str, voucher_id: str):
    ledger = _ledger(project_id)
    voucher = next((item for item in ledger.list_evidence_vouchers(project_id) if item["id"] == voucher_id), None)
    if not voucher:
        raise HTTPException(status_code=404, detail="凭证不存在")
    project_dir = (config.PROJECT_DATA_DIR / project_id).resolve()
    original = Path(str(voucher["original_path"]))
    candidates = [original] if original.is_absolute() else [project_dir / original, project_dir / "documents" / original]
    resolved = next((candidate.resolve() for candidate in candidates if candidate.exists()), None)
    if resolved is None or (resolved != project_dir and project_dir not in resolved.parents):
        raise HTTPException(status_code=404, detail="凭证原件不存在或路径不安全")
    media_type = mimetypes.guess_type(str(voucher["original_filename"]))[0] or "application/octet-stream"
    return FileResponse(
        resolved,
        media_type=media_type,
        filename=str(voucher["original_filename"]),
        content_disposition_type="inline",
    )


class FinanceQueryRequest(BaseModel):
    query: str = Field(..., min_length=1)
    start: str | None = None
    end: str | None = None


@router.post("/projects/{project_id}/finance/query")
async def finance_query(project_id: str, req: FinanceQueryRequest):
    ledger = _ledger(project_id)
    first, last = ledger.period_bounds(project_id)
    start, end = req.start or first, req.end or last
    if not start or not end:
        return {"answer": "暂无经营数据", "period": {"start": start, "end": end}, "metrics": [], "completeness": "no_data"}
    # Model calls are deliberately disabled inside pytest; tests inject a fake
    # gateway when exercising planning. Production uses the configured route.
    use_model = not bool(__import__("os").environ.get("PYTEST_CURRENT_TEST"))
    return answer_finance_question(ledger, project_id, req.query, start, end, use_model=use_model)


@router.post("/projects/{project_id}/finance/facts/{fact_id}/post")
async def post_finance_fact(project_id: str, fact_id: str):
    try:
        return _ledger(project_id).post_fact(project_id, fact_id)
    except FinanceMigrationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/projects/{project_id}/finance/capital-events")
async def create_capital_event(project_id: str, req: CapitalEventRequest):
    try:
        entry_id = _ledger(project_id).record_capital_event(
            project_id, req.date, req.event_type, money_to_minor(req.amount),
            req.reference, req.money_account, req.description,
        )
        return {"success": True, "entry_id": entry_id}
    except FinanceMigrationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/projects/{project_id}/finance/entries")
async def create_journal_entry(project_id: str, req: JournalEntryRequest):
    try:
        lines = [(line.account_code, line.debit_minor, line.credit_minor) for line in req.lines]
        entry_id = _ledger(project_id).post_entry(
            store_id=project_id,
            entry_date=req.entry_date,
            posting_key=f"manual:{project_id}:{req.entry_date}:{hash(tuple(lines))}",
            description=req.description,
            lines=lines,
            entry_type="manual",
        )
        return {"success": True, "entry_id": entry_id}
    except FinanceMigrationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/projects/{project_id}/finance/targets")
async def set_finance_target(project_id: str, req: FinancialTargetRequest):
    try:
        target_id = _ledger(project_id).set_financial_target(
            project_id, req.target_type, req.period_start, req.period_end, money_to_minor(req.amount),
        )
        return {"success": True, "target_id": target_id}
    except FinanceMigrationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/projects/{project_id}/finance/export.xlsx")
async def export_finance_workbook(project_id: str, start: str | None = None, end: str | None = None):
    ledger = _ledger(project_id)
    overview = ledger.finance_overview(project_id, start, end)
    if not overview.get("has_data"):
        raise HTTPException(status_code=404, detail="暂无可导出的财务数据")
    alerts = ledger.alerts(project_id, overview["period_start"], overview["period_end"])
    start_date, end_date = overview["period_start"], overview["period_end"]
    merchant_rows = overview["merchant_net_sales"]
    movements = ledger.list_fund_movements(project_id, start_date, end_date)
    bookkeeping_rows = ledger.list_bookkeeping_records(project_id, start_date, end_date, limit=2000)
    vouchers = ledger.list_evidence_vouchers(project_id, start_date, end_date)
    debt = overview["debt_summary"]
    daily: dict[str, dict[str, Any]] = {}
    for row in merchant_rows:
        item = daily.setdefault(row["business_date"], {"channels": {}, "reference_gross_minor": None})
        item["channels"][row["channel"]] = row["merchant_net_minor"]
        if row["reference_gross_minor"] is not None:
            item["reference_gross_minor"] = row["reference_gross_minor"]
    channel_names = ["客如云收款", "美团外卖", "美团团购", "淘宝闪购", "抖音团购", "京东外卖", "现金"]
    voucher_counts: dict[str, int] = {}
    for voucher in vouchers:
        if voucher["business_date"]:
            voucher_counts[voucher["business_date"]] = voucher_counts.get(voucher["business_date"], 0) + 1
    sheets = [
        ("资金总览", [
            ["指标", "金额/数量", "状态/口径"],
            ["期间", None, f"{start_date} ~ {end_date}"],
            ["实际到手营业额", overview["merchant_net_minor"] / 100, "老板第一经营口径；不是利润"],
            ["会计营业收入（已确认部分）", overview["revenue_minor"] / 100, "与到账分开；当前日期覆盖可能不完整"],
            ["店铺当前可控资金位置累计", overview["funds_minor"]["store_controlled"] / 100, "按流水位置；需与银行实时余额复核"],
            ["店铺多渠道实际流出", overview["fund_movement_totals_minor"]["store_outflow"] / 100, "银行卡/微信/支付宝/现金等"],
            ["个人消费（已剔除）", overview["fund_movement_totals_minor"]["personal_outflow"] / 100, "不进入店铺利润"],
            ["经营资金差额", (overview["merchant_net_minor"] - overview["fund_movement_totals_minor"]["store_outflow"]) / 100, "不是利润"],
            ["借款待还本金", debt["outstanding_minor"] / 100, "转让费是用途，不重复增加负债"],
            ["凭证引用数", len(vouchers), "原图存入门店凭证目录"],
            ["利润状态", None, "已确认" if overview["profit_status"] == "confirmed" else "成本/库存/平台扣费未闭环，不可确认"],
        ], [30, 20, 56]),
        ("实际到手明细", [["日期", "客如云显示总额(仅参考)", *channel_names, "实际到手营业额", "与客如云差额", "凭证引用数"]] + [
            [
                business_date,
                item["reference_gross_minor"] / 100 if item["reference_gross_minor"] is not None else None,
                *[item["channels"].get(channel, 0) / 100 for channel in channel_names],
                sum(item["channels"].values()) / 100,
                (sum(item["channels"].values()) - (item["reference_gross_minor"] or 0)) / 100,
                voucher_counts.get(business_date, 0),
            ]
            for business_date, item in sorted(daily.items())
        ], [15, 22, 15, 15, 15, 15, 15, 15, 12, 20, 18, 14]),
        ("资金流水", [["日期", "方向", "业务归属", "金额(元)", "来源账户", "去向账户", "事项", "对方", "凭证编号", "状态", "说明"]] + [
            [row["occurred_on"], row["movement_type"], row["business_scope"], row["amount_minor"] / 100,
             row["from_account_name"], row["to_account_name"], row["purpose"], row["counterparty"],
             row["evidence_reference"], row["status"], row["notes"]]
            for row in movements
        ], [15, 18, 12, 16, 24, 24, 20, 20, 24, 14, 56]),
        ("账户对账", [["账户", "类型", "所有者", "店铺可控", "流水位置净额(元)", "状态", "说明"]] + [
            [row["name"], row["account_kind"], row["owner_kind"], "是" if row["is_store_controlled"] else "否",
             row["balance_minor"] / 100, row["status"], "期间流水位置，不冒充银行实时余额"]
            for row in overview["fund_positions"] if row["account_key"] != "external-payees"
        ], [30, 18, 18, 14, 22, 14, 42]),
        ("借款接店", [["记录类型", "出借人", "日期/编号", "本金/用途金额(元)", "待还/分类", "说明"]] + [
            ["借款本金", item["lender"], item["received_on"], item["principal_minor"] / 100,
             (item["principal_minor"] - item["repaid_principal_minor"]) / 100, item["notes"]]
            for item in debt["items"]
        ] + [
            ["资金用途", item["lender"], item["allocation_key"], item["amount_minor"] / 100,
             item["classification"], item["notes"]]
            for item in debt["allocations"]
        ], [18, 18, 18, 24, 24, 52]),
        ("凭证索引", [["凭证编号", "业务日期", "类型", "渠道/事项", "金额(元)", "状态", "原表", "原单元格", "原图片名", "产品原图路径", "SHA-256"]] + [
            [row["voucher_number"], row["business_date"], row["evidence_type"], row["channel"],
             row["amount_minor"] / 100 if row["amount_minor"] is not None else None, row["status"],
             row["source_sheet"], row["source_cell"], row["original_filename"], row["original_path"], row["sha256"]]
            for row in vouchers
        ], [25, 15, 28, 20, 16, 20, 15, 14, 20, 54, 66]),
        ("利润表待补", [
            ["项目", "金额(元)", "状态", "需补资料"],
            ["实际到手营业额（经营参考）", overview["merchant_net_minor"] / 100, "完整", "不能替代会计营业收入"],
            ["会计营业收入", overview["revenue_minor"] / 100, "日期覆盖不完整", "平台订单收入、退款全量"],
            ["食材与包装成本", None, "阻断", "期初/期末库存、领用、报损与包装单价"],
            ["平台佣金/配送/推广", None, "阻断", "由外卖Agent拆平台对账单"],
            ["员工/房租/水电", None, "不完整", "工资、加班、水电、房租期间"],
            ["经营净利润", None, "不可确认", "全部必需成本闭环后计算"],
        ], [32, 18, 20, 60]),
        ("资金流量表", [
            ["项目", "金额(元)", "状态/说明"],
            ["实际到手营业额", overview["merchant_net_minor"] / 100, "包含平台/前老板处待转资金"],
            ["其中：店铺可控位置", overview["funds_minor"]["store_controlled"] / 100, "需与银行当前余额对账"],
            ["其中：平台钱包/绑定卡/权限待转", (overview["merchant_net_minor"] - overview["funds_minor"]["store_controlled"]) / 100, "不等于已到工商银行店铺账户"],
            ["减：店铺多渠道实际流出", overview["fund_movement_totals_minor"]["store_outflow"] / 100, "店铺资金流出"],
            ["经营资金差额（非利润）", (overview["merchant_net_minor"] - overview["fund_movement_totals_minor"]["store_outflow"]) / 100, "不可当作净利润"],
            ["个人消费流出", overview["fund_movement_totals_minor"]["personal_outflow"] / 100, "已从店铺经营剔除"],
            ["借款流入本金", debt["principal_minor"] / 100, "筹资活动，不是营业收入"],
            ["已说明接店用途", debt["allocated_minor"] / 100, "资金用途，不是新增负债"],
        ], [34, 20, 56]),
        ("预警与检查", [["编码", "级别", "问题", "金额(元)"]] + [
            [item["code"], item["severity"], item["title"], item.get("amount_minor", 0) / 100] for item in alerts
        ] + [["LEDGER_BALANCE", "check", "借贷平衡", 0 if not ledger.unbalanced_entries(project_id) else len(ledger.unbalanced_entries(project_id))]], [28, 14, 34, 18]),
    ]
    daily_headers = list(sheets[1][1][0])
    daily_rows: list[list[Any]] = []
    for data_index, source_row in enumerate(sheets[1][1][1:], start=1):
        excel_row = data_index + 5
        row = list(source_row)
        row[9] = Formula(f"ROUND(SUM(C{excel_row}:I{excel_row}),2)", source_row[9])
        row[10] = Formula(f"ROUND(J{excel_row}-B{excel_row},2)", source_row[10])
        daily_rows.append(row)
    first_daily_row = 6
    last_daily_row = 5 + len(daily_rows)
    if daily_rows:
        total_row: list[Any] = ["合计"]
        for column in range(2, 12):
            letter = chr(64 + column)
            total_row.append(Formula(f"ROUND(SUM({letter}{first_daily_row}:{letter}{last_daily_row}),2)"))
        total_row.append(sum(voucher_counts.values()))
        daily_rows.append(total_row)
    else:
        daily_rows.append([
            "合计",
            *[Formula(f"SUM({chr(64 + column)}6:{chr(64 + column)}6)", 0) for column in range(2, 12)],
            0,
        ])

    plan_until = (datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=30)).strftime("%Y-%m-%d")
    existing_plan = ledger.list_cash_plan_items(project_id, end_date, plan_until)
    forecast = ledger.cash_chain_forecast(project_id, end_date)
    plan_rows: list[list[Any]] = []
    for data_index in range(max(20, len(existing_plan)), 0, -1):
        item_index = max(20, len(existing_plan)) - data_index
        item = existing_plan[item_index] if item_index < len(existing_plan) else {}
        excel_row = item_index + 6
        flow_label = "预计流入" if item.get("flow_type") == "expected_inflow" else "必须支出" if item else None
        amount = item.get("amount_minor", 0) / 100 if item else None
        signed_formula = f'IF(C{excel_row}="预计流入",F{excel_row},-F{excel_row})'
        balance_formula = (
            f"'财务驾驶舱'!B9+J{excel_row}" if item_index == 0
            else f"K{excel_row-1}+J{excel_row}"
        )
        plan_rows.append([
            item.get("due_date"), item.get("category"), flow_label, item.get("counterparty"),
            {"must_pay": "必须支付", "expected": "预计", "optional": "可选"}.get(item.get("priority")),
            amount, item.get("status"), item.get("source_reference"), item.get("notes"),
            Formula(f"ROUND({signed_formula},2)"), Formula(f"ROUND({balance_formula},2)"),
            Formula(f"ROUND(K{excel_row}-'财务驾驶舱'!B15,2)"),
        ])

    channel_categories = {
        "客如云收款": ("营业收入与调整", "到店销售"),
        "现金": ("营业收入与调整", "现金销售"),
        "美团团购": ("营业收入与调整", "团购核销"),
        "抖音团购": ("营业收入与调整", "团购核销"),
    }
    settlement_labels = {
        "merchant_net_confirmed": "销售已确认",
        "wallet_credited": "已到平台钱包",
        "bound_bank_received": "已到绑定银行卡",
        "former_owner_received": "前老板已代收",
        "former_owner_pending_transfer": "已到平台绑定卡，待转店铺工商卡",
        "store_account_received": "已到店铺账户",
        "unknown": "位置待核对",
        "disputed": "金额有争议",
    }
    record_status_labels = {
        "draft": "待确认", "needs_review": "待补信息", "confirmed": "已确认",
        "posted": "已记账", "rejected": "已作废", "duplicate": "重复记录",
    }
    unified_rows = [
        [
            row["business_date"],
            channel_categories.get(row["channel"], ("营业收入与调整", "外卖销售"))[0],
            channel_categories.get(row["channel"], ("营业收入与调整", "外卖销售"))[1],
            "流入", "店铺", row["merchant_net_minor"] / 100,
            row["channel"], settlement_labels.get(row["settlement_state"], row["settlement_state"]), row["channel"], "实际到手营业额",
            row["evidence_reference"], record_status_labels.get(row["evidence_status"], "已确认"), "计入收入；后续到账只改变资金位置",
        ]
        for row in merchant_rows
    ] + [
        [
            row["transaction_date"], row.get("business_category_group") or "待归类",
            row["category_name"], {"inflow": "流入", "outflow": "流出", "transfer": "调拨"}.get(row["direction"], row["direction"]),
            {"store": "店铺", "personal": "个人", "mixed": "混合", "unknown": "待确认"}.get(row["business_scope"], row["business_scope"]),
            row["amount_minor"] / 100, row.get("account_name"), row.get("counter_account_name"),
            row.get("counterparty"), row.get("summary"), row.get("voucher_number"), record_status_labels.get(row["status"], row["status"]),
            (
                "不计店铺损益"
                if row["business_scope"] == "personal"
                else "先进入库存，耗用时进入成本"
                if row["transaction_kind"] == "inventory_purchase"
                else "只改变资金或负债位置"
                if (row.get("business_category_group") in {"借款与融资", "老板往来", "资金调拨与结算"}
                    or row["transaction_kind"] in {"account_transfer", "platform_settlement", "former_owner_transfer"})
                else "计入店铺经营成本或费用"
            ),
        ]
        for row in bookkeeping_rows
    ] + [
        [
            row["occurred_on"],
            "老板往来" if row["business_scope"] == "personal" else "资金调拨与结算" if row["movement_type"] in {"account_transfer", "platform_settlement", "former_owner_transfer", "cash_deposit"} else "待归类",
            "个人账户消费" if row["business_scope"] == "personal" else row["purpose"], "资金移动",
            {"store": "店铺", "personal": "个人", "mixed": "混合", "unknown": "待确认"}.get(row["business_scope"], row["business_scope"]),
            row["amount_minor"] / 100, row["from_account_name"], row["to_account_name"],
            row["counterparty"], row["notes"], row["evidence_reference"], record_status_labels.get(row["status"], row["status"]),
            "不计店铺损益" if row["business_scope"] == "personal" else "资金位置记录，不重复确认收入",
        ]
        for row in movements
        if not str(row.get("reference") or "").startswith("bookkeeping:")
    ]
    unified_rows.sort(key=lambda row: str(row[0] or ""))

    profit_rows = [
        ["实际到手营业额（经营参考）", overview["merchant_net_minor"] / 100, "完整", "不是利润；不能替代会计营业收入"],
        ["会计营业收入（已确认部分）", overview["revenue_minor"] / 100, "日期覆盖不完整", "补齐平台订单收入、退款"],
        ["店铺多渠道实际流出", overview["fund_movement_totals_minor"]["store_outflow"] / 100, "现金流口径", "不等同于当期费用"],
        ["个人消费", overview["fund_movement_totals_minor"]["personal_outflow"] / 100, "已剔除", "不进入店铺利润"],
        ["食材与包装成本", None, "阻断", "补期初/期末库存、领用、报损与包装单价"],
        ["平台佣金/配送/推广", None, "阻断", "由外卖经营模块拆平台对账单"],
        ["员工/房租/水电", None, "不完整", "补工资、加班、水电、房租归属期"],
        ["经营净利润", None, "不可确认", "全部必需成本闭环后计算"],
        ["经营资金差额（非利润）",
         Formula("ROUND(B6-B8,2)", (overview["merchant_net_minor"] - overview["fund_movement_totals_minor"]["store_outflow"]) / 100),
         "现金链参考", "仅用于判断资金是否够用"],
    ]

    professional_sheets = [
        FinanceSheet(
            name="财务驾驶舱", title="大口章鱼烧｜财务驾驶舱",
            subtitle=f"{start_date} 至 {end_date}　实际到手不是利润；结算到账不是新增收入；个人消费不进入店铺利润",
            headers=["指标", "金额/数量", "状态与口径"],
            rows=[
                ["报表期间", None, f"{start_date} ~ {end_date}"],
                ["实际到手营业额", Formula(f"ROUND('每日经营结账'!J{6 + len(daily_rows) - 1},2)", overview["merchant_net_minor"] / 100), "老板第一经营口径；不是利润"],
                ["会计营业收入（已确认部分）", overview["revenue_minor"] / 100, "收入确认与资金到账分开"],
                ["店铺当前可控资金位置累计", overview["funds_minor"]["store_controlled"] / 100, "需与银行实时余额复核"],
                ["店铺多渠道实际流出", overview["fund_movement_totals_minor"]["store_outflow"] / 100, "银行卡/微信/支付宝/现金等"],
                ["个人消费（已剔除）", overview["fund_movement_totals_minor"]["personal_outflow"] / 100, "不进入店铺利润"],
                ["经营资金差额", Formula("ROUND(B7-B10,2)", (overview["merchant_net_minor"] - overview["fund_movement_totals_minor"]["store_outflow"]) / 100), "不是利润"],
                ["借款待还本金", debt["outstanding_minor"] / 100, "转让费是资金用途，不重复增加负债"],
                ["凭证引用数", len(vouchers), "原图保留在门店凭证库存"],
                ["安全储备金", forecast["safety_reserve_minor"] / 100, "未来资金计划的预警基准"],
                ["7天预计期末资金", forecast["horizons"][0]["ending_minor"] / 100, {"safe": "安全", "partial": "资料待补", "at_risk": "存在缺口"}.get(forecast["status"], forecast["status"])],
                ["14天预计期末资金", forecast["horizons"][1]["ending_minor"] / 100, {"safe": "安全", "partial": "资料待补", "at_risk": "存在缺口"}.get(forecast["status"], forecast["status"])],
                ["30天预计期末资金", forecast["horizons"][2]["ending_minor"] / 100, {"safe": "安全", "partial": "资料待补", "at_risk": "存在缺口"}.get(forecast["status"], forecast["status"])],
                ["利润状态", None, "已确认" if overview["profit_status"] == "confirmed" else "成本、库存和平台扣费未闭环，不可确认"],
            ],
            widths=[34, 22, 72], currency_columns={2},
        ),
        FinanceSheet(
            name="每日经营结账", title="大口章鱼烧｜每日经营结账",
            subtitle="每晚只确认实际到手、资金位置、当日流出和凭证；公式自动汇总，不要求当晚猜利润",
            headers=daily_headers, rows=daily_rows, widths=sheets[1][2],
            currency_columns=set(range(2, 12)), integer_columns={12}, date_columns={1},
            total_rows={len(daily_rows)},
        ),
        FinanceSheet(
            name="统一资金流水账", title="大口章鱼烧｜统一资金流水账",
            subtitle="营业流入、店铺支出、个人消费、内部转账和平台结算统一查看；业务归属决定是否进入店铺经营",
            headers=["事实日期", "大类", "具体类别", "方向", "业务归属", "金额(元)", "收付账户/渠道", "对方账户/资金位置", "交易对方", "摘要", "凭证编号", "状态", "损益处理"],
            rows=unified_rows, widths=[15, 20, 22, 12, 14, 16, 24, 26, 20, 30, 25, 16, 42],
            currency_columns={6}, date_columns={1},
        ),
        FinanceSheet(
            name="未来资金计划", title="大口章鱼烧｜未来资金计划",
            subtitle=f"截至 {end_date} 的未来30天收付计划。浅蓝格可填写；预计余额和安全线差额自动计算",
            headers=["到期日", "类别", "收付类型", "对方", "优先级", "金额(元)", "状态", "来源编号", "备注", "净影响", "预计余额", "距安全线"],
            rows=plan_rows, widths=[15, 18, 16, 22, 16, 16, 16, 24, 38, 16, 18, 18],
            currency_columns={6, 10, 11, 12}, date_columns={1},
            input_columns=set(range(1, 10)),
            validations=[(3, "预计流入,必须支出"), (5, "必须支付,预计,可选"), (7, "planned,confirmed,paid,cancelled")],
            negative_warning_column=12,
        ),
        FinanceSheet(
            name="账户与对账", title="大口章鱼烧｜账户与对账",
            subtitle="工商银行作为店铺专用资金账户；招商银行作为个人账户。表内余额是流水位置，不冒充银行实时余额",
            headers=list(sheets[3][1][0]), rows=[list(row) for row in sheets[3][1][1:]],
            widths=sheets[3][2], currency_columns={5},
        ),
        FinanceSheet(
            name="借款与接店成本", title="大口章鱼烧｜借款与接店成本",
            subtitle="借款本金、还款义务和转让费等资金用途分开；接店用途不会重复增加负债",
            headers=list(sheets[4][1][0]), rows=[list(row) for row in sheets[4][1][1:]],
            widths=sheets[4][2], currency_columns={4, 5},
        ),
        FinanceSheet(
            name="凭证索引", title="大口章鱼烧｜凭证索引与图片库存",
            subtitle="每条记录保留业务日期、来源单元格、原图片路径与 SHA-256；产品内可追溯原始凭证",
            headers=list(sheets[5][1][0]), rows=[list(row) for row in sheets[5][1][1:]],
            widths=sheets[5][2], currency_columns={5}, date_columns={2},
        ),
        FinanceSheet(
            name="利润与现金流", title="大口章鱼烧｜利润与现金流",
            subtitle="利润表遵循权责发生与存货成本口径；现金链用于判断房租、进货、工资是否付得出，两者不能混用",
            headers=["项目", "金额(元)", "状态", "仍需资料/说明"],
            rows=profit_rows, widths=[36, 20, 20, 66], currency_columns={2},
        ),
        FinanceSheet(
            name="检查与口径", title="大口章鱼烧｜完整性检查与财务口径",
            subtitle="系统自动检查借贷平衡、资金链预警和关键资料缺口；PARTIAL 表示已有数据可用，但不能据此确认净利润",
            headers=["编码", "级别", "问题/口径", "金额或数量"],
            rows=[
                *[[item["code"], item["severity"], item["title"], item.get("amount_minor", 0) / 100] for item in alerts],
                ["LEDGER_BALANCE", "check", "借贷平衡", 0 if not ledger.unbalanced_entries(project_id) else len(ledger.unbalanced_entries(project_id))],
                ["PROFIT_COMPLETENESS", "PARTIAL" if overview["profit_status"] != "confirmed" else "CONFIRMED", "实际到手营业额不能直接当作利润", None],
                ["SETTLEMENT_RULE", "policy", "平台钱包或前老板转入银行卡只改变资金位置，不重复确认收入", None],
                ["PERSONAL_RULE", "policy", "个人消费必须与店铺经营剥离", None],
                ["INVENTORY_RULE", "policy", "采购先进入存货，按领用/销售结转成本", None],
            ],
            widths=[30, 18, 74, 20], currency_columns={4},
        ),
        FinanceSheet(
            name="分类字典", title="大口章鱼烧｜财务分类字典",
            subtitle="产品录入与导出台账共用同一稳定分类；大类用于分析，具体类别用于快速选择，会计科目只负责过账",
            headers=["大类编码", "大类", "类别编码", "具体类别", "默认方向", "业务归属", "会计科目", "财务处理"],
            rows=[
                [
                    group["key"], group["name"], item["key"], item["name"],
                    {"inflow": "流入", "outflow": "流出", "transfer": "调拨"}.get(item["direction"], item["direction"]),
                    {"store": "店铺", "personal": "个人", "mixed": "混合", "unknown": "待确认"}.get(item["business_scope"], item["business_scope"]),
                    item["account_code"],
                    {
                        "revenue": "计入营业收入", "contra_revenue": "冲减营业收入", "inventory": "先进入库存",
                        "inventory_adjustment": "调整库存", "cost": "计入销售成本", "expense": "计入经营费用",
                        "asset": "形成资产或长期投入", "liability": "形成或减少负债", "equity": "老板权益往来",
                        "excluded_personal": "个人资金，不计店铺损益", "fund_transfer": "只改变资金位置",
                        "receivable": "形成应收", "receivable_settlement": "核销应收", "excluded": "不计经营",
                        "pending_classification": "等待分类", "expense_when_accrued": "按薪酬规则计入费用",
                        "liability_to_owner": "老板垫付款往来",
                    }.get(item["accounting_treatment"], item["accounting_treatment"]),
                ]
                for group in finance_category_catalog()["groups"]
                for item in group["items"]
            ],
            widths=[20, 22, 30, 24, 14, 14, 14, 28],
        ),
    ]
    content = build_finance_workbook(professional_sheets)
    filename = f"finance-{project_id}-{overview['period_start']}-{overview['period_end']}.xlsx"
    return StreamingResponse(
        BytesIO(content),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


class FinanceRequest(BaseModel):
    investment: str = Field("10万", description="总投资额")
    daily_revenue: str = Field("1000", description="日均营业额（元）")
    daily_cost_rate: str = Field("0.35", description="食材成本率")
    rent_monthly: str = Field("3000", description="月租金（元）")
    labor_monthly: str = Field("5000", description="月人工（元）")
    other_monthly: str = Field("1000", description="月其他费用（元）")


@router.post("/finance", deprecated=True)
async def finance_endpoint(req: FinanceRequest):
    """财务测算端点 — 返回结构化 JSON。

    ⚠️ 已废弃：筹备期投资回本测算口径，请使用 /api/analyze 或 /api/reports。
    """
    logger.warning("POST /api/finance is deprecated (筹备期口径残留). Use /api/analyze or /api/reports instead.")
    try:
        invest = float(req.investment.replace("万", "")) * 10000 if "万" in req.investment else float(req.investment)
        rev = float(req.daily_revenue)
        cost_r = float(req.daily_cost_rate)
        rent = float(req.rent_monthly)
        labor = float(req.labor_monthly)
        other = float(req.other_monthly)

        daily_cost = rev * cost_r
        daily_gross = rev - daily_cost
        monthly_fixed = rent + labor + other
        monthly_net = (daily_gross * 30) - monthly_fixed
        break_even = monthly_fixed / (1 - cost_r) / 30 if cost_r < 1 else float('inf')
        payback = invest / monthly_net if monthly_net > 0 else float('inf')
        net_margin = monthly_net / (rev * 30) * 100 if rev > 0 else 0

        return {
            "success": True,
            "data": {
                "investment": round(invest),
                "daily_revenue": round(rev, 1),
                "daily_gross_profit": round(daily_gross),
                "monthly_fixed_cost": round(monthly_fixed),
                "monthly_net_profit": round(monthly_net),
                "break_even_daily_revenue": round(break_even),
                "payback_months": round(payback, 1) if payback != float('inf') else None,
                "net_margin_pct": round(net_margin, 1),
                "profitable": monthly_net > 0,
            },
        }
    except Exception as exc:
        return {"success": False, "error": str(exc)}
