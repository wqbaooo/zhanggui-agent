#!/usr/bin/env python3
"""Migrate confirmed daily revenue from the legacy store JSON into finance.db."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config import PROJECT_DATA_DIR
from models.finance_ledger import FinanceLedger


DEFAULT_PROJECT_ID = "xinyu-hengtai-dakou"


def migrate(project_id: str, data_dir: Path) -> dict:
    project_dir = data_dir / project_id
    source = project_dir / "memory.json"
    if not source.exists():
        raise FileNotFoundError(f"找不到迁移源：{source}")
    payload = json.loads(source.read_text(encoding="utf-8"))
    ledger = FinanceLedger(project_dir / "finance.db")
    ledger.initialize()
    migration = ledger.migrate_daily_operations(payload)
    start, end = "2026-07-01", "2026-07-10"
    audit = {
        **migration,
        "database": str(ledger.db_path),
        "period_start": start,
        "period_end": end,
        "revenue_minor": ledger.revenue_total(project_id, start, end),
        "orders": ledger.order_total(project_id, start, end),
        "posted_entries": ledger.count_posted_entries(project_id),
        "unbalanced_entries": ledger.unbalanced_entries(project_id),
        "account_balances_minor": ledger.account_balances(project_id, start, end),
        "profit_readiness": ledger.profit_readiness(project_id, start, end),
    }
    audit_path = project_dir / "finance_migration_v1_audit.json"
    audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    return audit


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-id", default=DEFAULT_PROJECT_ID)
    parser.add_argument("--data-dir", type=Path, default=PROJECT_DATA_DIR)
    args = parser.parse_args()
    print(json.dumps(migrate(args.project_id, args.data_dir), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
