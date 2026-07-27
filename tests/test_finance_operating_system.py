import io
from datetime import date, timedelta

from fastapi.testclient import TestClient
from openpyxl import Workbook

import config
import models.project as project_model
import server.routes.capture as capture_route
from core.finance_intake import parse_finance_file
from models.finance_ledger import FinanceLedger
from models.project import ProjectMemory
from server.main import app


PROJECT_ID = "finance-os-store"


def prepared_ledger(tmp_path):
    ledger = FinanceLedger(tmp_path / "finance.db")
    ledger.initialize()
    ledger.ensure_store(PROJECT_ID, "测试门店", "2026-07-01")
    ledger.upsert_fund_account(
        PROJECT_ID,
        account_key="store-icbc",
        name="工商银行店铺专用",
        account_kind="bank",
        owner_kind="store",
        is_store_controlled=True,
        opening_balance_minor=100_000,
    )
    ledger.upsert_fund_account(
        PROJECT_ID,
        account_key="owner-cmb",
        name="招商银行个人账户",
        account_kind="bank",
        owner_kind="owner",
        is_store_controlled=False,
    )
    return ledger


def test_fund_account_endpoint_initializes_an_empty_store(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "PROJECT_DATA_DIR", tmp_path)
    monkeypatch.setattr(project_model, "PROJECT_DATA_DIR", tmp_path)
    response = TestClient(app).post(
        f"/api/projects/{PROJECT_ID}/finance/fund-accounts",
        json={
            "account_key": "store-icbc",
            "name": "工商银行店铺专用",
            "account_kind": "bank",
            "owner_kind": "store",
            "is_store_controlled": True,
            "opening_balance": 0,
            "effective_from": "2026-07-01",
        },
    )
    assert response.status_code == 200
    assert FinanceLedger.for_project(PROJECT_ID).list_fund_accounts(PROJECT_ID)[0]["account_key"] == "store-icbc"


def test_bookkeeping_is_a_fund_input_and_posts_only_safe_accounting(tmp_path):
    ledger = prepared_ledger(tmp_path)
    store_expense = ledger.create_bookkeeping_record(
        PROJECT_ID,
        transaction_date="2026-07-17",
        direction="outflow",
        amount_minor=12_340,
        transaction_kind="operating_expense",
        business_scope="store",
        category_code="6003",
        category_name="水电燃气",
        account_key="store-icbc",
        counterparty="恒太城物业",
        summary="7月电费",
        source_type="manual",
        source_reference="manual-electricity-0717",
        confidence="confirmed",
    )
    first = ledger.confirm_bookkeeping_record(PROJECT_ID, store_expense)
    second = ledger.confirm_bookkeeping_record(PROJECT_ID, store_expense)

    assert first["status"] == "posted"
    assert second["journal_entry_id"] == first["journal_entry_id"]
    assert ledger.overview(PROJECT_ID, "2026-07-17", "2026-07-17")["costs_minor"]["utility"] == 12_340

    personal = ledger.create_bookkeeping_record(
        PROJECT_ID,
        transaction_date="2026-07-17",
        direction="outflow",
        amount_minor=3_500,
        transaction_kind="personal_spending",
        business_scope="personal",
        category_code=None,
        category_name="个人消费",
        account_key="owner-cmb",
        counterparty="个人消费",
        summary="个人支出",
        source_type="manual",
        source_reference="manual-personal-0717",
        confidence="confirmed",
    )
    result = ledger.confirm_bookkeeping_record(PROJECT_ID, personal)
    assert result["journal_entry_id"] is None
    assert ledger.fund_movement_totals(PROJECT_ID, "2026-07-17", "2026-07-17")["personal_outflow"] == 3_500


def test_posted_electricity_receipt_can_be_auditably_corrected_to_store_expense(tmp_path):
    ledger = prepared_ledger(tmp_path)
    voucher_id = ledger.register_evidence_voucher(
        PROJECT_ID,
        voucher_key="electricity-0720",
        evidence_type="platform_settlement",
        original_filename="electricity.jpg",
        original_path="documents/electricity.jpg",
        sha256="electricity-proof-sha256",
        status="confirmed",
        business_date="2026-07-20",
        amount_minor=2_205,
    )
    record_id = ledger.create_bookkeeping_record(
        PROJECT_ID,
        transaction_date="2026-07-20",
        direction="inflow",
        amount_minor=2_205,
        transaction_kind="platform_settlement",
        business_scope="store",
        category_code=None,
        category_name="平台结算到账",
        business_category_key="platform_wallet_credit",
        business_category_group="资金调拨与结算",
        account_key="store-icbc",
        counterparty="江西省电力",
        summary="电网充值花了22.05 工商银行 充值缴费",
        source_type="finance_execution_plan",
        source_reference="electricity-wrong-direction",
        voucher_id=voucher_id,
        confidence="confirmed",
    )
    wrong = ledger.confirm_bookkeeping_record(PROJECT_ID, record_id)
    assert wrong["direction"] == "inflow"
    assert ledger.fund_positions(PROJECT_ID, "2026-07-20")[0]["balance_minor"] == 102_205

    first = ledger.correct_posted_bookkeeping_classification(
        PROJECT_ID,
        record_id,
        business_category_key="utilities",
        reason="原凭证为工商银行店铺账户支付的电力缴费，不是平台到账",
        corrected_by="owner",
        correction_key="electricity-direction-20260723",
    )
    second = ledger.correct_posted_bookkeeping_classification(
        PROJECT_ID,
        record_id,
        business_category_key="utilities",
        reason="重复请求不应二次记账",
        corrected_by="owner",
        correction_key="electricity-direction-20260723",
    )

    corrected = ledger.get_bookkeeping_record(PROJECT_ID, record_id)
    assert first["correction"]["id"] == second["correction"]["id"]
    assert corrected["direction"] == "outflow"
    assert corrected["transaction_kind"] == "operating_expense"
    assert corrected["business_scope"] == "store"
    assert corrected["category_code"] == "6003"
    assert corrected["category_name"] == "水电燃气"
    assert corrected["business_category_key"] == "utilities"
    assert corrected["journal_entry_id"]
    assert ledger.overview(PROJECT_ID, "2026-07-20", "2026-07-20")["costs_minor"]["utility"] == 2_205
    assert ledger.fund_positions(PROJECT_ID, "2026-07-20")[0]["balance_minor"] == 97_795
    with ledger.connect() as connection:
        old_movement = connection.execute(
            "SELECT status FROM fund_movements WHERE id=?", (wrong["fund_movement_id"],)
        ).fetchone()
        voucher = connection.execute(
            "SELECT evidence_type FROM evidence_vouchers WHERE id=?", (voucher_id,)
        ).fetchone()
        correction = connection.execute(
            "SELECT before_json, after_json FROM bookkeeping_corrections WHERE id=?",
            (first["correction"]["id"],),
        ).fetchone()
    assert old_movement["status"] == "void"
    assert voucher["evidence_type"] == "operating_expense"
    assert '"direction": "inflow"' in correction["before_json"]
    assert '"direction": "outflow"' in correction["after_json"]
    snapshot = ledger.period_finance_snapshot(PROJECT_ID, "2026-07-20", "2026-07-20")
    matching_rows = [
        item for item in snapshot["ledger_entries"]
        if item["amount_minor"] == 2_205 and item.get("counterparty") == "江西省电力"
    ]
    assert len(matching_rows) == 1
    assert matching_rows[0]["entry_origin"] == "bookkeeping"


def test_confirmed_loan_bookkeeping_updates_liability_and_debt_schedule_once(tmp_path):
    ledger = prepared_ledger(tmp_path)
    loan = ledger.create_bookkeeping_record(
        PROJECT_ID,
        transaction_date="2026-07-01",
        direction="inflow",
        amount_minor=6_400_000,
        transaction_kind="loan_in",
        business_scope="store",
        category_code="2003",
        category_name="借款到账",
        account_key="store-icbc",
        counterparty="出借人",
        summary="接店借款",
        source_type="manual",
        source_reference="opening-loan-64000",
        confidence="confirmed",
    )

    ledger.confirm_bookkeeping_record(PROJECT_ID, loan)
    ledger.confirm_bookkeeping_record(PROJECT_ID, loan)

    debt = ledger.debt_summary(PROJECT_ID)
    overview = ledger.overview(PROJECT_ID, "2026-07-01", "2026-07-31")
    assert debt["principal_minor"] == 6_400_000
    assert debt["outstanding_minor"] == 6_400_000
    assert len(debt["items"]) == 1
    assert debt["items"][0]["lender"] == "出借人"
    assert overview["liabilities_minor"]["loans"] == 6_400_000
    assert overview["revenue_minor"] == 0

    repayment = ledger.create_bookkeeping_record(
        PROJECT_ID,
        transaction_date="2026-07-18",
        direction="outflow",
        amount_minor=1_000_000,
        transaction_kind="loan_repayment",
        business_scope="store",
        category_code="2003",
        category_name="偿还借款本金",
        account_key="store-icbc",
        counterparty="出借人",
        summary="偿还本金",
        source_type="manual",
        source_reference="loan-repayment-10000",
        confidence="confirmed",
    )
    ledger.confirm_bookkeeping_record(PROJECT_ID, repayment)
    after_repayment = ledger.debt_summary(PROJECT_ID)
    assert after_repayment["outstanding_minor"] == 5_400_000
    assert after_repayment["repaid_principal_minor"] == 1_000_000
    assert after_repayment["items"][0]["repaid_principal_minor"] == 1_000_000


def test_fund_close_without_cost_basis_never_publishes_fake_profit(tmp_path):
    ledger = prepared_ledger(tmp_path)
    ledger.record_confirmed_daily_revenue(PROJECT_ID, {
        "date": "2026-07-17",
        "actual_revenue": 1084.74,
        "payment_methods": [{"method": "微信", "amount": 1084.74}],
    })
    close = ledger.save_daily_close(PROJECT_ID, "2026-07-17", {
        "counted_cash_minor": 0,
        "reserve_cash_minor": 0,
        "merchant_net_confirmed": True,
        "fund_locations_reviewed": True,
        "outflows_reviewed": True,
    })

    readiness = ledger.profit_readiness(PROJECT_ID, "2026-07-17", "2026-07-17")
    assert close["status"] == "closed"
    assert readiness["status"] == "incomplete"
    assert readiness["net_profit_minor"] is None
    assert {"food_cost", "packaging_cost", "labor", "rent", "utility", "other_cost"}.issubset(
        readiness["blocking_reasons"],
    )


def test_bank_statement_parser_preserves_control_totals_and_does_not_call_receipts_revenue():
    statement = """交易日期,收支类型,收入金额,支出金额,对方户名,摘要,交易流水号,余额
2026-07-16,收入,328.50,,美团,商户平台结算,MT001,1328.50
2026-07-16,支出,,268.00,菜市场,采购蔬菜,ICBC002,1060.50
2026-07-16,支出,,39.90,便利店,个人消费,CMB003,1020.60
""".encode("utf-8-sig")

    parsed = parse_finance_file("工商银行流水.csv", "text/csv", statement, account_owner_kind="store")

    assert parsed["row_count"] == 3
    assert parsed["inflow_minor"] == 32_850
    assert parsed["outflow_minor"] == 30_790
    assert parsed["transactions"][0]["transaction_kind"] == "platform_settlement"
    assert parsed["transactions"][0]["category_code"] is None
    assert parsed["transactions"][0]["classification_reason"]
    assert parsed["transactions"][2]["business_scope"] == "personal"


def test_excel_statement_parser_reads_real_workbook_rows_and_control_totals():
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["工商银行交易流水明细"])
    sheet.append(["交易日期", "收支类型", "收入金额", "支出金额", "对方户名", "摘要", "交易流水号"])
    sheet.append(["2026-07-17", "收入", 328.5, None, "美团", "平台结算", "MT-XLSX-001"])
    sheet.append(["2026-07-17", "支出", None, 268, "菜市场", "采购蔬菜", "ICBC-XLSX-002"])
    buffer = io.BytesIO()
    workbook.save(buffer)
    workbook.close()

    parsed = parse_finance_file(
        "工商银行流水.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        buffer.getvalue(),
        account_owner_kind="store",
    )

    assert parsed["row_count"] == 2
    assert parsed["inflow_minor"] == 32_850
    assert parsed["outflow_minor"] == 26_800
    assert parsed["transactions"][0]["transaction_kind"] == "platform_settlement"
    assert parsed["transactions"][1]["transaction_kind"] == "inventory_purchase"


def test_daily_snapshot_separates_selected_day_from_as_of_position(tmp_path):
    ledger = prepared_ledger(tmp_path)
    ledger.record_merchant_net_sale(
        PROJECT_ID,
        business_date="2026-07-16",
        channel="美团外卖",
        amount_minor=32_850,
        source_basis="platform_statement",
        evidence_status="confirmed",
        settlement_state="wallet_credited",
    )
    entry_id = ledger.create_bookkeeping_record(
        PROJECT_ID,
        transaction_date="2026-07-17",
        direction="outflow",
        amount_minor=26_800,
        transaction_kind="inventory_purchase",
        business_scope="store",
        category_code="1401",
        category_name="原材料库存",
        account_key="store-icbc",
        counterparty="菜市场",
        summary="采购蔬菜",
        source_type="manual",
        source_reference="purchase-0717",
        confidence="confirmed",
    )
    ledger.confirm_bookkeeping_record(PROJECT_ID, entry_id)

    snapshot = ledger.daily_finance_snapshot(PROJECT_ID, "2026-07-17")

    assert snapshot["selected_date"] == "2026-07-17"
    assert snapshot["as_of"]["actual_bank_balance_minor"] is None
    assert snapshot["as_of"]["actual_bank_balance_status"] == "missing_statement_snapshot"
    assert "不是银行卡实时余额" in snapshot["as_of"]["store_controlled_label"]
    assert snapshot["money_flow"]["events"][0]["scene"] == "店铺支出"
    assert snapshot["money_flow"]["events"][0]["destination_label"] == "原材料库存"
    assert snapshot["day_activity"]["store_outflow_minor"] == 26_800
    assert snapshot["day_activity"]["merchant_net_minor"] == 0
    assert snapshot["as_of"]["store_controlled_minor"] == 73_200
    assert snapshot["bookkeeping_entries"][0]["category_name"] == "原材料库存"
    trace = snapshot["ledger_entries"][0]["traceability"]
    assert trace["business_date"] == "2026-07-17"
    assert trace["recorded_at"]
    assert trace["source_reference"] == "purchase-0717"
    assert trace["fund_ownership"] == "store"
    assert trace["account_name"] == "工商银行店铺专用"


def test_money_flow_uses_business_status_and_voucher_instead_of_review_state(tmp_path):
    ledger = prepared_ledger(tmp_path)
    wallet = ledger.upsert_fund_account(
        PROJECT_ID,
        account_key="meituan-wallet",
        name="美团平台钱包",
        account_kind="platform_wallet",
        owner_kind="platform",
        is_store_controlled=False,
    )
    voucher_id = ledger.register_evidence_voucher(
        PROJECT_ID,
        voucher_key="店铺收入:G3:IMG-001",
        business_date="2026-07-18",
        evidence_type="settlement_screenshot",
        channel="美团外卖",
        amount_minor=32_850,
        source_sheet="店铺收入",
        source_cell="G3",
        original_filename="meituan-wallet.png",
        original_path="documents/meituan-wallet.png",
        sha256="abc123",
        status="confirmed",
    )
    ledger.record_merchant_net_sale(
        PROJECT_ID,
        business_date="2026-07-18",
        channel="美团外卖",
        amount_minor=32_850,
        source_basis="平台截图",
        evidence_status="confirmed",
        settlement_state="wallet_credited",
        current_fund_account_id=wallet,
        evidence_reference="IMG-001",
    )

    snapshot = ledger.daily_finance_snapshot(PROJECT_ID, "2026-07-18")
    event = snapshot["money_flow"]["events"][0]
    row = next(item for item in snapshot["ledger_entries"] if item["entry_origin"] == "merchant_net")

    assert event["status"] == "awaiting_arrival"
    assert event["status_label"] == "已到平台钱包"
    assert event["voucher_id"] == voucher_id
    assert event["source_label"] == "美团外卖营业收入"
    assert row["status"] == "awaiting_arrival"
    assert row["voucher_filename"] == "meituan-wallet.png"


def test_period_finance_snapshot_returns_all_rows_in_selected_range(tmp_path):
    ledger = prepared_ledger(tmp_path)
    for business_date, amount in (("2026-07-17", 10_000), ("2026-07-18", 20_000)):
        ledger.record_merchant_net_sale(
            PROJECT_ID,
            business_date=business_date,
            channel="客如云线下",
            amount_minor=amount,
            source_basis="keruyun_report",
            evidence_status="confirmed",
            settlement_state="store_account_received",
            evidence_reference=f"voucher-{business_date}",
        )

    period = ledger.period_finance_snapshot(PROJECT_ID, "2026-07-17", "2026-07-18")
    day = ledger.daily_finance_snapshot(PROJECT_ID, "2026-07-18")

    assert period["period_start"] == "2026-07-17"
    assert period["period_end"] == "2026-07-18"
    assert period["scope_kind"] == "period"
    assert period["selected_date"] == "2026-07-18"
    assert period["period_activity"]["merchant_net_minor"] == 30_000
    assert len(period["money_flow"]["events"]) == 2
    assert len(period["ledger_entries"]) == 2
    assert day["scope_kind"] == "day"
    assert day["period_activity"]["merchant_net_minor"] == 20_000
    assert len(day["ledger_entries"]) == 1


def test_period_finance_snapshot_endpoint_rejects_reversed_range(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "PROJECT_DATA_DIR", tmp_path)
    monkeypatch.setattr(project_model, "PROJECT_DATA_DIR", tmp_path)
    client = TestClient(app)
    ledger = FinanceLedger.for_project(PROJECT_ID)
    ledger.ensure_store(PROJECT_ID, "测试门店", "2026-07-01")

    response = client.get(
        f"/api/projects/{PROJECT_ID}/finance/period-snapshot?start=2026-07-18&end=2026-07-17"
    )

    assert response.status_code == 422


def test_finance_analytics_preserves_accounting_boundaries_and_missing_days(tmp_path):
    ledger = prepared_ledger(tmp_path)
    wallet_id = ledger.upsert_fund_account(
        PROJECT_ID,
        account_key="meituan-wallet",
        name="美团外卖商家钱包",
        account_kind="platform_wallet",
        owner_kind="platform",
        is_store_controlled=False,
    )
    ledger.upsert_platform_collection_binding(
        PROJECT_ID,
        platform="美团外卖",
        collector_account_key="meituan-wallet",
        destination_account_key="store-icbc",
        collector_owner_kind="platform",
        settlement_rule="T+3个工作日进入平台钱包",
        settlement_delay_days=3,
        settlement_day_basis="working_day",
        settlement_rule_status="confirmed",
        settlement_delay_target="platform_wallet",
        withdrawal_mode="automatic",
        effective_from="2026-07-01",
    )
    ledger.record_merchant_net_sale(
        PROJECT_ID,
        business_date="2026-07-17",
        channel="美团外卖",
        amount_minor=50_000,
        source_basis="platform_statement",
        evidence_status="confirmed",
        settlement_state="wallet_credited",
        current_fund_account_id=wallet_id,
        evidence_reference="voucher-meituan-0717",
    )

    inventory = ledger.create_bookkeeping_record(
        PROJECT_ID,
        transaction_date="2026-07-17",
        direction="outflow",
        amount_minor=30_000,
        transaction_kind="inventory_purchase",
        business_scope="store",
        category_code="1401",
        category_name="食材原料采购",
        business_category_key="food_purchase",
        business_category_group="inventory",
        account_key="store-icbc",
        counterparty="供应商",
        summary="采购入库",
        source_type="manual",
        source_reference="inventory-0717",
        confidence="confirmed",
    )
    utility = ledger.create_bookkeeping_record(
        PROJECT_ID,
        transaction_date="2026-07-17",
        direction="outflow",
        amount_minor=8_000,
        transaction_kind="operating_expense",
        business_scope="store",
        category_code="6003",
        category_name="水电燃气",
        business_category_key="utilities",
        business_category_group="operating_expense",
        account_key="store-icbc",
        counterparty="物业",
        summary="电费",
        source_type="manual",
        source_reference="utility-0717",
        confidence="confirmed",
    )
    personal = ledger.create_bookkeeping_record(
        PROJECT_ID,
        transaction_date="2026-07-17",
        direction="outflow",
        amount_minor=3_898,
        transaction_kind="personal_spending",
        business_scope="personal",
        category_code=None,
        category_name="个人消费",
        business_category_key="personal_spending_personal_account",
        business_category_group="owner_current",
        account_key="owner-cmb",
        counterparty="淘宝",
        summary="个人购物",
        source_type="manual",
        source_reference="personal-0717",
        confidence="confirmed",
    )
    for record_id in (inventory, utility, personal):
        ledger.confirm_bookkeeping_record(PROJECT_ID, record_id)

    result = ledger.finance_analytics(PROJECT_ID, "2026-07-17", "2026-07-18")

    assert result["data_completeness"] == "partial"
    assert result["daily_series"][0]["merchant_net_minor"] == 50_000
    assert result["daily_series"][0]["state"] == "partial"
    assert result["daily_series"][0]["store_outflow_minor"] == 38_000
    assert result["daily_series"][0]["personal_outflow_minor"] == 3_898
    assert result["daily_series"][1]["state"] == "missing"
    assert result["daily_series"][1]["merchant_net_minor"] is None
    assert result["daily_series"][1]["store_outflow_minor"] is None
    assert result["expense_breakdown"] == [
        {"key": "utility", "label": "水电燃气", "amount_minor": 8_000},
    ]
    assert result["kpis"]["inventory_purchase_minor"] == 30_000
    assert result["kpis"]["personal_outflow_minor"] == 3_898
    assert result["settlement_timeline"][0]["expected_wallet_date"] == "2026-07-22"
    assert result["settlement_timeline"][0]["expected_bank_date"] is None
    assert result["settlement_timeline"][0]["withdrawal_mode"] == "automatic"
    assert result["settlement_timeline"][0]["status"] == "awaiting_arrival"
    assert "voucher-meituan-0717" in result["evidence_ids"]
    assert result["profit_bridge"]["status"] == "partial"
    assert result["profit_bridge"]["net_profit_minor"] is None


def test_finance_analytics_endpoint_uses_selected_period(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "PROJECT_DATA_DIR", tmp_path)
    monkeypatch.setattr(project_model, "PROJECT_DATA_DIR", tmp_path)
    client = TestClient(app)
    ledger = FinanceLedger.for_project(PROJECT_ID)
    ledger.ensure_store(PROJECT_ID, "测试门店", "2026-07-01")
    ledger.record_merchant_net_sale(
        PROJECT_ID,
        business_date="2026-07-20",
        channel="客如云线下",
        amount_minor=12_345,
        source_basis="keruyun_report",
        evidence_status="confirmed",
        settlement_state="store_account_received",
        evidence_reference="voucher-kry-0720",
    )

    response = client.get(
        f"/api/projects/{PROJECT_ID}/finance/analytics?start=2026-07-20&end=2026-07-21"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["period_start"] == "2026-07-20"
    assert payload["period_end"] == "2026-07-21"
    assert payload["channel_breakdown"][0]["channel"] == "客如云线下"
    assert payload["daily_series"][1]["state"] == "missing"


def test_finance_analytics_empty_period_never_invents_zero_activity(tmp_path):
    ledger = prepared_ledger(tmp_path)

    result = ledger.finance_analytics(PROJECT_ID, "2026-07-20", "2026-07-21")

    assert result["data_completeness"] == "missing"
    assert result["channel_breakdown"] == []
    assert result["expense_breakdown"] == []
    assert result["fund_flow_edges"] == []
    assert result["missing_days"] == ["2026-07-20", "2026-07-21"]
    assert all(item["merchant_net_minor"] is None for item in result["daily_series"])
    assert all(item["store_outflow_minor"] is None for item in result["daily_series"])


def test_former_owner_transfer_flow_does_not_mistake_receiving_bank_for_source(tmp_path):
    ledger = prepared_ledger(tmp_path)
    ledger.post_entry(
        store_id=PROJECT_ID,
        entry_date="2026-07-19",
        posting_key="seed-former-owner-receivable-for-flow",
        description="前老板代收四个平台款",
        lines=[("1013", 291_876, 0), ("4009", 0, 291_876)],
    )
    entry_id = ledger.create_bookkeeping_record(
        PROJECT_ID,
        transaction_date="2026-07-20",
        direction="inflow",
        amount_minor=291_876,
        transaction_kind="former_owner_transfer",
        business_scope="store",
        category_code="1013",
        category_name="前老板转回代收款",
        account_key="store-icbc",
        counterparty="前老板",
        summary="美团外卖、淘宝闪购、京东外卖、抖音团购代收款",
        source_type="manual",
        source_reference="former-owner-20260720",
        confidence="confirmed",
    )
    ledger.confirm_bookkeeping_record(PROJECT_ID, entry_id)

    snapshot = ledger.daily_finance_snapshot(PROJECT_ID, "2026-07-20")
    event = next(item for item in snapshot["money_flow"]["events"] if item["id"] == entry_id)

    assert event["amount_minor"] == 291_876
    assert event["source_label"] == "前老板"
    assert event["location_label"] == "工商银行店铺专用"
    assert event["destination_label"] == "核销前老板代收平台款"
    assert event["status_label"] == "已到账本人"


def test_cash_forecast_marks_first_chain_break_date(tmp_path):
    ledger = prepared_ledger(tmp_path)
    as_of = date(2026, 7, 17)
    ledger.create_cash_plan_item(
        PROJECT_ID,
        due_date=(as_of + timedelta(days=3)).isoformat(),
        flow_type="required_outflow",
        amount_minor=120_000,
        category="工资",
        counterparty="员工",
        priority="must_pay",
        source_reference="salary-july",
    )
    ledger.create_cash_plan_item(
        PROJECT_ID,
        due_date=(as_of + timedelta(days=2)).isoformat(),
        flow_type="expected_inflow",
        amount_minor=10_000,
        category="前老板转回款",
        counterparty="前老板",
        priority="expected",
        source_reference="former-owner-expected",
    )

    forecast = ledger.cash_chain_forecast(PROJECT_ID, as_of.isoformat(), safety_reserve_minor=0)

    seven_days = next(item for item in forecast["horizons"] if item["days"] == 7)
    assert seven_days["ending_minor"] == -10_000
    assert seven_days["shortfall_minor"] == 10_000
    assert forecast["first_risk_date"] == "2026-07-20"
    assert forecast["status"] == "at_risk"


def test_finance_os_api_imports_statement_idempotently_and_serves_snapshot(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "PROJECT_DATA_DIR", tmp_path)
    ledger = FinanceLedger.for_project(PROJECT_ID)
    ledger.ensure_store(PROJECT_ID, "测试门店", "2026-07-01")
    ledger.upsert_fund_account(
        PROJECT_ID,
        account_key="store-icbc",
        name="工商银行店铺专用",
        account_kind="bank",
        owner_kind="store",
        is_store_controlled=True,
    )
    client = TestClient(app)
    csv_bytes = """交易日期,收支类型,收入金额,支出金额,对方户名,摘要,交易流水号
2026-07-17,收入,328.50,,美团,平台结算,MT001
2026-07-17,支出,,268.00,菜市场,采购蔬菜,ICBC002
""".encode("utf-8-sig")

    def upload():
        return client.post(
            f"/api/projects/{PROJECT_ID}/finance/imports",
            data={"account_key": "store-icbc", "source_type": "bank_statement"},
            files={"file": ("工商银行流水.csv", io.BytesIO(csv_bytes), "text/csv")},
        )

    first = upload()
    second = upload()
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["batch_id"] == second.json()["batch_id"]
    assert first.json()["row_count"] == 2
    assert first.json()["inflow_minor"] == 32_850
    assert first.json()["outflow_minor"] == 26_800

    entries = client.get(f"/api/projects/{PROJECT_ID}/finance/bookkeeping?start=2026-07-17&end=2026-07-17")
    assert entries.status_code == 200
    assert len(entries.json()["rows"]) == 2

    snapshot = client.get(f"/api/projects/{PROJECT_ID}/finance/daily-snapshot?date=2026-07-17")
    assert snapshot.status_code == 200
    assert snapshot.json()["selected_date"] == "2026-07-17"


def test_confirmed_finance_image_enters_voucher_library_and_review_queue(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "PROJECT_DATA_DIR", tmp_path)
    monkeypatch.setattr(project_model, "PROJECT_DATA_DIR", tmp_path)
    monkeypatch.setattr(capture_route, "PROJECT_DATA_DIR", tmp_path)
    memory = ProjectMemory.create(PROJECT_ID)
    memory.update_profile({"store_name": "测试门店", "transfer_date": "2026-07-01"})
    capture_dir = tmp_path / PROJECT_ID / "captures"
    capture_dir.mkdir(parents=True)
    capture_dir.joinpath("bank-proof.png").write_bytes(b"not-a-real-image-but-an-immutable-test-voucher")

    response = TestClient(app).post(
        f"/api/capture/confirm/{PROJECT_ID}",
        json={
            "file_name": "工商银行转账截图.png",
            "image_url": f"/api/capture/captures/{PROJECT_ID}/bank-proof.png",
            "source_type": "银行转账凭证",
            "capture_kind": "document",
            "recognized_fields": [
                {"key": "date", "value": "2026-07-17"},
                {"key": "amount", "value": 268},
                {"key": "transaction_direction", "value": "outflow"},
                {"key": "counterparty", "value": "菜市场"},
            ],
            "write_target": "凭证库 + 待确认记账",
            "date": "2026-07-17",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["voucher_id"]
    assert len(payload["pending_bookkeeping_record_ids"]) == 1
    ledger = FinanceLedger.for_project(PROJECT_ID)
    assert ledger.list_evidence_vouchers(PROJECT_ID, "2026-07-17", "2026-07-17")[0]["original_path"] == "captures/bank-proof.png"
    pending = ledger.get_bookkeeping_record(PROJECT_ID, payload["pending_bookkeeping_record_ids"][0])
    assert pending["status"] == "needs_review"
    assert pending["transaction_kind"] == "inventory_purchase"
