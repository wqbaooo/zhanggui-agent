"""SQLite-backed finance ledger for the real single-store operating model."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Iterable
from zoneinfo import ZoneInfo


SCHEMA_PATH = Path(__file__).parents[1] / "docs" / "finance" / "schema_v1.sql"


class FinanceMigrationError(ValueError):
    """Raised when a finance fact cannot be posted without breaking the contract."""


ACCOUNT_SEED = (
    ("1001", "现金", "asset"),
    ("1002", "银行及已确认数字收款", "asset"),
    ("1012", "平台待结算", "asset"),
    ("1013", "其他应收款—前老板", "asset"),
    ("1019", "待核对收款", "asset"),
    ("1401", "原材料库存", "asset"),
    ("1402", "包装耗材库存", "asset"),
    ("1410", "预付供应商货款", "asset"),
    ("1601", "固定资产", "asset"),
    ("1801", "押金及长期待摊", "asset"),
    ("2001", "应付供应商", "liability"),
    ("2002", "应付员工薪酬", "liability"),
    ("2003", "借款", "liability"),
    ("2009", "应计费用与其他应付", "liability"),
    ("3001", "老板投入", "equity"),
    ("3002", "老板取款", "equity"),
    ("4001", "营业收入—堂食", "revenue"),
    ("4002", "营业收入—外卖", "revenue"),
    ("4003", "营业收入—团购", "revenue"),
    ("4009", "营业收入—待拆分渠道", "revenue"),
    ("4004", "退款与销售调整", "contra_revenue"),
    ("5001", "食材销售成本", "cost"),
    ("5002", "包装耗材成本", "cost"),
    ("5003", "平台佣金与配送", "expense"),
    ("5004", "活动与推广", "expense"),
    ("5005", "报损与盘亏", "cost"),
    ("6001", "员工工资", "expense"),
    ("6002", "房租与商场费", "expense"),
    ("6003", "水电燃气", "expense"),
    ("6004", "系统与服务费", "expense"),
    ("6005", "维修、清洁与杂费", "expense"),
    ("6006", "折旧与摊销", "expense"),
    ("6007", "证照、培训与健康检查", "expense"),
    ("6008", "加盟、品牌与管理费", "expense"),
    ("6009", "税费及附加", "expense"),
    ("6010", "利息与融资费用", "expense"),
    ("9001", "老板机会成本", "management_only"),
)

FORMER_OWNER_METHODS = {
    "美团外卖", "淘宝闪购餐饮", "饿了么外卖", "抖音团购券",
    "美团团购券", "京东外卖", "京东秒送",
}

# This product serves one real store.  These are the seven recurring daily
# revenue facts the owner expects to confirm, in the order used at close.
# Arrival is deliberately absent from this contract: it is a later fund event.
DAILY_REVENUE_CHANNELS: tuple[dict[str, Any], ...] = (
    {"channel": "客如云收款", "kind": "pos", "display_order": 10},
    {"channel": "现金", "kind": "cash", "display_order": 20},
    {"channel": "美团外卖", "kind": "delivery", "display_order": 30},
    {"channel": "淘宝闪购", "kind": "delivery", "display_order": 40},
    {"channel": "美团团购", "kind": "group_buy", "display_order": 50},
    {"channel": "抖音团购", "kind": "group_buy", "display_order": 60},
    {"channel": "京东外卖", "kind": "delivery", "display_order": 70},
)

METRIC_REGISTRY = {
    "revenue": {
        "version": "1.0",
        "label": "营业收入",
        "formula": "已确认销售收入 - 销售退回与调整",
        "basis": "journal_entries",
        "required_inputs": ["revenue_facts_confirmed"],
        "blocking_rules": ["收入主证据未确认"],
    },
    "average_order_value": {
        "version": "1.0",
        "label": "客单价",
        "formula": "营业收入 / 有效订单数",
        "basis": "sales_daily",
        "required_inputs": ["revenue", "orders"],
        "blocking_rules": ["订单口径未知"],
    },
    "gross_profit": {
        "version": "1.0",
        "label": "营业毛利",
        "formula": "营业收入 - 食材 - 包装",
        "basis": "journal_entries",
        "required_inputs": ["revenue", "food_cost", "packaging_cost"],
        "blocking_rules": ["销售成本未确认"],
    },
    "contribution_margin": {
        "version": "1.0",
        "label": "贡献毛利",
        "formula": "营业收入 - 全部变动成本",
        "basis": "journal_entries",
        "required_inputs": ["revenue", "food_cost", "packaging_cost", "platform_cost", "marketing_cost"],
        "blocking_rules": ["平台/活动/包装成本不完整"],
    },
    "operating_net_profit": {
        "version": "1.0",
        "label": "经营净利润",
        "formula": "贡献毛利 - 固定经营费用",
        "basis": "journal_entries",
        "required_inputs": ["contribution_margin", "labor", "rent", "utility", "systems", "other"],
        "blocking_rules": ["任一必需成本未确认"],
    },
    "prime_cost": {
        "version": "1.0",
        "label": "Prime Cost",
        "formula": "食材 + 包装 + 员工人工",
        "basis": "journal_entries",
        "required_inputs": ["food_cost", "packaging_cost", "labor"],
        "blocking_rules": ["库存耗用或工资未确认"],
    },
    "monthly_break_even": {
        "version": "1.0",
        "label": "月保本营业额",
        "formula": "月固定成本 / 贡献毛利率",
        "basis": "calculated",
        "required_inputs": ["fixed_cost", "contribution_margin_rate"],
        "blocking_rules": ["贡献毛利率不可用"],
    },
    "cash_coverage_days": {
        "version": "1.0",
        "label": "现金可支撑天数",
        "formula": "可用资金 / 近 N 日平均必要现金支出",
        "basis": "calculated",
        "required_inputs": ["available_cash", "daily_cash_expense"],
        "blocking_rules": ["未实点资金或支出样本不足"],
    },
    "net_margin": {
        "version": "1.0",
        "label": "净利率",
        "formula": "经营净利润 / 营业收入",
        "basis": "calculated",
        "required_inputs": ["operating_net_profit", "revenue"],
        "blocking_rules": ["净利润或营业收入为零"],
    },
    "contribution_margin_rate": {
        "version": "1.0",
        "label": "贡献毛利率",
        "formula": "贡献毛利 / 营业收入",
        "basis": "calculated",
        "required_inputs": ["contribution_margin", "revenue"],
        "blocking_rules": ["贡献毛利或营业收入为零"],
    },
}


def money_to_minor(value: Any) -> int:
    return int((Decimal(str(value or 0)) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


class FinanceLedger:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)

    @classmethod
    def for_project(cls, project_id: str) -> "FinanceLedger":
        import config
        from models.project import ProjectMemory

        ledger = cls(config.PROJECT_DATA_DIR / project_id / "finance.db")
        ledger.initialize()
        from core.finance_workflow import sync_finance_workflow_config

        sync_finance_workflow_config(
            ledger, project_id, config.PROJECT_DATA_DIR / project_id
        )
        memory = ProjectMemory.load(project_id)
        if memory:
            ledger.migrate_daily_operations({
                "project_id": memory.project_id,
                "profile": memory.profile,
                "daily_operations": memory.daily_operations,
            })
        return ledger

    def connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.db_path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 30000")
        return connection

    def initialize(self) -> None:
        schema = SCHEMA_PATH.read_text(encoding="utf-8")
        with self.connect() as connection:
            initialized = connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'schema_migrations'"
            ).fetchone()
            if initialized:
                columns = {row[1] for row in connection.execute("PRAGMA table_info(daily_close_sessions)")}
                if "inputs_json" not in columns:
                    connection.execute("ALTER TABLE daily_close_sessions ADD COLUMN inputs_json TEXT NOT NULL DEFAULT '{}'")
                    connection.execute(
                        "INSERT OR IGNORE INTO schema_migrations(version, name, applied_at) VALUES (2, ?, datetime('now'))",
                        ("daily_close_adjustment_inputs",),
                    )
                self._ensure_operating_cash_schema(connection)
                self._ensure_bookkeeping_category_schema(connection)
                self._ensure_bookkeeping_correction_schema(connection)
                self._ensure_daily_revenue_checklist_schema(connection)
                self._ensure_platform_transfer_matching_schema(connection)
                return
            connection.executescript(schema)
            connection.execute(
                "INSERT OR IGNORE INTO schema_migrations(version, name, applied_at) VALUES (1, ?, datetime('now'))",
                ("finance_schema_v1",),
            )
            self._ensure_operating_cash_schema(connection)
            self._ensure_bookkeeping_category_schema(connection)
            self._ensure_bookkeeping_correction_schema(connection)
            self._ensure_daily_revenue_checklist_schema(connection)
            self._ensure_platform_transfer_matching_schema(connection)

    @staticmethod
    def _ensure_bookkeeping_category_schema(connection: sqlite3.Connection) -> None:
        """Persist stable business categories separately from account codes."""
        columns = {row[1] for row in connection.execute("PRAGMA table_info(bookkeeping_records)")}
        if "business_category_key" not in columns:
            connection.execute("ALTER TABLE bookkeeping_records ADD COLUMN business_category_key TEXT")
        if "business_category_group" not in columns:
            connection.execute("ALTER TABLE bookkeeping_records ADD COLUMN business_category_group TEXT")
        connection.execute(
            "INSERT OR IGNORE INTO schema_migrations(version, name, applied_at) VALUES (8, ?, datetime('now'))",
            ("stable_business_categories",),
        )

    @staticmethod
    def _ensure_bookkeeping_correction_schema(connection: sqlite3.Connection) -> None:
        """Keep posted-data corrections auditable and idempotent."""
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS bookkeeping_corrections (
              id TEXT PRIMARY KEY,
              store_id TEXT NOT NULL REFERENCES stores(id),
              bookkeeping_record_id TEXT NOT NULL REFERENCES bookkeeping_records(id),
              correction_key TEXT NOT NULL,
              before_json TEXT NOT NULL,
              after_json TEXT NOT NULL,
              reason TEXT NOT NULL,
              corrected_by TEXT NOT NULL,
              created_at TEXT NOT NULL DEFAULT (datetime('now')),
              UNIQUE (store_id, correction_key)
            );
            CREATE INDEX IF NOT EXISTS idx_bookkeeping_corrections_record
              ON bookkeeping_corrections(store_id, bookkeeping_record_id);
            """
        )
        connection.execute(
            "INSERT OR IGNORE INTO schema_migrations(version, name, applied_at) VALUES (9, ?, datetime('now'))",
            ("auditable_bookkeeping_corrections",),
        )

    @staticmethod
    def _ensure_daily_revenue_checklist_schema(connection: sqlite3.Connection) -> None:
        """Track explicit zero/not-yet-available states without inventing sales."""
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS daily_revenue_channel_checks (
              id TEXT PRIMARY KEY,
              store_id TEXT NOT NULL REFERENCES stores(id),
              business_date TEXT NOT NULL,
              channel TEXT NOT NULL,
              status TEXT NOT NULL CHECK (status IN ('recorded','confirmed_zero','not_available')),
              merchant_net_sale_id TEXT REFERENCES merchant_net_sales(id),
              notes TEXT,
              created_at TEXT NOT NULL DEFAULT (datetime('now')),
              updated_at TEXT NOT NULL DEFAULT (datetime('now')),
              UNIQUE (store_id, business_date, channel)
            );
            CREATE INDEX IF NOT EXISTS idx_daily_revenue_checks_store_date
              ON daily_revenue_channel_checks(store_id, business_date);
            """
        )
        connection.execute(
            "INSERT OR IGNORE INTO schema_migrations(version, name, applied_at) VALUES (10, ?, datetime('now'))",
            ("daily_revenue_channel_checklist",),
        )

    @staticmethod
    def _ensure_platform_transfer_matching_schema(connection: sqlite3.Connection) -> None:
        """Version platform timing rules and reconcile one weekly transfer to many sales."""
        columns = {
            row[1] for row in connection.execute("PRAGMA table_info(platform_collection_bindings)")
        }
        additions = {
            "settlement_delay_days": "INTEGER",
            "settlement_day_basis": "TEXT",
            "settlement_rule_status": "TEXT NOT NULL DEFAULT 'unknown'",
            "settlement_rule_source": "TEXT",
            "settlement_delay_target": "TEXT NOT NULL DEFAULT 'bound_bank'",
            "withdrawal_mode": "TEXT NOT NULL DEFAULT 'automatic'",
        }
        for column, definition in additions.items():
            if column not in columns:
                connection.execute(
                    f"ALTER TABLE platform_collection_bindings ADD COLUMN {column} {definition}"
                )
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS platform_transfer_batches (
              id TEXT PRIMARY KEY,
              store_id TEXT NOT NULL REFERENCES stores(id),
              transfer_date TEXT NOT NULL,
              arrival_period_start TEXT NOT NULL,
              arrival_period_end TEXT NOT NULL,
              amount_minor INTEGER NOT NULL CHECK (amount_minor > 0),
              expected_minor INTEGER NOT NULL,
              from_account_key TEXT NOT NULL,
              to_account_key TEXT NOT NULL,
              source_reference TEXT NOT NULL,
              evidence_reference TEXT,
              fund_movement_id TEXT REFERENCES fund_movements(id),
              status TEXT NOT NULL CHECK (status IN ('matched','needs_review','void')),
              created_at TEXT NOT NULL DEFAULT (datetime('now')),
              UNIQUE (store_id, source_reference)
            );
            CREATE TABLE IF NOT EXISTS platform_transfer_allocations (
              id TEXT PRIMARY KEY,
              batch_id TEXT NOT NULL REFERENCES platform_transfer_batches(id),
              merchant_net_sale_id TEXT NOT NULL REFERENCES merchant_net_sales(id),
              expected_bank_date TEXT NOT NULL,
              amount_minor INTEGER NOT NULL CHECK (amount_minor > 0),
              created_at TEXT NOT NULL DEFAULT (datetime('now')),
              UNIQUE (batch_id, merchant_net_sale_id),
              UNIQUE (merchant_net_sale_id)
            );
            CREATE INDEX IF NOT EXISTS idx_platform_transfer_batch_store_date
              ON platform_transfer_batches(store_id, transfer_date);
            """
        )
        connection.execute(
            "INSERT OR IGNORE INTO schema_migrations(version, name, applied_at) VALUES (11, ?, datetime('now'))",
            ("platform_transfer_batch_matching",),
        )
        connection.execute(
            "INSERT OR IGNORE INTO schema_migrations(version, name, applied_at) VALUES (14, ?, datetime('now'))",
            ("platform_wallet_and_bank_settlement_targets",),
        )

    @staticmethod
    def _ensure_operating_cash_schema(connection: sqlite3.Connection) -> None:
        """Add the owner-facing cash subledger without rewriting existing books."""
        columns = {row[1] for row in connection.execute("PRAGMA table_info(daily_close_sessions)")}
        for column in ("merchant_net_confirmed", "fund_locations_reviewed", "outflows_reviewed"):
            if column not in columns:
                connection.execute(
                    f"ALTER TABLE daily_close_sessions ADD COLUMN {column} INTEGER NOT NULL DEFAULT 0"
                )
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS fund_accounts (
              id TEXT PRIMARY KEY,
              store_id TEXT NOT NULL REFERENCES stores(id),
              account_key TEXT NOT NULL,
              name TEXT NOT NULL,
              account_kind TEXT NOT NULL CHECK (account_kind IN ('cash','bank','platform_wallet','payment_wallet','clearing')),
              owner_kind TEXT NOT NULL CHECK (owner_kind IN ('store','owner','former_owner','platform','unknown')),
              institution TEXT,
              masked_number TEXT,
              is_store_controlled INTEGER NOT NULL DEFAULT 0,
              opening_balance_minor INTEGER NOT NULL DEFAULT 0,
              effective_from TEXT,
              effective_to TEXT,
              status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','planned','retired','unknown')),
              UNIQUE (store_id, account_key)
            );
            CREATE TABLE IF NOT EXISTS merchant_net_sales (
              id TEXT PRIMARY KEY,
              store_id TEXT NOT NULL REFERENCES stores(id),
              business_date TEXT NOT NULL,
              channel TEXT NOT NULL,
              merchant_net_minor INTEGER NOT NULL CHECK (merchant_net_minor >= 0),
              reference_gross_minor INTEGER,
              source_basis TEXT NOT NULL,
              evidence_status TEXT NOT NULL CHECK (evidence_status IN ('confirmed','keruyun_only','manual','missing','permission_blocked')),
              settlement_state TEXT NOT NULL CHECK (settlement_state IN ('merchant_net_confirmed','wallet_credited','bound_bank_received','former_owner_received','former_owner_pending_transfer','store_account_received','unknown','disputed')),
              current_fund_account_id TEXT REFERENCES fund_accounts(id),
              evidence_reference TEXT,
              source_document_id TEXT REFERENCES source_documents(id),
              notes TEXT,
              created_at TEXT NOT NULL DEFAULT (datetime('now')),
              updated_at TEXT NOT NULL DEFAULT (datetime('now')),
              UNIQUE (store_id, business_date, channel)
            );
            CREATE TABLE IF NOT EXISTS fund_movements (
              id TEXT PRIMARY KEY,
              store_id TEXT NOT NULL REFERENCES stores(id),
              occurred_on TEXT NOT NULL,
              amount_minor INTEGER NOT NULL CHECK (amount_minor > 0),
              movement_type TEXT NOT NULL,
              from_fund_account_id TEXT REFERENCES fund_accounts(id),
              to_fund_account_id TEXT REFERENCES fund_accounts(id),
              business_scope TEXT NOT NULL CHECK (business_scope IN ('store','personal','mixed','unknown')),
              purpose TEXT NOT NULL,
              counterparty TEXT,
              merchant_net_sale_id TEXT REFERENCES merchant_net_sales(id),
              evidence_reference TEXT,
              status TEXT NOT NULL CHECK (status IN ('expected','confirmed','reconciled','void')),
              reference TEXT NOT NULL,
              notes TEXT,
              created_at TEXT NOT NULL DEFAULT (datetime('now')),
              UNIQUE (store_id, reference)
            );
            CREATE TABLE IF NOT EXISTS debt_items (
              id TEXT PRIMARY KEY,
              store_id TEXT NOT NULL REFERENCES stores(id),
              debt_key TEXT NOT NULL,
              lender TEXT NOT NULL,
              principal_minor INTEGER NOT NULL CHECK (principal_minor > 0),
              received_on TEXT NOT NULL,
              due_on TEXT,
              annual_rate_decimal TEXT,
              repaid_principal_minor INTEGER NOT NULL DEFAULT 0,
              repaid_interest_minor INTEGER NOT NULL DEFAULT 0,
              status TEXT NOT NULL CHECK (status IN ('active','settled','disputed','unknown')),
              notes TEXT,
              UNIQUE (store_id, debt_key)
            );
            CREATE TABLE IF NOT EXISTS debt_allocations (
              id TEXT PRIMARY KEY,
              debt_id TEXT NOT NULL REFERENCES debt_items(id),
              allocation_key TEXT NOT NULL,
              purpose TEXT NOT NULL,
              amount_minor INTEGER NOT NULL CHECK (amount_minor > 0),
              classification TEXT NOT NULL,
              evidence_reference TEXT,
              notes TEXT,
              UNIQUE (debt_id, allocation_key)
            );
            CREATE TABLE IF NOT EXISTS evidence_vouchers (
              id TEXT PRIMARY KEY,
              store_id TEXT NOT NULL REFERENCES stores(id),
              voucher_key TEXT NOT NULL,
              voucher_number TEXT NOT NULL,
              business_date TEXT,
              evidence_type TEXT NOT NULL,
              channel TEXT,
              amount_minor INTEGER,
              source_sheet TEXT,
              source_cell TEXT,
              original_filename TEXT NOT NULL,
              original_path TEXT NOT NULL,
              sha256 TEXT NOT NULL,
              status TEXT NOT NULL CHECK (status IN ('confirmed','pending','permission_blocked','unmatched','duplicate')),
              notes TEXT,
              created_at TEXT NOT NULL DEFAULT (datetime('now')),
              UNIQUE (store_id, voucher_key),
              UNIQUE (store_id, voucher_number)
            );
            CREATE TABLE IF NOT EXISTS finance_import_batches (
              id TEXT PRIMARY KEY,
              store_id TEXT NOT NULL REFERENCES stores(id),
              source_type TEXT NOT NULL,
              account_key TEXT NOT NULL,
              original_filename TEXT NOT NULL,
              original_path TEXT NOT NULL,
              sha256 TEXT NOT NULL,
              row_count INTEGER NOT NULL DEFAULT 0,
              inflow_minor INTEGER NOT NULL DEFAULT 0,
              outflow_minor INTEGER NOT NULL DEFAULT 0,
              opening_balance_minor INTEGER,
              closing_balance_minor INTEGER,
              status TEXT NOT NULL CHECK (status IN ('parsed','needs_review','confirmed','failed','duplicate')),
              error_message TEXT,
              created_at TEXT NOT NULL DEFAULT (datetime('now')),
              UNIQUE (store_id, sha256, account_key)
            );
            CREATE TABLE IF NOT EXISTS bookkeeping_records (
              id TEXT PRIMARY KEY,
              store_id TEXT NOT NULL REFERENCES stores(id),
              transaction_date TEXT NOT NULL,
              transaction_time TEXT,
              direction TEXT NOT NULL CHECK (direction IN ('inflow','outflow','transfer')),
              amount_minor INTEGER NOT NULL CHECK (amount_minor > 0),
              transaction_kind TEXT NOT NULL,
              business_scope TEXT NOT NULL CHECK (business_scope IN ('store','personal','mixed','unknown')),
              category_code TEXT,
              category_name TEXT NOT NULL,
              account_key TEXT,
              counter_account_key TEXT,
              counterparty TEXT,
              summary TEXT,
              source_type TEXT NOT NULL,
              source_reference TEXT NOT NULL,
              voucher_id TEXT REFERENCES evidence_vouchers(id),
              import_batch_id TEXT REFERENCES finance_import_batches(id),
              confidence TEXT NOT NULL CHECK (confidence IN ('high','medium','low','confirmed')),
              classification_reason TEXT,
              raw_data_json TEXT NOT NULL DEFAULT '{}',
              status TEXT NOT NULL CHECK (status IN ('draft','needs_review','confirmed','posted','rejected','duplicate')),
              reconciliation_status TEXT NOT NULL DEFAULT 'unmatched' CHECK (reconciliation_status IN ('unmatched','suggested','matched','partial','conflict','not_required')),
              fingerprint TEXT NOT NULL,
              fund_movement_id TEXT REFERENCES fund_movements(id),
              journal_entry_id TEXT REFERENCES journal_entries(id),
              created_at TEXT NOT NULL DEFAULT (datetime('now')),
              updated_at TEXT NOT NULL DEFAULT (datetime('now')),
              UNIQUE (store_id, fingerprint)
            );
            CREATE TABLE IF NOT EXISTS finance_reconciliation_links (
              id TEXT PRIMARY KEY,
              store_id TEXT NOT NULL REFERENCES stores(id),
              bookkeeping_record_id TEXT NOT NULL REFERENCES bookkeeping_records(id),
              target_type TEXT NOT NULL,
              target_id TEXT NOT NULL,
              matched_amount_minor INTEGER NOT NULL CHECK (matched_amount_minor > 0),
              match_method TEXT NOT NULL,
              status TEXT NOT NULL CHECK (status IN ('matched','partial','rejected')),
              notes TEXT,
              created_at TEXT NOT NULL DEFAULT (datetime('now')),
              UNIQUE (bookkeeping_record_id, target_type, target_id)
            );
            CREATE TABLE IF NOT EXISTS cash_plan_items (
              id TEXT PRIMARY KEY,
              store_id TEXT NOT NULL REFERENCES stores(id),
              due_date TEXT NOT NULL,
              flow_type TEXT NOT NULL CHECK (flow_type IN ('expected_inflow','required_outflow')),
              amount_minor INTEGER NOT NULL CHECK (amount_minor > 0),
              category TEXT NOT NULL,
              counterparty TEXT,
              priority TEXT NOT NULL CHECK (priority IN ('must_pay','expected','optional')),
              status TEXT NOT NULL DEFAULT 'planned' CHECK (status IN ('planned','confirmed','paid','cancelled')),
              source_reference TEXT NOT NULL,
              notes TEXT,
              created_at TEXT NOT NULL DEFAULT (datetime('now')),
              UNIQUE (store_id, source_reference)
            );
            CREATE TABLE IF NOT EXISTS finance_execution_plans (
              id TEXT PRIMARY KEY,
              store_id TEXT NOT NULL REFERENCES stores(id),
              schema_version TEXT NOT NULL,
              event_type TEXT NOT NULL,
              status TEXT NOT NULL CHECK (status IN ('needs_input','blocked','awaiting_confirmation','executing','completed','failed')),
              risk_level TEXT NOT NULL CHECK (risk_level IN ('L1','L2','L3')),
              input_json TEXT NOT NULL,
              plan_json TEXT NOT NULL,
              source_reference TEXT NOT NULL,
              record_id TEXT,
              confirmed_by TEXT,
              confirmed_at TEXT,
              error_message TEXT,
              created_at TEXT NOT NULL DEFAULT (datetime('now')),
              updated_at TEXT NOT NULL DEFAULT (datetime('now')),
              UNIQUE (store_id, source_reference, event_type)
            );
            CREATE TABLE IF NOT EXISTS platform_collection_bindings (
              id TEXT PRIMARY KEY,
              store_id TEXT NOT NULL REFERENCES stores(id),
              platform TEXT NOT NULL,
              collector_account_key TEXT NOT NULL,
              destination_account_key TEXT,
              collector_owner_kind TEXT NOT NULL CHECK (
                collector_owner_kind IN ('store','owner','former_owner','platform','unknown')
              ),
              settlement_rule TEXT,
              effective_from TEXT NOT NULL,
              effective_to TEXT,
              status TEXT NOT NULL CHECK (status IN ('active','planned','retired','unknown')),
              notes TEXT,
              created_at TEXT NOT NULL DEFAULT (datetime('now')),
              updated_at TEXT NOT NULL DEFAULT (datetime('now')),
              UNIQUE (store_id, platform, effective_from)
            );
            CREATE INDEX IF NOT EXISTS idx_merchant_net_store_date ON merchant_net_sales(store_id, business_date);
            CREATE INDEX IF NOT EXISTS idx_fund_movements_store_date ON fund_movements(store_id, occurred_on);
            CREATE INDEX IF NOT EXISTS idx_evidence_vouchers_store_date ON evidence_vouchers(store_id, business_date);
            CREATE INDEX IF NOT EXISTS idx_bookkeeping_store_date ON bookkeeping_records(store_id, transaction_date);
            CREATE INDEX IF NOT EXISTS idx_cash_plan_store_due ON cash_plan_items(store_id, due_date);
            INSERT OR IGNORE INTO schema_migrations(version, name, applied_at)
              VALUES (3, 'merchant_net_and_fund_path', datetime('now'));
            INSERT OR IGNORE INTO schema_migrations(version, name, applied_at)
              VALUES (4, 'evidence_voucher_index', datetime('now'));
            INSERT OR IGNORE INTO schema_migrations(version, name, applied_at)
              VALUES (5, 'finance_operating_system', datetime('now'));
            INSERT OR IGNORE INTO schema_migrations(version, name, applied_at)
              VALUES (6, 'finance_execution_plans', datetime('now'));
            INSERT OR IGNORE INTO schema_migrations(version, name, applied_at)
              VALUES (7, 'platform_collection_bindings', datetime('now'));
            """
        )

    def ensure_store(self, store_id: str, name: str, opened_on: str) -> None:
        with self.connect() as connection:
            connection.execute(
                "INSERT OR IGNORE INTO stores(id, name, opened_on) VALUES (?, ?, ?)",
                (store_id, name, opened_on),
            )
            for code, account_name, account_type in ACCOUNT_SEED:
                connection.execute(
                    """INSERT OR IGNORE INTO accounts(id, store_id, code, name, account_type)
                       VALUES (?, ?, ?, ?, ?)""",
                    (f"{store_id}:{code}", store_id, code, account_name, account_type),
                )

    def list_accounts(self, store_id: str) -> list[sqlite3.Row]:
        with self.connect() as connection:
            return connection.execute(
                "SELECT code, name, account_type FROM accounts WHERE store_id = ? ORDER BY code",
                (store_id,),
            ).fetchall()

    def upsert_fund_account(
        self,
        store_id: str,
        *,
        account_key: str,
        name: str,
        account_kind: str,
        owner_kind: str,
        is_store_controlled: bool,
        institution: str | None = None,
        masked_number: str | None = None,
        opening_balance_minor: int = 0,
        effective_from: str | None = None,
        effective_to: str | None = None,
        status: str = "active",
    ) -> str:
        self.ensure_store(
            store_id,
            store_id,
            effective_from or datetime.now(ZoneInfo("Asia/Shanghai")).date().isoformat(),
        )
        account_id = f"fund:{store_id}:{account_key}"
        with self.connect() as connection:
            connection.execute(
                """INSERT INTO fund_accounts
                   (id, store_id, account_key, name, account_kind, owner_kind, institution,
                    masked_number, is_store_controlled, opening_balance_minor, effective_from,
                    effective_to, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(store_id, account_key) DO UPDATE SET
                     name=excluded.name, account_kind=excluded.account_kind,
                     owner_kind=excluded.owner_kind, institution=excluded.institution,
                     masked_number=excluded.masked_number,
                     is_store_controlled=excluded.is_store_controlled,
                     opening_balance_minor=excluded.opening_balance_minor,
                     effective_from=excluded.effective_from, effective_to=excluded.effective_to,
                     status=excluded.status""",
                (
                    account_id, store_id, account_key, name, account_kind, owner_kind,
                    institution, masked_number, 1 if is_store_controlled else 0,
                    int(opening_balance_minor), effective_from, effective_to, status,
                ),
            )
        return account_id

    def list_fund_accounts(self, store_id: str) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """SELECT id, account_key, name, account_kind, owner_kind, institution,
                          masked_number, is_store_controlled, opening_balance_minor,
                          effective_from, effective_to, status
                   FROM fund_accounts WHERE store_id = ?
                   ORDER BY is_store_controlled DESC, account_kind, name""",
                (store_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def save_execution_plan(
        self,
        store_id: str,
        *,
        plan_id: str,
        event_type: str,
        status: str,
        risk_level: str,
        source_reference: str,
        input_data: dict[str, Any],
        plan_data: dict[str, Any],
    ) -> dict[str, Any]:
        with self.connect() as connection:
            connection.execute(
                """INSERT INTO finance_execution_plans
                   (id, store_id, schema_version, event_type, status, risk_level,
                    input_json, plan_json, source_reference)
                   VALUES (?, ?, 'finance_execution_plan_v1', ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(store_id, source_reference, event_type) DO UPDATE SET
                     status=CASE
                       WHEN finance_execution_plans.status='completed' THEN 'completed'
                       ELSE excluded.status
                     END,
                     risk_level=excluded.risk_level,
                     input_json=excluded.input_json,
                     plan_json=CASE
                       WHEN finance_execution_plans.status='completed' THEN finance_execution_plans.plan_json
                       ELSE excluded.plan_json
                     END,
                     updated_at=datetime('now')""",
                (
                    plan_id,
                    store_id,
                    event_type,
                    status,
                    risk_level,
                    json.dumps(input_data, ensure_ascii=False),
                    json.dumps(plan_data, ensure_ascii=False),
                    source_reference,
                ),
            )
            row = connection.execute(
                """SELECT id FROM finance_execution_plans
                   WHERE store_id=? AND source_reference=? AND event_type=?""",
                (store_id, source_reference, event_type),
            ).fetchone()
        return self.get_execution_plan(store_id, str(row["id"]))

    def get_execution_plan(self, store_id: str, plan_id: str) -> dict[str, Any]:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM finance_execution_plans WHERE store_id=? AND id=?",
                (store_id, plan_id),
            ).fetchone()
        if not row:
            raise FinanceMigrationError("财务执行方案不存在")
        item = dict(row)
        item["input"] = json.loads(item.pop("input_json") or "{}")
        plan = json.loads(item.pop("plan_json") or "{}")
        plan.update({
            "plan_id": item["id"],
            "status": item["status"],
            "input": item["input"],
            "record_id": item.get("record_id"),
            "confirmed_by": item.get("confirmed_by"),
            "confirmed_at": item.get("confirmed_at"),
            "error_message": item.get("error_message"),
            "created_at": item.get("created_at"),
            "updated_at": item.get("updated_at"),
        })
        return plan

    def list_execution_plans(
        self,
        store_id: str,
        *,
        statuses: list[str] | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        allowed = {
            "needs_input", "blocked", "awaiting_confirmation", "executing",
            "completed", "failed",
        }
        requested = [value for value in (statuses or []) if value in allowed]
        conditions = ["store_id=?"]
        params: list[Any] = [store_id]
        if requested:
            placeholders = ",".join("?" for _ in requested)
            conditions.append(f"status IN ({placeholders})")
            params.extend(requested)
        params.append(max(1, min(int(limit), 500)))
        with self.connect() as connection:
            rows = connection.execute(
                f"""SELECT id FROM finance_execution_plans
                    WHERE {' AND '.join(conditions)}
                    ORDER BY updated_at DESC, created_at DESC LIMIT ?""",
                params,
            ).fetchall()
        return [self.get_execution_plan(store_id, str(row["id"])) for row in rows]

    def update_execution_plan(
        self,
        store_id: str,
        plan_id: str,
        *,
        status: str,
        plan_data: dict[str, Any] | None = None,
        record_id: str | None = None,
        confirmed_by: str | None = None,
        error_message: str | None = None,
    ) -> dict[str, Any]:
        with self.connect() as connection:
            current = connection.execute(
                "SELECT plan_json FROM finance_execution_plans WHERE store_id=? AND id=?",
                (store_id, plan_id),
            ).fetchone()
            if not current:
                raise FinanceMigrationError("财务执行方案不存在")
            payload = plan_data or json.loads(current["plan_json"] or "{}")
            connection.execute(
                """UPDATE finance_execution_plans
                   SET status=?, plan_json=?, record_id=COALESCE(?, record_id),
                       confirmed_by=COALESCE(?, confirmed_by),
                       confirmed_at=CASE WHEN ? IS NOT NULL THEN datetime('now') ELSE confirmed_at END,
                       error_message=?, updated_at=datetime('now')
                   WHERE store_id=? AND id=?""",
                (
                    status,
                    json.dumps(payload, ensure_ascii=False),
                    record_id,
                    confirmed_by,
                    confirmed_by,
                    error_message,
                    store_id,
                    plan_id,
                ),
            )
        return self.get_execution_plan(store_id, plan_id)

    def outstanding_merchant_sales(
        self,
        store_id: str,
        *,
        platforms: list[str],
        start: str,
        end: str,
    ) -> list[dict[str, Any]]:
        if not platforms:
            return []
        placeholders = ",".join("?" for _ in platforms)
        with self.connect() as connection:
            rows = connection.execute(
                f"""SELECT m.id, m.business_date, m.channel, m.merchant_net_minor,
                           COALESCE(SUM(CASE WHEN l.status IN ('matched','partial')
                                            THEN l.matched_amount_minor ELSE 0 END), 0) matched_minor
                    FROM merchant_net_sales m
                    LEFT JOIN finance_reconciliation_links l
                      ON l.store_id=m.store_id
                     AND l.target_type='merchant_net_sale'
                     AND l.target_id=m.id
                    WHERE m.store_id=? AND m.business_date BETWEEN ? AND ?
                      AND m.channel IN ({placeholders})
                      AND m.settlement_state IN (
                        'wallet_credited','former_owner_received',
                        'former_owner_pending_transfer','unknown'
                      )
                    GROUP BY m.id, m.business_date, m.channel, m.merchant_net_minor
                    HAVING m.merchant_net_minor > COALESCE(SUM(
                      CASE WHEN l.status IN ('matched','partial')
                           THEN l.matched_amount_minor ELSE 0 END
                    ), 0)
                    ORDER BY m.channel, m.business_date, m.id""",
                [store_id, start, end, *platforms],
            ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["remaining_minor"] = int(item["merchant_net_minor"]) - int(item["matched_minor"])
            result.append(item)
        return result

    def upsert_platform_collection_binding(
        self,
        store_id: str,
        *,
        platform: str,
        collector_account_key: str,
        collector_owner_kind: str,
        effective_from: str,
        destination_account_key: str | None = None,
        settlement_rule: str | None = None,
        settlement_delay_days: int | None = None,
        settlement_day_basis: str | None = None,
        settlement_rule_status: str = "unknown",
        settlement_rule_source: str | None = None,
        settlement_delay_target: str = "bound_bank",
        withdrawal_mode: str = "automatic",
        effective_to: str | None = None,
        status: str = "active",
        notes: str | None = None,
    ) -> dict[str, Any]:
        date.fromisoformat(effective_from)
        if effective_to:
            date.fromisoformat(effective_to)
        if settlement_delay_days is not None and settlement_delay_days < 0:
            raise FinanceMigrationError("结算延迟天数不能小于0")
        if settlement_day_basis not in {None, "calendar_day", "working_day"}:
            raise FinanceMigrationError("结算日口径只能是自然日或工作日")
        if settlement_rule_status not in {"confirmed", "unknown"}:
            raise FinanceMigrationError("结算规则状态不合法")
        if settlement_delay_target not in {"bound_bank", "platform_wallet"}:
            raise FinanceMigrationError("结算目标只能是平台钱包或平台绑定卡")
        if withdrawal_mode not in {"automatic", "manual"}:
            raise FinanceMigrationError("提现方式只能是自动或手动")
        binding_id = (
            f"platform-binding:{store_id}:"
            f"{hashlib.sha256(f'{platform}:{effective_from}'.encode()).hexdigest()[:16]}"
        )
        with self.connect() as connection:
            existing = connection.execute(
                """SELECT collector_account_key, destination_account_key
                   FROM platform_collection_bindings
                   WHERE store_id=? AND platform=? AND effective_from=?""",
                (store_id, platform, effective_from),
            ).fetchone()
            if existing and (
                str(existing["collector_account_key"]) != collector_account_key
                or (existing["destination_account_key"] or None) != destination_account_key
            ):
                raise FinanceMigrationError(
                    "该平台在此生效日已有不同收款路径；请选择新的实际生效日，历史路径不会被覆盖"
                )
            if status == "active":
                connection.execute(
                    """UPDATE platform_collection_bindings
                       SET effective_to=date(?, '-1 day'), status='retired',
                           updated_at=datetime('now')
                       WHERE store_id=? AND platform=? AND effective_from<?
                         AND (effective_to IS NULL OR effective_to>=?)""",
                    (effective_from, store_id, platform, effective_from, effective_from),
                )
            connection.execute(
                """INSERT INTO platform_collection_bindings
                   (id, store_id, platform, collector_account_key,
                    destination_account_key, collector_owner_kind, settlement_rule,
                    settlement_delay_days, settlement_day_basis, settlement_rule_status,
                    settlement_rule_source, settlement_delay_target, withdrawal_mode,
                    effective_from, effective_to, status, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(store_id, platform, effective_from) DO UPDATE SET
                     collector_account_key=excluded.collector_account_key,
                     destination_account_key=excluded.destination_account_key,
                     collector_owner_kind=excluded.collector_owner_kind,
                     settlement_rule=excluded.settlement_rule,
                     settlement_delay_days=excluded.settlement_delay_days,
                     settlement_day_basis=excluded.settlement_day_basis,
                     settlement_rule_status=excluded.settlement_rule_status,
                     settlement_rule_source=excluded.settlement_rule_source,
                     settlement_delay_target=excluded.settlement_delay_target,
                     withdrawal_mode=excluded.withdrawal_mode,
                     effective_to=excluded.effective_to, status=excluded.status,
                     notes=excluded.notes, updated_at=datetime('now')""",
                (
                    binding_id, store_id, platform, collector_account_key,
                    destination_account_key, collector_owner_kind, settlement_rule,
                    settlement_delay_days, settlement_day_basis, settlement_rule_status,
                    settlement_rule_source, settlement_delay_target, withdrawal_mode,
                    effective_from, effective_to, status, notes,
                ),
            )
            row = connection.execute(
                """SELECT * FROM platform_collection_bindings
                   WHERE store_id=? AND platform=? AND effective_from=?""",
                (store_id, platform, effective_from),
            ).fetchone()
        return dict(row)

    def list_platform_collection_bindings(
        self, store_id: str, on_date: str | None = None
    ) -> list[dict[str, Any]]:
        conditions = ["store_id=?"]
        params: list[Any] = [store_id]
        if on_date:
            conditions.extend([
                "effective_from<=?",
                "(effective_to IS NULL OR effective_to>=?)",
            ])
            params.extend([on_date, on_date])
        with self.connect() as connection:
            rows = connection.execute(
                f"""SELECT * FROM platform_collection_bindings
                    WHERE {' AND '.join(conditions)}
                    ORDER BY platform, effective_from""",
                params,
            ).fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def _expected_bank_date(business_date: str, delay_days: int, day_basis: str) -> str:
        current = date.fromisoformat(business_date)
        if day_basis == "calendar_day":
            return (current + timedelta(days=delay_days)).isoformat()
        remaining = delay_days
        while remaining > 0:
            current += timedelta(days=1)
            if current.weekday() < 5:
                remaining -= 1
        return current.isoformat()

    def platform_arrival_candidates(
        self,
        store_id: str,
        *,
        arrival_period_start: str,
        arrival_period_end: str,
    ) -> dict[str, Any]:
        """Find unmatched sales expected to reach the platform-bound card in a period."""
        start_date = date.fromisoformat(arrival_period_start)
        end_date = date.fromisoformat(arrival_period_end)
        if end_date < start_date:
            raise FinanceMigrationError("预计到账周期的截止日不能早于开始日")
        with self.connect() as connection:
            rows = connection.execute(
                """SELECT m.id, m.business_date, m.channel, m.merchant_net_minor,
                          m.settlement_state
                   FROM merchant_net_sales m
                   LEFT JOIN platform_transfer_allocations a ON a.merchant_net_sale_id=m.id
                   WHERE m.store_id=? AND a.id IS NULL AND m.merchant_net_minor>0
                     AND m.settlement_state NOT IN ('store_account_received','disputed')
                   ORDER BY m.business_date, m.channel""",
                (store_id,),
            ).fetchall()
        candidates: list[dict[str, Any]] = []
        missing_rule_platforms: set[str] = set()
        wallet_settlement_platforms: set[str] = set()
        manual_withdrawal_platforms: set[str] = set()
        for raw in rows:
            item = dict(raw)
            binding = next(
                (
                    row for row in self.list_platform_collection_bindings(
                        store_id, str(item["business_date"])
                    )
                    if str(row["platform"]) == str(item["channel"])
                ),
                None,
            )
            if not binding:
                if str(item["channel"]) not in {"现金", "客如云收款"}:
                    missing_rule_platforms.add(str(item["channel"]))
                continue
            delay_days = binding.get("settlement_delay_days")
            day_basis = binding.get("settlement_day_basis")
            if (
                binding.get("settlement_rule_status") != "confirmed"
                or delay_days is None
                or day_basis not in {"calendar_day", "working_day"}
            ):
                missing_rule_platforms.add(str(item["channel"]))
                continue
            settlement_target = str(binding.get("settlement_delay_target") or "bound_bank")
            withdrawal_mode = str(binding.get("withdrawal_mode") or "automatic")
            expected = self._expected_bank_date(
                str(item["business_date"]), int(delay_days), str(day_basis)
            )
            if settlement_target == "platform_wallet":
                if arrival_period_start <= expected <= arrival_period_end:
                    wallet_settlement_platforms.add(str(item["channel"]))
                    if withdrawal_mode == "manual":
                        manual_withdrawal_platforms.add(str(item["channel"]))
                continue
            if arrival_period_start <= expected <= arrival_period_end:
                candidates.append({
                    **item,
                    "expected_bank_date": expected,
                    "settlement_delay_days": int(delay_days),
                    "settlement_day_basis": str(day_basis),
                    "settlement_rule": binding.get("settlement_rule"),
                    "collector_account_key": binding.get("collector_account_key"),
                    "destination_account_key": binding.get("destination_account_key"),
                })
        return {
            "schema_version": "platform_arrival_match_v1",
            "arrival_period_start": arrival_period_start,
            "arrival_period_end": arrival_period_end,
            "expected_total_minor": sum(int(item["merchant_net_minor"]) for item in candidates),
            "candidates": candidates,
            "missing_rule_platforms": sorted(missing_rule_platforms),
            "wallet_settlement_platforms": sorted(wallet_settlement_platforms),
            "manual_withdrawal_platforms": sorted(manual_withdrawal_platforms),
            "working_day_note": "工作日预计暂按周一至周五计算，实际节假日以平台账单为准",
        }

    def match_platform_bound_card_transfer(
        self,
        store_id: str,
        *,
        transfer_date: str,
        amount_minor: int,
        arrival_period_start: str,
        arrival_period_end: str,
        source_reference: str,
        evidence_reference: str | None = None,
        from_account_key: str = "former-owner-icbc-9863",
        to_account_key: str = "planned-store-icbc",
    ) -> dict[str, Any]:
        """Match one owner receipt to many platform arrivals; revenue impact is always zero."""
        date.fromisoformat(transfer_date)
        if amount_minor <= 0:
            raise FinanceMigrationError("周期转入金额必须大于0")
        match = self.platform_arrival_candidates(
            store_id,
            arrival_period_start=arrival_period_start,
            arrival_period_end=arrival_period_end,
        )
        expected_minor = int(match["expected_total_minor"])
        difference_minor = int(amount_minor) - expected_minor
        response = {
            **match,
            "transfer_date": transfer_date,
            "amount_minor": int(amount_minor),
            "expected_minor": expected_minor,
            "difference_minor": difference_minor,
            "matched_minor": 0,
            "revenue_impact_minor": 0,
            "status": "needs_review",
            "allocations": [],
        }
        if difference_minor != 0 or not match["candidates"]:
            return response

        batch_id = f"platform-transfer:{store_id}:{hashlib.sha256(source_reference.encode()).hexdigest()[:20]}"
        movement_reference = f"platform-bound-card:{source_reference}"
        movement_id = f"fund-move:{store_id}:{hashlib.sha256(movement_reference.encode()).hexdigest()[:20]}"
        with self.connect() as connection:
            existing = connection.execute(
                "SELECT * FROM platform_transfer_batches WHERE store_id=? AND source_reference=?",
                (store_id, source_reference),
            ).fetchone()
            if existing:
                allocations = connection.execute(
                    """SELECT a.*, m.business_date, m.channel
                       FROM platform_transfer_allocations a
                       JOIN merchant_net_sales m ON m.id=a.merchant_net_sale_id
                       WHERE a.batch_id=? ORDER BY a.expected_bank_date, m.channel""",
                    (str(existing["id"]),),
                ).fetchall()
                return {
                    **response,
                    "status": str(existing["status"]),
                    "matched_minor": int(existing["expected_minor"]),
                    "difference_minor": int(existing["amount_minor"]) - int(existing["expected_minor"]),
                    "batch_id": str(existing["id"]),
                    "allocations": [dict(row) for row in allocations],
                }
            accounts = {
                str(row["account_key"]): str(row["id"])
                for row in connection.execute(
                    "SELECT id, account_key FROM fund_accounts WHERE store_id=?",
                    (store_id,),
                ).fetchall()
            }
            if from_account_key not in accounts or to_account_key not in accounts:
                raise FinanceMigrationError("平台绑定卡或工商银行店铺账户未配置")
            connection.execute(
                """INSERT INTO fund_movements
                   (id, store_id, occurred_on, amount_minor, movement_type,
                    from_fund_account_id, to_fund_account_id, business_scope, purpose,
                    counterparty, evidence_reference, status, reference, notes)
                   VALUES (?, ?, ?, ?, 'custody_transfer', ?, ?, 'store', ?, ?, ?,
                           'reconciled', ?, ?)""",
                (
                    movement_id, store_id, transfer_date, int(amount_minor),
                    accounts[from_account_key], accounts[to_account_key],
                    "平台绑定卡周期款转入工商银行店铺账户",
                    "平台绑定卡临时代管人", evidence_reference,
                    movement_reference, "内部资金位置变动，不新增营业收入",
                ),
            )
            connection.execute(
                """INSERT INTO platform_transfer_batches
                   (id, store_id, transfer_date, arrival_period_start, arrival_period_end,
                    amount_minor, expected_minor, from_account_key, to_account_key,
                    source_reference, evidence_reference, fund_movement_id, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'matched')""",
                (
                    batch_id, store_id, transfer_date, arrival_period_start,
                    arrival_period_end, int(amount_minor), expected_minor,
                    from_account_key, to_account_key, source_reference,
                    evidence_reference, movement_id,
                ),
            )
            allocations: list[dict[str, Any]] = []
            for item in match["candidates"]:
                allocation_key = f"{batch_id}:{item['id']}"
                allocation_id = f"platform-transfer-allocation:{hashlib.sha256(allocation_key.encode()).hexdigest()[:20]}"
                connection.execute(
                    """INSERT INTO platform_transfer_allocations
                       (id, batch_id, merchant_net_sale_id, expected_bank_date, amount_minor)
                       VALUES (?, ?, ?, ?, ?)""",
                    (
                        allocation_id, batch_id, item["id"], item["expected_bank_date"],
                        int(item["merchant_net_minor"]),
                    ),
                )
                connection.execute(
                    """UPDATE merchant_net_sales
                       SET settlement_state='store_account_received', current_fund_account_id=?,
                           updated_at=datetime('now') WHERE id=? AND store_id=?""",
                    (accounts[to_account_key], item["id"], store_id),
                )
                allocations.append({
                    "merchant_net_sale_id": item["id"],
                    "business_date": item["business_date"],
                    "channel": item["channel"],
                    "expected_bank_date": item["expected_bank_date"],
                    "amount_minor": int(item["merchant_net_minor"]),
                })
        return {
            **response,
            "status": "matched",
            "matched_minor": expected_minor,
            "difference_minor": 0,
            "batch_id": batch_id,
            "allocations": allocations,
        }

    def register_evidence_voucher(
        self,
        store_id: str,
        *,
        voucher_key: str,
        evidence_type: str,
        original_filename: str,
        original_path: str,
        sha256: str,
        status: str,
        business_date: str | None = None,
        channel: str | None = None,
        amount_minor: int | None = None,
        source_sheet: str | None = None,
        source_cell: str | None = None,
        notes: str | None = None,
    ) -> str:
        digest = hashlib.sha256(f"{store_id}:{voucher_key}".encode("utf-8")).hexdigest()[:8].upper()
        date_part = (business_date or "UNDATED").replace("-", "")
        voucher_number = f"PZ-{date_part}-{digest}"
        voucher_id = f"voucher:{store_id}:{hashlib.sha256(voucher_key.encode('utf-8')).hexdigest()[:16]}"
        with self.connect() as connection:
            connection.execute(
                """INSERT INTO evidence_vouchers
                   (id, store_id, voucher_key, voucher_number, business_date, evidence_type,
                    channel, amount_minor, source_sheet, source_cell, original_filename,
                    original_path, sha256, status, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(store_id, voucher_key) DO UPDATE SET
                     business_date=excluded.business_date, evidence_type=excluded.evidence_type,
                     channel=excluded.channel, amount_minor=excluded.amount_minor,
                     source_sheet=excluded.source_sheet, source_cell=excluded.source_cell,
                     original_filename=excluded.original_filename,
                     original_path=excluded.original_path, sha256=excluded.sha256,
                     status=excluded.status, notes=excluded.notes""",
                (
                    voucher_id, store_id, voucher_key, voucher_number, business_date,
                    evidence_type, channel, amount_minor, source_sheet, source_cell,
                    original_filename, original_path, sha256, status, notes,
                ),
            )
            row = connection.execute(
                "SELECT id FROM evidence_vouchers WHERE store_id=? AND voucher_key=?",
                (store_id, voucher_key),
            ).fetchone()
        return str(row["id"])

    def list_evidence_vouchers(
        self, store_id: str, start: str | None = None, end: str | None = None
    ) -> list[dict[str, Any]]:
        conditions = ["store_id = ?"]
        params: list[Any] = [store_id]
        if start:
            conditions.append("(business_date IS NULL OR business_date >= ?)")
            params.append(start)
        if end:
            conditions.append("(business_date IS NULL OR business_date <= ?)")
            params.append(end)
        with self.connect() as connection:
            rows = connection.execute(
                f"""SELECT id, voucher_key, voucher_number, business_date, evidence_type,
                           channel, amount_minor, source_sheet, source_cell, original_filename,
                           original_path, sha256, status, notes
                    FROM evidence_vouchers WHERE {' AND '.join(conditions)}
                    ORDER BY COALESCE(business_date, '9999-12-31'), voucher_number""",
                params,
            ).fetchall()
        return [dict(row) for row in rows]

    def create_import_batch(
        self,
        store_id: str,
        *,
        source_type: str,
        account_key: str,
        original_filename: str,
        original_path: str,
        sha256: str,
        row_count: int,
        inflow_minor: int,
        outflow_minor: int,
        opening_balance_minor: int | None,
        closing_balance_minor: int | None,
        status: str = "needs_review",
        error_message: str | None = None,
    ) -> str:
        batch_id = f"finance-import:{store_id}:{hashlib.sha256(f'{sha256}:{account_key}'.encode()).hexdigest()[:20]}"
        with self.connect() as connection:
            account = connection.execute(
                "SELECT 1 FROM fund_accounts WHERE store_id=? AND account_key=?",
                (store_id, account_key),
            ).fetchone()
            if not account:
                raise FinanceMigrationError("导入账单前必须选择已登记的资金账户")
            connection.execute(
                """INSERT INTO finance_import_batches
                   (id, store_id, source_type, account_key, original_filename, original_path,
                    sha256, row_count, inflow_minor, outflow_minor, opening_balance_minor,
                    closing_balance_minor, status, error_message)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(store_id, sha256, account_key) DO UPDATE SET
                     status=CASE WHEN finance_import_batches.status='confirmed' THEN 'confirmed' ELSE excluded.status END,
                     error_message=excluded.error_message""",
                (
                    batch_id, store_id, source_type, account_key, original_filename,
                    original_path, sha256, int(row_count), int(inflow_minor), int(outflow_minor),
                    opening_balance_minor, closing_balance_minor, status, error_message,
                ),
            )
            row = connection.execute(
                "SELECT id FROM finance_import_batches WHERE store_id=? AND sha256=? AND account_key=?",
                (store_id, sha256, account_key),
            ).fetchone()
        return str(row["id"])

    def list_import_batches(self, store_id: str) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """SELECT b.*, f.name account_name
                   FROM finance_import_batches b
                   LEFT JOIN fund_accounts f ON f.store_id=b.store_id AND f.account_key=b.account_key
                   WHERE b.store_id=? ORDER BY b.created_at DESC""",
                (store_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def create_bookkeeping_record(
        self,
        store_id: str,
        *,
        transaction_date: str,
        direction: str,
        amount_minor: int,
        transaction_kind: str,
        business_scope: str,
        category_code: str | None,
        category_name: str,
        business_category_key: str | None = None,
        business_category_group: str | None = None,
        account_key: str | None,
        counterparty: str | None,
        summary: str | None,
        source_type: str,
        source_reference: str,
        confidence: str,
        classification_reason: str | None = None,
        transaction_time: str | None = None,
        counter_account_key: str | None = None,
        voucher_id: str | None = None,
        import_batch_id: str | None = None,
        raw_data: dict[str, Any] | None = None,
        status: str | None = None,
        fingerprint: str | None = None,
    ) -> str:
        try:
            date.fromisoformat(transaction_date)
        except ValueError as exc:
            raise FinanceMigrationError("记账日期必须是 YYYY-MM-DD") from exc
        if amount_minor <= 0:
            raise FinanceMigrationError("记账金额必须大于 0")
        if direction not in {"inflow", "outflow", "transfer"}:
            raise FinanceMigrationError("记账方向不合法")
        stable_source = f"{source_type}:{source_reference}"
        record_fingerprint = fingerprint or hashlib.sha256(
            f"{store_id}|{stable_source}|{transaction_date}|{direction}|{amount_minor}|{account_key or ''}".encode()
        ).hexdigest()
        record_id = f"book:{store_id}:{record_fingerprint[:20]}"
        record_status = status or ("draft" if confidence == "confirmed" else "needs_review")
        with self.connect() as connection:
            connection.execute(
                """INSERT INTO bookkeeping_records
                   (id, store_id, transaction_date, transaction_time, direction, amount_minor,
                    transaction_kind, business_scope, category_code, category_name,
                    business_category_key, business_category_group, account_key,
                    counter_account_key, counterparty, summary, source_type, source_reference,
                    voucher_id, import_batch_id, confidence, classification_reason, raw_data_json,
                    status, reconciliation_status, fingerprint)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(store_id, fingerprint) DO NOTHING""",
                (
                    record_id, store_id, transaction_date, transaction_time, direction,
                    int(amount_minor), transaction_kind, business_scope, category_code,
                    category_name, business_category_key, business_category_group,
                    account_key, counter_account_key, counterparty, summary,
                    source_type, source_reference, voucher_id, import_batch_id, confidence,
                    classification_reason, json.dumps(raw_data or {}, ensure_ascii=False),
                    record_status, "not_required" if business_scope == "personal" else "unmatched",
                    record_fingerprint,
                ),
            )
            row = connection.execute(
                "SELECT id FROM bookkeeping_records WHERE store_id=? AND fingerprint=?",
                (store_id, record_fingerprint),
            ).fetchone()
        return str(row["id"])

    def update_bookkeeping_record(
        self,
        store_id: str,
        record_id: str,
        *,
        transaction_kind: str,
        business_scope: str,
        category_code: str | None,
        category_name: str,
        business_category_key: str | None = None,
        business_category_group: str | None = None,
        account_key: str | None,
        counter_account_key: str | None = None,
        counterparty: str | None = None,
        summary: str | None = None,
    ) -> dict[str, Any]:
        with self.connect() as connection:
            current = connection.execute(
                "SELECT status FROM bookkeeping_records WHERE id=? AND store_id=?",
                (record_id, store_id),
            ).fetchone()
            if not current:
                raise FinanceMigrationError("记账记录不存在")
            if current["status"] == "posted":
                raise FinanceMigrationError("已过账记录不能直接覆盖，请通过调整或冲销更正")
            connection.execute(
                """UPDATE bookkeeping_records SET transaction_kind=?, business_scope=?,
                     category_code=?, category_name=?, business_category_key=?, business_category_group=?,
                     account_key=?, counter_account_key=?,
                     counterparty=?, summary=?, confidence='confirmed', status='draft',
                     updated_at=datetime('now') WHERE id=? AND store_id=?""",
                (
                    transaction_kind, business_scope, category_code, category_name,
                    business_category_key, business_category_group,
                    account_key, counter_account_key, counterparty, summary, record_id, store_id,
                ),
            )
        return self.get_bookkeeping_record(store_id, record_id)

    @staticmethod
    def _bookkeeping_dict(row: sqlite3.Row) -> dict[str, Any]:
        item = dict(row)
        try:
            item["raw_data"] = json.loads(item.pop("raw_data_json", "{}") or "{}")
        except json.JSONDecodeError:
            item["raw_data"] = {}
        return item

    def get_bookkeeping_record(self, store_id: str, record_id: str) -> dict[str, Any]:
        with self.connect() as connection:
            row = connection.execute(
                """SELECT b.*, f.name account_name, f.owner_kind account_owner_kind,
                          cf.name counter_account_name
                   FROM bookkeeping_records b
                   LEFT JOIN fund_accounts f ON f.store_id=b.store_id AND f.account_key=b.account_key
                   LEFT JOIN fund_accounts cf ON cf.store_id=b.store_id AND cf.account_key=b.counter_account_key
                   WHERE b.store_id=? AND b.id=?""",
                (store_id, record_id),
            ).fetchone()
        if not row:
            raise FinanceMigrationError("记账记录不存在")
        return self._bookkeeping_dict(row)

    def list_bookkeeping_records(
        self,
        store_id: str,
        start: str | None = None,
        end: str | None = None,
        status: str | None = None,
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        conditions = ["b.store_id=?"]
        params: list[Any] = [store_id]
        if start:
            conditions.append("b.transaction_date>=?")
            params.append(start)
        if end:
            conditions.append("b.transaction_date<=?")
            params.append(end)
        if status:
            conditions.append("b.status=?")
            params.append(status)
        params.append(max(1, min(limit, 2000)))
        with self.connect() as connection:
            rows = connection.execute(
                f"""SELECT b.*, f.name account_name, f.owner_kind account_owner_kind,
                            cf.name counter_account_name, v.voucher_number
                     FROM bookkeeping_records b
                     LEFT JOIN fund_accounts f ON f.store_id=b.store_id AND f.account_key=b.account_key
                     LEFT JOIN fund_accounts cf ON cf.store_id=b.store_id AND cf.account_key=b.counter_account_key
                     LEFT JOIN evidence_vouchers v ON v.id=b.voucher_id
                     WHERE {' AND '.join(conditions)}
                     ORDER BY b.transaction_date DESC, COALESCE(b.transaction_time,'' ) DESC,
                              b.created_at DESC LIMIT ?""",
                params,
            ).fetchall()
        return [self._bookkeeping_dict(row) for row in rows]

    def confirm_bookkeeping_record(self, store_id: str, record_id: str) -> dict[str, Any]:
        item = self.get_bookkeeping_record(store_id, record_id)
        if item["status"] == "posted":
            self._sync_bookkeeping_debt(store_id, item)
            return item
        if item["status"] in {"rejected", "duplicate"}:
            raise FinanceMigrationError("已拒绝或重复的记录不能过账")
        if item["business_scope"] in {"unknown", "mixed"}:
            raise FinanceMigrationError("请先确认这笔流水属于店铺、个人还是混合用途")
        if not item.get("account_key"):
            raise FinanceMigrationError("请先选择实际收付款账户")
        if item["transaction_kind"] == "former_owner_transfer":
            receivable = self.account_balances(
                store_id, "0001-01-01", item["transaction_date"]
            ).get("1013", 0)
            if int(item["amount_minor"]) > int(receivable):
                raise FinanceMigrationError(
                    f"前老板转回金额超过当前可核销应收：到账 {int(item['amount_minor']) / 100:.2f} 元，"
                    f"可核销 {int(receivable) / 100:.2f} 元"
                )

        account_id = None
        account_owner_kind = item.get("account_owner_kind")
        counter_account_id = None
        with self.connect() as connection:
            account = connection.execute(
                "SELECT id, owner_kind, is_store_controlled FROM fund_accounts WHERE store_id=? AND account_key=?",
                (store_id, item["account_key"]),
            ).fetchone()
            if not account:
                raise FinanceMigrationError("记账账户不存在")
            account_id = str(account["id"])
            account_owner_kind = str(account["owner_kind"])
            if item.get("counter_account_key"):
                counter = connection.execute(
                    "SELECT id FROM fund_accounts WHERE store_id=? AND account_key=?",
                    (store_id, item["counter_account_key"]),
                ).fetchone()
                if not counter:
                    raise FinanceMigrationError("转入或转出账户不存在")
                counter_account_id = str(counter["id"])

        movement_type = item["transaction_kind"]
        from_account_id = account_id if item["direction"] == "outflow" else None
        to_account_id = account_id if item["direction"] == "inflow" else None
        if item["transaction_kind"] == "account_transfer":
            if not counter_account_id:
                raise FinanceMigrationError("账户间转账必须选择另一个资金账户")
            if item["direction"] == "outflow":
                to_account_id = counter_account_id
            else:
                from_account_id = counter_account_id
        elif item["direction"] == "outflow":
            movement_type = "personal_outflow" if item["business_scope"] == "personal" else "store_outflow"

        movement_id = self.record_fund_movement(
            store_id,
            occurred_on=item["transaction_date"],
            amount_minor=int(item["amount_minor"]),
            movement_type=movement_type,
            from_fund_account_id=from_account_id,
            to_fund_account_id=to_account_id,
            business_scope=item["business_scope"],
            purpose=item.get("category_name") or item.get("summary") or "记账流水",
            counterparty=item.get("counterparty"),
            evidence_reference=item.get("voucher_id"),
            status="confirmed",
            reference=f"bookkeeping:{record_id}",
            notes=item.get("summary"),
        )

        amount = int(item["amount_minor"])
        journal_entry_id: str | None = None
        kind = str(item["transaction_kind"])
        category_code = item.get("category_code")
        lines: list[tuple[str, int, int]] | None = None
        # A personal payment from the owner's personal account is recorded for
        # cash visibility but never enters store P&L.
        if item["business_scope"] == "personal" and account_owner_kind == "owner":
            lines = None
        elif item["business_scope"] == "personal" and item["direction"] == "outflow":
            lines = [("3002", amount, 0), ("1002", 0, amount)]
        elif kind in {"operating_expense", "inventory_purchase", "asset_purchase"} and category_code:
            credit_code = "3001" if account_owner_kind == "owner" else "1002"
            lines = [(str(category_code), amount, 0), (credit_code, 0, amount)]
        elif kind == "owner_investment":
            lines = [("1002", amount, 0), ("3001", 0, amount)]
        elif kind == "owner_draw":
            lines = [("3002", amount, 0), ("1002", 0, amount)]
        elif kind == "loan_in":
            lines = [("1002", amount, 0), ("2003", 0, amount)]
        elif kind == "loan_repayment":
            lines = [("2003", amount, 0), ("1002", 0, amount)]
        elif kind == "former_owner_transfer":
            lines = [("1002", amount, 0), ("1013", 0, amount)]
        elif kind == "sales_receipt" and item["direction"] == "inflow":
            lines = [("1002", amount, 0), ("4009", 0, amount)]
        elif kind == "platform_settlement" and item["reconciliation_status"] == "matched":
            lines = [("1002", amount, 0), ("1012", 0, amount)]
        # Bank receipts and platform settlements are not sales evidence by
        # themselves.  Unmatched receipts therefore stay as fund movements.
        if lines:
            journal_entry_id = self.post_entry(
                store_id=store_id,
                entry_date=item["transaction_date"],
                posting_key=f"bookkeeping-post:{record_id}",
                description=item.get("summary") or item.get("category_name") or "记账过账",
                lines=lines,
                entry_type="manual",
            )
        if kind == "sales_receipt" and item["direction"] == "inflow":
            self.record_merchant_net_sale(
                store_id,
                business_date=item["transaction_date"],
                channel=f"手工记账-{record_id.rsplit(':', 1)[-1][:8]}",
                amount_minor=amount,
                source_basis="manual_bookkeeping_confirmed",
                evidence_status="manual",
                settlement_state="store_account_received",
                current_fund_account_id=account_id,
                evidence_reference=item.get("voucher_id"),
                notes=item.get("summary"),
            )
        self._sync_bookkeeping_debt(store_id, item)
        with self.connect() as connection:
            connection.execute(
                """UPDATE bookkeeping_records SET status='posted', confidence='confirmed',
                     fund_movement_id=?, journal_entry_id=?, updated_at=datetime('now')
                   WHERE id=? AND store_id=?""",
                (movement_id, journal_entry_id, record_id, store_id),
            )
        return self.get_bookkeeping_record(store_id, record_id)

    def correct_posted_bookkeeping_classification(
        self,
        store_id: str,
        record_id: str,
        *,
        business_category_key: str,
        reason: str,
        corrected_by: str,
        correction_key: str,
    ) -> dict[str, Any]:
        """Correct a posted record without erasing its original evidence or history.

        The old fund movement is voided, a replacement movement and journal entry
        are created in the same transaction, and before/after snapshots are kept.
        Existing posted journal entries require a dedicated reversal workflow and
        are deliberately not overwritten here.
        """
        from core.finance_categories import find_finance_category

        category = find_finance_category(business_category_key)
        if not category:
            raise FinanceMigrationError("更正目标分类不存在")
        if not reason.strip() or not corrected_by.strip() or not correction_key.strip():
            raise FinanceMigrationError("更正必须保留原因、操作人和幂等键")

        with self.connect() as connection:
            existing = connection.execute(
                "SELECT * FROM bookkeeping_corrections WHERE store_id=? AND correction_key=?",
                (store_id, correction_key),
            ).fetchone()
            if existing:
                self._sync_corrected_execution_plan(
                    connection,
                    store_id=store_id,
                    record_id=record_id,
                    category=category,
                    correction_key=correction_key,
                    reason=reason.strip(),
                    corrected_by=corrected_by.strip(),
                )
                correction = dict(existing)
                correction["before"] = json.loads(correction.pop("before_json"))
                correction["after"] = json.loads(correction.pop("after_json"))
                return {
                    "correction": correction,
                    "record": self.get_bookkeeping_record(store_id, record_id),
                }

            row = connection.execute(
                "SELECT * FROM bookkeeping_records WHERE store_id=? AND id=?",
                (store_id, record_id),
            ).fetchone()
            if not row:
                raise FinanceMigrationError("记账记录不存在")
            record = dict(row)
            if record["status"] != "posted":
                raise FinanceMigrationError("只有已过账记录需要通过更正流程处理")
            if record.get("journal_entry_id"):
                raise FinanceMigrationError("该记录已有总账分录，需通过冲销分录另行更正")
            account = connection.execute(
                "SELECT id, owner_kind FROM fund_accounts WHERE store_id=? AND account_key=?",
                (store_id, record.get("account_key")),
            ).fetchone()
            if not account:
                raise FinanceMigrationError("原记录的收付款账户不存在")
            old_movement = connection.execute(
                "SELECT * FROM fund_movements WHERE store_id=? AND id=?",
                (store_id, record.get("fund_movement_id")),
            ).fetchone()
            voucher = connection.execute(
                "SELECT * FROM evidence_vouchers WHERE store_id=? AND id=?",
                (store_id, record.get("voucher_id")),
            ).fetchone() if record.get("voucher_id") else None
            execution_plan = connection.execute(
                "SELECT * FROM finance_execution_plans WHERE store_id=? AND record_id=?",
                (store_id, record_id),
            ).fetchone()

            before = {
                "record": record,
                "fund_movement": dict(old_movement) if old_movement else None,
                "voucher": dict(voucher) if voucher else None,
                "execution_plan": dict(execution_plan) if execution_plan else None,
            }
            amount = int(record["amount_minor"])
            direction = str(category["direction"])
            scope = str(category["business_scope"])
            movement_type = str(category["transaction_kind"])
            if direction == "outflow":
                movement_type = "personal_outflow" if scope == "personal" else "store_outflow"
            from_account_id = str(account["id"]) if direction == "outflow" else None
            to_account_id = str(account["id"]) if direction == "inflow" else None
            movement_reference = f"bookkeeping-correction:{record_id}:{correction_key}"
            movement_id = f"fund-move:{store_id}:{hashlib.sha256(movement_reference.encode()).hexdigest()[:20]}"

            if old_movement:
                connection.execute(
                    "UPDATE fund_movements SET status='void' WHERE store_id=? AND id=?",
                    (store_id, old_movement["id"]),
                )
            connection.execute(
                """INSERT INTO fund_movements
                   (id, store_id, occurred_on, amount_minor, movement_type,
                    from_fund_account_id, to_fund_account_id, business_scope, purpose,
                    counterparty, evidence_reference, status, reference, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'confirmed', ?, ?)""",
                (
                    movement_id, store_id, record["transaction_date"], amount,
                    movement_type, from_account_id, to_account_id, scope,
                    category["name"], record.get("counterparty"), record.get("voucher_id"),
                    movement_reference, record.get("summary"),
                ),
            )

            journal_entry_id: str | None = None
            category_code = category.get("account_code")
            if (
                category["transaction_kind"] in {"operating_expense", "inventory_purchase", "asset_purchase"}
                and category_code
            ):
                credit_code = "3001" if account["owner_kind"] == "owner" else "1002"
                period_id = self._period_id(connection, store_id, record["transaction_date"])
                posting_key = f"bookkeeping-correction-post:{record_id}:{correction_key}"
                journal_entry_id = f"je:{store_id}:{hashlib.sha256(posting_key.encode()).hexdigest()[:20]}"
                connection.execute(
                    """INSERT INTO journal_entries
                       (id, store_id, accounting_period_id, entry_date, entry_type,
                        status, posting_key, description, created_at, posted_at)
                       VALUES (?, ?, ?, ?, 'adjustment', 'posted', ?, ?, datetime('now'), datetime('now'))""",
                    (
                        journal_entry_id, store_id, period_id, record["transaction_date"],
                        posting_key, f"更正：{category['name']}",
                    ),
                )
                for index, (code, debit, credit) in enumerate(
                    ((str(category_code), amount, 0), (credit_code, 0, amount))
                ):
                    account_row = connection.execute(
                        "SELECT id FROM accounts WHERE store_id=? AND code=?",
                        (store_id, code),
                    ).fetchone()
                    if not account_row:
                        raise FinanceMigrationError(f"会计科目不存在：{code}")
                    connection.execute(
                        """INSERT INTO journal_lines
                           (id, journal_entry_id, account_id, debit_minor, credit_minor)
                           VALUES (?, ?, ?, ?, ?)""",
                        (f"{journal_entry_id}:{index}", journal_entry_id, account_row["id"], debit, credit),
                    )

            try:
                raw_data = json.loads(record.get("raw_data_json") or "{}")
            except json.JSONDecodeError:
                raw_data = {}
            raw_data.setdefault("classification_corrections", []).append({
                "correction_key": correction_key,
                "reason": reason.strip(),
                "corrected_by": corrected_by.strip(),
                "from": {
                    "direction": record["direction"],
                    "transaction_kind": record["transaction_kind"],
                    "category_name": record["category_name"],
                },
                "to": {
                    "direction": direction,
                    "transaction_kind": category["transaction_kind"],
                    "category_name": category["name"],
                },
            })
            connection.execute(
                """UPDATE bookkeeping_records SET
                     direction=?, transaction_kind=?, business_scope=?, category_code=?,
                     category_name=?, business_category_key=?, business_category_group=?,
                     classification_reason=?, raw_data_json=?, fund_movement_id=?,
                     journal_entry_id=?, reconciliation_status='not_required', updated_at=datetime('now')
                   WHERE store_id=? AND id=?""",
                (
                    direction, category["transaction_kind"], scope, category_code,
                    category["name"], category["key"], category["group_name"],
                    f"已更正：{reason.strip()}", json.dumps(raw_data, ensure_ascii=False),
                    movement_id, journal_entry_id, store_id, record_id,
                ),
            )
            if voucher:
                connection.execute(
                    "UPDATE evidence_vouchers SET evidence_type=? WHERE store_id=? AND id=?",
                    (category["transaction_kind"], store_id, voucher["id"]),
                )
            self._sync_corrected_execution_plan(
                connection,
                store_id=store_id,
                record_id=record_id,
                category=category,
                correction_key=correction_key,
                reason=reason.strip(),
                corrected_by=corrected_by.strip(),
            )
            corrected_row = connection.execute(
                "SELECT * FROM bookkeeping_records WHERE store_id=? AND id=?",
                (store_id, record_id),
            ).fetchone()
            after = {
                "record": dict(corrected_row),
                "fund_movement": dict(connection.execute(
                    "SELECT * FROM fund_movements WHERE id=?", (movement_id,)
                ).fetchone()),
                "journal_entry_id": journal_entry_id,
                "voucher_evidence_type": category["transaction_kind"] if voucher else None,
            }
            correction_id = f"book-correction:{store_id}:{hashlib.sha256(correction_key.encode()).hexdigest()[:20]}"
            connection.execute(
                """INSERT INTO bookkeeping_corrections
                   (id, store_id, bookkeeping_record_id, correction_key, before_json,
                    after_json, reason, corrected_by)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    correction_id, store_id, record_id, correction_key,
                    json.dumps(before, ensure_ascii=False), json.dumps(after, ensure_ascii=False),
                    reason.strip(), corrected_by.strip(),
                ),
            )

        return {
            "correction": {
                "id": correction_id,
                "store_id": store_id,
                "bookkeeping_record_id": record_id,
                "correction_key": correction_key,
                "before": before,
                "after": after,
                "reason": reason.strip(),
                "corrected_by": corrected_by.strip(),
            },
            "record": self.get_bookkeeping_record(store_id, record_id),
        }

    @staticmethod
    def _sync_corrected_execution_plan(
        connection: sqlite3.Connection,
        *,
        store_id: str,
        record_id: str,
        category: dict[str, Any],
        correction_key: str,
        reason: str,
        corrected_by: str,
    ) -> None:
        """Make completed-plan summaries reflect the corrected fact.

        ``input_json`` is intentionally untouched: it remains the immutable
        record of what the recognizer and user originally submitted.
        """
        plan_row = connection.execute(
            "SELECT id, plan_json FROM finance_execution_plans WHERE store_id=? AND record_id=?",
            (store_id, record_id),
        ).fetchone()
        if not plan_row:
            return
        try:
            plan = json.loads(plan_row["plan_json"] or "{}")
        except json.JSONDecodeError:
            plan = {}
        plan["event_type"] = category["transaction_kind"]
        plan["title"] = category["name"]
        plan["classification_correction"] = {
            "correction_key": correction_key,
            "business_category_key": category["key"],
            "reason": reason,
            "corrected_by": corrected_by,
            "original_input_preserved": True,
        }
        connection.execute(
            """UPDATE finance_execution_plans SET event_type=?, plan_json=?, updated_at=datetime('now')
               WHERE store_id=? AND id=?""",
            (
                category["transaction_kind"], json.dumps(plan, ensure_ascii=False),
                store_id, plan_row["id"],
            ),
        )

    def _sync_bookkeeping_debt(self, store_id: str, item: dict[str, Any]) -> None:
        """Keep a confirmed loan receipt visible in the structured debt schedule.

        The journal remains the accounting source of truth.  The debt item adds
        the lender/due-date workflow needed by the owner-facing cash plan and is
        idempotently keyed to the immutable bookkeeping record.
        """
        if item.get("transaction_kind") != "loan_in" or item.get("direction") != "inflow":
            return
        record_id = str(item["id"])
        self.record_debt(
            store_id,
            debt_key=f"bookkeeping-{hashlib.sha256(record_id.encode()).hexdigest()[:20]}",
            lender=str(item.get("counterparty") or "待补充出借人"),
            principal_minor=int(item["amount_minor"]),
            received_on=str(item["transaction_date"]),
            status="active",
            notes=str(item.get("summary") or "由已确认借款流水自动建立"),
        )

    def create_cash_plan_item(
        self,
        store_id: str,
        *,
        due_date: str,
        flow_type: str,
        amount_minor: int,
        category: str,
        counterparty: str | None,
        priority: str,
        source_reference: str,
        status: str = "planned",
        notes: str | None = None,
    ) -> str:
        try:
            date.fromisoformat(due_date)
        except ValueError as exc:
            raise FinanceMigrationError("计划收付日期必须是 YYYY-MM-DD") from exc
        if amount_minor <= 0:
            raise FinanceMigrationError("计划收付金额必须大于 0")
        item_id = f"cash-plan:{store_id}:{hashlib.sha256(source_reference.encode()).hexdigest()[:20]}"
        with self.connect() as connection:
            connection.execute(
                """INSERT INTO cash_plan_items
                   (id, store_id, due_date, flow_type, amount_minor, category, counterparty,
                    priority, status, source_reference, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(store_id, source_reference) DO UPDATE SET
                     due_date=excluded.due_date, flow_type=excluded.flow_type,
                     amount_minor=excluded.amount_minor, category=excluded.category,
                     counterparty=excluded.counterparty, priority=excluded.priority,
                     status=excluded.status, notes=excluded.notes""",
                (
                    item_id, store_id, due_date, flow_type, int(amount_minor), category,
                    counterparty, priority, status, source_reference, notes,
                ),
            )
            row = connection.execute(
                "SELECT id FROM cash_plan_items WHERE store_id=? AND source_reference=?",
                (store_id, source_reference),
            ).fetchone()
        return str(row["id"])

    def list_cash_plan_items(
        self, store_id: str, start: str, end: str, include_closed: bool = False
    ) -> list[dict[str, Any]]:
        status_clause = "" if include_closed else " AND status IN ('planned','confirmed')"
        with self.connect() as connection:
            rows = connection.execute(
                f"""SELECT * FROM cash_plan_items WHERE store_id=? AND due_date BETWEEN ? AND ?
                    {status_clause} ORDER BY due_date, CASE priority WHEN 'must_pay' THEN 0 WHEN 'expected' THEN 1 ELSE 2 END""",
                (store_id, start, end),
            ).fetchall()
        return [dict(row) for row in rows]

    def latest_finance_date(self, store_id: str) -> str | None:
        with self.connect() as connection:
            row = connection.execute(
                """SELECT MAX(value) latest FROM (
                     SELECT MAX(business_date) value FROM merchant_net_sales WHERE store_id=?
                     UNION ALL SELECT MAX(occurred_on) FROM fund_movements WHERE store_id=?
                     UNION ALL SELECT MAX(transaction_date) FROM bookkeeping_records WHERE store_id=?
                     UNION ALL SELECT MAX(business_date) FROM evidence_vouchers WHERE store_id=?
                     UNION ALL SELECT MAX(entry_date) FROM journal_entries WHERE store_id=?
                     UNION ALL SELECT MAX(business_date) FROM daily_close_sessions WHERE store_id=?
                   )""",
                (store_id, store_id, store_id, store_id, store_id, store_id),
            ).fetchone()
        return str(row["latest"]) if row and row["latest"] else None

    def daily_finance_snapshot(self, store_id: str, selected_date: str) -> dict[str, Any]:
        return self.period_finance_snapshot(store_id, selected_date, selected_date)

    def period_finance_snapshot(self, store_id: str, start_date: str, selected_date: str) -> dict[str, Any]:
        try:
            period_start = date.fromisoformat(start_date)
            date.fromisoformat(selected_date)
        except ValueError as exc:
            raise FinanceMigrationError("查询日期必须是 YYYY-MM-DD") from exc
        if period_start > date.fromisoformat(selected_date):
            raise FinanceMigrationError("开始日期不能晚于结束日期")
        merchant_net = self.merchant_net_total(store_id, start_date, selected_date)
        merchant_rows = self.merchant_net_sales(store_id, start_date, selected_date)
        movement_totals = self.fund_movement_totals(store_id, start_date, selected_date)
        movement_rows = self.list_fund_movements(store_id, start_date, selected_date)
        entries = self.list_bookkeeping_records(store_id, start_date, selected_date)
        vouchers = self.list_evidence_vouchers(store_id, start_date, selected_date)
        voucher_by_id = {str(item["id"]): item for item in vouchers}

        def related_voucher(reference: str | None) -> dict[str, Any] | None:
            if not reference:
                return None
            if reference in voucher_by_id:
                return voucher_by_id[reference]
            return next(
                (
                    item for item in vouchers
                    if reference in str(item.get("voucher_key") or "")
                ),
                None,
            )

        def public_status(value: str) -> tuple[str, str]:
            if value in {"store_account_received", "confirmed", "reconciled", "posted"}:
                return "completed", "已完成"
            if value == "wallet_credited":
                return "awaiting_arrival", "已到平台钱包"
            if value in {"bound_bank_received", "former_owner_received", "former_owner_pending_transfer"}:
                return "awaiting_reconciliation", "已到平台绑定卡，待转店铺工商卡"
            if value in {"unknown", "disputed", "draft", "needs_review"}:
                return "needs_information", "需要补信息"
            return "completed", "已记录"

        def location_label(item: dict[str, Any]) -> str:
            account_name = str(item.get("current_account_name") or "").strip()
            account_owner = str(item.get("current_account_owner_kind") or "")
            state = str(item.get("settlement_state") or "")
            if state == "wallet_credited":
                return account_name or f"{item['channel']}平台钱包"
            if state in {"bound_bank_received", "former_owner_received", "former_owner_pending_transfer"}:
                return "平台绑定卡（暂时代管）"
            if state == "store_account_received":
                if account_owner == "owner" and "招商银行" in account_name:
                    return "店铺资金暂存于老板个人招商卡"
                if account_name:
                    return f"{account_name}中的店铺款"
                return "本人已收店铺款"
            return "资金位置待补充"
        positions = self.fund_positions(store_id, selected_date)
        controlled = sum(int(item["balance_minor"]) for item in positions if item["is_store_controlled"])
        accounting_revenue = self.revenue_total(store_id, start_date, selected_date)
        costs = self.cost_totals(store_id, start_date, selected_date)
        close = self.daily_close(store_id, selected_date)
        ledger_entries: list[dict[str, Any]] = [
            {**item, "entry_origin": "bookkeeping"} for item in entries
        ]
        linked_bookkeeping_movement_ids = {
            str(item["fund_movement_id"])
            for item in entries
            if item.get("fund_movement_id")
        }
        money_events: list[dict[str, Any]] = []
        for item in merchant_rows:
            voucher = related_voucher(item.get("evidence_reference"))
            status_code, status_name = public_status(str(item["settlement_state"]))
            location = location_label(item)
            ledger_entries.append({
                "id": item["id"],
                "transaction_date": item["business_date"],
                "direction": "inflow",
                "amount_minor": item["merchant_net_minor"],
                "transaction_kind": "merchant_net_sale",
                "business_scope": "store",
                "category_name": f"营业收入·{item['channel']}",
                "account_name": location,
                "counterparty": item["channel"],
                "summary": item.get("notes"),
                "source_type": item["source_basis"],
                "status": status_code,
                "status_label": status_name,
                "reconciliation_status": "matched" if status_code == "completed" else "unmatched",
                "confidence": "confirmed" if item["evidence_status"] == "confirmed" else "low",
                "entry_origin": "merchant_net",
                "voucher_id": voucher.get("id") if voucher else None,
                "voucher_number": voucher.get("voucher_number") if voucher else None,
                "voucher_filename": voucher.get("original_filename") if voucher else None,
                "source_reference": item.get("evidence_reference") or item["id"],
                "created_at": item.get("created_at"),
            })
            money_events.append({
                "id": item["id"],
                "date": item["business_date"],
                "amount_minor": item["merchant_net_minor"],
                "event_type": "sale",
                "scene": "营业收入",
                "source_label": f"{item['channel']}营业收入",
                "location_label": location,
                "destination_label": "留在当前资金位置",
                "status": status_code,
                "status_label": status_name,
                "summary": f"{item['channel']}当日营业收入",
                "voucher_id": voucher.get("id") if voucher else None,
                "voucher_number": voucher.get("voucher_number") if voucher else None,
                "voucher_filename": voucher.get("original_filename") if voucher else None,
                "source_reference": item.get("reference") or item["id"],
                "created_at": item.get("created_at"),
            })
        for item in movement_rows:
            if (
                str(item.get("id") or "") in linked_bookkeeping_movement_ids
                or str(item.get("reference") or "").startswith("bookkeeping:")
                or str(item.get("reference") or "").startswith("bookkeeping-correction:")
            ):
                continue
            voucher = related_voucher(item.get("evidence_reference"))
            is_outflow = item["movement_type"] in {"store_outflow", "personal_outflow"}
            is_receipt = item["movement_type"] in {"former_owner_transfer", "platform_settlement", "sales_receipt"}
            status_code, status_name = public_status(str(item["status"]))
            source_name = item.get("from_account_name") or item.get("counterparty") or "外部资金来源"
            destination_name = item.get("to_account_name") or item.get("purpose") or "外部收款方"
            ledger_entries.append({
                "id": item["id"],
                "transaction_date": item["occurred_on"],
                "direction": "outflow" if is_outflow else "inflow" if is_receipt else "transfer",
                "amount_minor": item["amount_minor"],
                "transaction_kind": item["movement_type"],
                "business_scope": item["business_scope"],
                "category_name": item["purpose"],
                "account_name": item.get("from_account_name") or item.get("to_account_name"),
                "counterparty": item.get("counterparty"),
                "summary": item.get("notes"),
                "source_type": "fund_movement",
                "status": status_code,
                "status_label": status_name,
                "reconciliation_status": "matched" if item["status"] == "reconciled" else "unmatched",
                "confidence": "confirmed",
                "entry_origin": "fund_movement",
                "voucher_id": voucher.get("id") if voucher else None,
                "voucher_number": voucher.get("voucher_number") if voucher else None,
                "voucher_filename": voucher.get("original_filename") if voucher else None,
            })
            scene = "老板往来" if item["movement_type"] == "personal_outflow" else "店铺支出" if is_outflow else "资金到账"
            money_events.append({
                "id": item["id"],
                "date": item["occurred_on"],
                "amount_minor": item["amount_minor"],
                "event_type": "outflow" if is_outflow else "receipt" if is_receipt else "transfer",
                "scene": scene,
                "source_label": source_name,
                "location_label": destination_name if not is_outflow else "付款完成",
                "destination_label": item.get("purpose") or destination_name,
                "status": status_code,
                "status_label": status_name,
                "summary": item.get("notes") or item.get("purpose"),
                "voucher_id": voucher.get("id") if voucher else None,
                "voucher_number": voucher.get("voucher_number") if voucher else None,
                "voucher_filename": voucher.get("original_filename") if voucher else None,
            })

        # Bookkeeping-created movements are hidden above to prevent duplicate rows.
        # Their user-facing events are built from the canonical bookkeeping record.
        for item in entries:
            voucher = voucher_by_id.get(str(item.get("voucher_id") or ""))
            status_code, status_name = public_status(str(item["status"]))
            kind = str(item["transaction_kind"])
            if kind == "former_owner_transfer" and status_code == "completed":
                status_name = "已到账本人"
            account_name = item.get("account_name") or "收付款账户待补充"
            counterparty = item.get("counterparty")
            if item["business_scope"] == "personal":
                scene = "老板往来"
                destination = "老板个人取用"
            elif kind in {"loan_in", "loan_repayment", "owner_investment", "owner_draw"}:
                scene = "借款与接店" if kind.startswith("loan") else "老板往来"
                destination = item["category_name"]
            else:
                scene = "店铺支出" if item["direction"] == "outflow" else "资金到账"
                destination = item["category_name"]

            # The flow must describe where money really came from and where it
            # currently sits. A receiving bank account is never the source of
            # an inflow. This distinction is especially important while online
            # platforms are temporarily collected by the former owner.
            if kind == "former_owner_transfer":
                source_name = counterparty or "前老板代收账户"
                target_name = account_name
                destination = "核销前老板代收平台款"
            elif kind in {"platform_settlement", "sales_receipt", "loan_in", "owner_investment"}:
                source_name = counterparty or item["category_name"]
                target_name = account_name
            elif item["direction"] == "outflow":
                source_name = account_name
                target_name = counterparty or item.get("counter_account_name") or "收款方"
            else:
                source_name = account_name
                target_name = item.get("counter_account_name") or destination
            money_events.append({
                "id": item["id"],
                "date": item["transaction_date"],
                "amount_minor": item["amount_minor"],
                "event_type": "outflow" if item["direction"] == "outflow" else "receipt" if item["direction"] == "inflow" else "transfer",
                "scene": scene,
                "source_label": source_name,
                "location_label": target_name,
                "destination_label": destination,
                "status": status_code,
                "status_label": status_name,
                "summary": item.get("summary") or item["category_name"],
                "voucher_id": voucher.get("id") if voucher else item.get("voucher_id"),
                "voucher_number": voucher.get("voucher_number") if voucher else item.get("voucher_number"),
                "voucher_filename": voucher.get("original_filename") if voucher else None,
            })
        for item in ledger_entries:
            scope = str(item.get("business_scope") or "unknown")
            item["traceability"] = {
                "business_date": item.get("transaction_date"),
                "recorded_at": item.get("created_at") or item.get("updated_at"),
                "source_type": item.get("source_type"),
                "source_reference": item.get("source_reference") or item.get("id"),
                "voucher_id": item.get("voucher_id"),
                "account_name": item.get("account_name"),
                "fund_ownership": scope,
                "profit_treatment": (
                    "excluded_personal" if scope == "personal"
                    else "inventory_not_expensed" if item.get("transaction_kind") == "inventory_purchase"
                    else "included_when_posted"
                ),
            }
        ledger_entries.sort(key=lambda item: (str(item.get("transaction_date") or ""), str(item.get("transaction_time") or ""), str(item.get("id") or "")), reverse=True)
        money_events.sort(key=lambda item: (str(item.get("date") or ""), str(item.get("id") or "")), reverse=True)
        has_activity = any((merchant_net, movement_totals["store_outflow"], movement_totals["personal_outflow"], entries, vouchers, close.get("id")))
        period_activity = {
            "merchant_net_minor": merchant_net,
            "store_outflow_minor": movement_totals["store_outflow"],
            "personal_outflow_minor": movement_totals["personal_outflow"],
            "accounting_revenue_minor": accounting_revenue,
            "costs_minor": costs,
        }
        return {
            "selected_date": selected_date,
            "period_start": start_date,
            "period_end": selected_date,
            "scope_kind": "day" if start_date == selected_date else "period",
            "latest_data_date": self.latest_finance_date(store_id),
            "data_state": "available" if has_activity else "missing",
            "period_activity": period_activity,
            "day_activity": period_activity,
            "as_of": {
                "store_controlled_minor": controlled,
                "fund_positions": positions,
                "debt_outstanding_minor": self.debt_summary(store_id)["outstanding_minor"],
                "actual_bank_balance_minor": None,
                "actual_bank_balance_status": "missing_statement_snapshot",
                "store_controlled_label": "账面可追溯店铺资金（不是银行卡实时余额）",
            },
            "bookkeeping_entries": entries,
            "ledger_entries": ledger_entries,
            "money_flow": {
                "events": money_events,
                "actual_bank_balance_minor": None,
                "actual_bank_balance_status": "missing_statement_snapshot",
            },
            "vouchers": vouchers,
            "daily_close": close,
        }

    def cash_chain_forecast(
        self,
        store_id: str,
        as_of: str,
        *,
        safety_reserve_minor: int | None = None,
        horizons: tuple[int, ...] = (7, 14, 30),
    ) -> dict[str, Any]:
        as_of_date = date.fromisoformat(as_of)
        positions = self.fund_positions(store_id, as_of)
        opening = sum(int(item["balance_minor"]) for item in positions if item["is_store_controlled"])
        if safety_reserve_minor is None:
            with self.connect() as connection:
                reserve_row = connection.execute(
                    """SELECT reserve_cash_minor FROM daily_close_sessions
                       WHERE store_id=? AND business_date<=? AND reserve_cash_minor IS NOT NULL
                       ORDER BY business_date DESC LIMIT 1""",
                    (store_id, as_of),
                ).fetchone()
            reserve = int(reserve_row["reserve_cash_minor"] or 0) if reserve_row else 0
        else:
            reserve = int(safety_reserve_minor)
        end_date = as_of_date + timedelta(days=max(horizons))
        items = self.list_cash_plan_items(store_id, as_of, end_date.isoformat())
        balance = opening
        first_risk_date: str | None = None
        timeline: list[dict[str, Any]] = []
        for item in items:
            if item["flow_type"] == "expected_inflow":
                balance += int(item["amount_minor"])
            else:
                balance -= int(item["amount_minor"])
            if balance < reserve and first_risk_date is None:
                first_risk_date = str(item["due_date"])
            timeline.append({**item, "projected_balance_minor": balance})
        horizon_rows = []
        for days in horizons:
            cutoff = (as_of_date + timedelta(days=days)).isoformat()
            scoped = [item for item in items if item["due_date"] <= cutoff]
            inflow = sum(int(item["amount_minor"]) for item in scoped if item["flow_type"] == "expected_inflow")
            outflow = sum(int(item["amount_minor"]) for item in scoped if item["flow_type"] == "required_outflow")
            ending = opening + inflow - outflow
            horizon_rows.append({
                "days": days,
                "through_date": cutoff,
                "expected_inflow_minor": inflow,
                "required_outflow_minor": outflow,
                "ending_minor": ending,
                "shortfall_minor": max(reserve - ending, 0),
            })
        blocking: list[str] = []
        if not any(item["status"] == "active" and item["account_kind"] == "bank" and item["is_store_controlled"] for item in positions):
            blocking.append("store_bank_account_missing")
        if not items:
            blocking.append("future_receipts_and_obligations_missing")
        return {
            "as_of": as_of,
            "opening_store_controlled_minor": opening,
            "safety_reserve_minor": reserve,
            "horizons": horizon_rows,
            "timeline": timeline,
            "first_risk_date": first_risk_date,
            "status": "at_risk" if first_risk_date else "partial" if blocking else "safe",
            "blocking_reasons": blocking,
        }

    def reconciliation_queue(
        self, store_id: str, start: str | None = None, end: str | None = None
    ) -> list[dict[str, Any]]:
        records = self.list_bookkeeping_records(store_id, start, end, limit=1000)
        queue: list[dict[str, Any]] = []
        with self.connect() as connection:
            for record in records:
                if record["business_scope"] == "personal" or record["reconciliation_status"] in {"matched", "not_required"}:
                    continue
                candidates: list[dict[str, Any]] = []
                matched_row = connection.execute(
                    """SELECT COALESCE(SUM(matched_amount_minor), 0) amount
                       FROM finance_reconciliation_links
                       WHERE bookkeeping_record_id=? AND status IN ('matched','partial')""",
                    (record["id"],),
                ).fetchone()
                record_remaining = max(int(record["amount_minor"]) - int(matched_row["amount"] or 0), 0)
                raw_data = record.get("raw_data") or {}
                period_start = raw_data.get("business_period_start")
                period_end = raw_data.get("business_period_end")
                source_platform = str(raw_data.get("source_platform") or record.get("counterparty") or "")
                if record["direction"] == "inflow" and period_start and period_end and source_platform:
                    merchant_rows = connection.execute(
                        """SELECT m.id, m.business_date target_date,
                                  m.merchant_net_minor amount_minor,
                                  m.channel target_label, 'merchant_net_sale' target_type,
                                  COALESCE(SUM(l.matched_amount_minor), 0) matched_minor
                           FROM merchant_net_sales m
                           LEFT JOIN finance_reconciliation_links l
                             ON l.store_id=m.store_id
                            AND l.target_type='merchant_net_sale'
                            AND l.target_id=m.id
                            AND l.status IN ('matched','partial')
                           WHERE m.store_id=? AND m.business_date BETWEEN ? AND ?
                             AND m.channel LIKE ?
                           GROUP BY m.id, m.business_date, m.merchant_net_minor, m.channel
                           HAVING m.merchant_net_minor > COALESCE(SUM(l.matched_amount_minor), 0)
                           ORDER BY m.business_date, m.channel""",
                        (store_id, str(period_start), str(period_end), f"%{source_platform}%"),
                    ).fetchall()
                    candidates.extend(dict(row) for row in merchant_rows)
                elif record["direction"] == "inflow":
                    merchant_rows = connection.execute(
                        """SELECT m.id, m.business_date target_date,
                                  m.merchant_net_minor amount_minor,
                                  m.channel target_label, 'merchant_net_sale' target_type,
                                  COALESCE(SUM(l.matched_amount_minor), 0) matched_minor
                           FROM merchant_net_sales m
                           LEFT JOIN finance_reconciliation_links l
                             ON l.store_id=m.store_id
                            AND l.target_type='merchant_net_sale'
                            AND l.target_id=m.id
                            AND l.status IN ('matched','partial')
                           WHERE m.store_id=? AND m.merchant_net_minor=?
                             AND ABS(julianday(m.business_date)-julianday(?))<=3
                           GROUP BY m.id, m.business_date, m.merchant_net_minor, m.channel
                           HAVING m.merchant_net_minor > COALESCE(SUM(l.matched_amount_minor), 0)
                           ORDER BY ABS(julianday(m.business_date)-julianday(?)), m.channel""",
                        (store_id, record["amount_minor"], record["transaction_date"], record["transaction_date"]),
                    ).fetchall()
                    candidates.extend(dict(row) for row in merchant_rows)
                movement_rows = connection.execute(
                    """SELECT m.id, m.occurred_on target_date, m.amount_minor,
                              m.purpose target_label, 'fund_movement' target_type,
                              COALESCE(SUM(l.matched_amount_minor), 0) matched_minor
                       FROM fund_movements m
                       LEFT JOIN finance_reconciliation_links l
                         ON l.store_id=m.store_id
                        AND l.target_type='fund_movement'
                        AND l.target_id=m.id
                        AND l.status IN ('matched','partial')
                       WHERE m.store_id=? AND m.amount_minor=? AND m.reference<>?
                         AND ABS(julianday(m.occurred_on)-julianday(?))<=3
                       GROUP BY m.id, m.occurred_on, m.amount_minor, m.purpose
                       HAVING m.amount_minor > COALESCE(SUM(l.matched_amount_minor), 0)
                       ORDER BY ABS(julianday(m.occurred_on)-julianday(?)), m.created_at""",
                    (
                        store_id, record["amount_minor"], f"bookkeeping:{record['id']}",
                        record["transaction_date"], record["transaction_date"],
                    ),
                ).fetchall()
                candidates.extend(dict(row) for row in movement_rows)
                remaining_to_allocate = record_remaining
                candidate_rows: list[dict[str, Any]] = []
                for candidate in candidates[:10]:
                    target_remaining = max(
                        int(candidate["amount_minor"]) - int(candidate.get("matched_minor") or 0),
                        0,
                    )
                    suggested = min(target_remaining, remaining_to_allocate)
                    if suggested <= 0:
                        continue
                    is_period_match = bool(period_start and period_end and candidate["target_type"] == "merchant_net_sale")
                    candidate_rows.append({
                        **candidate,
                        "target_remaining_minor": target_remaining,
                        "suggested_match_minor": suggested,
                        "confidence": (
                            "high"
                            if candidate["target_date"] == record["transaction_date"]
                            else "medium"
                        ),
                        "reason": (
                            f"属于{period_start}至{period_end}的{source_platform}营业款"
                            if is_period_match
                            else "金额一致且日期相同"
                            if candidate["target_date"] == record["transaction_date"]
                            else "金额一致且日期相差不超过3天"
                        ),
                    })
                    remaining_to_allocate -= suggested
                    if remaining_to_allocate <= 0:
                        break
                queue.append({
                    "record": record,
                    "remaining_minor": record_remaining,
                    "candidates": candidate_rows,
                })
        return queue

    def match_reconciliation(
        self,
        store_id: str,
        record_id: str,
        *,
        target_type: str,
        target_id: str,
        matched_amount_minor: int,
        match_method: str = "owner_confirmed",
        notes: str | None = None,
    ) -> dict[str, Any]:
        record = self.get_bookkeeping_record(store_id, record_id)
        if matched_amount_minor <= 0 or matched_amount_minor > int(record["amount_minor"]):
            raise FinanceMigrationError("对账金额必须大于0且不能超过流水金额")
        if target_type == "merchant_net_sale":
            with self.connect() as connection:
                target = connection.execute(
                    "SELECT merchant_net_minor amount_minor FROM merchant_net_sales WHERE id=? AND store_id=?",
                    (target_id, store_id),
                ).fetchone()
        elif target_type == "fund_movement":
            with self.connect() as connection:
                target = connection.execute(
                    "SELECT amount_minor FROM fund_movements WHERE id=? AND store_id=?",
                    (target_id, store_id),
                ).fetchone()
        else:
            raise FinanceMigrationError("不支持的对账目标")
        if not target:
            raise FinanceMigrationError("对账目标不存在")
        link_id = f"reconcile:{hashlib.sha256(f'{record_id}:{target_type}:{target_id}'.encode()).hexdigest()[:20]}"
        with self.connect() as connection:
            existing = connection.execute(
                """SELECT matched_amount_minor FROM finance_reconciliation_links
                   WHERE bookkeeping_record_id=? AND target_type=? AND target_id=?""",
                (record_id, target_type, target_id),
            ).fetchone()
            if existing:
                if int(existing["matched_amount_minor"]) == int(matched_amount_minor):
                    return self.get_bookkeeping_record(store_id, record_id)
                raise FinanceMigrationError("该对账关系已确认；如需更正请先撤销原匹配")
            record_matched = connection.execute(
                """SELECT COALESCE(SUM(matched_amount_minor),0) amount
                   FROM finance_reconciliation_links
                   WHERE bookkeeping_record_id=? AND status IN ('matched','partial')""",
                (record_id,),
            ).fetchone()
            target_matched = connection.execute(
                """SELECT COALESCE(SUM(matched_amount_minor),0) amount
                   FROM finance_reconciliation_links
                   WHERE store_id=? AND target_type=? AND target_id=?
                     AND status IN ('matched','partial')""",
                (store_id, target_type, target_id),
            ).fetchone()
            record_remaining = int(record["amount_minor"]) - int(record_matched["amount"] or 0)
            target_remaining = int(target["amount_minor"]) - int(target_matched["amount"] or 0)
            if matched_amount_minor > record_remaining:
                raise FinanceMigrationError("对账金额不能超过该流水的剩余未核销金额")
            if matched_amount_minor > target_remaining:
                raise FinanceMigrationError("对账金额不能超过目标销售或资金流水的剩余金额")
            status = "matched" if matched_amount_minor == target_remaining else "partial"
            connection.execute(
                """INSERT INTO finance_reconciliation_links
                   (id, store_id, bookkeeping_record_id, target_type, target_id,
                    matched_amount_minor, match_method, status, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(bookkeeping_record_id, target_type, target_id) DO UPDATE SET
                     matched_amount_minor=excluded.matched_amount_minor,
                     match_method=excluded.match_method, status=excluded.status, notes=excluded.notes""",
                (
                    link_id, store_id, record_id, target_type, target_id,
                    int(matched_amount_minor), match_method, status, notes,
                ),
            )
            total = connection.execute(
                """SELECT COALESCE(SUM(matched_amount_minor),0) amount
                   FROM finance_reconciliation_links
                   WHERE bookkeeping_record_id=? AND status IN ('matched','partial')""",
                (record_id,),
            ).fetchone()
            reconciliation_status = "matched" if int(total["amount"] or 0) >= int(record["amount_minor"]) else "partial"
            connection.execute(
                "UPDATE bookkeeping_records SET reconciliation_status=?, updated_at=datetime('now') WHERE id=? AND store_id=?",
                (reconciliation_status, record_id, store_id),
            )
            if target_type == "merchant_net_sale" and int(target_matched["amount"] or 0) + matched_amount_minor >= int(target["amount_minor"]):
                connection.execute(
                    """UPDATE merchant_net_sales
                       SET settlement_state='store_account_received', updated_at=datetime('now')
                       WHERE id=? AND store_id=?""",
                    (target_id, store_id),
                )
        refreshed = self.get_bookkeeping_record(store_id, record_id)
        if (
            refreshed["status"] == "posted"
            and refreshed["transaction_kind"] == "platform_settlement"
            and refreshed["reconciliation_status"] == "matched"
            and not refreshed.get("journal_entry_id")
        ):
            journal_entry_id = self.post_entry(
                store_id=store_id,
                entry_date=refreshed["transaction_date"],
                posting_key=f"bookkeeping-settlement-match:{record_id}",
                description=refreshed.get("summary") or "平台结算到账对账",
                lines=[("1002", int(refreshed["amount_minor"]), 0), ("1012", 0, int(refreshed["amount_minor"]))],
                entry_type="reconciliation",
            )
            with self.connect() as connection:
                connection.execute(
                    "UPDATE bookkeeping_records SET journal_entry_id=?, updated_at=datetime('now') WHERE id=?",
                    (journal_entry_id, record_id),
                )
        return self.get_bookkeeping_record(store_id, record_id)

    def record_merchant_net_sale(
        self,
        store_id: str,
        *,
        business_date: str,
        channel: str,
        amount_minor: int,
        source_basis: str,
        evidence_status: str,
        settlement_state: str,
        evidence_reference: str | None = None,
        current_fund_account_id: str | None = None,
        reference_gross_minor: int | None = None,
        source_document_id: str | None = None,
        notes: str | None = None,
    ) -> str:
        if amount_minor < 0:
            raise FinanceMigrationError("实际到手营业额不能小于 0")
        record_id = f"merchant-net:{store_id}:{business_date}:{hashlib.sha256(channel.encode()).hexdigest()[:10]}"
        with self.connect() as connection:
            connection.execute(
                """INSERT INTO merchant_net_sales
                   (id, store_id, business_date, channel, merchant_net_minor,
                    reference_gross_minor, source_basis, evidence_status, settlement_state,
                    current_fund_account_id, evidence_reference, source_document_id, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(store_id, business_date, channel) DO UPDATE SET
                     merchant_net_minor=excluded.merchant_net_minor,
                     reference_gross_minor=excluded.reference_gross_minor,
                     source_basis=excluded.source_basis,
                     evidence_status=excluded.evidence_status,
                     settlement_state=excluded.settlement_state,
                     current_fund_account_id=excluded.current_fund_account_id,
                     evidence_reference=excluded.evidence_reference,
                     source_document_id=excluded.source_document_id,
                     notes=excluded.notes, updated_at=datetime('now')""",
                (
                    record_id, store_id, business_date, channel, int(amount_minor),
                    reference_gross_minor, source_basis, evidence_status, settlement_state,
                    current_fund_account_id, evidence_reference, source_document_id, notes,
                ),
            )
            row = connection.execute(
                "SELECT id FROM merchant_net_sales WHERE store_id=? AND business_date=? AND channel=?",
                (store_id, business_date, channel),
            ).fetchone()
        return str(row["id"])

    @staticmethod
    def daily_revenue_channels() -> list[dict[str, Any]]:
        return [dict(item) for item in DAILY_REVENUE_CHANNELS]

    def _daily_channel_fund_path(
        self, store_id: str, channel: str, business_date: str,
    ) -> dict[str, Any]:
        if channel == "现金":
            return {
                "expected_fund_path": "当天留在店内现金",
                "collector_owner_kind": "store",
                "settlement_rule": "营业结束后按现金实点核对，保留500元备用金",
            }
        if channel == "客如云收款":
            return {
                "expected_fund_path": "客如云收款 → 工商银行店铺账户",
                "collector_owner_kind": "owner",
                "settlement_rule": "营业与到账分开；通常次日到工商银行店铺账户，以银行实际入账为准",
                "expected_bank_date": (date.fromisoformat(business_date) + timedelta(days=1)).isoformat(),
                "settlement_rule_status": "confirmed",
            }

        bindings = {
            str(item["platform"]): item
            for item in self.list_platform_collection_bindings(store_id, business_date)
        }
        accounts = {
            str(item["account_key"]): str(item["name"])
            for item in self.list_fund_accounts(store_id)
        }
        binding = bindings.get(channel)
        if binding:
            collector = accounts.get(
                str(binding.get("collector_account_key") or ""), "绑定收款账户",
            )
            destination_key = str(binding.get("destination_account_key") or "")
            destination = accounts.get(destination_key, "")
            if str(binding.get("collector_owner_kind")) == "former_owner":
                path = f"{channel}平台钱包 → 平台绑定卡（暂时代管） → {destination or '工商银行店铺账户'}"
            elif destination and destination != collector:
                path = f"{channel}平台钱包 → {collector} → {destination}"
            else:
                path = f"{channel}平台钱包 → {collector}"
            delay_days = binding.get("settlement_delay_days")
            day_basis = binding.get("settlement_day_basis")
            expected_settlement_date = (
                self._expected_bank_date(business_date, int(delay_days), str(day_basis))
                if binding.get("settlement_rule_status") == "confirmed"
                and delay_days is not None
                and day_basis in {"calendar_day", "working_day"}
                else None
            )
            settlement_target = str(binding.get("settlement_delay_target") or "bound_bank")
            withdrawal_mode = str(binding.get("withdrawal_mode") or "automatic")
            if settlement_target == "platform_wallet" and withdrawal_mode == "manual":
                path = f"{channel}平台钱包（需手动提现） → 平台绑定卡（暂时代管） → {destination or '工商银行店铺账户'}"
            return {
                "expected_fund_path": path,
                "collector_owner_kind": str(binding.get("collector_owner_kind") or "unknown"),
                "settlement_rule": binding.get("settlement_rule") or "以平台账单和银行回单为准",
                "expected_bank_date": expected_settlement_date if settlement_target == "bound_bank" else None,
                "expected_wallet_date": expected_settlement_date if settlement_target == "platform_wallet" else None,
                "withdrawal_mode": withdrawal_mode,
                "settlement_rule_status": binding.get("settlement_rule_status") or "unknown",
            }
        return {
            "expected_fund_path": f"{channel}平台钱包 → 平台绑定卡（暂时代管） → 工商银行店铺账户",
            "collector_owner_kind": "former_owner",
            "settlement_rule": "平台结算规则待确认；未确认前不猜测到账日",
            "expected_bank_date": None,
            "settlement_rule_status": "unknown",
        }

    def daily_revenue_checklist(
        self, store_id: str, start: str, end: str,
    ) -> dict[str, Any]:
        try:
            start_date = date.fromisoformat(start)
            end_date = date.fromisoformat(end)
        except ValueError as exc:
            raise FinanceMigrationError("每日营业日期必须是 YYYY-MM-DD") from exc
        if end_date < start_date:
            raise FinanceMigrationError("每日营业截止日不能早于开始日")

        channel_definitions = self.daily_revenue_channels()
        channel_names = [str(item["channel"]) for item in channel_definitions]
        sales = self.merchant_net_sales(store_id, start, end)
        sale_by_key = {
            (str(item["business_date"]), str(item["channel"])): item
            for item in sales if str(item["channel"]) in channel_names
        }
        with self.connect() as connection:
            check_rows = connection.execute(
                """SELECT * FROM daily_revenue_channel_checks
                   WHERE store_id=? AND business_date BETWEEN ? AND ?""",
                (store_id, start, end),
            ).fetchall()
        checks = {
            (str(row["business_date"]), str(row["channel"])): dict(row)
            for row in check_rows
        }

        days: list[dict[str, Any]] = []
        current = start_date
        while current <= end_date:
            business_date = current.isoformat()
            rows: list[dict[str, Any]] = []
            for definition in channel_definitions:
                channel = str(definition["channel"])
                sale = sale_by_key.get((business_date, channel))
                check = checks.get((business_date, channel))
                if sale:
                    status = "confirmed_zero" if int(sale["merchant_net_minor"]) == 0 else "recorded"
                elif check and check.get("status") == "not_available":
                    status = "not_available"
                else:
                    status = "missing"
                path = self._daily_channel_fund_path(store_id, channel, business_date)
                rows.append({
                    **definition,
                    **path,
                    "business_date": business_date,
                    "status": status,
                    "status_label": {
                        "recorded": "已录入",
                        "confirmed_zero": "已确认0元",
                        "not_available": "平台数据暂未出",
                        "missing": "待录入",
                    }[status],
                    "amount_minor": int(sale["merchant_net_minor"]) if sale else None,
                    "record_id": str(sale["id"]) if sale else None,
                    "settlement_state": str(sale["settlement_state"]) if sale else None,
                    "evidence_status": str(sale["evidence_status"]) if sale else None,
                    "notes": (sale.get("notes") if sale else None) or (check.get("notes") if check else None),
                })
            completed_count = sum(item["status"] in {"recorded", "confirmed_zero"} for item in rows)
            not_available_count = sum(item["status"] == "not_available" for item in rows)
            missing_count = sum(item["status"] == "missing" for item in rows)
            days.append({
                "business_date": business_date,
                "status": "complete" if completed_count == len(rows) else "incomplete",
                "total_count": len(rows),
                "completed_count": completed_count,
                "not_available_count": not_available_count,
                "missing_count": missing_count,
                "channels": rows,
            })
            current += timedelta(days=1)

        return {
            "schema_version": "daily_revenue_checklist_v1",
            "period_start": start,
            "period_end": end,
            "channels": channel_definitions,
            "days": days,
            "summary": {
                "complete_days": sum(item["status"] == "complete" for item in days),
                "incomplete_days": sum(item["status"] != "complete" for item in days),
                "missing_entries": sum(int(item["missing_count"]) for item in days),
                "not_available_entries": sum(int(item["not_available_count"]) for item in days),
            },
        }

    def save_daily_revenue_entries(
        self,
        store_id: str,
        business_date: str,
        items: list[dict[str, Any]],
    ) -> dict[str, Any]:
        try:
            date.fromisoformat(business_date)
        except ValueError as exc:
            raise FinanceMigrationError("每日营业日期必须是 YYYY-MM-DD") from exc
        if not items:
            raise FinanceMigrationError("至少需要提交一个营业渠道")
        allowed_channels = {str(item["channel"]) for item in DAILY_REVENUE_CHANNELS}
        allowed_statuses = {"recorded", "confirmed_zero", "not_available"}
        seen: set[str] = set()
        normalized: list[dict[str, Any]] = []
        for raw in items:
            channel = str(raw.get("channel") or "").strip()
            status = str(raw.get("status") or "").strip()
            if channel not in allowed_channels:
                raise FinanceMigrationError(f"不是本店固定营业渠道：{channel or '未填写'}")
            if channel in seen:
                raise FinanceMigrationError(f"同一天不能重复提交渠道：{channel}")
            if status not in allowed_statuses:
                raise FinanceMigrationError(f"营业渠道状态不合法：{status or '未填写'}")
            amount = raw.get("amount_minor")
            if status == "recorded" and (amount is None or int(amount) <= 0):
                raise FinanceMigrationError(f"{channel}请填写大于0的当天金额，0元请使用“当天0元”")
            if status == "confirmed_zero" and int(amount or 0) != 0:
                raise FinanceMigrationError(f"{channel}确认0元时金额必须为0")
            seen.add(channel)
            normalized.append({
                "channel": channel,
                "status": status,
                "amount_minor": None if status == "not_available" else int(amount or 0),
                "notes": str(raw.get("notes") or "").strip() or None,
            })

        with self.connect() as connection:
            existing = {
                str(row["channel"]): dict(row)
                for row in connection.execute(
                    """SELECT * FROM merchant_net_sales
                       WHERE store_id=? AND business_date=?""",
                    (store_id, business_date),
                ).fetchall()
            }
            for item in normalized:
                channel = str(item["channel"])
                if item["status"] == "not_available" and channel in existing:
                    raise FinanceMigrationError(f"{channel}已有营业金额，不能改成平台数据暂未出")

            for item in normalized:
                channel = str(item["channel"])
                check_id = (
                    f"daily-revenue-check:{store_id}:{business_date}:"
                    f"{hashlib.sha256(channel.encode()).hexdigest()[:12]}"
                )
                sale_id: str | None = None
                if item["status"] != "not_available":
                    sale_id = f"merchant-net:{store_id}:{business_date}:{hashlib.sha256(channel.encode()).hexdigest()[:10]}"
                    cash_account = connection.execute(
                        "SELECT id FROM fund_accounts WHERE store_id=? AND account_key='cash-on-hand'",
                        (store_id,),
                    ).fetchone() if channel == "现金" else None
                    settlement_state = "store_account_received" if channel == "现金" else "merchant_net_confirmed"
                    connection.execute(
                        """INSERT INTO merchant_net_sales
                           (id, store_id, business_date, channel, merchant_net_minor,
                            source_basis, evidence_status, settlement_state,
                            current_fund_account_id, notes)
                           VALUES (?, ?, ?, ?, ?, 'daily_revenue_checklist', 'manual', ?, ?, ?)
                           ON CONFLICT(store_id, business_date, channel) DO UPDATE SET
                             merchant_net_minor=excluded.merchant_net_minor,
                             notes=COALESCE(excluded.notes, merchant_net_sales.notes),
                             updated_at=datetime('now')""",
                        (
                            sale_id, store_id, business_date, channel,
                            int(item["amount_minor"] or 0), settlement_state,
                            str(cash_account["id"]) if cash_account else None,
                            item["notes"],
                        ),
                    )
                    row = connection.execute(
                        "SELECT id FROM merchant_net_sales WHERE store_id=? AND business_date=? AND channel=?",
                        (store_id, business_date, channel),
                    ).fetchone()
                    sale_id = str(row["id"])
                connection.execute(
                    """INSERT INTO daily_revenue_channel_checks
                       (id, store_id, business_date, channel, status, merchant_net_sale_id, notes)
                       VALUES (?, ?, ?, ?, ?, ?, ?)
                       ON CONFLICT(store_id, business_date, channel) DO UPDATE SET
                         status=excluded.status,
                         merchant_net_sale_id=excluded.merchant_net_sale_id,
                         notes=excluded.notes,
                         updated_at=datetime('now')""",
                    (
                        check_id, store_id, business_date, channel, item["status"],
                        sale_id, item["notes"],
                    ),
                )

        return {
            "success": True,
            "business_date": business_date,
            "saved_count": len(normalized),
            "revenue_impact_from_settlement_minor": 0,
            "checklist": self.daily_revenue_checklist(store_id, business_date, business_date),
        }

    def merchant_net_total(self, store_id: str, start: str, end: str) -> int:
        with self.connect() as connection:
            row = connection.execute(
                """SELECT COALESCE(SUM(merchant_net_minor), 0) amount
                   FROM merchant_net_sales
                   WHERE store_id = ? AND business_date BETWEEN ? AND ?""",
                (store_id, start, end),
            ).fetchone()
        return int(row["amount"] or 0)

    def merchant_net_sales(self, store_id: str, start: str, end: str) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """SELECT m.*, f.name current_account_name, f.is_store_controlled,
                          f.owner_kind current_account_owner_kind
                   FROM merchant_net_sales m
                   LEFT JOIN fund_accounts f ON f.id = m.current_fund_account_id
                   WHERE m.store_id = ? AND m.business_date BETWEEN ? AND ?
                   ORDER BY m.business_date DESC, m.channel""",
                (store_id, start, end),
            ).fetchall()
        return [dict(row) for row in rows]

    def record_fund_movement(
        self,
        store_id: str,
        *,
        occurred_on: str,
        amount_minor: int,
        movement_type: str,
        from_fund_account_id: str | None,
        to_fund_account_id: str | None,
        business_scope: str,
        purpose: str,
        status: str,
        reference: str,
        counterparty: str | None = None,
        merchant_net_sale_id: str | None = None,
        evidence_reference: str | None = None,
        notes: str | None = None,
    ) -> str:
        if amount_minor <= 0:
            raise FinanceMigrationError("资金流水金额必须大于 0")
        if not from_fund_account_id and not to_fund_account_id:
            raise FinanceMigrationError("资金流水至少需要一个来源或去向账户")
        movement_id = f"fund-move:{store_id}:{hashlib.sha256(reference.encode()).hexdigest()[:20]}"
        with self.connect() as connection:
            connection.execute(
                """INSERT OR IGNORE INTO fund_movements
                   (id, store_id, occurred_on, amount_minor, movement_type,
                    from_fund_account_id, to_fund_account_id, business_scope, purpose,
                    counterparty, merchant_net_sale_id, evidence_reference, status,
                    reference, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    movement_id, store_id, occurred_on, int(amount_minor), movement_type,
                    from_fund_account_id, to_fund_account_id, business_scope, purpose,
                    counterparty, merchant_net_sale_id, evidence_reference, status,
                    reference, notes,
                ),
            )
            row = connection.execute(
                "SELECT id FROM fund_movements WHERE store_id=? AND reference=?",
                (store_id, reference),
            ).fetchone()
        return str(row["id"])

    def list_fund_movements(
        self, store_id: str, start: str, end: str, business_scope: str | None = None
    ) -> list[dict[str, Any]]:
        scope_clause = " AND m.business_scope = ?" if business_scope else ""
        params: tuple[Any, ...] = (store_id, start, end, business_scope) if business_scope else (store_id, start, end)
        with self.connect() as connection:
            rows = connection.execute(
                f"""SELECT m.id, m.occurred_on, m.amount_minor, m.movement_type,
                          m.business_scope, m.purpose, m.counterparty, m.status,
                          m.reference, m.evidence_reference, m.notes,
                          source.name from_account_name, destination.name to_account_name
                   FROM fund_movements m
                   LEFT JOIN fund_accounts source ON source.id = m.from_fund_account_id
                   LEFT JOIN fund_accounts destination ON destination.id = m.to_fund_account_id
                   WHERE m.store_id = ? AND m.occurred_on BETWEEN ? AND ?
                     AND m.status <> 'void'
                   {scope_clause}
                   ORDER BY m.occurred_on DESC, m.created_at DESC""",
                params,
            ).fetchall()
        return [dict(row) for row in rows]

    def fund_movement_totals(self, store_id: str, start: str, end: str) -> dict[str, int]:
        with self.connect() as connection:
            rows = connection.execute(
                """SELECT business_scope, COALESCE(SUM(amount_minor), 0) amount_minor
                   FROM fund_movements
                   WHERE store_id=? AND occurred_on BETWEEN ? AND ?
                     AND status IN ('confirmed','reconciled')
                     AND movement_type IN ('store_outflow','personal_outflow')
                   GROUP BY business_scope""",
                (store_id, start, end),
            ).fetchall()
        totals = {"store_outflow": 0, "personal_outflow": 0}
        for row in rows:
            key = "personal_outflow" if row["business_scope"] == "personal" else "store_outflow"
            totals[key] += int(row["amount_minor"] or 0)
        return totals

    def fund_positions(self, store_id: str, as_of: str) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """SELECT f.*,
                          f.opening_balance_minor
                          + COALESCE((SELECT SUM(s.merchant_net_minor) FROM merchant_net_sales s
                                      WHERE s.current_fund_account_id=f.id
                                        AND s.business_date <= ?), 0)
                          + COALESCE((SELECT SUM(m.amount_minor) FROM fund_movements m
                                      WHERE m.to_fund_account_id=f.id AND m.status IN ('confirmed','reconciled')
                                        AND m.occurred_on <= ?), 0)
                          - COALESCE((SELECT SUM(m.amount_minor) FROM fund_movements m
                                      WHERE m.from_fund_account_id=f.id AND m.status IN ('confirmed','reconciled')
                                        AND m.occurred_on <= ?), 0) balance_minor
                   FROM fund_accounts f WHERE f.store_id=?
                   ORDER BY f.is_store_controlled DESC, f.account_kind, f.name""",
                (as_of, as_of, as_of, store_id),
            ).fetchall()
        return [dict(row) for row in rows]

    def record_debt(
        self,
        store_id: str,
        *,
        debt_key: str,
        lender: str,
        principal_minor: int,
        received_on: str,
        status: str,
        due_on: str | None = None,
        annual_rate_decimal: str | None = None,
        notes: str | None = None,
    ) -> str:
        if principal_minor <= 0:
            raise FinanceMigrationError("借款本金必须大于 0")
        debt_id = f"debt:{store_id}:{debt_key}"
        with self.connect() as connection:
            connection.execute(
                """INSERT INTO debt_items
                   (id, store_id, debt_key, lender, principal_minor, received_on, due_on,
                    annual_rate_decimal, status, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(store_id, debt_key) DO UPDATE SET
                     lender=excluded.lender, principal_minor=excluded.principal_minor,
                     received_on=excluded.received_on, due_on=excluded.due_on,
                     annual_rate_decimal=excluded.annual_rate_decimal,
                     status=excluded.status, notes=excluded.notes""",
                (
                    debt_id, store_id, debt_key, lender, int(principal_minor), received_on,
                    due_on, annual_rate_decimal, status, notes,
                ),
            )
            row = connection.execute(
                "SELECT id FROM debt_items WHERE store_id=? AND debt_key=?",
                (store_id, debt_key),
            ).fetchone()
        return str(row["id"])

    def record_debt_allocation(
        self,
        store_id: str,
        *,
        debt_id: str,
        allocation_key: str,
        purpose: str,
        amount_minor: int,
        classification: str,
        evidence_reference: str | None = None,
        notes: str | None = None,
    ) -> str:
        allocation_id = f"debt-use:{hashlib.sha256(f'{debt_id}:{allocation_key}'.encode()).hexdigest()[:20]}"
        with self.connect() as connection:
            debt = connection.execute(
                "SELECT principal_minor FROM debt_items WHERE id=? AND store_id=?", (debt_id, store_id)
            ).fetchone()
            if not debt:
                raise FinanceMigrationError("借款记录不存在")
            other = connection.execute(
                "SELECT COALESCE(SUM(amount_minor),0) amount FROM debt_allocations WHERE debt_id=? AND allocation_key<>?",
                (debt_id, allocation_key),
            ).fetchone()
            if int(other["amount"] or 0) + amount_minor > int(debt["principal_minor"]):
                raise FinanceMigrationError("借款用途分配超过借款本金")
            connection.execute(
                """INSERT INTO debt_allocations
                   (id, debt_id, allocation_key, purpose, amount_minor, classification,
                    evidence_reference, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(debt_id, allocation_key) DO UPDATE SET
                     purpose=excluded.purpose, amount_minor=excluded.amount_minor,
                     classification=excluded.classification,
                     evidence_reference=excluded.evidence_reference, notes=excluded.notes""",
                (
                    allocation_id, debt_id, allocation_key, purpose, int(amount_minor),
                    classification, evidence_reference, notes,
                ),
            )
        return allocation_id

    def debt_summary(self, store_id: str) -> dict[str, Any]:
        with self.connect() as connection:
            rows = connection.execute(
                """SELECT d.*,
                          COALESCE((SELECT SUM(a.amount_minor) FROM debt_allocations a WHERE a.debt_id=d.id),0) allocated_minor
                   FROM debt_items d WHERE d.store_id=? ORDER BY d.received_on, d.lender""",
                (store_id,),
            ).fetchall()
            allocation_rows = connection.execute(
                """SELECT a.id, a.debt_id, d.lender, a.allocation_key, a.purpose,
                          a.amount_minor, a.classification, a.evidence_reference, a.notes
                   FROM debt_allocations a JOIN debt_items d ON d.id=a.debt_id
                   WHERE d.store_id=? ORDER BY d.received_on, d.lender, a.allocation_key""",
                (store_id,),
            ).fetchall()
            ledger_row = connection.execute(
                """SELECT COALESCE(SUM(jl.credit_minor - jl.debit_minor), 0) balance_minor,
                          COUNT(DISTINCT je.id) entry_count
                   FROM journal_entries je
                   JOIN journal_lines jl ON jl.journal_entry_id=je.id
                   JOIN accounts a ON a.id=jl.account_id
                   WHERE je.store_id=? AND je.status='posted' AND a.code='2003'""",
                (store_id,),
            ).fetchone()
        items = [dict(row) for row in rows]
        registered_principal = sum(int(row["principal_minor"]) for row in items)
        stored_repaid = sum(int(row["repaid_principal_minor"]) for row in items)
        allocated = sum(int(row["allocated_minor"]) for row in items)
        has_ledger_debt = bool(ledger_row and int(ledger_row["entry_count"] or 0))
        ledger_outstanding = max(int(ledger_row["balance_minor"] or 0), 0) if ledger_row else 0
        registered_outstanding = max(registered_principal - stored_repaid, 0)
        registry_gap = max(ledger_outstanding - registered_outstanding, 0) if has_ledger_debt else 0
        principal = registered_principal + registry_gap
        outstanding = ledger_outstanding if has_ledger_debt else registered_outstanding
        repaid = max(principal - outstanding, stored_repaid)
        remaining_inferred_repayment = max(repaid - stored_repaid, 0)
        for item in items:
            if remaining_inferred_repayment <= 0:
                break
            capacity = max(int(item["principal_minor"]) - int(item["repaid_principal_minor"]), 0)
            applied = min(capacity, remaining_inferred_repayment)
            item["repaid_principal_minor"] = int(item["repaid_principal_minor"]) + applied
            remaining_inferred_repayment -= applied
        return {
            "principal_minor": principal,
            "repaid_principal_minor": repaid,
            "outstanding_minor": outstanding,
            "allocated_minor": allocated,
            "unallocated_minor": max(principal - allocated, 0),
            "total_financing_and_uses_minor": principal,
            "ledger_outstanding_minor": ledger_outstanding if has_ledger_debt else None,
            "registry_gap_minor": registry_gap,
            "items": items,
            "allocations": [dict(row) for row in allocation_rows],
        }

    def _period_id(self, connection: sqlite3.Connection, store_id: str, entry_date: str) -> str:
        month = entry_date[:7]
        period_id = f"{store_id}:{month}"
        connection.execute(
            """INSERT OR IGNORE INTO accounting_periods
               (id, store_id, period_start, period_end, status)
               VALUES (?, ?, ?, ?, 'open')""",
            (period_id, store_id, f"{month}-01", f"{month}-31"),
        )
        return period_id

    def post_entry(
        self,
        *,
        store_id: str,
        entry_date: str,
        posting_key: str,
        description: str,
        lines: Iterable[tuple[str, int, int]],
        business_fact_id: str | None = None,
        entry_type: str = "automatic",
    ) -> str:
        normalized = [(code, int(debit), int(credit)) for code, debit, credit in lines]
        debit_total = sum(line[1] for line in normalized)
        credit_total = sum(line[2] for line in normalized)
        if debit_total <= 0 or debit_total != credit_total:
            raise FinanceMigrationError(f"借贷不平衡：借 {debit_total}，贷 {credit_total}")
        if any((debit <= 0) == (credit <= 0) for _, debit, credit in normalized):
            raise FinanceMigrationError("每行分录必须且只能有借方或贷方金额")

        with self.connect() as connection:
            existing = connection.execute(
                "SELECT id FROM journal_entries WHERE store_id = ? AND posting_key = ?",
                (store_id, posting_key),
            ).fetchone()
            if existing:
                return str(existing["id"])
            period_id = self._period_id(connection, store_id, entry_date)
            entry_id = f"je:{store_id}:{hashlib.sha256(posting_key.encode()).hexdigest()[:20]}"
            connection.execute(
                """INSERT INTO journal_entries
                   (id, store_id, accounting_period_id, business_fact_id, entry_date, entry_type,
                    status, posting_key, description, created_at, posted_at)
                   VALUES (?, ?, ?, ?, ?, ?, 'posted', ?, ?, datetime('now'), datetime('now'))""",
                (entry_id, store_id, period_id, business_fact_id, entry_date, entry_type, posting_key, description),
            )
            for index, (code, debit, credit) in enumerate(normalized):
                account = connection.execute(
                    "SELECT id FROM accounts WHERE store_id = ? AND code = ?",
                    (store_id, code),
                ).fetchone()
                if not account:
                    raise FinanceMigrationError(f"会计科目不存在：{code}")
                connection.execute(
                    """INSERT INTO journal_lines
                       (id, journal_entry_id, account_id, debit_minor, credit_minor)
                       VALUES (?, ?, ?, ?, ?)""",
                    (f"{entry_id}:{index}", entry_id, account["id"], debit, credit),
                )
            return entry_id

    def migrate_daily_operations(self, payload: dict[str, Any]) -> dict[str, Any]:
        store_id = str(payload["project_id"])
        profile = payload.get("profile") or {}
        self.ensure_store(
            store_id,
            str(profile.get("store_name") or profile.get("name") or store_id),
            str(profile.get("transfer_date") or datetime.now().strftime("%Y-%m-%d")),
        )
        self._migrate_profile_facts(store_id, profile)
        entries = sorted(payload.get("daily_operations") or [], key=lambda row: row.get("date", ""))
        new_entries = 0
        for operation in entries:
            if self._migrate_operation(store_id, operation):
                new_entries += 1
        self._repair_legacy_digital_receipts(store_id, entries)
        return {"store_id": store_id, "migrated_days": len(entries), "new_entries": new_entries}

    def _repair_legacy_digital_receipts(self, store_id: str, entries: list[dict[str, Any]]) -> None:
        """Move legacy same-day digital receipts from bank to pending settlement.

        Older builds treated WeChat/Alipay POS sales as already in the bank on the
        business date. The real store settles them later, usually the next day.
        This idempotent adjustment preserves revenue and only repairs money location.
        """
        for operation in entries:
            business_date = str(operation.get("date") or "")
            if not business_date or operation.get("settlement_breakdown"):
                continue
            desired_pending = sum(
                money_to_minor(payment.get("amount"))
                for payment in operation.get("payment_methods") or []
                if str(payment.get("method", "")) != "现金"
                and str(payment.get("method", "")) not in FORMER_OWNER_METHODS
            )
            if desired_pending <= 0:
                continue
            original_key = f"migration:daily-revenue:{store_id}:{business_date}"
            with self.connect() as connection:
                row = connection.execute(
                    """SELECT COALESCE(SUM(jl.debit_minor), 0) amount
                       FROM journal_entries je JOIN journal_lines jl ON jl.journal_entry_id = je.id
                       JOIN accounts a ON a.id = jl.account_id
                       WHERE je.store_id = ? AND je.posting_key = ? AND a.code = '1002'""",
                    (store_id, original_key),
                ).fetchone()
            legacy_bank_debit = int(row["amount"] or 0)
            correction = min(legacy_bank_debit, desired_pending)
            if correction:
                self.post_entry(
                    store_id=store_id,
                    entry_date=business_date,
                    posting_key=f"settlement-reclass-v1:{store_id}:{business_date}",
                    description=f"{business_date} 数字收款改列待结算",
                    lines=[("1012", correction, 0), ("1002", 0, correction)],
                    entry_type="adjustment",
                )

    def _migrate_profile_facts(self, store_id: str, profile: dict[str, Any]) -> None:
        date = str(profile.get("transfer_date") or datetime.now().strftime("%Y-%m-%d"))
        candidates = (
            ("transfer_fee", "门店转让费", profile.get("transfer_fee"), "long_term_asset_review"),
            ("initial_inventory_purchase", "首批库存采购", profile.get("initial_inventory_purchase"), "inventory_purchase_review"),
        )
        with self.connect() as connection:
            for fact_type, title, value, accounting_review in candidates:
                amount = money_to_minor(value)
                if amount <= 0:
                    continue
                fact_id = f"fact:{store_id}:profile:{fact_type}"
                connection.execute(
                    """INSERT OR IGNORE INTO business_facts
                       (id, store_id, fact_type, occurred_on, amount_minor, dimensions_json,
                        review_status, posting_status, dedup_key, created_at, confirmed_at)
                       VALUES (?, ?, ?, ?, ?, ?, 'confirmed', 'unposted', ?, datetime('now'), datetime('now'))""",
                    (fact_id, store_id, fact_type, date, amount, json.dumps({"title": title, "accounting_review": accounting_review}, ensure_ascii=False), fact_id),
                )

    def _migrate_operation(self, store_id: str, operation: dict[str, Any]) -> bool:
        date = str(operation["date"])
        revenue = money_to_minor(operation.get("actual_revenue") or operation.get("revenue"))
        posting_key = f"migration:daily-revenue:{store_id}:{date}"
        with self.connect() as connection:
            exists = connection.execute(
                "SELECT 1 FROM journal_entries WHERE store_id = ? AND posting_key = ?",
                (store_id, posting_key),
            ).fetchone()
        if exists:
            return False

        source_id = f"source:{store_id}:memory:{date}"
        fact_id = f"fact:{store_id}:daily-revenue:{date}"
        raw_json = json.dumps(operation, ensure_ascii=False, sort_keys=True)
        with self.connect() as connection:
            connection.execute(
                """INSERT OR IGNORE INTO source_documents
                   (id, store_id, source_type, source_platform, file_name, content_hash,
                    captured_at, period_start, period_end, raw_payload_json)
                   VALUES (?, ?, 'legacy_json_migration', 'keruyun', 'memory.json', ?, datetime('now'), ?, ?, ?)""",
                (source_id, store_id, hashlib.sha256(raw_json.encode()).hexdigest(), date, date, raw_json),
            )
            connection.execute(
                """INSERT OR IGNORE INTO business_facts
                   (id, store_id, source_document_id, fact_type, occurred_on, amount_minor,
                    review_status, posting_status, dedup_key, created_at, confirmed_at)
                   VALUES (?, ?, ?, 'daily_recognized_revenue', ?, ?, 'confirmed', 'unposted', ?, datetime('now'), datetime('now'))""",
                (fact_id, store_id, source_id, date, revenue, posting_key),
            )

        debit_lines = self._settlement_lines(operation, revenue)
        credit_lines = self._revenue_lines(operation, revenue)
        self.post_entry(
            store_id=store_id,
            entry_date=date,
            posting_key=posting_key,
            description=f"{date} 已确认营业收入",
            business_fact_id=fact_id,
            lines=[*debit_lines, *credit_lines],
        )
        with self.connect() as connection:
            connection.execute("UPDATE business_facts SET posting_status = 'posted' WHERE id = ?", (fact_id,))
            for channel, amount, orders in self._sales_rows(operation, revenue):
                connection.execute(
                    """INSERT OR IGNORE INTO sales_daily
                       (id, store_id, business_date, channel, recognized_revenue_minor,
                        order_count, item_count, source_document_id, basis)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'keruyun_recognized_revenue')""",
                    (
                        f"sales:{store_id}:{date}:{channel}", store_id, date, channel, amount, orders,
                        int(operation.get("items_sold", 0) or 0) if channel == "unallocated" else None,
                        source_id,
                    ),
                )
        return True

    def record_confirmed_daily_revenue(self, store_id: str, operation: dict[str, Any]) -> bool:
        """Post an owner-confirmed daily sales fact into the canonical ledger.

        This deliberately reuses the idempotent daily posting contract used by
        migration so chat confirmation and imported history cannot double count.
        """
        if not operation.get("date"):
            raise FinanceMigrationError("营业收入缺少营业日期")
        if money_to_minor(operation.get("actual_revenue") or operation.get("revenue")) <= 0:
            raise FinanceMigrationError("营业收入必须大于 0")
        self.ensure_store(store_id, store_id, str(operation["date"]))
        return self._migrate_operation(store_id, operation)

    def record_inventory_movement(
        self, store_id: str, *, movement_id: str, item_id: str, item_name: str,
        business_date: str, movement_type: str, quantity: float, unit_cost: float,
    ) -> dict[str, Any]:
        """Mirror a confirmed warehouse movement into inventory accounting."""
        self.ensure_store(store_id, store_id, business_date)
        unit_cost_minor = money_to_minor(unit_cost)
        amount_minor = round(abs(Decimal(str(quantity))) * unit_cost_minor)
        if amount_minor <= 0:
            return {"posted": False, "reason": "missing_unit_cost"}
        normalized_type = {
            "stock_in": "purchase", "usage": "usage", "loss": "waste",
            "count_adjustment": "count_adjustment",
        }.get(movement_type, movement_type)
        with self.connect() as connection:
            connection.execute(
                """INSERT OR IGNORE INTO inventory_items(id, store_id, name, category, base_unit)
                   VALUES (?, ?, ?, 'ingredient', '库存单位')""",
                (item_id, store_id, item_name),
            )
            existing = connection.execute(
                "SELECT id FROM inventory_movements WHERE id = ?", (movement_id,),
            ).fetchone()
            if existing:
                return {"posted": False, "reason": "already_posted"}
            connection.execute(
                """INSERT INTO inventory_movements
                   (id, store_id, item_id, occurred_on, movement_type, quantity, unit_cost_minor)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (movement_id, store_id, item_id, business_date, normalized_type, quantity, unit_cost_minor),
            )
        if normalized_type in {"purchase", "opening"} or (normalized_type == "count_adjustment" and quantity > 0):
            lines = [("1401", amount_minor, 0), ("2001", 0, amount_minor)]
        elif normalized_type == "usage":
            lines = [("5001", amount_minor, 0), ("1401", 0, amount_minor)]
        else:
            lines = [("5005", amount_minor, 0), ("1401", 0, amount_minor)]
        entry_id = self.post_entry(
            store_id=store_id, entry_date=business_date,
            posting_key=f"inventory:{movement_id}", description=f"{item_name} {movement_type}",
            lines=lines,
        )
        return {"posted": True, "entry_id": entry_id, "amount_minor": amount_minor}

    def _settlement_lines(self, operation: dict[str, Any], revenue: int) -> list[tuple[str, int, int]]:
        buckets: dict[str, int] = {}
        breakdown = operation.get("settlement_breakdown") or []
        if breakdown:
            for item in breakdown:
                if item.get("status") == "cash_on_hand":
                    code = "1001"
                elif item.get("owner") == "former_owner":
                    code = "1013"
                else:
                    code = "1019"
                buckets[code] = buckets.get(code, 0) + money_to_minor(item.get("amount"))
        else:
            for payment in operation.get("payment_methods") or []:
                method = str(payment.get("method", ""))
                # 营业发生日只确认收入和资金位置。现金当天在店；微信/支付宝等
                # POS 数字收款通常次日才入银行卡；线上平台结算更晚。只有明确由
                # 前老板代收的平台款进入 1013，其他数字收款先进入 1012。
                code = "1001" if method == "现金" else "1013" if method in FORMER_OWNER_METHODS else "1012"
                buckets[code] = buckets.get(code, 0) + money_to_minor(payment.get("amount"))
        allocated = sum(buckets.values())
        if allocated < revenue:
            buckets["1019"] = buckets.get("1019", 0) + revenue - allocated
        elif allocated > revenue:
            raise FinanceMigrationError(f"{operation['date']} 收款归属超过营业收入")
        return [(code, amount, 0) for code, amount in sorted(buckets.items()) if amount]

    def _sales_rows(self, operation: dict[str, Any], revenue: int) -> list[tuple[str, int, int | None]]:
        dine_in = money_to_minor(operation.get("dine_in_revenue"))
        delivery = money_to_minor(operation.get("delivery_revenue"))
        if dine_in + delivery == revenue and (dine_in or delivery):
            return [
                ("dine_in", dine_in, int(operation.get("dine_in_orders", 0) or 0)),
                ("delivery", delivery, int(operation.get("delivery_orders", 0) or 0)),
            ]
        return [("unallocated", revenue, int(operation.get("orders", 0) or 0))]

    def _revenue_lines(self, operation: dict[str, Any], revenue: int) -> list[tuple[str, int, int]]:
        mapping = {"dine_in": "4001", "delivery": "4002", "unallocated": "4009"}
        return [(mapping[channel], 0, amount) for channel, amount, _ in self._sales_rows(operation, revenue) if amount]

    def count_posted_entries(self, store_id: str) -> int:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT COUNT(*) count FROM journal_entries WHERE store_id = ? AND status = 'posted'",
                (store_id,),
            ).fetchone()
            return int(row["count"])

    def unbalanced_entries(self, store_id: str) -> list[str]:
        with self.connect() as connection:
            rows = connection.execute(
                """SELECT je.id
                   FROM journal_entries je JOIN journal_lines jl ON jl.journal_entry_id = je.id
                   WHERE je.store_id = ? AND je.status = 'posted'
                   GROUP BY je.id HAVING SUM(jl.debit_minor) != SUM(jl.credit_minor)""",
                (store_id,),
            ).fetchall()
            return [str(row["id"]) for row in rows]

    def revenue_total(self, store_id: str, start: str, end: str) -> int:
        with self.connect() as connection:
            row = connection.execute(
                """SELECT COALESCE(SUM(credit_minor - debit_minor), 0) total
                   FROM journal_lines jl JOIN journal_entries je ON je.id = jl.journal_entry_id
                   JOIN accounts a ON a.id = jl.account_id
                   WHERE je.store_id = ? AND je.status = 'posted' AND je.entry_date BETWEEN ? AND ?
                     AND a.account_type IN ('revenue', 'contra_revenue')""",
                (store_id, start, end),
            ).fetchone()
            return int(row["total"])

    def order_total(self, store_id: str, start: str, end: str) -> int:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT COALESCE(SUM(order_count), 0) total FROM sales_daily WHERE store_id = ? AND business_date BETWEEN ? AND ?",
                (store_id, start, end),
            ).fetchone()
            return int(row["total"])

    def account_balances(self, store_id: str, start: str, end: str) -> dict[str, int]:
        with self.connect() as connection:
            rows = connection.execute(
                """SELECT a.code, a.account_type,
                          COALESCE(SUM(CASE WHEN je.id IS NOT NULL THEN jl.debit_minor ELSE 0 END), 0) debit,
                          COALESCE(SUM(CASE WHEN je.id IS NOT NULL THEN jl.credit_minor ELSE 0 END), 0) credit
                   FROM accounts a
                   LEFT JOIN journal_lines jl ON jl.account_id = a.id
                   LEFT JOIN journal_entries je ON je.id = jl.journal_entry_id
                     AND je.status = 'posted' AND je.entry_date BETWEEN ? AND ?
                   WHERE a.store_id = ? GROUP BY a.id""",
                (start, end, store_id),
            ).fetchall()
        result = {}
        for row in rows:
            normal_debit = row["account_type"] in {"asset", "cost", "expense", "contra_revenue", "management_only"}
            result[str(row["code"])] = int(row["debit"] - row["credit"] if normal_debit else row["credit"] - row["debit"])
        return result

    def record_former_owner_transfer(self, store_id: str, date: str, amount_minor: int, reference: str) -> str:
        if amount_minor <= 0:
            raise FinanceMigrationError("到账金额必须大于 0")
        return self.post_entry(
            store_id=store_id,
            entry_date=date,
            posting_key=f"former-owner-transfer:{reference}",
            description="前老板代收款转回",
            lines=[("1002", amount_minor, 0), ("1013", 0, amount_minor)],
        )

    def record_platform_settlement(self, store_id: str, date: str, amount_minor: int, reference: str) -> str:
        """Confirm a delayed POS/platform receipt without recognizing revenue twice."""
        if amount_minor <= 0:
            raise FinanceMigrationError("到账金额必须大于 0")
        return self.post_entry(
            store_id=store_id,
            entry_date=date,
            posting_key=f"platform-settlement:{reference}",
            description="客如云/POS或线上平台结算到账",
            lines=[("1002", amount_minor, 0), ("1012", 0, amount_minor)],
        )

    def record_owner_paid_inventory_purchase(
        self,
        store_id: str,
        *,
        fact_id: str,
        receipt_date: str,
        payments: list[dict[str, Any]],
        supplier: str,
        reference: str,
    ) -> dict[str, Any]:
        """Record a mixed-personal-card inventory purchase without inventing store bank cash.

        Each owner-paid installment creates a supplier prepayment funded by owner equity.
        On receipt, the prepayment is reclassified to inventory. Retries are idempotent.
        """
        total = sum(int(item.get("amount_minor", 0)) for item in payments)
        if total <= 0 or any(int(item.get("amount_minor", 0)) <= 0 for item in payments):
            raise FinanceMigrationError("库存采购付款金额必须大于0")
        self.ensure_store(store_id, store_id, receipt_date)
        with self.connect() as connection:
            fact_exists = connection.execute(
                "SELECT 1 FROM business_facts WHERE id=? AND store_id=?", (fact_id, store_id)
            ).fetchone()
        payment_entries = []
        for index, payment in enumerate(payments, 1):
            amount = int(payment["amount_minor"])
            payment_entries.append(self.post_entry(
                store_id=store_id,
                entry_date=str(payment["date"]),
                posting_key=f"inventory-prepayment:{reference}:{index}",
                description=f"老板代付{supplier}库存货款（第{index}笔）",
                lines=[("1410", amount, 0), ("3001", 0, amount)],
                entry_type="manual",
            ))
        receipt_entry = self.post_entry(
            store_id=store_id,
            entry_date=receipt_date,
            posting_key=f"inventory-receipt:{reference}",
            description=f"{supplier}采购到货转库存",
            lines=[("1401", total, 0), ("1410", 0, total)],
            business_fact_id=fact_id if fact_exists else None,
            entry_type="manual",
        )
        if fact_exists:
            with self.connect() as connection:
                connection.execute(
                    "UPDATE business_facts SET posting_status='posted' WHERE id=? AND store_id=?",
                    (fact_id, store_id),
                )
        return {"payment_entries": payment_entries, "receipt_entry": receipt_entry, "amount_minor": total}

    def record_capital_event(
        self, store_id: str, date: str, event_type: str, amount_minor: int,
        reference: str, money_account: str = "1002", description: str = "",
    ) -> str:
        if amount_minor <= 0:
            raise FinanceMigrationError("金额必须大于 0")
        if money_account not in {"1001", "1002"}:
            raise FinanceMigrationError("资金账户只能是现金或银行存款")
        templates = {
            "owner_investment": [(money_account, amount_minor, 0), ("3001", 0, amount_minor)],
            "owner_draw": [("3002", amount_minor, 0), (money_account, 0, amount_minor)],
            "loan_in": [(money_account, amount_minor, 0), ("2003", 0, amount_minor)],
            "loan_repayment": [("2003", amount_minor, 0), (money_account, 0, amount_minor)],
            "equipment_purchase": [("1601", amount_minor, 0), (money_account, 0, amount_minor)],
            "deposit_payment": [("1801", amount_minor, 0), (money_account, 0, amount_minor)],
        }
        if event_type not in templates:
            raise FinanceMigrationError(f"不支持的资金事件：{event_type}")
        entry_id = self.post_entry(
            store_id=store_id, entry_date=date, posting_key=f"capital:{reference}",
            description=description or event_type, lines=templates[event_type],
        )
        if event_type == "loan_in":
            self.record_debt(
                store_id,
                debt_key=f"capital-{hashlib.sha256(reference.encode()).hexdigest()[:20]}",
                lender=description or "待补充出借人",
                principal_minor=amount_minor,
                received_on=date,
                status="active",
                notes=f"由资金事件 {reference} 自动建立",
            )
        return entry_id

    def set_financial_target(self, store_id: str, target_type: str, start: str, end: str, amount_minor: int) -> str:
        if target_type not in {"monthly_profit", "minimum_cash", "revenue"}:
            raise FinanceMigrationError(f"不支持的目标：{target_type}")
        target_id = f"target:{store_id}:{target_type}:{start}:{end}"
        with self.connect() as connection:
            connection.execute(
                """INSERT INTO financial_targets(id, store_id, target_type, period_start, period_end, amount_minor, status)
                   VALUES (?, ?, ?, ?, ?, ?, 'active')
                   ON CONFLICT(id) DO UPDATE SET amount_minor=excluded.amount_minor, status='active'""",
                (target_id, store_id, target_type, start, end, amount_minor),
            )
        return target_id

    def financial_targets(self, store_id: str, start: str, end: str) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """SELECT target_type, period_start, period_end, amount_minor, status
                   FROM financial_targets WHERE store_id = ? AND period_end >= ? AND period_start <= ?
                   ORDER BY period_start, target_type""",
                (store_id, start, end),
            ).fetchall()
            return [dict(row) for row in rows]

    def cash_flow_summary(self, store_id: str, start: str, end: str) -> dict[str, int]:
        with self.connect() as connection:
            rows = connection.execute(
                """SELECT je.id, a.code, jl.debit_minor, jl.credit_minor
                   FROM journal_entries je JOIN journal_lines jl ON jl.journal_entry_id = je.id
                   JOIN accounts a ON a.id = jl.account_id
                   WHERE je.store_id = ? AND je.status = 'posted' AND je.entry_date BETWEEN ? AND ?
                   ORDER BY je.id""",
                (store_id, start, end),
            ).fetchall()
        entries: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            entries.setdefault(str(row["id"]), []).append(dict(row))
        result = {"operating": 0, "investing": 0, "financing": 0}
        for lines in entries.values():
            cash_change = sum(
                int(line["debit_minor"]) - int(line["credit_minor"])
                for line in lines if line["code"] in {"1001", "1002"}
            )
            if not cash_change:
                continue
            codes = {str(line["code"]) for line in lines}
            if codes & {"1601", "1801"}:
                result["investing"] += cash_change
            elif codes & {"2003", "3001", "3002"}:
                result["financing"] += cash_change
            else:
                result["operating"] += cash_change
        result["net_change"] = sum(result.values())
        return result

    def profit_readiness(self, store_id: str, start: str, end: str) -> dict[str, Any]:
        revenue = self.revenue_total(store_id, start, end)
        required_cost_inputs = {
            "food_cost_minor": "food_cost",
            "packaging_cost_minor": "packaging_cost",
            "overtime_hours": "labor",
            "rent_minor": "rent",
            "utility_minor": "utility",
            "other_cost_minor": "other_cost",
        }
        with self.connect() as connection:
            sales_days = {
                row["business_date"] for row in connection.execute(
                    "SELECT DISTINCT business_date FROM sales_daily WHERE store_id = ? AND business_date BETWEEN ? AND ?",
                    (store_id, start, end),
                )
            }
            closed_days = {
                row["business_date"] for row in connection.execute(
                    "SELECT business_date FROM daily_close_sessions WHERE store_id = ? AND business_date BETWEEN ? AND ? AND status = 'closed'",
                    (store_id, start, end),
                )
            }
            rows = connection.execute(
                """SELECT business_date, status, missing_inputs_json, inputs_json
                   FROM daily_close_sessions
                   WHERE store_id = ? AND business_date BETWEEN ? AND ?""",
                (store_id, start, end),
            ).fetchall()
        close_by_day = {str(row["business_date"]): row for row in rows}
        missing: set[str] = set()
        if not sales_days:
            missing.add("daily_sales")
        if sales_days != closed_days:
            missing.add("daily_close")
        for business_date in sales_days:
            row = close_by_day.get(business_date)
            if not row or row["status"] != "closed":
                missing.update(required_cost_inputs.values())
                continue
            missing.update(
                item for item in json.loads(row["missing_inputs_json"] or "[]")
                if item != "cash_count"
            )
            inputs = json.loads(row["inputs_json"] or "{}")
            for field, reason in required_cost_inputs.items():
                if inputs.get(field) is None:
                    missing.add(reason)
        ready = bool(sales_days) and sales_days == closed_days and not missing
        balances = self.account_balances(store_id, start, end)
        expense_codes = [code for code, _, kind in ACCOUNT_SEED if kind in {"cost", "expense"}]
        total_cost = sum(balances.get(code, 0) for code in expense_codes)
        return {
            "period_start": start,
            "period_end": end,
            "revenue_minor": revenue,
            "status": "confirmed" if ready else "incomplete",
            "net_profit_minor": revenue - total_cost if ready else None,
            "total_cost_minor": total_cost if ready else None,
            "blocking_reasons": sorted(missing),
            "closed_days": len(closed_days),
            "sales_days": len(sales_days),
        }

    def period_bounds(self, store_id: str) -> tuple[str | None, str | None]:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT MIN(business_date) start, MAX(business_date) end FROM sales_daily WHERE store_id = ?",
                (store_id,),
            ).fetchone()
            sales_start, sales_end = row["start"], row["end"]

            row = connection.execute(
                "SELECT MIN(entry_date) start, MAX(entry_date) end FROM journal_entries WHERE store_id = ?",
                (store_id,),
            ).fetchone()
            je_start, je_end = row["start"], row["end"]

            row = connection.execute(
                "SELECT MIN(business_date) start, MAX(business_date) end FROM merchant_net_sales WHERE store_id = ?",
                (store_id,),
            ).fetchone()
            merchant_start, merchant_end = row["start"], row["end"]

            starts = [value for value in (sales_start, je_start, merchant_start) if value]
            ends = [value for value in (sales_end, je_end, merchant_end) if value]
            start = min(starts) if starts else None
            end = max(ends) if ends else None
            return start, end

    def daily_revenue(self, store_id: str, start: str, end: str) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """SELECT business_date, SUM(recognized_revenue_minor) revenue_minor,
                          SUM(COALESCE(order_count, 0)) orders
                   FROM sales_daily WHERE store_id = ? AND business_date BETWEEN ? AND ?
                   GROUP BY business_date ORDER BY business_date""",
                (store_id, start, end),
            ).fetchall()
            return [dict(row) for row in rows]

    def operating_calendar(self, store_id: str, start: str, end: str) -> list[dict[str, Any]]:
        """Return every Shanghai calendar day, including days without uploads."""
        if start.startswith("0000-"):
            first, _ = self.period_bounds(store_id)
            start = first or end
        revenue_rows = {row["business_date"]: row for row in self.daily_revenue(store_id, start, end)}
        with self.connect() as connection:
            close_rows = {
                row["business_date"]: row["status"]
                for row in connection.execute(
                    "SELECT business_date, status FROM daily_close_sessions WHERE store_id = ? AND business_date BETWEEN ? AND ?",
                    (store_id, start, end),
                )
            }
        current = date.fromisoformat(start)
        last = date.fromisoformat(end)
        rows: list[dict[str, Any]] = []
        while current <= last:
            business_date = current.isoformat()
            sales = revenue_rows.get(business_date)
            close_status = close_rows.get(business_date)
            status = "closed" if close_status == "closed" else "partial" if sales or close_status else "missing"
            rows.append({
                "business_date": business_date,
                "revenue_minor": sales["revenue_minor"] if sales else None,
                "orders": sales["orders"] if sales else None,
                "status": status,
                "missing_inputs": [] if status == "closed" else (["daily_sales"] if not sales else ["daily_close"]),
            })
            current += timedelta(days=1)
        return rows

    def cost_totals(self, store_id: str, start: str, end: str) -> dict[str, int]:
        balances = self.account_balances(store_id, start, end)
        mapping = {
            "food_cost": "5001", "packaging_cost": "5002", "platform_cost": "5003",
            "marketing_cost": "5004", "waste_cost": "5005", "labor": "6001",
            "rent": "6002", "utility": "6003", "systems": "6004",
            "other": "6005", "depreciation": "6006",
        }
        return {name: balances.get(code, 0) for name, code in mapping.items()}

    def spending_summary(self, store_id: str, start: str, end: str) -> dict[str, int]:
        """Separate actual money paid from P&L cost and unpaid commitments."""
        with self.connect() as connection:
            rows = connection.execute(
                """SELECT je.id, je.posting_key, a.code, jl.debit_minor, jl.credit_minor
                   FROM journal_entries je JOIN journal_lines jl ON jl.journal_entry_id = je.id
                   JOIN accounts a ON a.id = jl.account_id
                   WHERE je.store_id = ? AND je.status = 'posted' AND je.entry_date BETWEEN ? AND ?""",
                (store_id, start, end),
            ).fetchall()
        cash_bank_paid = sum(
            int(row["credit_minor"])
            for row in rows
            if row["code"] in {"1001", "1002"}
            and not str(row["posting_key"]).startswith("settlement-reclass-v1:")
        )
        owner_paid = sum(
            int(row["credit_minor"])
            for row in rows
            if row["code"] == "3001" and str(row["posting_key"]).startswith("inventory-prepayment:")
        )
        balances = self.account_balances(store_id, start, end)
        unpaid = sum(max(balances.get(code, 0), 0) for code in ("2001", "2002", "2003", "2009"))
        actual_paid = cash_bank_paid + owner_paid
        return {
            "store_cash_bank_paid": cash_bank_paid,
            "owner_paid_for_store": owner_paid,
            "actual_paid": actual_paid,
            "unpaid_committed": unpaid,
            "recorded_total_spending": actual_paid + unpaid,
        }

    def finance_overview(self, store_id: str, start: str | None = None, end: str | None = None) -> dict[str, Any]:
        first, last = self.period_bounds(store_id)
        shanghai_today = datetime.now(ZoneInfo("Asia/Shanghai")).date().isoformat()
        start, end = start or first, end or shanghai_today
        if not start or not end:
            return {"store_id": store_id, "period_start": start, "period_end": end, "has_data": False}
        revenue = self.revenue_total(store_id, start, end)
        orders = self.order_total(store_id, start, end)
        order_covered_revenue = sum(
            int(row["revenue_minor"] or 0)
            for row in self.daily_revenue(store_id, start, end)
        )
        order_coverage_status = (
            "complete" if orders > 0 and order_covered_revenue == revenue
            else "partial" if orders > 0
            else "missing"
        )
        balances = self.account_balances(store_id, start, end)
        readiness = self.profit_readiness(store_id, start, end)
        costs = self.cost_totals(store_id, start, end)
        known_cost = sum(costs.values())
        estimated_adjustments: dict[str, int] = {}
        inventory_usage_bridge: dict[str, Any] = {
            "status": "not_enough_data",
            "period_start": start,
            "period_end": end,
            "food_cost": 0,
            "packaging_cost": 0,
            "other_consumables_cost": 0,
            "total_usage_cost": 0,
            "evidence_event_ids": [],
            "accounting_boundary": "仅作暂估成本桥接；不自动过账，不覆盖已过账实际成本",
        }
        try:
            from models.project import ProjectMemory
            from models.sku import SkuCatalog
            from models.store_facts import StoreFactBook

            memory = ProjectMemory.load(store_id)
            profile = memory.profile if memory else {}
            monthly_labor = money_to_minor(profile.get("monthly_labor"))
            if costs["labor"] == 0 and monthly_labor > 0 and readiness["sales_days"]:
                estimated_adjustments["labor"] = round(monthly_labor / 31 * readiness["sales_days"])
            fact_summary = StoreFactBook.load(store_id).finance_summary()
            packaging_estimate = int(fact_summary.get("estimated_packaging_cost_minor", 0))
            if costs["packaging_cost"] == 0 and packaging_estimate > 0:
                estimated_adjustments["packaging_cost"] = packaging_estimate
            catalog = SkuCatalog.load(store_id)
            if catalog is not None:
                inventory_usage_bridge = catalog.period_usage_cost_summary(start, end)
                food_usage_minor = money_to_minor(inventory_usage_bridge.get("food_cost"))
                packaging_usage_minor = money_to_minor(inventory_usage_bridge.get("packaging_cost"))
                if costs["food_cost"] == 0 and food_usage_minor > 0:
                    estimated_adjustments["food_cost"] = food_usage_minor
                if costs["packaging_cost"] == 0 and packaging_usage_minor > 0:
                    estimated_adjustments["packaging_cost"] = packaging_usage_minor
        except (FileNotFoundError, TypeError, ValueError):
            estimated_adjustments = {}
        provisional_cost = known_cost + sum(estimated_adjustments.values())
        net_profit = readiness["net_profit_minor"]
        contribution_cost = sum(costs[key] for key in ("food_cost", "packaging_cost", "platform_cost", "marketing_cost", "waste_cost"))
        contribution_margin = revenue - contribution_cost
        contribution_margin_rate = contribution_margin / revenue if revenue and readiness["status"] == "confirmed" else None
        fixed_cost = sum(costs[key] for key in ("labor", "rent", "utility", "systems", "other", "depreciation"))
        break_even = round(fixed_cost / contribution_margin_rate) if contribution_margin_rate and contribution_margin_rate > 0 else None
        with self.connect() as connection:
            pending_capital_rows = connection.execute(
                """SELECT fact_type, occurred_on, amount_minor, dimensions_json
                   FROM business_facts WHERE store_id = ? AND posting_status = 'unposted'
                     AND fact_type IN ('transfer_fee', 'initial_inventory_purchase') ORDER BY occurred_on""",
                (store_id,),
            ).fetchall()
        pending_capital = []
        for row in pending_capital_rows:
            dimensions = json.loads(row["dimensions_json"] or "{}")
            pending_capital.append({
                "fact_type": row["fact_type"], "date": row["occurred_on"], "amount_minor": row["amount_minor"],
                "title": dimensions.get("title"), "status": "awaiting_posting_details",
            })
        merchant_rows = self.merchant_net_sales(store_id, start, end)
        merchant_net = sum(int(row["merchant_net_minor"]) for row in merchant_rows)
        fund_positions = self.fund_positions(store_id, end)
        controlled_funds = sum(
            int(row["balance_minor"])
            for row in fund_positions
            if row["is_store_controlled"] and row["status"] == "active"
        )
        debt = self.debt_summary(store_id)
        return {
            "store_id": store_id,
            "has_data": True,
            "period_start": start,
            "period_end": end,
            "last_data_date": last,
            "calendar_today": shanghai_today,
            "revenue_minor": revenue,
            "merchant_net_minor": merchant_net,
            "merchant_net_status": "confirmed" if merchant_rows and all(row["evidence_status"] == "confirmed" for row in merchant_rows) else "partial" if merchant_rows else "missing",
            "merchant_net_sales": merchant_rows,
            "orders": orders,
            "order_covered_revenue_minor": order_covered_revenue,
            "order_coverage_status": order_coverage_status,
            "average_order_value_minor": round(order_covered_revenue / orders) if orders else None,
            "profit_status": readiness["status"],
            "net_profit_minor": net_profit,
            "net_margin": net_profit / revenue if net_profit is not None and revenue else None,
            "total_cost_minor": readiness["total_cost_minor"],
            "known_operating_cost_minor": known_cost,
            "estimated_adjustments_minor": estimated_adjustments,
            "inventory_usage_bridge": inventory_usage_bridge,
            "provisional_operating_cost_minor": provisional_cost,
            "provisional_net_profit_minor": revenue - provisional_cost,
            "provisional_profit_status": "estimated_incomplete" if readiness["status"] != "confirmed" else "confirmed",
            "costs_minor": costs,
            "contribution_margin_minor": contribution_margin if readiness["status"] == "confirmed" else None,
            "contribution_margin_rate": contribution_margin_rate,
            "break_even_revenue_minor": break_even,
            "missing_inputs": readiness["blocking_reasons"],
            "closed_days": readiness["closed_days"],
            "sales_days": readiness["sales_days"],
            "funds_minor": {
                "cash": balances.get("1001", 0),
                "bank_confirmed": balances.get("1002", 0),
                "platform_unsettled": balances.get("1012", 0),
                "former_owner_receivable": balances.get("1013", 0),
                "unclassified_receipts": balances.get("1019", 0),
                "store_controlled": controlled_funds,
            },
            "liabilities_minor": {
                "supplier_payable": balances.get("2001", 0),
                "salary_payable": balances.get("2002", 0),
                "loans": balances.get("2003", 0),
                "accrued_payables": balances.get("2009", 0),
            },
            "assets_minor": {
                "inventory": balances.get("1401", 0) + balances.get("1402", 0),
                "fixed_assets": balances.get("1601", 0),
                "deposits_and_deferred": balances.get("1801", 0),
            },
            "owner_equity_minor": {
                "invested": balances.get("3001", 0),
                "drawn": -balances.get("3002", 0),
            },
            "cash_flow_minor": self.cash_flow_summary(store_id, start, end),
            "spending_minor": self.spending_summary(store_id, start, end),
            "targets": self.financial_targets(store_id, start, end),
            "pending_capital_items": pending_capital,
            "fund_positions": fund_positions,
            "fund_movement_totals_minor": self.fund_movement_totals(store_id, start, end),
            "recent_fund_movements": self.list_fund_movements(store_id, start, end, "store")[:20],
            "debt_summary": debt,
            "daily_revenue": self.operating_calendar(store_id, start, end),
        }

    def finance_analytics(self, store_id: str, start: str, end: str) -> dict[str, Any]:
        """Build one evidence-backed read model for finance charts and Agent context.

        The read model deliberately keeps sales, money location, operating cost,
        inventory purchases and personal spending separate.  Missing calendar days
        remain ``None`` instead of being rendered as zero revenue or zero spending.
        """
        try:
            start_date = date.fromisoformat(start)
            end_date = date.fromisoformat(end)
        except ValueError as exc:
            raise FinanceMigrationError("分析日期必须是 YYYY-MM-DD") from exc
        if end_date < start_date:
            raise FinanceMigrationError("分析截止日不能早于开始日")

        overview = self.finance_overview(store_id, start, end)
        merchant_rows = self.merchant_net_sales(store_id, start, end)
        movement_rows = self.list_fund_movements(store_id, start, end)
        bookkeeping_rows = self.list_bookkeeping_records(store_id, start, end, limit=2000)
        calendar_rows = self.operating_calendar(store_id, start, end)

        merchant_by_date: dict[str, list[dict[str, Any]]] = {}
        movement_by_date: dict[str, list[dict[str, Any]]] = {}
        bookkeeping_by_date: dict[str, list[dict[str, Any]]] = {}
        for item in merchant_rows:
            merchant_by_date.setdefault(str(item["business_date"]), []).append(item)
        for item in movement_rows:
            movement_by_date.setdefault(str(item["occurred_on"]), []).append(item)
        for item in bookkeeping_rows:
            bookkeeping_by_date.setdefault(str(item["transaction_date"]), []).append(item)

        daily_series: list[dict[str, Any]] = []
        for day in calendar_rows:
            business_date = str(day["business_date"])
            daily_merchants = merchant_by_date.get(business_date, [])
            daily_movements = [
                item for item in movement_by_date.get(business_date, [])
                if item["status"] in {"confirmed", "reconciled"}
            ]
            daily_books = bookkeeping_by_date.get(business_date, [])
            has_activity = bool(daily_merchants or daily_movements or daily_books or day["revenue_minor"] is not None)
            store_outflow = sum(
                int(item["amount_minor"])
                for item in daily_movements
                if item["movement_type"] == "store_outflow" and item["business_scope"] != "personal"
            )
            personal_outflow = sum(
                int(item["amount_minor"])
                for item in daily_movements
                if item["movement_type"] == "personal_outflow" or item["business_scope"] == "personal"
            )
            daily_series.append({
                "business_date": business_date,
                "state": (
                    day["status"] if day["status"] != "missing"
                    else "partial" if has_activity
                    else "missing"
                ),
                "merchant_net_minor": (
                    sum(int(item["merchant_net_minor"]) for item in daily_merchants)
                    if daily_merchants else None
                ),
                "accounting_revenue_minor": day["revenue_minor"] if has_activity else None,
                "store_outflow_minor": store_outflow if has_activity else None,
                "personal_outflow_minor": personal_outflow if has_activity else None,
                "orders": day["orders"] if has_activity else None,
            })

        channel_totals: dict[str, dict[str, Any]] = {}
        for item in merchant_rows:
            channel = str(item["channel"])
            target = channel_totals.setdefault(channel, {
                "channel": channel,
                "amount_minor": 0,
                "records": 0,
                "confirmed_records": 0,
                "states_minor": {},
            })
            amount_minor = int(item["merchant_net_minor"])
            state = str(item["settlement_state"])
            target["amount_minor"] += amount_minor
            target["records"] += 1
            if item["evidence_status"] == "confirmed":
                target["confirmed_records"] += 1
            target["states_minor"][state] = target["states_minor"].get(state, 0) + amount_minor
        channel_breakdown = sorted(
            channel_totals.values(), key=lambda item: (-int(item["amount_minor"]), str(item["channel"])),
        )

        cost_labels = {
            "food_cost": "食材实际耗用",
            "packaging_cost": "包装耗用",
            "platform_cost": "平台佣金与配送",
            "marketing_cost": "活动推广",
            "waste_cost": "报损盘亏",
            "labor": "员工人工",
            "rent": "房租与商场费",
            "utility": "水电燃气",
            "systems": "系统与服务费",
            "other": "其他经营费用",
            "depreciation": "折旧与摊销",
        }
        expense_breakdown = sorted(
            [
                {"key": key, "label": cost_labels[key], "amount_minor": int(amount)}
                for key, amount in overview.get("costs_minor", {}).items()
                if int(amount) > 0 and key in cost_labels
            ],
            key=lambda item: (-int(item["amount_minor"]), str(item["label"])),
        )

        def public_settlement_status(value: str) -> tuple[str, str]:
            if value == "store_account_received":
                return "completed", "已到店铺账户"
            if value == "wallet_credited":
                return "awaiting_arrival", "已到平台钱包"
            if value in {"bound_bank_received", "former_owner_received", "former_owner_pending_transfer"}:
                return "awaiting_reconciliation", "已到平台绑定卡，待转店铺工商卡"
            return "needs_information", "资金位置待补充"

        def add_business_days(value: str, days: int) -> str:
            current = date.fromisoformat(value)
            remaining = days
            while remaining:
                current += timedelta(days=1)
                if current.weekday() < 5:
                    remaining -= 1
            return current.isoformat()

        def expected_settlement_dates(
            item: dict[str, Any],
        ) -> tuple[str | None, str | None, str | None, str | None]:
            bindings = self.list_platform_collection_bindings(store_id, str(item["business_date"]))
            binding = next((row for row in bindings if row["platform"] == item["channel"]), None)
            rule = str(binding.get("settlement_rule") or "") if binding else ""
            if (
                binding
                and binding.get("settlement_rule_status") == "confirmed"
                and binding.get("settlement_delay_days") is not None
                and binding.get("settlement_day_basis") in {"calendar_day", "working_day"}
            ):
                expected = self._expected_bank_date(
                    str(item["business_date"]),
                    int(binding["settlement_delay_days"]),
                    str(binding["settlement_day_basis"]),
                )
                target = str(binding.get("settlement_delay_target") or "bound_bank")
                withdrawal_mode = str(binding.get("withdrawal_mode") or "automatic")
                return (
                    expected if target == "platform_wallet" else None,
                    expected if target == "bound_bank" else None,
                    rule,
                    withdrawal_mode,
                )
            normalized = rule.upper().replace(" ", "")
            if "T+3" in normalized and "工作日" in rule:
                return add_business_days(str(item["business_date"]), 3), None, rule, None
            if "次日" in rule or "T+1" in normalized or "D+1" in normalized:
                return (date.fromisoformat(str(item["business_date"])) + timedelta(days=1)).isoformat(), None, rule, None
            return None, None, rule or None, None

        settlement_timeline = []
        for item in sorted(merchant_rows, key=lambda row: (str(row["business_date"]), str(row["channel"]))):
            status, status_label = public_settlement_status(str(item["settlement_state"]))
            expected_wallet_date, expected_bank_date, rule, withdrawal_mode = expected_settlement_dates(item)
            location = item.get("current_account_name")
            if not location:
                location = (
                    "平台绑定卡（暂时代管）" if status == "awaiting_reconciliation"
                    else f"{item['channel']}平台钱包" if status == "awaiting_arrival"
                    else "资金位置待补充"
                )
            settlement_timeline.append({
                "id": item["id"],
                "business_date": item["business_date"],
                "channel": item["channel"],
                "amount_minor": int(item["merchant_net_minor"]),
                "expected_wallet_date": expected_wallet_date,
                "expected_bank_date": expected_bank_date,
                "withdrawal_mode": withdrawal_mode,
                "settlement_rule": rule,
                "status": status,
                "status_label": status_label,
                "current_location": location,
                "evidence_id": item.get("evidence_reference"),
            })

        flow_edges_map: dict[tuple[str, str, str], dict[str, Any]] = {}

        def add_flow_edge(source: str, target: str, amount_minor: int, status: str, evidence_id: str | None) -> None:
            if amount_minor <= 0 or source == target:
                return
            key = (source, target, status)
            edge = flow_edges_map.setdefault(key, {
                "source": source,
                "target": target,
                "amount_minor": 0,
                "status": status,
                "evidence_ids": [],
            })
            edge["amount_minor"] += int(amount_minor)
            if evidence_id and evidence_id not in edge["evidence_ids"]:
                edge["evidence_ids"].append(evidence_id)

        for item in settlement_timeline:
            add_flow_edge(
                f"{item['channel']}营业收入", str(item["current_location"]),
                int(item["amount_minor"]), str(item["status"]), item.get("evidence_id"),
            )
        for item in movement_rows:
            if item["status"] not in {"confirmed", "reconciled"}:
                continue
            source = str(item.get("from_account_name") or item.get("counterparty") or "外部资金来源")
            target = str(item.get("to_account_name") or item.get("purpose") or "外部收款方")
            add_flow_edge(source, target, int(item["amount_minor"]), "completed", item.get("evidence_reference"))
        fund_flow_edges = list(flow_edges_map.values())
        node_names = {name for edge in fund_flow_edges for name in (edge["source"], edge["target"])}
        fund_flow_nodes = [
            {
                "name": name,
                "kind": (
                    "channel" if name.endswith("营业收入")
                    else "personal" if "个人" in name
                    else "pending" if "前老板" in name or "钱包" in name
                    else "account"
                ),
            }
            for name in sorted(node_names)
        ]

        inventory_purchase_minor = sum(
            int(item["amount_minor"])
            for item in bookkeeping_rows
            if item["status"] == "posted"
            and item["business_scope"] == "store"
            and item["transaction_kind"] == "inventory_purchase"
        )
        personal_outflow_minor = sum(
            int(item["amount_minor"])
            for item in movement_rows
            if item["status"] in {"confirmed", "reconciled"}
            and (item["movement_type"] == "personal_outflow" or item["business_scope"] == "personal")
        )
        missing_days = [item["business_date"] for item in daily_series if item["state"] == "missing"]
        has_data = bool(merchant_rows or movement_rows or bookkeeping_rows or overview.get("revenue_minor"))
        data_completeness = (
            "missing" if not has_data
            else "confirmed" if overview.get("profit_status") == "confirmed" and not missing_days
            else "partial"
        )
        profit_rows = [{"key": "revenue", "label": "营业收入", "amount_minor": int(overview.get("revenue_minor") or 0)}]
        profit_rows.extend(
            {"key": item["key"], "label": item["label"], "amount_minor": -int(item["amount_minor"])}
            for item in expense_breakdown
        )
        estimated_labels = {
            "food_cost": "食材库存耗用（暂估）",
            "labor": "员工人工（暂估）",
            "packaging_cost": "包装耗用（暂估）",
        }
        profit_rows.extend(
            {
                "key": f"estimated_{key}",
                "label": estimated_labels.get(key, f"{cost_labels.get(key, key)}（暂估）"),
                "amount_minor": -int(amount),
            }
            for key, amount in overview.get("estimated_adjustments_minor", {}).items()
            if int(amount) > 0
        )
        profit_bridge = {
            "status": "confirmed" if overview.get("profit_status") == "confirmed" else "partial",
            "rows": profit_rows,
            "net_profit_minor": overview.get("net_profit_minor"),
            "provisional_net_profit_minor": int(overview.get("provisional_net_profit_minor") or 0),
            "label": "经营净利润" if overview.get("profit_status") == "confirmed" else "按已记录成本暂算",
        }
        evidence_ids = sorted({
            str(value)
            for value in (
                [item.get("evidence_reference") for item in merchant_rows]
                + [item.get("evidence_reference") for item in movement_rows]
                + [item.get("voucher_id") for item in bookkeeping_rows]
            )
            if value
        })
        return {
            "schema_version": "finance_analytics_v1",
            "store_id": store_id,
            "period_start": start,
            "period_end": end,
            "data_completeness": data_completeness,
            "missing_inputs": list(overview.get("missing_inputs") or []),
            "missing_days": missing_days,
            "kpis": {
                "merchant_net_minor": int(overview.get("merchant_net_minor") or 0),
                "store_controlled_minor": int(overview.get("funds_minor", {}).get("store_controlled") or 0),
                "pending_collection_minor": int(overview.get("funds_minor", {}).get("platform_unsettled") or 0)
                    + int(overview.get("funds_minor", {}).get("former_owner_receivable") or 0),
                "known_operating_cost_minor": int(overview.get("known_operating_cost_minor") or 0),
                "inventory_purchase_minor": inventory_purchase_minor,
                "personal_outflow_minor": personal_outflow_minor,
                "net_profit_minor": overview.get("net_profit_minor"),
                "provisional_net_profit_minor": int(overview.get("provisional_net_profit_minor") or 0),
            },
            "daily_series": daily_series,
            "channel_breakdown": channel_breakdown,
            "expense_breakdown": expense_breakdown,
            "fund_flow_nodes": fund_flow_nodes,
            "fund_flow_edges": fund_flow_edges,
            "settlement_timeline": settlement_timeline,
            "profit_bridge": profit_bridge,
            "cash_forecast": self.cash_chain_forecast(store_id, end),
            "evidence_ids": evidence_ids,
        }

    # Compatibility for existing capture integrations.
    def overview(self, store_id: str, start: str | None = None, end: str | None = None) -> dict[str, Any]:
        return self.finance_overview(store_id, start, end)

    def record_expense(
        self, store_id: str, date: str, category_code: str, amount_minor: int,
        reference: str, paid_from: str | None = None, description: str = "",
    ) -> str:
        allowed = {code for code, _, kind in ACCOUNT_SEED if kind in {"cost", "expense"}}
        if category_code not in allowed:
            raise FinanceMigrationError(f"不允许的成本费用科目：{category_code}")
        if amount_minor <= 0:
            raise FinanceMigrationError("费用金额必须大于 0")
        credit = paid_from if paid_from in {"1001", "1002"} else "2009"
        return self.post_entry(
            store_id=store_id, entry_date=date, posting_key=f"expense:{reference}",
            description=description or "成本费用", lines=[(category_code, amount_minor, 0), (credit, 0, amount_minor)],
        )

    def save_daily_close(self, store_id: str, date: str, payload: dict[str, Any]) -> dict[str, Any]:
        legacy_cost_fields = [
            "food_cost_minor", "packaging_cost_minor", "overtime_hours",
            "rent_minor", "utility_minor", "other_cost_minor",
        ]
        legacy_complete = all(payload.get(key) is not None for key in legacy_cost_fields)
        merchant_net_confirmed = bool(payload.get("merchant_net_confirmed")) or legacy_complete
        fund_locations_reviewed = bool(payload.get("fund_locations_reviewed")) or legacy_complete
        outflows_reviewed = bool(payload.get("outflows_reviewed")) or legacy_complete
        missing = []
        if payload.get("counted_cash_minor") is None:
            missing.append("cash_count")
        if not merchant_net_confirmed:
            missing.append("merchant_net_review")
        if not fund_locations_reviewed:
            missing.append("fund_location_review")
        if not outflows_reviewed:
            missing.append("outflow_review")
        with self.connect() as connection:
            existing = connection.execute(
                "SELECT status, inputs_json FROM daily_close_sessions WHERE store_id = ? AND business_date = ?",
                (store_id, date),
            ).fetchone()
            if existing and existing["status"] == "closed":
                return self.daily_close(store_id, date)

        if not missing or any(payload.get(key) is not None for key in legacy_cost_fields):
            overtime_hours = payload.get("overtime_hours")
            overtime_pay = money_to_minor(Decimal(str(overtime_hours)) * Decimal("16")) if overtime_hours is not None else None
            base_daily = money_to_minor(Decimal("5200") / Decimal("31"))
            new_costs = {
                "food": ("5001", payload.get("food_cost_minor")),
                "packaging": ("5002", payload.get("packaging_cost_minor")),
                "rent": ("6002", payload.get("rent_minor")),
                "utility": ("6003", payload.get("utility_minor")),
                "other": ("6005", payload.get("other_cost_minor")),
                "labor": ("6001", base_daily + overtime_pay if overtime_pay is not None else None),
            }
            old_payload = json.loads(existing["inputs_json"] or "{}") if existing else {}
            old_overtime = old_payload.get("overtime_hours")
            old_costs = {
                "food": int(old_payload.get("food_cost_minor") or 0),
                "packaging": int(old_payload.get("packaging_cost_minor") or 0),
                "rent": int(old_payload.get("rent_minor") or 0),
                "utility": int(old_payload.get("utility_minor") or 0),
                "other": int(old_payload.get("other_cost_minor") or 0),
                "labor": base_daily + money_to_minor(Decimal(str(old_overtime)) * Decimal("16")) if old_overtime is not None else 0,
            }
            for label, (account, amount) in new_costs.items():
                if amount is None:
                    continue
                amount = int(amount)
                previous = old_costs[label]
                delta = amount - previous
                if not existing and amount > 0:
                    self.record_expense(store_id, date, account, amount, f"daily-close:{date}:{label}")
                elif existing and delta:
                    adjustment_key = f"daily-close:{date}:{label}:adjust:{previous}:{amount}"
                    lines = [(account, delta, 0), ("2009", 0, delta)] if delta > 0 else [("2009", -delta, 0), (account, 0, -delta)]
                    self.post_entry(
                        store_id=store_id, entry_date=date, posting_key=adjustment_key,
                        description=f"{date} {label} 关账调整", entry_type="adjustment", lines=lines,
                    )

        balances = self.account_balances(store_id, "0000-01-01", date)
        expected = balances.get("1001", 0)
        counted = payload.get("counted_cash_minor")
        reserve = int(payload.get("reserve_cash_minor") or 10000)
        deposit = max(int(counted or 0) - reserve, 0) if counted is not None else None
        status = "closed" if not missing else "awaiting_inputs"
        session_id = f"close:{store_id}:{date}"
        with self.connect() as connection:
            connection.execute(
                """INSERT INTO daily_close_sessions
                   (id, store_id, business_date, status, expected_cash_minor, counted_cash_minor,
                    reserve_cash_minor, deposit_due_minor, merchant_net_confirmed,
                    fund_locations_reviewed, outflows_reviewed, inputs_json, missing_inputs_json, closed_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CASE WHEN ? = 'closed' THEN datetime('now') END)
                   ON CONFLICT(store_id, business_date) DO UPDATE SET
                     status=excluded.status, expected_cash_minor=excluded.expected_cash_minor,
                     counted_cash_minor=excluded.counted_cash_minor, reserve_cash_minor=excluded.reserve_cash_minor,
                     deposit_due_minor=excluded.deposit_due_minor,
                     merchant_net_confirmed=excluded.merchant_net_confirmed,
                     fund_locations_reviewed=excluded.fund_locations_reviewed,
                     outflows_reviewed=excluded.outflows_reviewed, inputs_json=excluded.inputs_json,
                     missing_inputs_json=excluded.missing_inputs_json,
                     closed_at=excluded.closed_at""",
                (
                    session_id, store_id, date, status, expected, counted, reserve, deposit,
                    1 if merchant_net_confirmed else 0, 1 if fund_locations_reviewed else 0,
                    1 if outflows_reviewed else 0, json.dumps(payload), json.dumps(missing), status,
                ),
            )
        return self.daily_close(store_id, date)

    def reopen_daily_close(self, store_id: str, date: str, reason: str) -> dict[str, Any]:
        if not reason.strip():
            raise FinanceMigrationError("重开关账必须填写原因")
        with self.connect() as connection:
            row = connection.execute(
                "SELECT id, status FROM daily_close_sessions WHERE store_id = ? AND business_date = ?",
                (store_id, date),
            ).fetchone()
            if not row:
                raise FinanceMigrationError("该营业日尚未建立关账记录")
            connection.execute(
                "UPDATE daily_close_sessions SET status='reopened', closed_at=NULL WHERE id = ?",
                (row["id"],),
            )
            connection.execute(
                """INSERT INTO audit_logs(id, store_id, actor_type, action, object_type, object_id, reason, created_at)
                   VALUES (?, ?, 'owner', 'reopen', 'daily_close', ?, ?, datetime('now'))""",
                (f"audit:reopen:{store_id}:{date}:{int(__import__('time').time() * 1000)}", store_id, row["id"], reason),
            )
        return self.daily_close(store_id, date)

    def daily_close(self, store_id: str, date: str) -> dict[str, Any]:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM daily_close_sessions WHERE store_id = ? AND business_date = ?",
                (store_id, date),
            ).fetchone()
        if not row:
            return {
                "store_id": store_id,
                "business_date": date,
                "status": "open",
                "missing_inputs": ["cash_count", "merchant_net_review", "fund_location_review", "outflow_review"],
            }
        result = dict(row)
        result["missing_inputs"] = json.loads(result.pop("missing_inputs_json") or "[]")
        result["inputs"] = json.loads(result.pop("inputs_json") or "{}")
        counted = result.get("counted_cash_minor")
        expected = result.get("expected_cash_minor")
        result["cash_difference_minor"] = counted - expected if counted is not None and expected is not None else None
        return result

    def alerts(self, store_id: str, start: str | None = None, end: str | None = None) -> list[dict[str, Any]]:
        overview = self.finance_overview(store_id, start, end)
        if not overview.get("has_data"):
            return []
        alerts: list[dict[str, Any]] = []
        funds = overview["funds_minor"]
        costs = overview["costs_minor"]
        balances = self.account_balances(store_id, start or overview["period_start"], end or overview["period_end"])

        if overview["missing_inputs"]:
            alerts.append({"code": "BOOKS_INCOMPLETE", "severity": "warning", "title": "利润账未闭合", "detail": "还缺：" + "、".join(overview["missing_inputs"])})

        if funds["former_owner_receivable"] > 0:
            alerts.append({"code": "FORMER_OWNER_RECEIVABLE", "severity": "warning", "title": "前老板代收待转", "amount_minor": funds["former_owner_receivable"]})

        if funds["unclassified_receipts"] > 0:
            alerts.append({"code": "UNCLASSIFIED_RECEIPTS", "severity": "warning", "title": "收款位置待核对", "amount_minor": funds["unclassified_receipts"]})

        with self.connect() as connection:
            close_rows = connection.execute(
                "SELECT business_date, status, counted_cash_minor, expected_cash_minor FROM daily_close_sessions WHERE store_id = ? AND business_date BETWEEN ? AND ?",
                (store_id, overview["period_start"], overview["period_end"]),
            ).fetchall()

            for row in close_rows:
                counted = row["counted_cash_minor"]
                expected = row["expected_cash_minor"]
                if counted is not None and expected is not None and abs(counted - expected) > 100:
                    alerts.append({
                        "code": "CASH_DISCREPANCY", "severity": "high", "title": "现金实点与账面不符",
                        "detail": f"{row['business_date']} 差异: {(counted - expected)/100:.2f}元",
                        "amount_minor": abs(counted - expected),
                    })

            open_close_days = connection.execute(
                """SELECT business_date FROM daily_close_sessions WHERE store_id = ? AND status NOT IN ('closed', 'reopened')
                   ORDER BY business_date DESC LIMIT 5""",
                (store_id,),
            ).fetchall()
            if len(open_close_days) >= 3:
                dates = [row["business_date"] for row in open_close_days[:3]]
                alerts.append({"code": "UNFINISHED_CLOSE", "severity": "warning", "title": "连续未完成打烊", "detail": f"最近未关账日期: {', '.join(dates)}"})

        available_cash = funds["cash"] + funds["bank_confirmed"]
        daily_fixed_cost = costs["labor"] + costs["rent"] + costs["utility"] + costs["systems"] + costs["other"]
        sales_days = overview["sales_days"]
        if sales_days > 0 and available_cash > 0:
            daily_avg = daily_fixed_cost / sales_days
            coverage_days = available_cash / daily_avg if daily_avg > 0 else float('inf')
            if coverage_days < 7:
                alerts.append({
                    "code": "CASH_SHORTAGE", "severity": "high", "title": "可用现金不足7天",
                    "detail": f"当前可用现金可支撑约{coverage_days:.1f}天",
                    "amount_minor": available_cash,
                })
            elif coverage_days < 30:
                alerts.append({
                    "code": "CASH_WARNING", "severity": "warning", "title": "可用现金不足30天",
                    "detail": f"当前可用现金可支撑约{coverage_days:.1f}天",
                    "amount_minor": available_cash,
                })

        profit = overview["net_profit_minor"]
        cf_operating = overview["cash_flow_minor"]["operating"]
        if profit is not None and profit > 0 and cf_operating < -1000:
            alerts.append({
                "code": "PROFIT_CASH_MISMATCH", "severity": "warning",
                "title": "盈利但经营现金流为负",
                "detail": f"净利润{(profit)/100:.2f}元，经营现金流{(cf_operating)/100:.2f}元",
            })

        if funds["platform_unsettled"] > 5000:
            alerts.append({
                "code": "PLATFORM_PENDING", "severity": "warning", "title": "平台待结算金额较大",
                "amount_minor": funds["platform_unsettled"],
            })

        liabilities = overview["liabilities_minor"]
        total_liabilities = sum(liabilities.values())
        if total_liabilities > available_cash:
            alerts.append({
                "code": "LIABILITY_RISK", "severity": "warning", "title": "应付债务超过可用现金",
                "detail": f"应付{total_liabilities/100:.2f}元，现金{available_cash/100:.2f}元",
                "amount_minor": total_liabilities - available_cash,
            })

        return alerts

    def profit_and_loss(self, store_id: str, start: str, end: str) -> dict[str, Any]:
        balances = self.account_balances(store_id, start, end)
        overview = self.finance_overview(store_id, start, end)
        revenue = overview["revenue_minor"]
        costs = overview["costs_minor"]
        readiness = self.profit_readiness(store_id, start, end)

        operating_revenue = sum(balances.get(code, 0) for code in ("4001", "4002", "4003", "4009"))
        contra_revenue = balances.get("4004", 0)
        net_revenue = operating_revenue - contra_revenue

        cost_of_sales = costs["food_cost"] + costs["packaging_cost"] + costs["waste_cost"]
        gross_profit = net_revenue - cost_of_sales if readiness["status"] == "confirmed" else None

        variable_expenses = costs["platform_cost"] + costs["marketing_cost"]
        contribution_margin = gross_profit - variable_expenses if gross_profit is not None else None

        fixed_expenses = costs["labor"] + costs["rent"] + costs["utility"] + costs["systems"] + costs["other"] + costs["depreciation"]
        operating_net_profit = contribution_margin - fixed_expenses if contribution_margin is not None else None

        return {
            "period_start": start,
            "period_end": end,
            "profit_status": readiness["status"],
            "blocking_reasons": readiness["blocking_reasons"],
            "sections": [
                {
                    "label": "营业收入",
                    "items": [
                        {"account": "营业收入—堂食", "code": "4001", "amount_minor": balances.get("4001", 0)},
                        {"account": "营业收入—外卖", "code": "4002", "amount_minor": balances.get("4002", 0)},
                        {"account": "营业收入—团购", "code": "4003", "amount_minor": balances.get("4003", 0)},
                        {"account": "营业收入—待拆分", "code": "4009", "amount_minor": balances.get("4009", 0)},
                        {"account": "退款与销售调整", "code": "4004", "amount_minor": contra_revenue},
                    ],
                    "total_minor": net_revenue,
                },
                {
                    "label": "销售成本",
                    "items": [
                        {"account": "食材销售成本", "code": "5001", "amount_minor": costs["food_cost"]},
                        {"account": "包装耗材成本", "code": "5002", "amount_minor": costs["packaging_cost"]},
                        {"account": "报损与盘亏", "code": "5005", "amount_minor": costs["waste_cost"]},
                    ],
                    "total_minor": cost_of_sales,
                },
                {
                    "label": "营业毛利",
                    "amount_minor": gross_profit,
                },
                {
                    "label": "变动销售费用",
                    "items": [
                        {"account": "平台佣金与配送", "code": "5003", "amount_minor": costs["platform_cost"]},
                        {"account": "活动与推广", "code": "5004", "amount_minor": costs["marketing_cost"]},
                    ],
                    "total_minor": variable_expenses,
                },
                {
                    "label": "贡献毛利",
                    "amount_minor": contribution_margin,
                },
                {
                    "label": "固定经营费用",
                    "items": [
                        {"account": "员工工资", "code": "6001", "amount_minor": costs["labor"]},
                        {"account": "房租与商场费", "code": "6002", "amount_minor": costs["rent"]},
                        {"account": "水电燃气", "code": "6003", "amount_minor": costs["utility"]},
                        {"account": "系统与服务费", "code": "6004", "amount_minor": costs["systems"]},
                        {"account": "维修、清洁与杂费", "code": "6005", "amount_minor": costs["other"]},
                        {"account": "折旧与摊销", "code": "6006", "amount_minor": costs["depreciation"]},
                    ],
                    "total_minor": fixed_expenses,
                },
                {
                    "label": "经营净利润",
                    "amount_minor": operating_net_profit,
                },
            ],
        }

    def balance_sheet(self, store_id: str, as_of: str) -> dict[str, Any]:
        balances = self.account_balances(store_id, "0000-01-01", as_of)

        current_assets = [
            {"account": "现金", "code": "1001", "amount_minor": balances.get("1001", 0)},
            {"account": "银行存款", "code": "1002", "amount_minor": balances.get("1002", 0)},
            {"account": "平台待结算", "code": "1012", "amount_minor": balances.get("1012", 0)},
            {"account": "其他应收款—前老板", "code": "1013", "amount_minor": balances.get("1013", 0)},
            {"account": "待核对收款", "code": "1019", "amount_minor": balances.get("1019", 0)},
        ]
        current_assets_total = sum(item["amount_minor"] for item in current_assets)

        inventory_assets = [
            {"account": "原材料库存", "code": "1401", "amount_minor": balances.get("1401", 0)},
            {"account": "包装耗材库存", "code": "1402", "amount_minor": balances.get("1402", 0)},
        ]
        inventory_total = sum(item["amount_minor"] for item in inventory_assets)

        long_term_assets = [
            {"account": "固定资产", "code": "1601", "amount_minor": balances.get("1601", 0)},
            {"account": "押金及长期待摊", "code": "1801", "amount_minor": balances.get("1801", 0)},
        ]
        long_term_total = sum(item["amount_minor"] for item in long_term_assets)

        total_assets = current_assets_total + inventory_total + long_term_total

        current_liabilities = [
            {"account": "应付供应商", "code": "2001", "amount_minor": balances.get("2001", 0)},
            {"account": "应付员工薪酬", "code": "2002", "amount_minor": balances.get("2002", 0)},
            {"account": "应计费用与其他应付", "code": "2009", "amount_minor": balances.get("2009", 0)},
        ]
        current_liabilities_total = sum(item["amount_minor"] for item in current_liabilities)

        long_term_liabilities = [
            {"account": "借款", "code": "2003", "amount_minor": balances.get("2003", 0)},
        ]
        long_term_liabilities_total = sum(item["amount_minor"] for item in long_term_liabilities)

        total_liabilities = current_liabilities_total + long_term_liabilities_total

        pl = self.profit_and_loss(store_id, "0000-01-01", as_of)
        retained_earnings = pl["sections"][-1]["amount_minor"] or 0

        equity = [
            {"account": "老板投入", "code": "3001", "amount_minor": balances.get("3001", 0)},
            {"account": "老板取款", "code": "3002", "amount_minor": -balances.get("3002", 0)},
            {"account": "留存收益（累计净利润）", "code": "3003", "amount_minor": retained_earnings},
        ]
        total_equity = sum(item["amount_minor"] for item in equity)

        return {
            "as_of": as_of,
            "assets": {
                "current_assets": current_assets,
                "current_assets_total": current_assets_total,
                "inventory": inventory_assets,
                "inventory_total": inventory_total,
                "long_term_assets": long_term_assets,
                "long_term_total": long_term_total,
                "total_assets": total_assets,
            },
            "liabilities": {
                "current_liabilities": current_liabilities,
                "current_liabilities_total": current_liabilities_total,
                "long_term_liabilities": long_term_liabilities,
                "long_term_liabilities_total": long_term_liabilities_total,
                "total_liabilities": total_liabilities,
            },
            "equity": {
                "items": equity,
                "total_equity": total_equity,
            },
            "balance_check": total_assets - total_liabilities - total_equity,
        }

    def get_metric(self, store_id: str, metric_code: str, start: str, end: str) -> dict[str, Any]:
        if metric_code not in METRIC_REGISTRY:
            return {"error": f"未知指标：{metric_code}", "available_metrics": list(METRIC_REGISTRY.keys())}

        registry = METRIC_REGISTRY[metric_code]
        overview = self.finance_overview(store_id, start, end)
        if not overview.get("has_data"):
            return {
                "metric_code": metric_code,
                "label": registry["label"],
                "version": registry["version"],
                "formula": registry["formula"],
                "value_minor": None,
                "value": None,
                "completeness": "no_data",
                "blocking_reasons": ["暂无经营数据"],
            }

        costs = overview["costs_minor"]
        revenue = overview["revenue_minor"]
        orders = overview["orders"]
        readiness = self.profit_readiness(store_id, start, end)

        value_minor = None
        blocking_reasons = []

        if metric_code == "revenue":
            value_minor = revenue
        elif metric_code == "average_order_value":
            if orders > 0 and revenue > 0:
                value_minor = round(revenue / orders)
            else:
                blocking_reasons.append("订单口径未知")
        elif metric_code == "gross_profit":
            if readiness["status"] == "confirmed":
                value_minor = revenue - costs["food_cost"] - costs["packaging_cost"] - costs["waste_cost"]
            else:
                blocking_reasons.append("销售成本未确认")
        elif metric_code == "contribution_margin":
            if readiness["status"] == "confirmed":
                variable_cost = costs["food_cost"] + costs["packaging_cost"] + costs["waste_cost"] + costs["platform_cost"] + costs["marketing_cost"]
                value_minor = revenue - variable_cost
            else:
                blocking_reasons.append("平台/活动/包装成本不完整")
        elif metric_code == "operating_net_profit":
            value_minor = overview["net_profit_minor"]
            if value_minor is None:
                blocking_reasons.append("任一必需成本未确认")
        elif metric_code == "prime_cost":
            if costs["food_cost"] > 0 and costs["packaging_cost"] > 0 and costs["labor"] > 0:
                value_minor = costs["food_cost"] + costs["packaging_cost"] + costs["labor"]
            else:
                blocking_reasons.append("库存耗用或工资未确认")
        elif metric_code == "monthly_break_even":
            cm_rate = overview["contribution_margin_rate"]
            if cm_rate and cm_rate > 0:
                fixed_cost = costs["labor"] + costs["rent"] + costs["utility"] + costs["systems"] + costs["other"] + costs["depreciation"]
                value_minor = round(fixed_cost / cm_rate)
            else:
                blocking_reasons.append("贡献毛利率不可用")
        elif metric_code == "cash_coverage_days":
            funds = overview["funds_minor"]
            available_cash = funds["cash"] + funds["bank_confirmed"]
            if available_cash > 0 and readiness["sales_days"] > 3:
                daily_expense = sum(costs.values()) / readiness["sales_days"] if readiness["sales_days"] > 0 else 0
                if daily_expense > 0:
                    value_minor = round(available_cash / daily_expense)
                else:
                    blocking_reasons.append("支出样本不足")
            else:
                blocking_reasons.append("未实点资金或支出样本不足")
        elif metric_code == "net_margin":
            net_profit = overview["net_profit_minor"]
            if net_profit is not None and revenue > 0:
                value_minor = round((net_profit / revenue) * 10000)
            else:
                blocking_reasons.append("净利润或营业收入为零")
        elif metric_code == "contribution_margin_rate":
            cm = overview["contribution_margin_minor"]
            if cm is not None and revenue > 0:
                value_minor = round((cm / revenue) * 10000)
            else:
                blocking_reasons.append("贡献毛利或营业收入为零")

        completeness = "confirmed" if value_minor is not None and not blocking_reasons else "partial" if value_minor is not None else "blocked"

        return {
            "metric_code": metric_code,
            "label": registry["label"],
            "version": registry["version"],
            "formula": registry["formula"],
            "basis": registry["basis"],
            "period_start": start,
            "period_end": end,
            "value_minor": value_minor,
            "value": value_minor / 100 if value_minor is not None else None,
            "completeness": completeness,
            "blocking_reasons": blocking_reasons or readiness["blocking_reasons"],
            "source_entry_ids": [],
        }

    def list_metrics(self) -> list[dict[str, Any]]:
        return [
            {
                "metric_code": code,
                "label": info["label"],
                "version": info["version"],
                "formula": info["formula"],
                "basis": info["basis"],
                "required_inputs": info["required_inputs"],
            }
            for code, info in METRIC_REGISTRY.items()
        ]

    def reconcile_platforms(self, store_id: str, start: str, end: str) -> dict[str, Any]:
        with self.connect() as connection:
            rows = connection.execute(
                """SELECT channel, SUM(recognized_revenue_minor) revenue_minor, SUM(COALESCE(order_count, 0)) orders
                   FROM sales_daily WHERE store_id = ? AND business_date BETWEEN ? AND ?
                   GROUP BY channel ORDER BY channel""",
                (store_id, start, end),
            ).fetchall()
            sales_by_channel = {row["channel"]: {"revenue_minor": row["revenue_minor"], "orders": row["orders"]} for row in rows}

            platform_entries = connection.execute(
                """SELECT je.entry_date, a.code, SUM(jl.debit_minor) debit, SUM(jl.credit_minor) credit
                   FROM journal_entries je JOIN journal_lines jl ON jl.journal_entry_id = je.id
                   JOIN accounts a ON a.id = jl.account_id
                   WHERE je.store_id = ? AND je.status = 'posted' AND je.entry_date BETWEEN ? AND ?
                     AND a.code IN ('1012', '1013', '1019', '4001', '4002', '4003', '4009')
                   GROUP BY je.entry_date, a.code ORDER BY je.entry_date, a.code""",
                (store_id, start, end),
            ).fetchall()

        platform_settled = {}
        for row in platform_entries:
            date = row["entry_date"]
            code = row["code"]
            platform_settled.setdefault(date, {})[code] = row["debit"] - row["credit"]

        return {
            "period_start": start,
            "period_end": end,
            "sales_by_channel": sales_by_channel,
            "platform_settlement_details": platform_settled,
            "platform_unsettled": self.account_balances(store_id, start, end).get("1012", 0),
            "former_owner_receivable": self.account_balances(store_id, start, end).get("1013", 0),
        }

    def reconcile_cash(self, store_id: str, date: str) -> dict[str, Any]:
        close_session = self.daily_close(store_id, date)
        balances = self.account_balances(store_id, "0000-01-01", date)

        expected_cash = balances.get("1001", 0)
        counted_cash = close_session.get("counted_cash_minor")
        cash_difference = counted_cash - expected_cash if counted_cash is not None and expected_cash is not None else None

        with self.connect() as connection:
            cash_entries = connection.execute(
                """SELECT je.entry_date, je.description, jl.debit_minor, jl.credit_minor
                   FROM journal_entries je JOIN journal_lines jl ON jl.journal_entry_id = je.id
                   JOIN accounts a ON a.id = jl.account_id
                   WHERE je.store_id = ? AND je.status = 'posted' AND a.code = '1001' AND je.entry_date = ?
                   ORDER BY je.entry_date""",
                (store_id, date),
            ).fetchall()

        return {
            "business_date": date,
            "expected_cash_minor": expected_cash,
            "counted_cash_minor": counted_cash,
            "cash_difference_minor": cash_difference,
            "reconciliation_status": "balanced" if cash_difference == 0 else "unbalanced" if cash_difference is not None else "pending",
            "close_session_status": close_session.get("status"),
            "cash_entries": [
                {"date": row["entry_date"], "description": row["description"], "debit_minor": row["debit_minor"], "credit_minor": row["credit_minor"]}
                for row in cash_entries
            ],
        }

    def reconcile_receivables(self, store_id: str, start: str, end: str) -> dict[str, Any]:
        balances = self.account_balances(store_id, start, end)

        with self.connect() as connection:
            receivable_entries = connection.execute(
                """SELECT je.entry_date, je.description, a.code, a.name,
                          SUM(jl.debit_minor) debit, SUM(jl.credit_minor) credit
                   FROM journal_entries je JOIN journal_lines jl ON jl.journal_entry_id = je.id
                   JOIN accounts a ON a.id = jl.account_id
                   WHERE je.store_id = ? AND je.status = 'posted' AND je.entry_date BETWEEN ? AND ?
                     AND a.code IN ('1012', '1013', '1019')
                   GROUP BY je.entry_date, a.id ORDER BY je.entry_date, a.code""",
                (store_id, start, end),
            ).fetchall()

        movements = []
        for row in receivable_entries:
            movements.append({
                "date": row["entry_date"],
                "description": row["description"],
                "account_code": row["code"],
                "account_name": row["name"],
                "debit_minor": row["debit"],
                "credit_minor": row["credit"],
                "net_minor": row["debit"] - row["credit"],
            })

        return {
            "period_start": start,
            "period_end": end,
            "platform_unsettled_minor": balances.get("1012", 0),
            "former_owner_receivable_minor": balances.get("1013", 0),
            "unclassified_receipts_minor": balances.get("1019", 0),
            "total_receivables_minor": balances.get("1012", 0) + balances.get("1013", 0) + balances.get("1019", 0),
            "movements": movements,
        }

    def finance_query(self, store_id: str, query: str, start: str, end: str) -> dict[str, Any]:
        overview = self.finance_overview(store_id, start, end)
        if not overview.get("has_data"):
            return {
                "answer": "暂无经营数据",
                "period": {"start": start, "end": end},
                "metrics": [],
                "formula_trace": [],
                "evidence_ids": [],
                "completeness": "no_data",
                "warnings": ["暂无经营数据"],
                "follow_up_inputs": [],
            }

        query_lower = query.lower()
        evidence_ids = [
            str(item["id"])
            for item in self.list_evidence_vouchers(store_id, start, end)[:20]
        ]

        if any(keyword in query_lower for keyword in ["没到账", "未到账", "还没到", "没到店铺", "未到店铺", "钱在哪", "应收", "前老板", "平台钱包"]):
            funds = dict(overview["funds_minor"])
            with self.connect() as connection:
                position_rows = connection.execute(
                    """SELECT settlement_state, SUM(merchant_net_minor - matched_minor) amount_minor
                       FROM (
                         SELECT m.id, m.settlement_state, m.merchant_net_minor,
                                COALESCE(SUM(CASE WHEN l.status IN ('matched','partial')
                                     THEN l.matched_amount_minor ELSE 0 END), 0) matched_minor
                         FROM merchant_net_sales m
                         LEFT JOIN finance_reconciliation_links l
                           ON l.store_id=m.store_id
                          AND l.target_type='merchant_net_sale'
                          AND l.target_id=m.id
                         WHERE m.store_id=? AND m.business_date BETWEEN ? AND ?
                         GROUP BY m.id, m.settlement_state, m.merchant_net_minor
                       ) positions
                       GROUP BY settlement_state""",
                    (store_id, start, end),
                ).fetchall()
            if position_rows:
                by_state = {
                    str(row["settlement_state"]): max(int(row["amount_minor"] or 0), 0)
                    for row in position_rows
                }
                funds["platform_unsettled"] = by_state.get("wallet_credited", 0)
                funds["former_owner_receivable"] = (
                    by_state.get("former_owner_received", 0)
                    + by_state.get("former_owner_pending_transfer", 0)
                )
                funds["unclassified_receipts"] = (
                    by_state.get("unknown", 0) + by_state.get("disputed", 0)
                )
            snapshot = self.daily_finance_snapshot(store_id, end)
            metrics_result = [
                {"metric_code": "platform_unsettled", "label": "平台待结算", "value_minor": funds["platform_unsettled"], "value": funds["platform_unsettled"] / 100, "formula": "已确认销售中尚在平台钱包或结算链路的金额", "completeness": "confirmed", "blocking_reasons": []},
                {"metric_code": "former_owner_receivable", "label": "前老板代收待转", "value_minor": funds["former_owner_receivable"], "value": funds["former_owner_receivable"] / 100, "formula": "前老板代收销售 - 已核销转回金额", "completeness": "confirmed", "blocking_reasons": []},
                {"metric_code": "store_controlled_funds", "label": "账面可追溯店铺资金", "value_minor": funds["store_controlled"], "value": funds["store_controlled"] / 100, "formula": "店铺可控账户已登记资金位置", "completeness": "partial", "blocking_reasons": ["尚未用完整银行流水确认实际余额"]},
            ]
            actual_bank = snapshot["as_of"].get("actual_bank_balance_minor")
            answer = (
                f"截至{end}，平台待结算 {funds['platform_unsettled'] / 100:.2f}元，"
                f"前老板代收待转 {funds['former_owner_receivable'] / 100:.2f}元，"
                f"另有收款位置待核对 {funds['unclassified_receipts'] / 100:.2f}元。"
                + (
                    f"已核对的店铺银行卡实际余额为 {actual_bank / 100:.2f}元。"
                    if actual_bank is not None
                    else "当前没有完整银行流水或余额截图，所以系统不会把累计到账金额冒充银行卡实际余额。"
                )
            )
            return {
                "answer": answer,
                "period": {"start": start, "end": end},
                "metrics": metrics_result,
                "formula_trace": [f"{item['label']}: {item['formula']} = {item['value']:.2f}元" for item in metrics_result],
                "evidence_ids": evidence_ids,
                "completeness": "partial" if actual_bank is None else "confirmed",
                "warnings": [] if actual_bank is not None else ["银行卡实际余额待银行流水或余额截图确认"],
                "follow_up_inputs": [] if actual_bank is not None else [{"type": "bank_statement", "label": "银行卡实际余额", "description": "上传工商银行店铺账户流水或余额截图"}],
            }

        if any(keyword in query_lower for keyword in ["缺哪些", "缺什么", "资料缺", "还要补", "不完整"]):
            missing = list(overview.get("missing_inputs") or [])
            labels = [self._input_label(item) for item in missing]
            return {
                "answer": "当前最影响真实利润的资料缺口是：" + "、".join(labels) + "。补齐前系统只显示已知成本和利润上限，不把估算冒充净利润。",
                "period": {"start": start, "end": end},
                "metrics": [],
                "formula_trace": [],
                "evidence_ids": evidence_ids,
                "completeness": "blocked" if missing else "confirmed",
                "warnings": [f"待补：{label}" for label in labels],
                "follow_up_inputs": [{"type": "close_input", "label": item, "description": f"请补充{self._input_label(item)}"} for item in missing],
            }

        requested_metrics = []

        if any(keyword in query_lower for keyword in ["收入", "营收", "营业额"]):
            requested_metrics.append("revenue")
        if any(keyword in query_lower for keyword in ["利润", "净利", "盈利"]):
            requested_metrics.append("operating_net_profit")
        if any(keyword in query_lower for keyword in ["毛利", "毛利率"]):
            requested_metrics.append("gross_profit")
            requested_metrics.append("contribution_margin")
        if any(keyword in query_lower for keyword in ["成本", "费用"]):
            requested_metrics.append("prime_cost")
        if any(keyword in query_lower for keyword in ["保本", "盈亏"]):
            requested_metrics.append("monthly_break_even")
            requested_metrics.append("contribution_margin_rate")
        if any(keyword in query_lower for keyword in ["现金", "资金"]):
            requested_metrics.append("cash_coverage_days")
        if any(keyword in query_lower for keyword in ["客单价"]):
            requested_metrics.append("average_order_value")
        if any(keyword in query_lower for keyword in ["净利率"]):
            requested_metrics.append("net_margin")

        if not requested_metrics:
            requested_metrics = ["revenue", "operating_net_profit", "gross_profit"]

        metrics_result = []
        for metric_code in requested_metrics:
            metric = self.get_metric(store_id, metric_code, start, end)
            if "error" not in metric:
                metrics_result.append(metric)

        with self.connect() as connection:
            evidence_rows = connection.execute(
                """SELECT bf.id, bf.fact_type, bf.occurred_on, bf.amount_minor, sd.source_type, sd.source_platform
                   FROM business_facts bf LEFT JOIN source_documents sd ON sd.id = bf.source_document_id
                   WHERE bf.store_id = ? AND bf.review_status = 'confirmed' AND bf.posting_status = 'posted'
                     AND bf.occurred_on BETWEEN ? AND ?
                   ORDER BY bf.occurred_on LIMIT 20""",
                (store_id, start, end),
            ).fetchall()
            evidence_ids = [*evidence_ids, *[str(row["id"]) for row in evidence_rows]]

        formula_trace = []
        for metric in metrics_result:
            if metric["value_minor"] is not None:
                formula_trace.append(f"{metric['label']}: {metric['formula']} = {metric['value']}")

        warnings = []
        for metric in metrics_result:
            if metric["completeness"] != "confirmed":
                warnings.append(f"{metric['label']} 数据不完整: {', '.join(metric.get('blocking_reasons', []))}")

        follow_up_inputs = []
        if overview["missing_inputs"]:
            follow_up_inputs = [
                {"type": "close_input", "label": item, "description": f"请补充{self._input_label(item)}"}
                for item in overview["missing_inputs"]
            ]

        answer_parts = []
        for metric in metrics_result:
            if metric["value_minor"] is not None:
                if metric["metric_code"] in ["net_margin", "contribution_margin_rate"]:
                    answer_parts.append(f"{metric['label']}为{metric['value']:.2f}%")
                elif metric["metric_code"] == "cash_coverage_days":
                    answer_parts.append(f"{metric['label']}约{metric['value']}天")
                else:
                    answer_parts.append(f"{metric['label']}为{metric['value']:.2f}元")

        answer = "；".join(answer_parts) if answer_parts else "无法计算相关指标"

        completeness_count = sum(1 for m in metrics_result if m["completeness"] == "confirmed")
        completeness_ratio = completeness_count / len(metrics_result) if metrics_result else 0

        return {
            "answer": answer,
            "period": {"start": start, "end": end},
            "metrics": metrics_result,
            "formula_trace": formula_trace,
            "evidence_ids": evidence_ids,
            "completeness": "confirmed" if completeness_ratio == 1 else "partial" if completeness_ratio > 0 else "blocked",
            "warnings": warnings,
            "follow_up_inputs": follow_up_inputs,
        }

    def _input_label(self, input_key: str) -> str:
        labels = {
            "food_cost": "食材成本",
            "packaging_cost": "包装成本",
            "labor": "人工成本",
            "rent": "房租",
            "utility": "水电费",
            "other_cost": "其他费用",
            "cash_count": "现金实点",
        }
        return labels.get(input_key, input_key)

    def post_fact(self, store_id: str, fact_id: str) -> dict[str, Any]:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT id, fact_type, occurred_on, amount_minor, dimensions_json, posting_status, dedup_key FROM business_facts WHERE id = ? AND store_id = ?",
                (fact_id, store_id),
            ).fetchone()

        if not row:
            raise FinanceMigrationError(f"经营事实不存在：{fact_id}")

        if row["posting_status"] == "posted":
            return {"success": True, "fact_id": fact_id, "status": "already_posted", "entry_id": None}

        fact_type = row["fact_type"]
        occurred_on = row["occurred_on"]
        amount_minor = row["amount_minor"]
        dimensions = json.loads(row["dimensions_json"] or "{}")
        dedup_key = row["dedup_key"]

        lines = []
        description = ""

        if fact_type == "daily_recognized_revenue":
            lines = [("4009", 0, amount_minor), ("1019", amount_minor, 0)]
            description = f"{occurred_on} 已确认营业收入"
        elif fact_type == "transfer_fee":
            lines = [("1801", amount_minor, 0), ("3001", 0, amount_minor)]
            description = "门店转让费"
        elif fact_type == "initial_inventory_purchase":
            lines = [("1401", amount_minor, 0), ("3001", 0, amount_minor)]
            description = "首批库存采购"
        elif fact_type == "expense":
            category_code = dimensions.get("category_code")
            if category_code:
                lines = [(category_code, amount_minor, 0), ("2009", 0, amount_minor)]
                description = dimensions.get("description", "费用支出")
            else:
                raise FinanceMigrationError("费用类事实缺少 category_code")
        else:
            raise FinanceMigrationError(f"不支持的事实类型：{fact_type}")

        entry_id = self.post_entry(
            store_id=store_id,
            entry_date=occurred_on,
            posting_key=dedup_key or f"fact:{fact_id}",
            description=description,
            lines=lines,
            business_fact_id=fact_id,
            entry_type="manual",
        )

        with self.connect() as connection:
            connection.execute("UPDATE business_facts SET posting_status = 'posted' WHERE id = ?", (fact_id,))

        return {"success": True, "fact_id": fact_id, "status": "posted", "entry_id": entry_id}

    def cash_flow(self, store_id: str, start: str, end: str) -> dict[str, Any]:
        cf = self.cash_flow_summary(store_id, start, end)
        balances = self.account_balances(store_id, start, end)

        operating_inflows = [
            {"label": "现金销售收款", "code": "1001", "amount_minor": balances.get("1001", 0)},
            {"label": "平台结算到账", "code": "1002", "amount_minor": balances.get("1002", 0)},
            {"label": "前老板转款", "code": "1013", "amount_minor": balances.get("1013", 0)},
        ]

        operating_outflows = [
            {"label": "采购付款", "code": "1401", "amount_minor": balances.get("1401", 0)},
            {"label": "员工工资支付", "code": "6001", "amount_minor": balances.get("6001", 0)},
            {"label": "房租与商场费", "code": "6002", "amount_minor": balances.get("6002", 0)},
            {"label": "水电燃气", "code": "6003", "amount_minor": balances.get("6003", 0)},
            {"label": "系统与服务费", "code": "6004", "amount_minor": balances.get("6004", 0)},
            {"label": "维修、清洁与杂费", "code": "6005", "amount_minor": balances.get("6005", 0)},
        ]

        investing_activities = [
            {"label": "固定资产购置", "code": "1601", "amount_minor": balances.get("1601", 0)},
            {"label": "押金及长期待摊", "code": "1801", "amount_minor": balances.get("1801", 0)},
        ]

        financing_activities = [
            {"label": "老板投入", "code": "3001", "amount_minor": balances.get("3001", 0)},
            {"label": "老板取款", "code": "3002", "amount_minor": -balances.get("3002", 0)},
            {"label": "借入资金", "code": "2003", "amount_minor": balances.get("2003", 0)},
        ]

        return {
            "period_start": start,
            "period_end": end,
            "sections": [
                {
                    "label": "经营活动现金流",
                    "inflows": operating_inflows,
                    "outflows": operating_outflows,
                    "net_amount_minor": cf["operating"],
                },
                {
                    "label": "投资活动现金流",
                    "activities": investing_activities,
                    "net_amount_minor": cf["investing"],
                },
                {
                    "label": "筹资活动现金流",
                    "activities": financing_activities,
                    "net_amount_minor": cf["financing"],
                },
            ],
            "net_cash_change_minor": cf["net_change"],
        }
