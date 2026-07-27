import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import config
from server.main import app


def ledger_client(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "PROJECT_DATA_DIR", tmp_path)
    return TestClient(app)


def seed_ledger(client, project_id):
    response = client.post(f"/api/projects/{project_id}/operating-ledger/seed")
    assert response.status_code == 200


def test_seeded_money_view_separates_sales_settlement_and_former_owner_transfer(tmp_path, monkeypatch):
    client = ledger_client(tmp_path, monkeypatch)
    project_id = "xinyu-ledger-test"
    seed_ledger(client, project_id)

    card = client.get(f"/api/projects/{project_id}/today-operating-card?date=2026-07-04").json()
    money = card["money_where"]

    assert card["date"] == "2026-07-04"
    assert card["fixture_sales"]["sales"]["order_amount"] == 2080.34
    assert card["fixture_sales"]["sales"]["net_operating_income"] == 1794.8
    assert card["fixture_sales"]["sales"]["order_count"] == 114
    assert money["fixture_sales"]["money"][0]["label"] == "现金"
    assert money["fixture_sales"]["money"][0]["amount"] == 185
    assert money["former_owner"]["receivable_from_former_owner"] == "待确认"
    assert money["former_owner"]["transferred_to_owner"] == "待确认"
    assert card["estimated_profit"] is None
    assert "利润暂不能精确确认" in card["profit_statement"]
    assert any("前老板转账是应收前老板回款" in rule for rule in money["rules"])


def test_pending_fact_must_be_confirmed_before_it_posts_to_ledger(tmp_path, monkeypatch):
    client = ledger_client(tmp_path, monkeypatch)
    project_id = "xinyu-confirm-flow"
    seed_ledger(client, project_id)

    pending = client.get(f"/api/projects/{project_id}/business-facts?review_status=need_review").json()["facts"]
    sources = {item["raw_material"]["title"] for item in pending}
    assert "7/4 客如云营业日报" in sources
    assert "7/4 客如云营业概况" in sources
    assert "7/4 大口章鱼烧物料盘点表" in sources
    assert "7/6 大口章鱼烧供应链进货单" in sources
    assert "微信聊天长截图" in sources
    fact = next(item for item in pending if item["id"] == "fact-wechat-former-collected")
    before = client.get(f"/api/projects/{project_id}/money-view").json()
    assert fact["ledger_status"] == "not_posted"
    assert before["former_owner"]["receivable_from_former_owner"] == "待确认"

    marked = client.post(
        f"/api/projects/{project_id}/business-facts/{fact['id']}/mark",
        json={"action": "former_owner_collected"},
    )
    assert marked.status_code == 200
    confirmed = client.post(f"/api/projects/{project_id}/business-facts/{fact['id']}/confirm")
    assert confirmed.status_code == 200
    assert confirmed.json()["fact"]["ledger_status"] == "posted"

    after = client.get(f"/api/projects/{project_id}/money-view").json()
    assert after["accounts"]["former_owner_account"] == 0


def test_inventory_view_has_core_items_and_purchase_recommendation(tmp_path, monkeypatch):
    client = ledger_client(tmp_path, monkeypatch)
    project_id = "xinyu-inventory-view"
    seed_ledger(client, project_id)

    inventory = client.get(f"/api/projects/{project_id}/first-stage-inventory").json()
    items = {item["name"]: item for item in inventory["items"]}

    for name in ["章鱼粒", "章鱼预拌粉", "原味照烧酱", "木鱼花", "海苔粉", "沙拉酱", "6 粒盒", "包装耗材"]:
        assert name in items
    assert items["章鱼粒"]["risk_level"] == "high"
    assert items["木鱼花"]["risk_level"] == "watch"
    assert inventory["last_count_date"] == "2026-07-04"
    assert inventory["pending_inventory_facts"] > 0
    assert items["章鱼粒"]["evidence_source"] == "7/4 盘点表 / 7/6 进货单"
    assert items["章鱼粒"]["confirmation_status"] == "低置信度"
    assert items["章鱼粒"]["owner_confirmed"] is False
    assert inventory["consumption_methods"]["theoretical"] == "销量 × BOM 理论用量"
    assert inventory["consumption_methods"]["actual"] == "期初库存 + 今日入库 - 期末库存"


def test_cost_question_lists_missing_bom_fields_instead_of_guessing(tmp_path, monkeypatch):
    client = ledger_client(tmp_path, monkeypatch)
    project_id = "xinyu-cost-gap"
    seed_ledger(client, project_id)

    answer = client.get(
        f"/api/projects/{project_id}/cost-question",
        params={"question": "一盒 6 粒章鱼烧成本是多少？"},
    ).json()

    assert "不能精确确认" in answer["answer"]
    assert "一盒基础 6 粒至少需要 6 个章鱼粒。" in answer["known_costs"]
    assert "一包粉可做多少盒 6 粒" in answer["missing_fields"]
    assert "每盒酱料克重" in answer["missing_fields"]
    assert answer["follow_up"]["priority"] == "P1"


def test_same_day_keruyun_overview_daily_report_not_double_counted(tmp_path, monkeypatch):
    client = ledger_client(tmp_path, monkeypatch)
    project_id = "xinyu-dedupe-test"
    seed_ledger(client, project_id)

    facts = client.get(f"/api/projects/{project_id}/business-facts").json()["facts"]
    daily_net = next(f for f in facts if f["id"] == "fact-kyy-net-income")
    overview_net = next(f for f in facts if f["id"] == "fact-kyy-overview-net-income")

    assert daily_net["evidence_role"] == "primary"
    assert overview_net["evidence_role"] == "supporting"
    assert overview_net["primary_evidence_id"] == "fact-kyy-net-income"
    assert daily_net["ledger_status"] == "posted"
    assert overview_net["ledger_status"] == "duplicate_suppressed"

    daily_order = next(f for f in facts if f["id"] == "fact-kyy-order-amount")
    overview_order = next(f for f in facts if f["id"] == "fact-kyy-overview-order-amount")
    assert daily_order["fact_type"] == "pos_sale"
    assert overview_order["fact_type"] == "pos_sale"
    assert overview_order["evidence_role"] == "supporting"
    assert overview_order["primary_evidence_id"] == "fact-kyy-order-amount"

    posted_count = sum(
        1 for f in facts
        if f["fact_type"] == "net_operating_income"
        and f["ledger_status"] == "posted"
        and f["evidence_role"] != "supporting"
    )
    assert posted_count == 1

    money = client.get(f"/api/projects/{project_id}/money-view").json()
    assert money["total_sales"] == 1794.8


def test_business_fact_confirmation_posts_ledger_entry(tmp_path, monkeypatch):
    client = ledger_client(tmp_path, monkeypatch)
    project_id = "xinyu-confirm-posts"
    seed_ledger(client, project_id)

    fact = next(
        f for f in client.get(f"/api/projects/{project_id}/business-facts?review_status=need_review").json()["facts"]
        if f["id"] == "fact-kyy-dine-in"
    )
    assert fact["ledger_status"] == "not_posted"
    assert fact["posted_at"] == ""

    result = client.post(f"/api/projects/{project_id}/business-facts/{fact['id']}/confirm").json()
    assert result["fact"]["ledger_status"] == "posted"
    assert result["fact"]["review_status"] == "posted"
    assert result["fact"]["posted_at"] != ""
    assert len(result["ledger_entries"]) > 0
    assert result["ledger_entries"][0]["entry_type"] == "revenue"
    assert result["fact"]["affects_accounts"] == ["keruyun_pending_settlement"]

    money = client.get(f"/api/projects/{project_id}/money-view").json()
    assert money["total_sales"] > 1794.8


def test_former_owner_transfer_moves_money_not_revenue(tmp_path, monkeypatch):
    client = ledger_client(tmp_path, monkeypatch)
    project_id = "xinyu-former-owner-transfer"
    seed_ledger(client, project_id)

    transfer_fact = next(
        f for f in client.get(f"/api/projects/{project_id}/business-facts?review_status=need_review").json()["facts"]
        if f["id"] == "fact-wechat-former-transfer"
    )

    before = client.get(f"/api/projects/{project_id}/money-view").json()
    before_sales = before["total_sales"]

    update_res = client.patch(
        f"/api/projects/{project_id}/business-facts/{transfer_fact['id']}",
        json={"amount": 500},
    )
    assert update_res.status_code == 200

    result = client.post(f"/api/projects/{project_id}/business-facts/{transfer_fact['id']}/confirm").json()
    entries = result["ledger_entries"]

    entry_types = {e["entry_type"] for e in entries}
    assert "revenue" not in entry_types
    assert "receivable_repayment" in entry_types
    assert "internal_transfer" in entry_types

    accounts_affected = {e["account"] for e in entries}
    assert "former_owner_account" in accounts_affected
    assert "owner_cmb_bank" in accounts_affected

    after = client.get(f"/api/projects/{project_id}/money-view").json()
    assert after["total_sales"] == before_sales
    assert after["accounts"]["former_owner_account"] == -500
    assert after["accounts"]["owner_cmb_bank"] == 500


def test_capture_keruyun_report_creates_pending_facts_then_posts_income(tmp_path, monkeypatch):
    client = ledger_client(tmp_path, monkeypatch)
    project_id = "xinyu-capture-keruyun"
    seed_ledger(client, project_id)

    payload = {
        "file_name": "客如云-2026-07-09.png",
        "source_type": "客如云日报",
        "fields": [
            {"key": "date", "value": "2026-07-09"},
            {"key": "order_amount", "value": 1119.83},
            {"key": "operating_income", "value": 882.89},
            {"key": "dine_in_revenue", "value": 704.88},
            {"key": "delivery_revenue", "value": 178.01},
            {"key": "merchant_discount", "value": 91.76},
            {"key": "delivery_fee", "value": 36.45},
            {"key": "service_fee", "value": 91.89},
            {"key": "cash_amount", "value": 77},
        ],
        "structured_artifact": {"type": "operation_record", "summary": "客如云 7/9 日报"},
        "raw_text": "客如云 2026-07-09",
    }

    created = client.post(f"/api/projects/{project_id}/business-facts/from-capture", json=payload).json()
    assert created["success"] is True
    assert created["created"] >= 8
    assert all(f["review_status"] == "need_review" for f in created["facts"])

    money_before = client.get(f"/api/projects/{project_id}/money-view?date=2026-07-09").json()
    assert money_before["total_sales"] == 0

    income_fact = next(f for f in created["facts"] if f["fact_type"] == "net_operating_income")
    posted = client.post(f"/api/projects/{project_id}/business-facts/{income_fact['id']}/confirm").json()
    assert posted["fact"]["ledger_status"] == "posted"
    assert posted["ledger_entries"][0]["entry_type"] == "revenue"

    money_after = client.get(f"/api/projects/{project_id}/money-view?date=2026-07-09").json()
    assert money_after["total_sales"] == 882.89
    finance_after = client.get(f"/api/projects/{project_id}/finance/overview?start=2026-07-09&end=2026-07-09").json()
    assert finance_after["revenue_minor"] == 88289

    cash_fact = next(f for f in created["facts"] if f["title"] == "现金收款")
    client.post(f"/api/projects/{project_id}/business-facts/{cash_fact['id']}/confirm")
    money_cash = client.get(f"/api/projects/{project_id}/money-view?date=2026-07-09").json()
    assert money_cash["total_sales"] == 882.89
    assert money_cash["accounts"]["owner_cash"] == 77


def test_supplier_credit_receipt_posts_payable_without_cash_spend(tmp_path, monkeypatch):
    client = ledger_client(tmp_path, monkeypatch)
    project_id = "xinyu-supplier-credit"
    seed_ledger(client, project_id)

    payload = {
        "file_name": "菜场挂账-2026-07-03.jpg",
        "source_type": "菜场挂账小票",
        "fields": [],
        "structured_artifact": {
            "type": "supplier_credit_receipt",
            "facts": [{"label": "挂账金额", "value": 15.15}, {"label": "供应商/客户", "value": "菜场"}],
            "write_payloads": {
                "supplier_credit": {
                    "amount": 15.15,
                    "payment_status": "unpaid",
                    "cash_impact": 0,
                    "items": [{"name": "包菜", "quantity": 6, "unit_cost": 7.5, "total": 11.55}],
                }
            },
        },
        "raw_text": "菜场挂账 合计 15.15",
    }

    created = client.post(f"/api/projects/{project_id}/business-facts/from-capture", json=payload).json()
    payable_fact = next(f for f in created["facts"] if f["fact_type"] == "supplier_invoice")
    result = client.post(f"/api/projects/{project_id}/business-facts/{payable_fact['id']}/confirm").json()
    assert result["ledger_entries"][0]["entry_type"] == "supplier_payable"
    money = client.get(f"/api/projects/{project_id}/money-view?date={payable_fact['date']}").json()
    assert money["purchase_spend"] == 0
    assert money["accounts"]["supplier_payable"] == -15.15


def test_purchase_capture_creates_inventory_and_payable_candidates_without_period_expense(tmp_path, monkeypatch):
    client = ledger_client(tmp_path, monkeypatch)
    project_id = "xinyu-purchase-capture"
    seed_ledger(client, project_id)
    payload = {
        "file_name": "进货单-2026-07-10.jpg",
        "source_type": "进货单",
        "fields": [{"key": "date", "value": "2026-07-10"}],
        "structured_artifact": {
            "type": "purchase_order",
            "write_payloads": {
                "purchase_order": {
                    "date": "2026-07-10",
                    "supplier": "大口供应链",
                    "items": [{"name": "章鱼粒", "quantity": 2, "unit_cost": 60}],
                }
            },
        },
    }

    first = client.post(f"/api/projects/{project_id}/business-facts/from-capture", json=payload).json()
    second = client.post(f"/api/projects/{project_id}/business-facts/from-capture", json=payload).json()

    assert first["created"] == 2
    assert second["created"] == 0
    assert {item["fact_type"] for item in first["facts"]} == {"purchase_confirmation", "stock_in"}
    stock_fact = next(item for item in first["facts"] if item["fact_type"] == "stock_in")
    posted = client.post(f"/api/projects/{project_id}/business-facts/{stock_fact['id']}/confirm").json()
    assert posted["finance_inventory"][0]["amount_minor"] == 12000

    from models.finance_ledger import FinanceLedger

    finance = FinanceLedger.for_project(project_id).overview(project_id, "2026-07-10", "2026-07-10")
    assert finance["liabilities_minor"]["supplier_payable"] == 12000
    assert finance["assets_minor"]["inventory"] == 12000
    assert finance["costs_minor"]["food_cost"] == 0


def test_inventory_photo_stays_as_unposted_observation_until_quantity_is_reviewed(tmp_path, monkeypatch):
    client = ledger_client(tmp_path, monkeypatch)
    project_id = "xinyu-inventory-photo"
    seed_ledger(client, project_id)
    payload = {
        "file_name": "冰柜库存.jpg",
        "source_type": "库存照片",
        "fields": [],
        "structured_artifact": {
            "type": "inventory_observation",
            "facts": [{"label": "可见物料", "value": "章鱼粒"}],
            "summary": "冰柜中看到章鱼粒，数量待老板确认",
        },
    }

    created = client.post(f"/api/projects/{project_id}/business-facts/from-capture", json=payload).json()

    assert created["created"] == 1
    observation = created["facts"][0]
    assert observation["fact_type"] == "inventory_count_photo"
    assert observation["ledger_status"] == "not_posted"
    assert "quantity" in observation["missing_fields"]
    inventory = client.get(f"/api/projects/{project_id}/first-stage-inventory").json()
    assert not any(move["source_fact_id"] == observation["id"] for move in inventory["movements"])


def test_platform_reconciliation_is_visible_but_not_second_revenue_total(tmp_path, monkeypatch):
    client = ledger_client(tmp_path, monkeypatch)
    project_id = "xinyu-reconciliation-view"
    seed_ledger(client, project_id)
    project_dir = Path(tmp_path) / project_id
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "platform_reconciliations.json").write_text(json.dumps({
        "source_file": "captures/source/revenue.docx",
        "aggregation_rule": "platform detail does not duplicate store revenue",
        "records": [
            {"platform": "taobao_flash", "business_date": "2026-07-01", "amount": 92.76, "counted_in_store_revenue": False},
            {"platform": "jd", "business_date": "2026-07-01", "amount": 53.95, "counted_in_store_revenue": False},
        ],
        "missing_platform_evidence": [{"platform": "douyin", "status": "missing_independent_reconciliation"}],
    }), encoding="utf-8")

    response = client.get(f"/api/projects/{project_id}/platform-reconciliations?start=2026-07-01&end=2026-07-01")
    assert response.status_code == 200
    payload = response.json()
    assert payload["not_a_second_revenue_total"] is True
    assert {item["platform"] for item in payload["by_platform"]} == {"taobao_flash", "jd"}
    assert payload["missing_platform_evidence"][0]["platform"] == "douyin"


def test_cash_flow_does_not_turn_missing_cash_into_zero(tmp_path, monkeypatch):
    client = ledger_client(tmp_path, monkeypatch)
    project_id = "xinyu-cash-flow-gap"
    seed_ledger(client, project_id)

    response = client.get(f"/api/projects/{project_id}/cash-flow")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "awaiting_cash_inputs"
    assert payload["cash_balance"] is None
    assert "daily_cash_count" in payload["missing_inputs"]


def test_purchase_and_stock_in_are_separate(tmp_path, monkeypatch):
    client = ledger_client(tmp_path, monkeypatch)
    project_id = "xinyu-purchase-stock-separate"
    seed_ledger(client, project_id)

    purchase_fact = next(
        f for f in client.get(f"/api/projects/{project_id}/business-facts?review_status=need_review").json()["facts"]
        if f["id"] == "fact-purchase"
    )
    update_res = client.patch(
        f"/api/projects/{project_id}/business-facts/{purchase_fact['id']}",
        json={"amount": 500, "metadata": {"supplier": "供应链"}},
    )
    assert update_res.status_code == 200

    before_inv = client.get(f"/api/projects/{project_id}/first-stage-inventory").json()
    octopus_before = next(i for i in before_inv["items"] if i["name"] == "章鱼粒")["current_quantity"]

    purchase_result = client.post(f"/api/projects/{project_id}/business-facts/{purchase_fact['id']}/confirm").json()
    assert len(purchase_result["ledger_entries"]) > 0
    assert purchase_result["ledger_entries"][0]["entry_type"] == "purchase_cost"
    assert len(purchase_result["inventory_movements"]) == 0

    after_inv = client.get(f"/api/projects/{project_id}/first-stage-inventory").json()
    octopus_after = next(i for i in after_inv["items"] if i["name"] == "章鱼粒")["current_quantity"]
    assert octopus_after == octopus_before

    money = client.get(f"/api/projects/{project_id}/money-view?date=2026-07-06").json()
    assert money["purchase_spend"] == 500

    stockin_fact = next(
        f for f in client.get(f"/api/projects/{project_id}/business-facts?review_status=need_review").json()["facts"]
        if f["id"] == "fact-stock-in"
    )
    update_res2 = client.patch(
        f"/api/projects/{project_id}/business-facts/{stockin_fact['id']}",
        json={"metadata": {"item_id": "inv-octopus", "quantity": 3, "unit_cost": 60}},
    )
    assert update_res2.status_code == 200

    stockin_result = client.post(f"/api/projects/{project_id}/business-facts/{stockin_fact['id']}/confirm").json()
    assert len(stockin_result["inventory_movements"]) > 0
    assert stockin_result["inventory_movements"][0]["movement_type"] == "stock_in"
    assert stockin_result["fact"]["affects_inventory_items"] == ["inv-octopus"]

    after_inv2 = client.get(f"/api/projects/{project_id}/first-stage-inventory").json()
    octopus_after2 = next(i for i in after_inv2["items"] if i["name"] == "章鱼粒")["current_quantity"]
    assert octopus_after2 == octopus_before + 3

    money2 = client.get(f"/api/projects/{project_id}/money-view?date=2026-07-06").json()
    assert money2["purchase_spend"] == 500


def test_daily_close_check_blocks_when_inventory_low_confidence(tmp_path, monkeypatch):
    client = ledger_client(tmp_path, monkeypatch)
    project_id = "xinyu-close-block-inv"
    seed_ledger(client, project_id)

    check = client.get(f"/api/projects/{project_id}/daily-close-check?date=2026-07-04").json()
    review_check = client.get(f"/api/projects/{project_id}/daily-review-check?date=2026-07-04").json()
    assert check["can_close"] is False
    assert review_check["can_close"] is False
    assert review_check["pending_facts_count"] == check["pending_facts_count"]
    assert check["close_status"] == "blocked"
    assert check["low_confidence_inventory_count"] > 0

    blocked = check["blocking_reasons"]
    assert any("低置信度" in reason for reason in blocked)
    assert any("章鱼粒" in reason for reason in blocked)

    assert check["next_actions"]
    assert any("确认低置信度" in action or "盘点表" in action for action in check["next_actions"])


def test_daily_review_uses_requested_date_instead_of_fixture_actions(tmp_path, monkeypatch):
    client = ledger_client(tmp_path, monkeypatch)
    project_id = "xinyu-review-requested-date"
    seed_ledger(client, project_id)

    check = client.get(
        f"/api/projects/{project_id}/daily-review-check?date=2026-07-16"
    ).json()

    assert check["date"] == "2026-07-16"
    assert any("2026-07-16" in action for action in check["next_actions"])
    assert all("确认 7/4 客如云" not in action for action in check["next_actions"])
    assert all("现金 185 元" not in reason for reason in check["blocking_reasons"])


def test_confirm_fact_stays_retryable_when_cross_ledger_sync_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "PROJECT_DATA_DIR", tmp_path)
    from core.posting_coordinator import PostingCoordinator
    from models.operating_ledger import OperatingLedger

    project_id = "xinyu-posting-retry"
    ledger = OperatingLedger(project_id)
    ledger.seed_real_store()
    ledger.save()
    fact_id = "fact-kyy-dine-in"
    before_entries = len(ledger.ledger_entries)

    def fail_sync(self, **kwargs):
        raise RuntimeError("finance unavailable")

    monkeypatch.setattr(PostingCoordinator, "sync_confirmed_fact", fail_sync)

    with pytest.raises(RuntimeError, match="finance unavailable"):
        ledger.confirm_fact(fact_id)

    reloaded = OperatingLedger.load(project_id)
    fact = reloaded.find_fact(fact_id)
    assert fact["ledger_status"] == "not_posted"
    assert fact["review_status"] == "need_review"
    assert len(reloaded.ledger_entries) == before_entries


def test_daily_close_check_blocks_when_duplicate_risk_exists(tmp_path, monkeypatch):
    client = ledger_client(tmp_path, monkeypatch)
    project_id = "xinyu-close-block-dupe"
    seed_ledger(client, project_id)

    pending = client.get(f"/api/projects/{project_id}/business-facts?review_status=need_review").json()["facts"]
    target = next(f for f in pending if f["id"] == "fact-kyy-third-party")
    update_res = client.patch(
        f"/api/projects/{project_id}/business-facts/{target['id']}",
        json={"amount": 1794.8, "fact_type": "net_operating_income", "account_location": "keruyun_pending_settlement", "platform": "keruyun"},
    )
    assert update_res.status_code == 200

    result = client.post(f"/api/projects/{project_id}/business-facts/{target['id']}/confirm").json()
    assert result.get("duplicate_of") == "fact-kyy-net-income" or result["fact"]["duplicate_of"] == "fact-kyy-net-income"

    check = client.get(f"/api/projects/{project_id}/daily-close-check?date=2026-07-04").json()
    assert check["can_close"] is False
    assert check["duplicate_risks_count"] >= 0
    assert isinstance(check["confirmed_facts_count"], int)
    assert isinstance(check["pending_facts_count"], int)
    assert isinstance(check["posted_entries_count"], int)
    assert len(check["blocking_reasons"]) > 0
    assert len(check["next_actions"]) > 0
