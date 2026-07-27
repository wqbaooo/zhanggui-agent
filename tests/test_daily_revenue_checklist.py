from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import config
import models.project as project_model
from models.finance_ledger import FinanceLedger, FinanceMigrationError
from server.main import app


PROJECT_ID = "daily-revenue-checklist-store"


def _ledger(tmp_path: Path, monkeypatch) -> FinanceLedger:
    monkeypatch.setattr(config, "PROJECT_DATA_DIR", tmp_path)
    monkeypatch.setattr(project_model, "PROJECT_DATA_DIR", tmp_path)
    ledger = FinanceLedger.for_project(PROJECT_ID)
    ledger.ensure_store(PROJECT_ID, "每日营业测试店", "2026-07-01")
    ledger.upsert_fund_account(
        PROJECT_ID,
        account_key="cash-on-hand",
        name="店内现金",
        account_kind="cash",
        owner_kind="store",
        is_store_controlled=True,
        effective_from="2026-07-01",
    )
    ledger.upsert_fund_account(
        PROJECT_ID,
        account_key="former-owner-icbc-9863",
        name="前老板工商银行9863",
        account_kind="bank",
        owner_kind="former_owner",
        is_store_controlled=False,
        effective_from="2026-07-01",
    )
    ledger.upsert_fund_account(
        PROJECT_ID,
        account_key="planned-store-icbc",
        name="工商银行店铺账户",
        account_kind="bank",
        owner_kind="store",
        is_store_controlled=True,
        effective_from="2026-07-01",
    )
    ledger.upsert_platform_collection_binding(
        PROJECT_ID,
        platform="美团外卖",
        collector_account_key="former-owner-icbc-9863",
        destination_account_key="planned-store-icbc",
        collector_owner_kind="former_owner",
        settlement_rule="T+3个工作日进入平台钱包，随后到平台绑定卡",
        settlement_delay_days=3,
        settlement_day_basis="working_day",
        settlement_rule_status="confirmed",
        effective_from="2026-07-01",
    )
    ledger.upsert_platform_collection_binding(
        PROJECT_ID,
        platform="淘宝闪购",
        collector_account_key="former-owner-icbc-9863",
        destination_account_key="planned-store-icbc",
        collector_owner_kind="former_owner",
        settlement_rule="T+3个自然日结算到平台钱包，随后自动提现到平台绑定卡",
        settlement_delay_days=3,
        settlement_day_basis="calendar_day",
        settlement_rule_status="confirmed",
        settlement_delay_target="platform_wallet",
        withdrawal_mode="automatic",
        effective_from="2026-07-01",
    )
    ledger.upsert_platform_collection_binding(
        PROJECT_ID,
        platform="美团团购",
        collector_account_key="former-owner-icbc-9863",
        destination_account_key="planned-store-icbc",
        collector_owner_kind="former_owner",
        settlement_rule="T+1个自然日结算到平台钱包，需手动提现",
        settlement_delay_days=1,
        settlement_day_basis="calendar_day",
        settlement_rule_status="confirmed",
        settlement_delay_target="platform_wallet",
        withdrawal_mode="manual",
        effective_from="2026-07-01",
    )
    return ledger


def test_checklist_exposes_all_fixed_channels_and_missing_rows(tmp_path, monkeypatch):
    ledger = _ledger(tmp_path, monkeypatch)
    ledger.record_merchant_net_sale(
        PROJECT_ID,
        business_date="2026-07-19",
        channel="美团外卖",
        amount_minor=12_064,
        source_basis="平台日报",
        evidence_status="confirmed",
        settlement_state="merchant_net_confirmed",
    )

    result = ledger.daily_revenue_checklist(PROJECT_ID, "2026-07-19", "2026-07-19")

    assert [item["channel"] for item in result["channels"]] == [
        "客如云收款", "现金", "美团外卖", "淘宝闪购", "美团团购", "抖音团购", "京东外卖",
    ]
    day = result["days"][0]
    assert day["total_count"] == 7
    assert day["completed_count"] == 1
    assert day["missing_count"] == 6
    by_channel = {item["channel"]: item for item in day["channels"]}
    assert by_channel["美团外卖"]["status"] == "recorded"
    assert by_channel["美团外卖"]["amount_minor"] == 12_064
    assert by_channel["客如云收款"]["status"] == "missing"
    assert "平台绑定卡" in by_channel["美团外卖"]["expected_fund_path"]
    assert by_channel["美团外卖"]["expected_bank_date"] == "2026-07-22"


def test_daily_sales_do_not_claim_former_owner_or_bank_arrival(tmp_path, monkeypatch):
    ledger = _ledger(tmp_path, monkeypatch)

    result = ledger.save_daily_revenue_entries(
        PROJECT_ID,
        "2026-07-20",
        [{"channel": "美团外卖", "status": "recorded", "amount_minor": 9_384}],
    )

    assert result["saved_count"] == 1
    sale = ledger.merchant_net_sales(PROJECT_ID, "2026-07-20", "2026-07-20")[0]
    assert sale["merchant_net_minor"] == 9_384
    assert sale["settlement_state"] == "merchant_net_confirmed"
    assert sale["current_fund_account_id"] is None
    assert ledger.list_fund_movements(PROJECT_ID, "2026-07-20", "2026-07-20") == []
    assert ledger.revenue_total(PROJECT_ID, "2026-07-20", "2026-07-20") == 0


def test_zero_and_not_available_are_distinct_and_later_data_can_complete(tmp_path, monkeypatch):
    ledger = _ledger(tmp_path, monkeypatch)
    ledger.save_daily_revenue_entries(
        PROJECT_ID,
        "2026-07-21",
        [
            {"channel": "现金", "status": "confirmed_zero", "amount_minor": 0},
            {"channel": "京东外卖", "status": "not_available", "amount_minor": None},
        ],
    )

    first = ledger.daily_revenue_checklist(PROJECT_ID, "2026-07-21", "2026-07-21")["days"][0]
    rows = {item["channel"]: item for item in first["channels"]}
    assert rows["现金"]["status"] == "confirmed_zero"
    assert rows["京东外卖"]["status"] == "not_available"
    assert first["completed_count"] == 1
    assert first["not_available_count"] == 1
    assert first["missing_count"] == 5

    ledger.save_daily_revenue_entries(
        PROJECT_ID,
        "2026-07-21",
        [{"channel": "京东外卖", "status": "recorded", "amount_minor": 8_888}],
    )
    second = ledger.daily_revenue_checklist(PROJECT_ID, "2026-07-21", "2026-07-21")["days"][0]
    rows = {item["channel"]: item for item in second["channels"]}
    assert rows["京东外卖"]["status"] == "recorded"
    assert second["not_available_count"] == 0
    assert second["completed_count"] == 2


def test_cannot_hide_an_existing_sale_as_not_available(tmp_path, monkeypatch):
    ledger = _ledger(tmp_path, monkeypatch)
    ledger.save_daily_revenue_entries(
        PROJECT_ID,
        "2026-07-22",
        [{"channel": "抖音团购", "status": "recorded", "amount_minor": 2_000}],
    )

    with pytest.raises(FinanceMigrationError, match="已有营业金额"):
        ledger.save_daily_revenue_entries(
            PROJECT_ID,
            "2026-07-22",
            [{"channel": "抖音团购", "status": "not_available", "amount_minor": None}],
        )


def test_daily_revenue_checklist_api_saves_once_and_returns_completion(tmp_path, monkeypatch):
    _ledger(tmp_path, monkeypatch)
    client = TestClient(app)

    saved = client.post(
        f"/api/projects/{PROJECT_ID}/finance/daily-revenue/2026-07-23",
        json={
            "items": [
                {"channel": "客如云收款", "status": "recorded", "amount": 1053.99},
                {"channel": "现金", "status": "confirmed_zero", "amount": 0},
                {"channel": "美团外卖", "status": "not_available"},
            ]
        },
    )
    loaded = client.get(
        f"/api/projects/{PROJECT_ID}/finance/daily-revenue-checklist",
        params={"start": "2026-07-23", "end": "2026-07-23"},
    )

    assert saved.status_code == 200
    assert loaded.status_code == 200
    day = loaded.json()["days"][0]
    assert day["completed_count"] == 2
    assert day["not_available_count"] == 1
    assert day["missing_count"] == 4
    assert saved.json()["revenue_impact_from_settlement_minor"] == 0


def test_weekly_transfer_exactly_matches_expected_platform_arrivals(tmp_path, monkeypatch):
    ledger = _ledger(tmp_path, monkeypatch)
    for business_date, amount_minor in [("2026-07-13", 10_000), ("2026-07-14", 20_000)]:
        ledger.save_daily_revenue_entries(
            PROJECT_ID,
            business_date,
            [{"channel": "美团外卖", "status": "recorded", "amount_minor": amount_minor}],
        )

    result = ledger.match_platform_bound_card_transfer(
        PROJECT_ID,
        transfer_date="2026-07-20",
        amount_minor=30_000,
        arrival_period_start="2026-07-16",
        arrival_period_end="2026-07-17",
        source_reference="weekly-transfer-20260720",
    )

    assert result["status"] == "matched"
    assert result["matched_minor"] == 30_000
    assert result["difference_minor"] == 0
    assert result["revenue_impact_minor"] == 0
    assert len(result["allocations"]) == 2
    sales = ledger.merchant_net_sales(PROJECT_ID, "2026-07-13", "2026-07-14")
    assert {row["settlement_state"] for row in sales} == {"store_account_received"}
    movements = ledger.list_fund_movements(PROJECT_ID, "2026-07-20", "2026-07-20")
    assert len(movements) == 1
    assert movements[0]["from_account_name"] == "前老板工商银行9863"
    assert movements[0]["to_account_name"] == "工商银行店铺账户"


def test_weekly_transfer_mismatch_is_not_posted_or_marked_arrived(tmp_path, monkeypatch):
    ledger = _ledger(tmp_path, monkeypatch)
    ledger.save_daily_revenue_entries(
        PROJECT_ID,
        "2026-07-13",
        [{"channel": "美团外卖", "status": "recorded", "amount_minor": 10_000}],
    )

    result = ledger.match_platform_bound_card_transfer(
        PROJECT_ID,
        transfer_date="2026-07-20",
        amount_minor=9_999,
        arrival_period_start="2026-07-16",
        arrival_period_end="2026-07-16",
        source_reference="weekly-transfer-mismatch",
    )

    assert result["status"] == "needs_review"
    assert result["expected_minor"] == 10_000
    assert result["difference_minor"] == -1
    assert ledger.list_fund_movements(PROJECT_ID, "2026-07-20", "2026-07-20") == []
    sale = ledger.merchant_net_sales(PROJECT_ID, "2026-07-13", "2026-07-13")[0]
    assert sale["settlement_state"] == "merchant_net_confirmed"


def test_taobao_t3_tracks_wallet_without_claiming_bank_arrival(tmp_path, monkeypatch):
    ledger = _ledger(tmp_path, monkeypatch)
    ledger.save_daily_revenue_entries(
        PROJECT_ID,
        "2026-07-13",
        [{"channel": "淘宝闪购", "status": "recorded", "amount_minor": 5_000}],
    )

    checklist = ledger.daily_revenue_checklist(
        PROJECT_ID, "2026-07-13", "2026-07-13",
    )["days"][0]
    row = next(item for item in checklist["channels"] if item["channel"] == "淘宝闪购")
    assert row["expected_wallet_date"] == "2026-07-16"
    assert row["expected_bank_date"] is None
    assert row["withdrawal_mode"] == "automatic"

    result = ledger.platform_arrival_candidates(
        PROJECT_ID, arrival_period_start="2026-07-16", arrival_period_end="2026-07-16",
    )

    assert result["expected_total_minor"] == 0
    assert result["missing_rule_platforms"] == []
    assert result["candidates"] == []
    assert result["wallet_settlement_platforms"] == ["淘宝闪购"]
    assert result["manual_withdrawal_platforms"] == []


def test_meituan_group_buy_tracks_wallet_date_but_not_bound_card_arrival(tmp_path, monkeypatch):
    ledger = _ledger(tmp_path, monkeypatch)
    ledger.save_daily_revenue_entries(
        PROJECT_ID,
        "2026-07-13",
        [{"channel": "美团团购", "status": "recorded", "amount_minor": 6_000}],
    )

    checklist = ledger.daily_revenue_checklist(
        PROJECT_ID, "2026-07-13", "2026-07-13",
    )["days"][0]
    row = next(item for item in checklist["channels"] if item["channel"] == "美团团购")
    assert row["expected_wallet_date"] == "2026-07-14"
    assert row["expected_bank_date"] is None
    assert row["withdrawal_mode"] == "manual"

    arrivals = ledger.platform_arrival_candidates(
        PROJECT_ID, arrival_period_start="2026-07-14", arrival_period_end="2026-07-20",
    )
    assert arrivals["expected_total_minor"] == 0
    assert arrivals["candidates"] == []
    assert arrivals["missing_rule_platforms"] == []
    assert arrivals["wallet_settlement_platforms"] == ["美团团购"]
    assert arrivals["manual_withdrawal_platforms"] == ["美团团购"]
