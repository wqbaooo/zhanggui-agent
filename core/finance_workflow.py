"""Load versioned, store-specific collection routes into the finance ledger."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from models.finance_ledger import FinanceLedger


def sync_finance_workflow_config(
    ledger: "FinanceLedger", store_id: str, project_dir: Path
) -> None:
    path = project_dir / "finance_workflow.json"
    if not path.exists():
        return
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") not in {"finance_workflow_config_v1", "finance_workflow_config_v2"}:
        raise ValueError("不支持的财务流程配置版本")
    ledger.upsert_fund_account(
        store_id,
        account_key="planned-store-icbc",
        name="工商银行店铺账户",
        account_kind="bank",
        owner_kind="store",
        is_store_controlled=True,
        institution="工商银行",
        status="active",
    )
    # Owner-confirmed correction (2026-07-26): store sales receipts belong in
    # the ICBC store account.  Only the derived location on merchant sales is
    # corrected; personal CMB movements and every original voucher stay intact.
    with ledger.connect() as connection:
        already_applied = connection.execute(
            "SELECT 1 FROM schema_migrations WHERE version=12"
        ).fetchone()
        if not already_applied:
            store_bank = connection.execute(
                "SELECT id FROM fund_accounts WHERE store_id=? AND account_key='planned-store-icbc'",
                (store_id,),
            ).fetchone()
            personal_cmb = connection.execute(
                "SELECT id FROM fund_accounts WHERE store_id=? AND account_key='cmb-personal'",
                (store_id,),
            ).fetchone()
            if store_bank and personal_cmb:
                connection.execute(
                    """UPDATE merchant_net_sales SET
                         current_fund_account_id=?, settlement_state='store_account_received',
                         notes=TRIM(COALESCE(notes || '；', '') ||
                           '账户口径更正：店主于2026-07-26确认店铺营业款进入工商银行店铺账户，原凭证保留'),
                         updated_at=datetime('now')
                       WHERE store_id=? AND current_fund_account_id=?
                         AND settlement_state IN ('store_account_received','bound_bank_received')""",
                    (store_bank["id"], store_id, personal_cmb["id"]),
                )
            connection.execute(
                "INSERT INTO schema_migrations(version, name, applied_at) VALUES (12, ?, datetime('now'))",
                ("owner_confirmed_store_sales_to_icbc",),
            )
        bound_card_fix = connection.execute(
            "SELECT 1 FROM schema_migrations WHERE version=13"
        ).fetchone()
        if not bound_card_fix:
            bound_card = connection.execute(
                "SELECT id FROM fund_accounts WHERE store_id=? AND account_key='former-owner-icbc-9863'",
                (store_id,),
            ).fetchone()
            if bound_card:
                connection.execute(
                    """UPDATE merchant_net_sales SET
                         settlement_state='bound_bank_received',
                         notes=TRIM(COALESCE(notes || '；', '') ||
                           '状态口径更正：已到平台绑定卡，尚未核销至工商银行店铺账户'),
                         updated_at=datetime('now')
                       WHERE store_id=? AND current_fund_account_id=?
                         AND settlement_state='store_account_received'""",
                    (store_id, bound_card["id"]),
                )
            connection.execute(
                "INSERT INTO schema_migrations(version, name, applied_at) VALUES (13, ?, datetime('now'))",
                ("bound_card_is_not_store_bank_arrival",),
            )
    for item in payload.get("platform_collection_bindings") or []:
        existing = next(
            (
                row for row in ledger.list_platform_collection_bindings(store_id)
                if str(row["platform"]) == str(item["platform"])
                and str(row["effective_from"]) == str(item["effective_from"])
            ),
            None,
        )
        if existing and payload.get("schema_version") == "finance_workflow_config_v2":
            with ledger.connect() as connection:
                connection.execute(
                    """UPDATE platform_collection_bindings SET
                         destination_account_key=?, settlement_rule=?,
                         settlement_delay_days=?, settlement_day_basis=?,
                         settlement_rule_status=?, settlement_rule_source=?,
                         settlement_delay_target=?, withdrawal_mode=?, notes=?,
                         updated_at=datetime('now') WHERE id=? AND store_id=?""",
                    (
                        item.get("destination_account_key"), item.get("settlement_rule"),
                        item.get("settlement_delay_days"), item.get("settlement_day_basis"),
                        item.get("settlement_rule_status") or "unknown",
                        item.get("settlement_rule_source"),
                        item.get("settlement_delay_target") or "bound_bank",
                        item.get("withdrawal_mode") or "automatic",
                        item.get("notes"),
                        existing["id"], store_id,
                    ),
                )
        elif not existing:
            ledger.upsert_platform_collection_binding(
                store_id,
                platform=str(item["platform"]),
                collector_account_key=str(item["collector_account_key"]),
                destination_account_key=item.get("destination_account_key"),
                collector_owner_kind=str(item["collector_owner_kind"]),
                settlement_rule=item.get("settlement_rule"),
                settlement_delay_days=item.get("settlement_delay_days"),
                settlement_day_basis=item.get("settlement_day_basis"),
                settlement_rule_status=str(item.get("settlement_rule_status") or "unknown"),
                settlement_rule_source=item.get("settlement_rule_source"),
                settlement_delay_target=str(item.get("settlement_delay_target") or "bound_bank"),
                withdrawal_mode=str(item.get("withdrawal_mode") or "automatic"),
                effective_from=str(item["effective_from"]),
                effective_to=item.get("effective_to"),
                status=str(item.get("status") or "active"),
                notes=item.get("notes"),
            )
    with ledger.connect() as connection:
        connection.execute(
            """UPDATE fund_accounts
               SET status='active', effective_to=NULL
               WHERE store_id=? AND account_key IN (
                 SELECT DISTINCT collector_account_key
                 FROM platform_collection_bindings
                 WHERE store_id=? AND status='active'
               )""",
            (store_id, store_id),
        )
