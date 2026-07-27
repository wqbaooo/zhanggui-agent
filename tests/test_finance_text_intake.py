from fastapi.testclient import TestClient

import config
import models.project as project_model
from core.finance_text_intake import parse_finance_text
from models.finance_ledger import FinanceLedger
from server.main import app


PROJECT_ID = "finance-text-store"


def test_personal_purchase_sentence_prefills_every_known_field_and_only_asks_for_date():
    result = parse_finance_text(
        "买袜子花了38.98 是在淘宝买的 用的招商银行卡",
        today="2026-07-23",
        accounts=[
            {
                "account_key": "cmb-personal",
                "name": "招商银行个人账户",
                "institution": "招商银行",
                "owner_kind": "owner",
                "status": "active",
            },
            {
                "account_key": "store-icbc",
                "name": "工商银行店铺账户",
                "institution": "工商银行",
                "owner_kind": "store",
                "status": "active",
            },
        ],
    )

    assert result["schema_version"] == "finance_text_parse_v1"
    assert result["fields"] == {
        "fact_type": "personal_spending",
        "business_date": None,
        "amount": 38.98,
        "account_key": "cmb-personal",
        "counterparty": "淘宝",
        "category_code": None,
        "category_name": "个人账户消费",
        "business_category_key": "personal_spending_personal_account",
        "source_basis": "自然语言自动识别",
        "notes": "购买袜子",
    }
    assert result["business_scope"] == "personal"
    assert result["profit_treatment"] == "excluded_personal"
    assert result["missing_fields"] == ["business_date"]
    assert result["can_confirm"] is False


def test_relative_date_and_store_expense_are_resolved_without_posting():
    result = parse_finance_text(
        "昨天用工商卡付了店铺水费128元",
        today="2026-07-23",
        accounts=[{
            "account_key": "store-icbc",
            "name": "工商银行店铺账户",
            "institution": "工商银行",
            "owner_kind": "store",
            "status": "active",
        }],
    )

    assert result["fields"]["fact_type"] == "operating_expense"
    assert result["fields"]["business_date"] == "2026-07-22"
    assert result["fields"]["amount"] == 128
    assert result["fields"]["account_key"] == "store-icbc"
    assert result["fields"]["category_code"] == "6003"
    assert result["fields"]["category_name"] == "水电燃气"
    assert result["fields"]["business_category_key"] == "utilities"
    assert result["business_scope"] == "store"
    assert result["can_confirm"] is True


def test_electricity_top_up_is_an_expense_even_when_paid_by_bank_card():
    result = parse_finance_text(
        "7月20日电网充值花了22.05元，用工商银行卡充值缴费",
        today="2026-07-23",
        accounts=[{
            "account_key": "store-icbc",
            "name": "工商银行店铺账户",
            "institution": "工商银行",
            "owner_kind": "store",
            "status": "active",
        }],
    )

    assert result["fields"]["fact_type"] == "operating_expense"
    assert result["fields"]["business_date"] == "2026-07-20"
    assert result["fields"]["amount"] == 22.05
    assert result["fields"]["account_key"] == "store-icbc"
    assert result["fields"]["counterparty"] is None
    assert result["fields"]["category_code"] == "6003"
    assert result["fields"]["category_name"] == "水电燃气"
    assert result["fields"]["business_category_key"] == "utilities"
    assert result["fields"]["notes"] == "店铺电费"
    assert result["business_scope"] == "store"
    assert result["can_confirm"] is True


def test_ambiguous_sentence_stays_unconfirmed_instead_of_inventing_money_facts():
    result = parse_finance_text(
        "随便记一下以后再说",
        today="2026-07-23",
        accounts=[],
    )

    assert result["fields"]["fact_type"] is None
    assert result["fields"]["amount"] is None
    assert result["fields"]["business_date"] is None
    assert result["fields"]["account_key"] is None
    assert result["can_confirm"] is False
    assert result["missing_fields"] == ["fact_type", "business_date", "amount", "account_key"]


def test_former_owner_transfer_defaults_to_confirmed_store_icbc_not_personal_card():
    result = parse_finance_text(
        "今天前老板转给我2918.76元",
        today="2026-07-26",
        accounts=[
            {
                "account_key": "cmb-personal",
                "name": "招商银行个人账户",
                "institution": "招商银行",
                "owner_kind": "owner",
                "status": "active",
            },
            {
                "account_key": "planned-store-icbc",
                "name": "工商银行店铺账户",
                "institution": "工商银行",
                "owner_kind": "store",
                "status": "active",
            },
        ],
    )

    assert result["fields"]["fact_type"] == "former_owner_transfer"
    assert result["fields"]["account_key"] == "planned-store-icbc"
    assert result["account_name"] == "工商银行店铺账户"
    assert "account_key" not in result["missing_fields"]


def test_text_parse_api_returns_prefill_but_does_not_create_a_plan_or_bookkeeping(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "PROJECT_DATA_DIR", tmp_path)
    monkeypatch.setattr(project_model, "PROJECT_DATA_DIR", tmp_path)
    ledger = FinanceLedger.for_project(PROJECT_ID)
    ledger.ensure_store(PROJECT_ID, "测试门店", "2026-07-01")
    ledger.upsert_fund_account(
        PROJECT_ID,
        account_key="cmb-personal",
        name="招商银行个人账户",
        account_kind="bank",
        owner_kind="owner",
        is_store_controlled=False,
        institution="招商银行",
    )

    response = TestClient(app).post(
        f"/api/projects/{PROJECT_ID}/finance/intake/parse-text",
        json={"text": "今天在淘宝买袜子花了38.98元，用招商银行卡"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["fields"]["business_date"]
    assert body["fields"]["account_key"] == "cmb-personal"
    assert body["fields"]["amount"] == 38.98
    assert ledger.list_execution_plans(PROJECT_ID) == []
    assert ledger.list_bookkeeping_records(PROJECT_ID) == []
