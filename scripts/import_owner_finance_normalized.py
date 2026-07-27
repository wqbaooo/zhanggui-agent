#!/usr/bin/env python3
"""Import the owner's normalized workbook ledger and immutable image vouchers.

The source workbook is never modified. Run this only with a normalized JSON file
created from the owner's reviewed workbook; the import is idempotent by business
date/channel, movement reference, voucher key, and debt key.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import config
from models.finance_ledger import FinanceLedger, money_to_minor


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("normalized_json", type=Path)
    parser.add_argument("--project-id", default="xinyu-hengtai-dakou")
    return parser.parse_args()


def _copy_voucher(source: Path, destination_dir: Path) -> tuple[str, Path]:
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = destination_dir / f"{digest[:16]}{source.suffix.lower()}"
    if not destination.exists():
        shutil.copy2(source, destination)
    return digest, destination


def import_normalized(payload: dict[str, Any], project_id: str) -> dict[str, Any]:
    metadata = payload["metadata"]
    ledger = FinanceLedger.for_project(project_id)
    ledger.ensure_store(project_id, metadata["storeName"], metadata["periodStart"])

    account_ids: dict[str, str] = {}
    for account in payload["accounts"]:
        account_ids[account["key"]] = ledger.upsert_fund_account(
            project_id,
            account_key=account["key"],
            name=account["name"],
            account_kind=account["kind"],
            owner_kind=account["ownerKind"],
            is_store_controlled=bool(account["controlled"]),
            institution=account.get("institution"),
            masked_number=account.get("maskedNumber"),
            effective_from=account.get("effectiveFrom"),
            effective_to=account.get("effectiveTo"),
            status=account.get("status", "active"),
        )

    evidence_dir = config.PROJECT_DATA_DIR / project_id / "documents" / "evidence" / "owner-finance-20260716"
    voucher_count = 0
    for voucher in payload["vouchers"]:
        source_path = Path(voucher["sourceImagePath"])
        if not source_path.exists():
            raise FileNotFoundError(f"凭证原图不存在: {source_path}")
        sha256, destination = _copy_voucher(source_path, evidence_dir)
        relative_path = destination.relative_to(config.PROJECT_DATA_DIR / project_id).as_posix()
        ledger.register_evidence_voucher(
            project_id,
            voucher_key=voucher["voucherKey"],
            business_date=voucher.get("businessDate"),
            evidence_type=voucher["evidenceType"],
            channel=voucher.get("channel"),
            amount_minor=money_to_minor(voucher.get("amount")) if voucher.get("amount") is not None else None,
            source_sheet=voucher.get("sourceSheet"),
            source_cell=voucher.get("sourceCell"),
            original_filename=voucher["originalFilename"],
            original_path=relative_path,
            sha256=sha256,
            status=voucher["status"],
            notes=voucher.get("notes"),
        )
        voucher_count += 1

    voucher_numbers = {
        row["voucher_key"]: row["voucher_number"]
        for row in ledger.list_evidence_vouchers(project_id)
    }

    for sale in payload["merchantNetSales"]:
        voucher_number = voucher_numbers.get(sale.get("voucherKey"))
        ledger.record_merchant_net_sale(
            project_id,
            business_date=sale["businessDate"],
            channel=sale["channel"],
            amount_minor=money_to_minor(sale["amount"]),
            reference_gross_minor=money_to_minor(sale["referenceGross"]) if sale.get("referenceGross") is not None else None,
            source_basis=sale["sourceBasis"],
            evidence_status=sale["evidenceStatus"],
            settlement_state=sale["settlementState"],
            current_fund_account_id=account_ids.get(sale.get("currentAccountKey")),
            evidence_reference=voucher_number,
            notes=sale.get("notes"),
        )

    all_outflows = [*payload["storeOutflows"], *payload["personalOutflows"]]
    for movement in all_outflows:
        ledger.record_fund_movement(
            project_id,
            occurred_on=movement["occurredOn"],
            amount_minor=money_to_minor(movement["amount"]),
            movement_type="store_outflow" if movement["businessScope"] == "store" else "personal_outflow",
            from_fund_account_id=account_ids.get(movement.get("fromAccountKey")),
            to_fund_account_id=account_ids.get(movement.get("toAccountKey")),
            business_scope=movement["businessScope"],
            purpose=movement["item"],
            counterparty=movement.get("counterparty"),
            evidence_reference=voucher_numbers.get(movement.get("voucherKey")),
            status="confirmed",
            reference=movement["reference"],
            notes=(
                f"原分类：{movement.get('originalCategory') or '未填'}；"
                f"支付渠道：{movement.get('paymentChannel') or '未填'}；"
                f"会计分类：{movement['classification']}；明细：{movement.get('details') or '无'}"
            ),
        )

    for debt in payload["debts"]:
        debt_id = ledger.record_debt(
            project_id,
            debt_key=debt["debtKey"],
            lender=debt["lender"],
            principal_minor=money_to_minor(debt["principal"]),
            received_on=debt["receivedOn"],
            status=debt["status"],
            notes=debt.get("notes"),
        )
        for allocation in debt.get("allocations", []):
            ledger.record_debt_allocation(
                project_id,
                debt_id=debt_id,
                allocation_key=allocation["key"],
                purpose=allocation["purpose"],
                amount_minor=money_to_minor(allocation["amount"]),
                classification=allocation["classification"],
                notes=allocation.get("notes"),
            )

    start, end = metadata["periodStart"], metadata["periodEnd"]
    store_outflows_minor = sum(
        row["amount_minor"]
        for row in ledger.list_fund_movements(project_id, start, end)
        if row["business_scope"] == "store" and row["movement_type"] == "store_outflow"
    )
    personal_outflows_minor = sum(
        row["amount_minor"]
        for row in ledger.list_fund_movements(project_id, start, end)
        if row["business_scope"] == "personal" and row["movement_type"] == "personal_outflow"
    )
    return {
        "project_id": project_id,
        "period": {"start": start, "end": end},
        "merchant_net_minor": ledger.merchant_net_total(project_id, start, end),
        "store_outflows_minor": store_outflows_minor,
        "personal_outflows_minor": personal_outflows_minor,
        "voucher_rows": voucher_count,
        "voucher_files": len({row["sha256"] for row in ledger.list_evidence_vouchers(project_id)}),
        "debt_summary": ledger.debt_summary(project_id),
    }


def main() -> None:
    args = parse_args()
    payload = json.loads(args.normalized_json.read_text(encoding="utf-8"))
    print(json.dumps(import_normalized(payload, args.project_id), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
