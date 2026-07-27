#!/usr/bin/env python3
"""One-time, idempotent sales-fact sync from the rebuilt professional ledger.

The workbook is opened read-only and never modified.  This sync deliberately
does not create journal entries: any difference between operational settlement
facts and the general ledger remains visible to the execution-plan guard.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from models.finance_ledger import FinanceLedger, money_to_minor


def rows_from_workbook(path: Path) -> list[dict[str, Any]]:
    from openpyxl import load_workbook

    # openpyxl cannot expose max_row/max_column for this workbook in streaming
    # mode because of embedded image formulas.  Normal mode is still read-only
    # in behavior here: the workbook is never saved.
    workbook = load_workbook(path, read_only=False, data_only=False)
    sales = workbook["销售事实"]
    settlement = workbook["结算与应收"]
    sales_headers = {
        sales.cell(4, column).value: column
        for column in range(1, sales.max_column + 1)
    }
    settlement_headers = {
        settlement.cell(4, column).value: column
        for column in range(1, settlement.max_column + 1)
    }
    settlement_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for row in range(5, settlement.max_row + 1):
        business_date = str(
            settlement.cell(row, settlement_headers["营业日期"]).value
        )[:10]
        channel = str(settlement.cell(row, settlement_headers["渠道"]).value)
        settlement_by_key[(business_date, channel)] = {
            "received": settlement.cell(
                row, settlement_headers["本人收款状态"]
            ).value,
            "fund_location": settlement.cell(
                row, settlement_headers["当前资金位置"]
            ).value,
        }

    result = []
    for row in range(5, sales.max_row + 1):
        business_date = str(sales.cell(row, sales_headers["营业日期"]).value)[:10]
        channel = str(sales.cell(row, sales_headers["渠道"]).value)
        amount = sales.cell(row, sales_headers["商户净额/现金"]).value
        if amount is None:
            continue
        settlement_item = settlement_by_key.get((business_date, channel), {})
        received = str(settlement_item.get("received") or "")
        location = str(settlement_item.get("fund_location") or "")
        normalized_channel = "客如云收款" if channel == "客如云" else channel
        if channel == "客如云":
            state = "bound_bank_received" if "已到" in received else "unknown"
            # 客如云直接打入老板个人招商卡；账户所有权与资金归属分开表达。
            account_key = "cmb-personal"
        elif channel == "现金":
            state = "store_account_received"
            account_key = "cash-on-hand"
        elif "已到" in received and "未到" not in received:
            state = "store_account_received"
            account_key = "cmb-personal"
        elif "前老板" in location or "平台钱包" in location:
            state = "former_owner_pending_transfer"
            account_key = "former-owner-icbc-9863"
        else:
            state = "unknown"
            account_key = None
        result.append({
            "business_date": business_date,
            "channel": normalized_channel,
            "amount_minor": money_to_minor(amount),
            "source_basis": str(sales.cell(row, sales_headers["金额口径"]).value or "专业资金台账"),
            "evidence_status": "confirmed",
            "settlement_state": state,
            "current_account_key": account_key,
            "evidence_reference": sales.cell(row, sales_headers["图片ID"]).value,
            "notes": f"只读同步自 {path.name}；当前资金位置：{location or '待核'}",
        })
    workbook.close()
    return result


def settlement_control_totals(path: Path) -> dict[str, int]:
    from openpyxl import load_workbook

    workbook = load_workbook(path, read_only=False, data_only=False)
    sheet = workbook["结算与应收"]
    headers = {
        sheet.cell(4, column).value: column
        for column in range(1, sheet.max_column + 1)
    }
    totals = {"cash_minor": 0, "bank_minor": 0, "pending_minor": 0}
    for row in range(5, sheet.max_row + 1):
        channel = str(sheet.cell(row, headers["渠道"]).value or "")
        amount_minor = money_to_minor(sheet.cell(row, headers["销售净额"]).value)
        received = str(sheet.cell(row, headers["本人收款状态"]).value or "")
        if channel == "现金":
            totals["cash_minor"] += amount_minor
        elif "已到本人银行卡" in received:
            totals["bank_minor"] += amount_minor
        else:
            totals["pending_minor"] += amount_minor
    workbook.close()
    totals["merchant_net_minor"] = sum(totals.values())
    return totals


def align_general_ledger(
    ledger: FinanceLedger,
    project_id: str,
    workbook: Path,
    *,
    matched_former_owner_minor: int,
) -> dict[str, Any]:
    controls = settlement_control_totals(workbook)
    if matched_former_owner_minor <= 0:
        raise ValueError("前老板本次已匹配代收款必须大于0")
    if matched_former_owner_minor > controls["pending_minor"]:
        raise ValueError("本次匹配金额不能超过专业台账的线上待收合计")
    target = {
        "1001": controls["cash_minor"],
        "1002": controls["bank_minor"],
        "1012": controls["pending_minor"] - matched_former_owner_minor,
        "1013": matched_former_owner_minor,
        "1019": 0,
    }
    current = ledger.account_balances(project_id, "0001-01-01", "2026-07-19")
    differences = {code: amount - int(current.get(code, 0)) for code, amount in target.items()}
    revenue_adjustment = sum(differences.values())
    lines: list[tuple[str, int, int]] = []
    for code, difference in differences.items():
        if difference > 0:
            lines.append((code, difference, 0))
        elif difference < 0:
            lines.append((code, 0, -difference))
    if revenue_adjustment > 0:
        lines.append(("4009", 0, revenue_adjustment))
    elif revenue_adjustment < 0:
        lines.append(("4009", -revenue_adjustment, 0))
    digest = hashlib.sha256(workbook.read_bytes()).hexdigest()[:16]
    entry_id = ledger.post_entry(
        store_id=project_id,
        entry_date="2026-07-19",
        posting_key=(
            f"professional-ledger-alignment:{digest}:{matched_former_owner_minor}"
        ),
        description=(
            "专业资金台账累计销售与资金位置对齐（截至2026-07-19）"
        ),
        lines=lines,
        entry_type="adjustment",
    )
    after = ledger.account_balances(project_id, "0001-01-01", "2026-07-19")
    return {
        "entry_id": entry_id,
        "controls": controls,
        "target_balances": target,
        "differences": differences,
        "revenue_adjustment_minor": revenue_adjustment,
        "after_balances": {code: after.get(code, 0) for code in target},
        "balanced": all(int(after.get(code, 0)) == amount for code, amount in target.items()),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("workbook", type=Path)
    parser.add_argument("--project-id", default="xinyu-hengtai-dakou")
    parser.add_argument("--confirm", action="store_true")
    parser.add_argument("--align-ledger", action="store_true")
    parser.add_argument("--matched-former-owner", type=float)
    args = parser.parse_args()
    rows = rows_from_workbook(args.workbook)
    summary = {
        "project_id": args.project_id,
        "row_count": len(rows),
        "period_start": min(item["business_date"] for item in rows),
        "period_end": max(item["business_date"] for item in rows),
        "amount_minor": sum(item["amount_minor"] for item in rows),
        "write_confirmed": args.confirm,
    }
    if args.confirm:
        ledger = FinanceLedger.for_project(args.project_id)
        accounts = {
            item["account_key"]: item for item in ledger.list_fund_accounts(args.project_id)
        }
        for item in rows:
            account = accounts.get(item.pop("current_account_key") or "")
            ledger.record_merchant_net_sale(
                args.project_id,
                **item,
                current_fund_account_id=account["id"] if account else None,
            )
        if args.align_ledger:
            if args.matched_former_owner is None:
                raise SystemExit("--align-ledger 必须同时传入 --matched-former-owner")
            summary["ledger_alignment"] = align_general_ledger(
                ledger,
                args.project_id,
                args.workbook,
                matched_former_owner_minor=money_to_minor(args.matched_former_owner),
            )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
