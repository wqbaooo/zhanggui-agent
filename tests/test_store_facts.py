from models.store_facts import StoreFactBook
from fastapi.testclient import TestClient
from server.main import app


PROJECT_ID = "xinyu-hengtai-dakou"


def test_supplier_invoices_separate_direct_use_inventory_and_payable():
    book = StoreFactBook.load(PROJECT_ID)
    summary = book.finance_summary()

    assert summary["local_supplier_payable_minor"] == 28010
    assert summary["direct_use_food_cost_minor"] == 6410
    assert summary["inventory_purchase_minor"] == 21600
    assert summary["supplier_invoice_count"] == 7


def test_verified_cash_and_former_owner_transfer_are_explicit_facts():
    book = StoreFactBook.load(PROJECT_ID)
    summary = book.finance_summary()

    assert summary["latest_cash_count"] == {"date": "2026-07-12", "amount_minor": 4700}
    assert summary["former_owner_transfer_minor"] == 257080
    assert summary["former_owner_transfer_direction"] == "former_owner_to_current_owner"
    assert summary["hq_payments"] == [
        {"date": "2026-07-03", "amount_minor": 400000},
        {"date": "2026-07-04", "amount_minor": 499900},
        {"date": "2026-07-05", "amount_minor": 479200},
    ]


def test_product_sales_keep_gross_sales_separate_from_recognized_revenue():
    book = StoreFactBook.load(PROJECT_ID)
    sales = book.product_sales_summary()

    assert sales["period"] == {"start": "2026-07-01", "end": "2026-07-12"}
    assert sales["total_quantity"] == 989
    assert sales["gross_sales_minor"] == 1815061
    assert sales["recognized_revenue_minor"] == 1477148
    assert sales["visible_ranked_quantity"] == 875
    assert sales["visible_ranked_amount_minor"] == 1503389


def test_product_mapping_estimates_packaging_only_when_spec_is_supported():
    book = StoreFactBook.load(PROJECT_ID)
    estimate = book.packaging_estimate()

    assert estimate["standard_six_box"] == 656
    assert estimate["family_nine_box"] == 83
    assert estimate["four_piece_box"] == 74
    assert estimate["large_three_box"] == 41
    assert estimate["unmapped_quantity"] == 45
    assert estimate["rule"] == "official_name_or_cross_platform_official_consensus"


def test_daily_usage_policy_records_actual_open_or_issue_quantity():
    book = StoreFactBook.load(PROJECT_ID)
    assert book.inventory_policy["tracking_rule"] == "daily_open_or_issue_quantity"
    assert book.inventory_policy["default_open_quantity"] == 1


def test_operating_facts_api_exposes_linked_finance_product_and_form_contracts():
    response = TestClient(app).get(f"/api/projects/{PROJECT_ID}/finance/operating-facts")
    assert response.status_code == 200
    payload = response.json()
    assert payload["finance"]["local_supplier_payable_minor"] == 28010
    assert payload["packaging_estimate"]["standard_six_box"] == 656
    assert {item["id"] for item in payload["operational_forms"]} >= {
        "daily-material-usage", "period-stocktake", "purchase-ledger"
    }
