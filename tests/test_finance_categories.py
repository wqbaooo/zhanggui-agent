from pathlib import Path

from fastapi.testclient import TestClient

import config
import models.project as project_model
from models.finance_ledger import FinanceLedger
from server.main import app


PROJECT_ID = "finance-category-store"


def _client(tmp_path: Path, monkeypatch) -> TestClient:
    monkeypatch.setattr(config, "PROJECT_DATA_DIR", tmp_path)
    monkeypatch.setattr(project_model, "PROJECT_DATA_DIR", tmp_path)
    ledger = FinanceLedger.for_project(PROJECT_ID)
    ledger.ensure_store(PROJECT_ID, "分类测试店", "2026-07-01")
    ledger.upsert_fund_account(
        PROJECT_ID,
        account_key="store-icbc",
        name="工商银行店铺账户",
        account_kind="bank",
        owner_kind="store",
        is_store_controlled=True,
        institution="工商银行",
    )
    return TestClient(app)


def test_finance_category_contract_has_seven_stable_business_groups(tmp_path, monkeypatch):
    response = _client(tmp_path, monkeypatch).get(
        f"/api/projects/{PROJECT_ID}/finance/categories"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "finance_category_catalog_v1"
    assert [group["name"] for group in payload["groups"]] == [
        "营业收入与调整",
        "进货与库存",
        "经营费用",
        "接店与长期投入",
        "借款与融资",
        "老板往来",
        "资金调拨与结算",
    ]
    keys = {item["key"] for group in payload["groups"] for item in group["items"]}
    assert {"food_purchase", "former_owner_transfer", "personal_spending_from_store"} <= keys


def test_selected_business_category_is_authoritative_and_persisted(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    response = client.post(
        f"/api/projects/{PROJECT_ID}/finance/bookkeeping",
        json={
            "transaction_date": "2026-07-23",
            "direction": "inflow",
            "amount": 128,
            "transaction_kind": "wrong_kind",
            "business_scope": "personal",
            "category_code": None,
            "category_name": "随手输入的错误分类",
            "business_category_key": "utilities",
            "account_key": "store-icbc",
            "summary": "店铺水费",
            "source_reference": "category-contract-001",
        },
    )

    assert response.status_code == 200
    row = response.json()["record"]
    assert row["direction"] == "outflow"
    assert row["transaction_kind"] == "operating_expense"
    assert row["business_scope"] == "store"
    assert row["category_code"] == "6003"
    assert row["category_name"] == "水电燃气"
    assert row["business_category_key"] == "utilities"
    assert row["business_category_group"] == "经营费用"


def test_daily_close_defaults_to_store_five_hundred_yuan_cash_reserve(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    response = client.post(
        f"/api/projects/{PROJECT_ID}/finance/daily-close/2026-07-23",
        json={"counted_cash": 500},
    )

    assert response.status_code == 200
    assert response.json()["inputs"]["reserve_cash_minor"] == 50_000


def test_evidence_image_opens_inline_instead_of_forcing_download(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    evidence_dir = tmp_path / PROJECT_ID / "documents" / "evidence"
    evidence_dir.mkdir(parents=True)
    image = evidence_dir / "receipt.png"
    image.write_bytes(b"\x89PNG\r\n\x1a\nfixture")
    ledger = FinanceLedger.for_project(PROJECT_ID)
    voucher_id = ledger.register_evidence_voucher(
        PROJECT_ID,
        voucher_key="inline-receipt",
        business_date="2026-07-23",
        evidence_type="bank_receipt_screenshot",
        original_filename="银行回单.png",
        original_path="documents/evidence/receipt.png",
        sha256="fixture-sha256",
        status="confirmed",
    )

    response = client.get(
        f"/api/projects/{PROJECT_ID}/finance/evidence-vouchers/{voucher_id}/file"
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/png")
    assert response.headers["content-disposition"].startswith("inline;")


def test_finance_agent_separates_unsettled_money_from_actual_bank_balance(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    ledger = FinanceLedger.for_project(PROJECT_ID)
    ledger.record_merchant_net_sale(
        PROJECT_ID,
        business_date="2026-07-23",
        channel="美团外卖",
        amount_minor=12_345,
        source_basis="测试平台结算单",
        evidence_status="confirmed",
        settlement_state="wallet_credited",
    )

    response = client.post(
        f"/api/projects/{PROJECT_ID}/finance/query",
        json={"query": "哪些钱还没到店铺账户？", "start": "2026-07-23", "end": "2026-07-23"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["completeness"] == "partial"
    assert "平台待结算 123.45元" in body["answer"]
    assert "不会把累计到账金额冒充银行卡实际余额" in body["answer"]
    assert {item["metric_code"] for item in body["metrics"]} >= {
        "platform_unsettled", "former_owner_receivable", "store_controlled_funds",
    }
