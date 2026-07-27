import json
import sqlite3
from pathlib import Path

import pytest

from models.finance_ledger import FinanceLedger, FinanceMigrationError


PROJECT_ID = "xinyu-hengtai-dakou"
SOURCE_MEMORY = Path(__file__).parents[1] / "project_data" / PROJECT_ID / "memory.json"


@pytest.fixture()
def ledger(tmp_path):
    return FinanceLedger(tmp_path / "finance.db")


def test_schema_initializes_and_seeds_required_accounts(ledger):
    ledger.initialize()
    ledger.initialize()
    ledger.ensure_store(PROJECT_ID, "新余恒太城五楼大口章鱼烧", "2026-07-01")

    codes = {row["code"] for row in ledger.list_accounts(PROJECT_ID)}
    assert {"1001", "1002", "1012", "1013", "1019", "4001", "4002", "4003"}.issubset(codes)


def test_journal_rejects_unbalanced_and_is_idempotent(ledger):
    ledger.initialize()
    ledger.ensure_store(PROJECT_ID, "test", "2026-07-01")

    with pytest.raises(FinanceMigrationError, match="借贷不平衡"):
        ledger.post_entry(
            store_id=PROJECT_ID,
            entry_date="2026-07-01",
            posting_key="bad-entry",
            description="bad",
            lines=[("1001", 10000, 0), ("4001", 0, 9000)],
        )

    first = ledger.post_entry(
        store_id=PROJECT_ID,
        entry_date="2026-07-01",
        posting_key="cash-sale-1",
        description="cash sale",
        lines=[("1001", 10000, 0), ("4001", 0, 10000)],
    )
    second = ledger.post_entry(
        store_id=PROJECT_ID,
        entry_date="2026-07-01",
        posting_key="cash-sale-1",
        description="retry",
        lines=[("1001", 10000, 0), ("4001", 0, 10000)],
    )
    assert second == first
    assert ledger.count_posted_entries(PROJECT_ID) == 1


def test_owner_paid_inventory_installments_clear_prepayment_to_inventory_idempotently(ledger):
    ledger.initialize()
    ledger.ensure_store(PROJECT_ID, "test", "2026-07-01")
    payload = {
        "fact_id": "missing-fact-is-allowed-for-ledger-test",
        "receipt_date": "2026-07-05",
        "payments": [
            {"date": "2026-07-03", "amount_minor": 400000},
            {"date": "2026-07-04", "amount_minor": 499900},
            {"date": "2026-07-05", "amount_minor": 479200},
        ],
        "supplier": "林雄杰",
        "reference": "hq-13791",
    }
    first = ledger.record_owner_paid_inventory_purchase(PROJECT_ID, **payload)
    second = ledger.record_owner_paid_inventory_purchase(PROJECT_ID, **payload)

    balances = ledger.account_balances(PROJECT_ID, "2026-07-01", "2026-07-31")
    assert first["amount_minor"] == 1379100
    assert second["receipt_entry"] == first["receipt_entry"]
    assert balances["1410"] == 0
    assert balances["1401"] == 1379100
    assert balances["3001"] == 1379100
    assert ledger.count_posted_entries(PROJECT_ID) == 4
    spending = ledger.spending_summary(PROJECT_ID, "2026-07-01", "2026-07-31")
    assert spending["owner_paid_for_store"] == 1379100
    assert spending["actual_paid"] == 1379100


def test_real_july_revenue_migrates_once_without_platform_double_count(ledger):
    ledger.initialize()
    payload = json.loads(SOURCE_MEMORY.read_text(encoding="utf-8"))

    first = ledger.migrate_daily_operations(payload)
    second = ledger.migrate_daily_operations(payload)

    assert first["migrated_days"] == 12
    assert second["new_entries"] == 0
    assert ledger.revenue_total(PROJECT_ID, "2026-07-01", "2026-07-10") == 1187978
    assert ledger.order_total(PROJECT_ID, "2026-07-01", "2026-07-10") == 778
    assert ledger.count_posted_entries(PROJECT_ID) == 12
    assert ledger.unbalanced_entries(PROJECT_ID) == []


def test_unknown_payment_location_stays_in_clearing_not_cash(ledger):
    ledger.initialize()
    payload = json.loads(SOURCE_MEMORY.read_text(encoding="utf-8"))
    ledger.migrate_daily_operations(payload)

    balances = ledger.account_balances(PROJECT_ID, "2026-07-01", "2026-07-10")
    assert balances["1019"] > 0
    assert balances["1001"] == 69100


def test_merchant_net_sales_are_primary_operating_metric_without_changing_accounting_revenue(ledger):
    ledger.initialize()
    ledger.ensure_store(PROJECT_ID, "test", "2026-07-01")
    ledger.post_entry(
        store_id=PROJECT_ID,
        entry_date="2026-07-01",
        posting_key="recognized-sale",
        description="会计营业收入",
        lines=[("1012", 12000, 0), ("4002", 0, 12000)],
    )

    first = ledger.record_merchant_net_sale(
        PROJECT_ID,
        business_date="2026-07-01",
        channel="美团外卖",
        amount_minor=8560,
        source_basis="platform_wallet_screenshot",
        evidence_status="confirmed",
        settlement_state="wallet_credited",
        evidence_reference="voucher-meituan-0701",
    )
    second = ledger.record_merchant_net_sale(
        PROJECT_ID,
        business_date="2026-07-01",
        channel="美团外卖",
        amount_minor=8560,
        source_basis="platform_wallet_screenshot",
        evidence_status="confirmed",
        settlement_state="wallet_credited",
        evidence_reference="voucher-meituan-0701",
    )

    assert second == first
    assert ledger.merchant_net_total(PROJECT_ID, "2026-07-01", "2026-07-01") == 8560
    assert ledger.revenue_total(PROJECT_ID, "2026-07-01", "2026-07-01") == 12000


def test_merchant_net_sale_is_visible_at_its_current_fund_location(ledger):
    ledger.initialize()
    ledger.ensure_store(PROJECT_ID, "test", "2026-07-01")
    wallet = ledger.upsert_fund_account(
        PROJECT_ID, account_key="meituan-wallet", name="美团商家钱包",
        account_kind="platform_wallet", owner_kind="platform", is_store_controlled=False,
    )
    ledger.record_merchant_net_sale(
        PROJECT_ID, business_date="2026-07-01", channel="美团外卖", amount_minor=8560,
        source_basis="platform_wallet_screenshot", evidence_status="confirmed",
        settlement_state="wallet_credited", current_fund_account_id=wallet,
    )

    positions = {row["account_key"]: row["balance_minor"] for row in ledger.fund_positions(PROJECT_ID, "2026-07-01")}
    assert positions["meituan-wallet"] == 8560


def test_fund_movement_tracks_wallet_former_owner_and_store_bank_path(ledger):
    ledger.initialize()
    ledger.ensure_store(PROJECT_ID, "test", "2026-07-01")
    wallet = ledger.upsert_fund_account(
        PROJECT_ID, account_key="meituan-wallet", name="美团商家钱包",
        account_kind="platform_wallet", owner_kind="platform", is_store_controlled=False,
    )
    former = ledger.upsert_fund_account(
        PROJECT_ID, account_key="former-9863", name="前老板工商银行9863",
        account_kind="bank", owner_kind="former_owner", is_store_controlled=False,
    )
    store_bank = ledger.upsert_fund_account(
        PROJECT_ID, account_key="store-icbc", name="工商银行店铺专用",
        account_kind="bank", owner_kind="store", is_store_controlled=True,
    )

    ledger.record_fund_movement(
        PROJECT_ID, occurred_on="2026-07-02", amount_minor=10000,
        movement_type="wallet_withdrawal", from_fund_account_id=wallet,
        to_fund_account_id=former, business_scope="store", purpose="平台自动提现",
        status="confirmed", reference="wallet-to-former-0702",
    )
    ledger.record_fund_movement(
        PROJECT_ID, occurred_on="2026-07-05", amount_minor=10000,
        movement_type="former_owner_transfer", from_fund_account_id=former,
        to_fund_account_id=store_bank, business_scope="store", purpose="前老板转回代收款",
        status="confirmed", reference="former-to-store-0705",
    )

    movements = ledger.list_fund_movements(PROJECT_ID, "2026-07-01", "2026-07-31")
    assert [row["movement_type"] for row in movements] == ["former_owner_transfer", "wallet_withdrawal"]
    assert movements[0]["to_account_name"] == "工商银行店铺专用"
    assert movements[1]["from_account_name"] == "美团商家钱包"


def test_store_and_personal_outflows_are_separate_totals(ledger):
    ledger.initialize()
    ledger.ensure_store(PROJECT_ID, "test", "2026-07-01")
    owner = ledger.upsert_fund_account(
        PROJECT_ID, account_key="owner-card", name="个人卡", account_kind="bank",
        owner_kind="owner", is_store_controlled=False,
    )
    for scope, amount in (("store", 12000), ("personal", 3500)):
        ledger.record_fund_movement(
            PROJECT_ID, occurred_on="2026-07-02", amount_minor=amount,
            movement_type=f"{scope}_outflow", from_fund_account_id=owner,
            to_fund_account_id=None, business_scope=scope, purpose="test",
            status="confirmed", reference=f"{scope}-outflow",
        )

    assert ledger.fund_movement_totals(PROJECT_ID, "2026-07-01", "2026-07-31") == {
        "store_outflow": 12000,
        "personal_outflow": 3500,
    }


def test_debt_principal_and_transfer_fee_allocation_are_not_double_counted(ledger):
    ledger.initialize()
    ledger.ensure_store(PROJECT_ID, "test", "2026-07-01")
    debt_id = ledger.record_debt(
        PROJECT_ID, debt_key="sun-yongqun", lender="孙永群", principal_minor=5400000,
        received_on="2026-07-01", status="active", notes="接店借款",
    )
    ledger.record_debt_allocation(
        PROJECT_ID, debt_id=debt_id, allocation_key="transfer-fee",
        purpose="门店转让费", amount_minor=4000000, classification="acquisition_investment",
    )

    summary = ledger.debt_summary(PROJECT_ID)
    assert summary["principal_minor"] == 5400000
    assert summary["allocated_minor"] == 4000000
    assert summary["outstanding_minor"] == 5400000
    assert summary["total_financing_and_uses_minor"] != 9400000


def test_evidence_voucher_preserves_original_image_and_business_links(ledger):
    ledger.initialize()
    ledger.ensure_store(PROJECT_ID, "test", "2026-07-01")

    first = ledger.register_evidence_voucher(
        PROJECT_ID,
        voucher_key="income-20260701-meituan",
        business_date="2026-07-01",
        evidence_type="platform_wallet_screenshot",
        source_sheet="店铺收入",
        source_cell="G3",
        original_filename="image12.png",
        original_path="evidence/2026-07/image12.png",
        sha256="abc123",
        status="confirmed",
        channel="美团外卖",
        amount_minor=8560,
    )
    second = ledger.register_evidence_voucher(
        PROJECT_ID,
        voucher_key="income-20260701-meituan",
        business_date="2026-07-01",
        evidence_type="platform_wallet_screenshot",
        source_sheet="店铺收入",
        source_cell="G3",
        original_filename="image12.png",
        original_path="evidence/2026-07/image12.png",
        sha256="abc123",
        status="confirmed",
        channel="美团外卖",
        amount_minor=8560,
    )

    vouchers = ledger.list_evidence_vouchers(PROJECT_ID, "2026-07-01", "2026-07-31")
    assert second == first
    assert len(vouchers) == 1
    assert vouchers[0]["voucher_number"].startswith("PZ-20260701-")
    assert vouchers[0]["original_path"] == "evidence/2026-07/image12.png"


def test_former_owner_transfer_reclassifies_asset_without_new_revenue(ledger):
    ledger.initialize()
    payload = json.loads(SOURCE_MEMORY.read_text(encoding="utf-8"))
    ledger.migrate_daily_operations(payload)
    revenue_before = ledger.revenue_total(PROJECT_ID, "2026-07-01", "2026-07-31")
    balances_before = ledger.account_balances(PROJECT_ID, "2026-07-01", "2026-07-31")
    former_before = balances_before["1013"]
    bank_before = balances_before["1002"]

    ledger.record_former_owner_transfer(PROJECT_ID, "2026-07-11", 50000, "transfer-001")
    balances = ledger.account_balances(PROJECT_ID, "2026-07-01", "2026-07-31")

    assert ledger.revenue_total(PROJECT_ID, "2026-07-01", "2026-07-31") == revenue_before
    assert balances["1013"] == former_before - 50000
    assert balances["1002"] == bank_before + 50000


def test_digital_sales_wait_for_settlement_and_receipt_does_not_add_revenue(ledger):
    ledger.initialize()
    ledger.ensure_store(PROJECT_ID, "test", "2026-07-01")
    operation = {
        "date": "2026-07-13",
        "actual_revenue": 100,
        "orders": 2,
        "payment_methods": [
            {"method": "微信", "amount": 80, "orders": 1},
            {"method": "现金", "amount": 20, "orders": 1},
        ],
    }

    ledger.record_confirmed_daily_revenue(PROJECT_ID, operation)
    sales_balances = ledger.account_balances(PROJECT_ID, "2026-07-13", "2026-07-13")
    assert sales_balances["1001"] == 2000
    assert sales_balances["1012"] == 8000
    assert sales_balances["1002"] == 0

    revenue_before = ledger.revenue_total(PROJECT_ID, "2026-07-13", "2026-07-14")
    first = ledger.record_platform_settlement(PROJECT_ID, "2026-07-14", 8000, "wechat-0713")
    second = ledger.record_platform_settlement(PROJECT_ID, "2026-07-14", 8000, "wechat-0713")
    balances = ledger.account_balances(PROJECT_ID, "2026-07-13", "2026-07-14")

    assert second == first
    assert balances["1012"] == 0
    assert balances["1002"] == 8000
    assert ledger.revenue_total(PROJECT_ID, "2026-07-13", "2026-07-14") == revenue_before


def test_jd_online_sale_collected_by_former_owner_stays_receivable(ledger):
    ledger.initialize()
    ledger.ensure_store(PROJECT_ID, "test", "2026-07-01")
    ledger.record_confirmed_daily_revenue(PROJECT_ID, {
        "date": "2026-07-13",
        "actual_revenue": 66,
        "orders": 1,
        "payment_methods": [{"method": "京东外卖", "amount": 66, "orders": 1}],
    })

    balances = ledger.account_balances(PROJECT_ID, "2026-07-13", "2026-07-13")
    assert balances["1013"] == 6600
    assert balances["1002"] == 0


def test_profit_remains_incomplete_after_revenue_only_migration(ledger):
    ledger.initialize()
    payload = json.loads(SOURCE_MEMORY.read_text(encoding="utf-8"))
    ledger.migrate_daily_operations(payload)

    result = ledger.profit_readiness(PROJECT_ID, "2026-07-01", "2026-07-10")
    assert result["status"] == "incomplete"
    assert result["net_profit_minor"] is None
    assert {"food_cost", "packaging_cost", "labor", "utility"}.issubset(result["blocking_reasons"])
