import io
import json
import zipfile
from pathlib import Path

from fastapi.testclient import TestClient

import config
from models.finance_ledger import FinanceLedger
from server.main import app


PROJECT_ID = "xinyu-hengtai-dakou"
SOURCE_MEMORY = Path(__file__).parents[1] / "project_data" / PROJECT_ID / "memory.json"


def seeded_client(tmp_path, monkeypatch):
    project_dir = tmp_path / PROJECT_ID
    project_dir.mkdir(parents=True)
    project_dir.joinpath("memory.json").write_text(SOURCE_MEMORY.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setattr(config, "PROJECT_DATA_DIR", tmp_path)
    return TestClient(app)


def test_finance_overview_uses_sqlite_ledger_and_dynamic_period(tmp_path, monkeypatch):
    client = seeded_client(tmp_path, monkeypatch)
    response = client.get(f"/api/projects/{PROJECT_ID}/finance/overview")
    assert response.status_code == 200
    data = response.json()
    assert data["period_start"] == "2026-07-01"
    assert data["period_end"] == data["calendar_today"]
    assert data["last_data_date"] == "2026-07-12"
    missing_days = [row["business_date"] for row in data["daily_revenue"] if row["status"] == "missing"]
    assert "2026-07-13" in missing_days
    assert data["revenue_minor"] == 1477148
    assert data["orders"] == 960
    assert data["average_order_value_minor"] == 1539
    assert data["order_coverage_status"] == "complete"
    assert data["order_covered_revenue_minor"] == data["revenue_minor"]
    assert data["profit_status"] == "incomplete"
    assert data["net_profit_minor"] is None
    assert data["funds_minor"]["former_owner_receivable"] > 0
    assert data["funds_minor"]["unclassified_receipts"] > 0
    assert {item["amount_minor"] for item in data["pending_capital_items"]} == {4000000, 1379100}


def test_average_order_value_uses_only_revenue_with_order_coverage(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "PROJECT_DATA_DIR", tmp_path)
    store_id = "order-coverage-store"
    ledger = FinanceLedger.for_project(store_id)
    ledger.ensure_store(store_id, "test", "2026-07-01")
    ledger.record_confirmed_daily_revenue(store_id, {
        "date": "2026-07-01",
        "revenue": 100,
        "orders": 2,
        "payment_methods": [{"method": "微信", "amount": 100, "orders": 2}],
    })
    ledger.post_entry(
        store_id=store_id,
        entry_date="2026-07-02",
        posting_key="migration-alignment-test",
        description="累计迁移差额",
        lines=[("1019", 30000, 0), ("4009", 0, 30000)],
    )

    overview = ledger.finance_overview(store_id, "2026-07-01", "2026-07-02")

    assert overview["revenue_minor"] == 40_000
    assert overview["orders"] == 2
    assert overview["order_covered_revenue_minor"] == 10_000
    assert overview["order_coverage_status"] == "partial"
    assert overview["average_order_value_minor"] == 5_000


def test_daily_close_requires_nightly_reviews_not_daily_profit_estimates(tmp_path, monkeypatch):
    client = seeded_client(tmp_path, monkeypatch)
    partial = client.post(
        f"/api/projects/{PROJECT_ID}/finance/daily-close/2026-07-01",
        json={"counted_cash": 110, "reserve_cash": 100},
    )
    assert partial.status_code == 200
    assert partial.json()["status"] == "awaiting_inputs"
    assert set(partial.json()["missing_inputs"]) == {
        "merchant_net_review", "fund_location_review", "outflow_review",
    }

    closed = client.post(
        f"/api/projects/{PROJECT_ID}/finance/daily-close/2026-07-01",
        json={
            "counted_cash": 110,
            "reserve_cash": 100,
            "merchant_net_confirmed": True,
            "fund_locations_reviewed": True,
            "outflows_reviewed": True,
        },
    )
    assert closed.status_code == 200
    assert closed.json()["status"] == "closed"


def test_confirming_former_owner_bank_receipt_clears_receivable_without_new_income(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "PROJECT_DATA_DIR", tmp_path)
    client = TestClient(app)
    ledger = FinanceLedger.for_project(PROJECT_ID)
    ledger.ensure_store(PROJECT_ID, "test", "2026-07-01")
    ledger.post_entry(
        store_id=PROJECT_ID, entry_date="2026-07-01", posting_key="former-owner-sale",
        description="线上平台由前老板代收", lines=[("1013", 10000, 0), ("4002", 0, 10000)],
    )
    revenue_before = ledger.revenue_total(PROJECT_ID, "2026-07-01", "2026-07-03")
    balances_before = ledger.account_balances(PROJECT_ID, "2026-07-01", "2026-07-03")

    response = client.post(f"/api/projects/{PROJECT_ID}/finance/settlements/confirm", json={
        "date": "2026-07-03", "amount": 100, "reference": "bank-image-001", "source": "former_owner",
    })
    assert response.status_code == 200
    assert response.json()["revenue_impact_minor"] == 0
    assert ledger.revenue_total(PROJECT_ID, "2026-07-01", "2026-07-03") == revenue_before
    balances = ledger.account_balances(PROJECT_ID, "2026-07-01", "2026-07-03")
    assert balances["1013"] == balances_before["1013"] - 10000
    assert balances["1002"] == balances_before["1002"] + 10000


def test_daily_close_posts_confirmed_costs_and_cash_difference(tmp_path, monkeypatch):
    client = seeded_client(tmp_path, monkeypatch)
    response = client.post(
        f"/api/projects/{PROJECT_ID}/finance/daily-close/2026-07-01",
        json={
            "counted_cash": 110,
            "reserve_cash": 100,
            "food_cost": 365.35,
            "packaging_cost": 37.2,
            "overtime_hours": 0,
            "rent": 0,
            "utility": 20,
            "other_cost": 1,
        },
    )
    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "closed"
    assert result["deposit_due_minor"] == 1000
    assert result["cash_difference_minor"] == 0

    overview = client.get(f"/api/projects/{PROJECT_ID}/finance/overview").json()
    assert overview["closed_days"] == 1
    assert overview["profit_status"] == "incomplete"
    assert overview["costs_minor"]["food_cost"] == 36535
    assert overview["costs_minor"]["labor"] == 16774


def test_expense_is_idempotent_and_alerts_are_evidence_backed(tmp_path, monkeypatch):
    client = seeded_client(tmp_path, monkeypatch)
    payload = {"date": "2026-07-06", "category_code": "6005", "amount": 30, "reference": "garbage-july", "description": "垃圾费"}
    assert client.post(f"/api/projects/{PROJECT_ID}/finance/expenses", json=payload).status_code == 200
    assert client.post(f"/api/projects/{PROJECT_ID}/finance/expenses", json=payload).status_code == 200
    overview = client.get(f"/api/projects/{PROJECT_ID}/finance/overview").json()
    assert overview["costs_minor"]["other"] == 3000
    alerts = client.get(f"/api/projects/{PROJECT_ID}/finance/alerts").json()["alerts"]
    assert {item["code"] for item in alerts} >= {"BOOKS_INCOMPLETE", "FORMER_OWNER_RECEIVABLE", "UNCLASSIFIED_RECEIPTS"}


def test_finance_export_is_real_xlsx(tmp_path, monkeypatch):
    client = seeded_client(tmp_path, monkeypatch)
    response = client.get(f"/api/projects/{PROJECT_ID}/finance/export.xlsx")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    assert response.content[:2] == b"PK"
    assert len(response.content) > 2000
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        workbook_xml = archive.read("xl/workbook.xml").decode("utf-8")
        styles_xml = archive.read("xl/styles.xml").decode("utf-8")
        dashboard_xml = archive.read("xl/worksheets/sheet1.xml").decode("utf-8")
        daily_xml = archive.read("xl/worksheets/sheet2.xml").decode("utf-8")
        plan_xml = archive.read("xl/worksheets/sheet4.xml").decode("utf-8")
        vouchers_xml = archive.read("xl/worksheets/sheet7.xml").decode("utf-8")
        profit_xml = archive.read("xl/worksheets/sheet8.xml").decode("utf-8")
        unified_xml = archive.read("xl/worksheets/sheet3.xml").decode("utf-8")
        category_xml = archive.read("xl/worksheets/sheet10.xml").decode("utf-8")
    assert all(name in workbook_xml for name in (
        "财务驾驶舱", "每日经营结账", "统一资金流水账", "未来资金计划",
        "账户与对账", "借款与接店成本", "凭证索引", "利润与现金流", "检查与口径",
        "分类字典",
    ))
    assert "FF173B57" in styles_xml and "FFEA4F11" in styles_xml
    assert '<mergeCell ref="A1:' in dashboard_xml
    assert "实际到手不是利润" in dashboard_xml
    assert "<f>SUM(" in daily_xml
    assert "<dataValidations" in plan_xml and "<conditionalFormatting" in plan_xml
    assert "SHA-256" in vouchers_xml
    assert "不可确认" in profit_xml
    assert all(label in unified_xml for label in ("事实日期", "大类", "具体类别", "业务归属", "损益处理"))
    assert all(label in category_xml for label in ("营业收入与调整", "进货与库存", "老板往来", "资金调拨与结算"))


def test_finance_intake_keeps_platform_net_sales_separate_from_later_bank_receipt(tmp_path, monkeypatch):
    client = seeded_client(tmp_path, monkeypatch)
    baseline_merchant_net = client.get(f"/api/projects/{PROJECT_ID}/finance/overview").json()["merchant_net_minor"]
    created = client.post(f"/api/projects/{PROJECT_ID}/finance/fund-accounts", json={
        "account_key": "icbc-9863", "name": "工商银行尾号9863", "account_kind": "bank",
        "owner_kind": "store", "is_store_controlled": True, "institution": "工商银行",
        "masked_number": "9863", "effective_from": "2026-07-03", "status": "active",
    })
    assert created.status_code == 200
    store_account = {"account_key": "icbc-9863"}

    sale = client.post(
        f"/api/projects/{PROJECT_ID}/finance/intake",
        data={
            "fact_type": "merchant_net_sale",
            "business_date": "2026-07-16",
            "amount": "300",
            "channel": "美团外卖",
            "settlement_state": "wallet_credited",
            "current_account_key": store_account["account_key"],
            "source_basis": "美团钱包余额截图",
        },
        files={"file": ("meituan-wallet.png", b"real-evidence-bytes", "image/png")},
    )
    assert sale.status_code == 200
    sale_data = sale.json()
    assert sale_data["plan"]["normalized_fact"]["amount_minor"] == 30000
    assert sale_data["plan"]["status"] == "awaiting_confirmation"
    assert sale_data["voucher"]["status"] == "pending"
    confirmed_sale = client.post(
        f"/api/projects/{PROJECT_ID}/finance/execution-plans/{sale_data['plan']['plan_id']}/confirm",
        json={"confirmed": True, "confirmed_by": "owner"},
    )
    assert confirmed_sale.status_code == 200
    assert client.get(f"/api/projects/{PROJECT_ID}/finance/overview").json()["last_data_date"] == "2026-07-16"

    receipt = client.post(
        f"/api/projects/{PROJECT_ID}/finance/intake",
        data={
            "fact_type": "platform_settlement",
            "business_date": "2026-07-17",
            "amount": "300",
            "account_key": store_account["account_key"],
            "counterparty": "美团",
            "source_basis": "工商银行到账截图",
        },
        files={"file": ("icbc-receipt.png", b"bank-receipt-bytes", "image/png")},
    )
    assert receipt.status_code == 200
    assert receipt.json()["plan"]["event_type"] == "platform_settlement"
    assert receipt.json()["plan"]["status"] == "awaiting_confirmation"

    overview = client.get(f"/api/projects/{PROJECT_ID}/finance/overview").json()
    assert overview["merchant_net_minor"] == baseline_merchant_net + 30000


def test_capital_debt_and_targets_are_not_treated_as_revenue(tmp_path, monkeypatch):
    client = seeded_client(tmp_path, monkeypatch)
    revenue_before = client.get(f"/api/projects/{PROJECT_ID}/finance/overview").json()["revenue_minor"]

    investment = client.post(f"/api/projects/{PROJECT_ID}/finance/capital-events", json={
        "date": "2026-07-01", "event_type": "owner_investment", "amount": 40000,
        "reference": "initial-owner-investment",
    })
    loan = client.post(f"/api/projects/{PROJECT_ID}/finance/capital-events", json={
        "date": "2026-07-02", "event_type": "loan_in", "amount": 10000,
        "reference": "test-loan",
    })
    target = client.post(f"/api/projects/{PROJECT_ID}/finance/targets", json={
        "target_type": "monthly_profit", "period_start": "2026-07-01",
        "period_end": "2026-07-31", "amount": 8000,
    })
    assert investment.status_code == loan.status_code == target.status_code == 200

    overview = client.get(f"/api/projects/{PROJECT_ID}/finance/overview").json()
    assert overview["revenue_minor"] == revenue_before
    assert overview["owner_equity_minor"]["invested"] == 4000000
    assert overview["liabilities_minor"]["loans"] == 1000000
    assert overview["cash_flow_minor"]["financing"] == 5000000
    assert overview["targets"][0]["amount_minor"] == 800000
    assert overview["debt_summary"]["outstanding_minor"] == 1000000


def test_closed_day_requires_reopen_and_posts_only_cost_adjustment(tmp_path, monkeypatch):
    client = seeded_client(tmp_path, monkeypatch)
    original = {
        "counted_cash": 110, "reserve_cash": 100, "food_cost": 300,
        "packaging_cost": 30, "overtime_hours": 0, "rent": 0, "utility": 20, "other_cost": 0,
    }
    adjusted = {**original, "food_cost": 320}
    first = client.post(f"/api/projects/{PROJECT_ID}/finance/daily-close/2026-07-01", json=original)
    assert first.json()["status"] == "closed"

    ignored = client.post(f"/api/projects/{PROJECT_ID}/finance/daily-close/2026-07-01", json=adjusted)
    assert ignored.json()["status"] == "closed"
    assert client.get(f"/api/projects/{PROJECT_ID}/finance/overview").json()["costs_minor"]["food_cost"] == 30000

    reopened = client.post(
        f"/api/projects/{PROJECT_ID}/finance/daily-close/2026-07-01/reopen",
        json={"reason": "盘点后更正食材耗用"},
    )
    assert reopened.status_code == 200
    assert reopened.json()["status"] == "reopened"
    reclosed = client.post(f"/api/projects/{PROJECT_ID}/finance/daily-close/2026-07-01", json=adjusted)
    assert reclosed.json()["status"] == "closed"
    assert client.get(f"/api/projects/{PROJECT_ID}/finance/overview").json()["costs_minor"]["food_cost"] == 32000
