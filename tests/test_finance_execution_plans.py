import pytest
from fastapi.testclient import TestClient

import config
import models.project as project_model
from core.finance_execution import FinanceExecutionService
from models.finance_ledger import FinanceLedger, FinanceMigrationError
from server.main import app


PROJECT_ID = "finance-execution-store"


def prepared_ledger(tmp_path) -> FinanceLedger:
    ledger = FinanceLedger(tmp_path / "finance.db")
    ledger.initialize()
    ledger.ensure_store(PROJECT_ID, "测试门店", "2026-07-01")
    ledger.upsert_fund_account(
        PROJECT_ID,
        account_key="owner-cmb-6936",
        name="老板招商银行尾号6936",
        account_kind="bank",
        owner_kind="owner",
        is_store_controlled=True,
        masked_number="6936",
        effective_from="2026-07-01",
    )
    ledger.upsert_fund_account(
        PROJECT_ID,
        account_key="former-owner-icbc-9863",
        name="前老板工商银行尾号9863",
        account_kind="bank",
        owner_kind="former_owner",
        is_store_controlled=False,
        masked_number="9863",
        effective_from="2026-07-01",
    )
    return ledger


def seed_combined_transfer_sources(ledger: FinanceLedger) -> list[str]:
    rows = [
        ("2026-07-12", "美团外卖", 70_596),
        ("2026-07-11", "淘宝闪购", 117_108),
        ("2026-07-13", "京东外卖", 2_965),
        ("2026-07-09", "抖音团购", 101_207),
    ]
    ids = []
    for business_date, channel, amount_minor in rows:
        ids.append(
            ledger.record_merchant_net_sale(
                PROJECT_ID,
                business_date=business_date,
                channel=channel,
                amount_minor=amount_minor,
                source_basis="平台结算证据",
                evidence_status="confirmed",
                settlement_state="former_owner_pending_transfer",
            )
        )
    ledger.post_entry(
        store_id=PROJECT_ID,
        entry_date="2026-07-19",
        posting_key="seed-former-owner-receivable",
        description="前老板代收平台款",
        lines=[("1013", 291_876, 0), ("4009", 0, 291_876)],
    )
    return ids


def transfer_input(**overrides):
    payload = {
        "event_type": "former_owner_transfer",
        "transaction_date": "2026-07-20",
        "amount_minor": 291_876,
        "account_key": "owner-cmb-6936",
        "counterparty": "前老板",
        "source_reference": "icbc-receipt-ZZHK-0010-7208-9438-0138",
        "evidence_reference": "receipt-image-sha256",
        "business_period_start": "2026-07-09",
        "business_period_end": "2026-07-19",
        "platforms": ["美团外卖", "淘宝闪购", "京东外卖", "抖音团购"],
        "notes": "回单附言 7.14-7.20",
    }
    payload.update(overrides)
    return payload


def test_preview_explains_combined_transfer_without_writing_books(tmp_path):
    ledger = prepared_ledger(tmp_path)
    sale_ids = seed_combined_transfer_sources(ledger)
    revenue_before = ledger.revenue_total(PROJECT_ID, "2026-07-01", "2026-07-31")

    plan = FinanceExecutionService(ledger).preview(PROJECT_ID, transfer_input())

    assert plan["schema_version"] == "finance_execution_plan_v1"
    assert plan["status"] == "awaiting_confirmation"
    assert plan["risk_level"] == "L3"
    assert plan["accounting_effect"]["revenue_impact_minor"] == 0
    assert plan["accounting_effect"]["journal_preview"] == [
        {"account_code": "1002", "debit_minor": 291_876, "credit_minor": 0},
        {"account_code": "1013", "debit_minor": 0, "credit_minor": 291_876},
    ]
    assert plan["reconciliation"]["difference_minor"] == 0
    assert {row["target_id"] for row in plan["reconciliation"]["allocations"]} == set(sale_ids)
    assert sum(row["amount_minor"] for row in plan["reconciliation"]["allocations"]) == 291_876
    assert ledger.revenue_total(PROJECT_ID, "2026-07-01", "2026-07-31") == revenue_before
    assert ledger.list_bookkeeping_records(PROJECT_ID) == []


def test_preview_blocks_transfer_larger_than_receivable(tmp_path):
    ledger = prepared_ledger(tmp_path)
    seed_combined_transfer_sources(ledger)
    ledger.post_entry(
        store_id=PROJECT_ID,
        entry_date="2026-07-19",
        posting_key="seed-prior-partial-transfer",
        description="此前已转回一部分代收款",
        lines=[("1002", 10_000, 0), ("1013", 0, 10_000)],
    )

    plan = FinanceExecutionService(ledger).preview(
        PROJECT_ID,
        transfer_input(source_reference="too-large-transfer"),
    )

    assert plan["status"] == "blocked"
    assert any(check["code"] == "RECEIVABLE_INSUFFICIENT" and check["status"] == "failed" for check in plan["checks"])
    assert plan["actions"] == []
    assert plan["next_steps"][0]["action"] == "reclassify_receivable_before_transfer"


def test_preview_blocks_expense_language_misclassified_as_platform_settlement(tmp_path):
    ledger = prepared_ledger(tmp_path)
    service = FinanceExecutionService(ledger)

    plan = service.preview(PROJECT_ID, {
        "event_type": "platform_settlement",
        "transaction_date": "2026-07-20",
        "amount_minor": 2_205,
        "account_key": "owner-cmb-6936",
        "counterparty": "江西省电力",
        "source_reference": "voucher:electricity-0720",
        "notes": "电网充值花了22.05 工商银行 充值缴费",
    })

    assert plan["status"] == "blocked"
    assert plan["actions"] == []
    assert any(
        check["code"] == "BUSINESS_SEMANTIC_CONTRADICTION"
        and check["status"] == "failed"
        for check in plan["checks"]
    )


def test_preview_keeps_real_platform_settlement_available_for_confirmation(tmp_path):
    ledger = prepared_ledger(tmp_path)
    plan = FinanceExecutionService(ledger).preview(PROJECT_ID, {
        "event_type": "platform_settlement",
        "transaction_date": "2026-07-20",
        "amount_minor": 12_064,
        "account_key": "owner-cmb-6936",
        "counterparty": "美团外卖",
        "source_reference": "voucher:meituan-settlement-0720",
        "notes": "美团商家钱包结算提现到银行卡",
    })

    assert plan["status"] == "awaiting_confirmation"
    assert not any(
        check["code"] == "BUSINESS_SEMANTIC_CONTRADICTION"
        and check["status"] == "failed"
        for check in plan["checks"]
    )


def test_execute_is_confirmed_idempotent_and_reconciles_every_source(tmp_path):
    ledger = prepared_ledger(tmp_path)
    seed_combined_transfer_sources(ledger)
    service = FinanceExecutionService(ledger)
    plan = service.preview(PROJECT_ID, transfer_input())
    revenue_before = ledger.revenue_total(PROJECT_ID, "2026-07-01", "2026-07-31")

    first = service.execute(PROJECT_ID, plan["plan_id"], confirmed_by="owner")
    second = service.execute(PROJECT_ID, plan["plan_id"], confirmed_by="owner")

    assert first["status"] == "completed"
    assert second["record_id"] == first["record_id"]
    record = ledger.get_bookkeeping_record(PROJECT_ID, first["record_id"])
    assert record["status"] == "posted"
    assert record["reconciliation_status"] == "matched"
    assert ledger.account_balances(PROJECT_ID, "2026-07-01", "2026-07-31")["1013"] == 0
    assert ledger.revenue_total(PROJECT_ID, "2026-07-01", "2026-07-31") == revenue_before
    assert len(ledger.list_bookkeeping_records(PROJECT_ID)) == 1


def test_execution_plan_api_requires_separate_confirmation(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "PROJECT_DATA_DIR", tmp_path)
    monkeypatch.setattr(project_model, "PROJECT_DATA_DIR", tmp_path)
    ledger = FinanceLedger.for_project(PROJECT_ID)
    ledger.ensure_store(PROJECT_ID, "测试门店", "2026-07-01")
    ledger.upsert_fund_account(
        PROJECT_ID,
        account_key="owner-cmb-6936",
        name="老板招商银行尾号6936",
        account_kind="bank",
        owner_kind="owner",
        is_store_controlled=True,
        masked_number="6936",
        effective_from="2026-07-01",
    )
    ledger.upsert_fund_account(
        PROJECT_ID,
        account_key="former-owner-icbc-9863",
        name="前老板工商银行尾号9863",
        account_kind="bank",
        owner_kind="former_owner",
        is_store_controlled=False,
        masked_number="9863",
        effective_from="2026-07-01",
    )
    seed_combined_transfer_sources(ledger)
    client = TestClient(app)

    preview = client.post(
        f"/api/projects/{PROJECT_ID}/finance/execution-plans/preview",
        json={**transfer_input(), "amount": 2918.76},
    )
    assert preview.status_code == 200
    plan = preview.json()["plan"]
    assert plan["status"] == "awaiting_confirmation"
    assert ledger.list_bookkeeping_records(PROJECT_ID) == []

    confirmed = client.post(
        f"/api/projects/{PROJECT_ID}/finance/execution-plans/{plan['plan_id']}/confirm",
        json={"confirmed": True, "confirmed_by": "owner"},
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["plan"]["status"] == "completed"


def test_platform_bank_rebind_creates_new_effective_version(tmp_path):
    ledger = prepared_ledger(tmp_path)
    ledger.upsert_platform_collection_binding(
        PROJECT_ID,
        platform="美团外卖",
        collector_account_key="former-owner-icbc-9863",
        destination_account_key="owner-cmb-6936",
        collector_owner_kind="former_owner",
        settlement_rule="T+3个工作日",
        effective_from="2026-07-01",
    )
    ledger.upsert_platform_collection_binding(
        PROJECT_ID,
        platform="美团外卖",
        collector_account_key="owner-cmb-6936",
        destination_account_key="owner-cmb-6936",
        collector_owner_kind="owner",
        settlement_rule="T+3个工作日",
        effective_from="2026-08-01",
        notes="营业执照与银行卡完成换绑",
    )

    july = ledger.list_platform_collection_bindings(PROJECT_ID, "2026-07-31")
    august = ledger.list_platform_collection_bindings(PROJECT_ID, "2026-08-01")
    history = ledger.list_platform_collection_bindings(PROJECT_ID)

    assert july[0]["collector_owner_kind"] == "former_owner"
    assert july[0]["effective_to"] == "2026-07-31"
    assert august[0]["collector_owner_kind"] == "owner"
    assert len(history) == 2


def test_platform_bank_rebind_cannot_overwrite_a_different_path_on_the_same_effective_date(tmp_path):
    ledger = prepared_ledger(tmp_path)
    ledger.upsert_platform_collection_binding(
        PROJECT_ID,
        platform="美团外卖",
        collector_account_key="former-owner-icbc-9863",
        destination_account_key="owner-cmb-6936",
        collector_owner_kind="former_owner",
        effective_from="2026-07-01",
    )

    with pytest.raises(FinanceMigrationError, match="历史路径不会被覆盖"):
        ledger.upsert_platform_collection_binding(
            PROJECT_ID,
            platform="美团外卖",
            collector_account_key="owner-cmb-6936",
            destination_account_key="owner-cmb-6936",
            collector_owner_kind="owner",
            effective_from="2026-07-01",
        )

    history = ledger.list_platform_collection_bindings(PROJECT_ID)
    assert len(history) == 1
    assert history[0]["collector_account_key"] == "former-owner-icbc-9863"


def test_pending_execution_plan_can_be_recovered_with_original_input(tmp_path):
    ledger = prepared_ledger(tmp_path)
    service = FinanceExecutionService(ledger)
    plan = service.preview(PROJECT_ID, {
        "event_type": "personal_spending",
        "transaction_date": "2026-07-21",
        "amount_minor": 1_600,
        "account_key": "owner-cmb-6936",
        "counterparty": "新余市人民医院",
        "source_reference": "voucher:personal-hospital-0721",
        "evidence_reference": "voucher:personal-hospital-0721",
        "notes": "看病挂号",
    })

    pending = ledger.list_execution_plans(
        PROJECT_ID, statuses=["awaiting_confirmation"]
    )

    assert [item["plan_id"] for item in pending] == [plan["plan_id"]]
    assert pending[0]["input"]["account_key"] == "owner-cmb-6936"
    assert pending[0]["input"]["transaction_date"] == "2026-07-21"
    assert pending[0]["input"]["evidence_reference"] == "voucher:personal-hospital-0721"
    assert "不计入店铺收入、成本或利润" in pending[0]["accounting_effect"]["explanation"]
    assert pending[0]["created_at"]
    assert pending[0]["updated_at"]

    service.execute(PROJECT_ID, plan["plan_id"], confirmed_by="owner")
    assert ledger.list_execution_plans(
        PROJECT_ID, statuses=["awaiting_confirmation"]
    ) == []


def test_pending_execution_plan_api_returns_recoverable_items(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "PROJECT_DATA_DIR", tmp_path)
    monkeypatch.setattr(project_model, "PROJECT_DATA_DIR", tmp_path)
    ledger = FinanceLedger.for_project(PROJECT_ID)
    ledger.ensure_store(PROJECT_ID, "测试门店", "2026-07-01")
    ledger.upsert_fund_account(
        PROJECT_ID,
        account_key="owner-cmb-6936",
        name="招商银行个人账户",
        account_kind="bank",
        owner_kind="owner",
        is_store_controlled=False,
    )
    FinanceExecutionService(ledger).preview(PROJECT_ID, {
        "event_type": "personal_spending",
        "transaction_date": "2026-07-21",
        "amount_minor": 1_600,
        "account_key": "owner-cmb-6936",
        "source_reference": "voucher:pending-api",
    })

    response = TestClient(app).get(
        f"/api/projects/{PROJECT_ID}/finance/execution-plans",
        params={"status": "awaiting_confirmation"},
    )

    assert response.status_code == 200
    rows = response.json()["rows"]
    assert len(rows) == 1
    assert rows[0]["input"]["source_reference"] == "voucher:pending-api"
