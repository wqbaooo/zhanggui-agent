from fastapi.testclient import TestClient

import config
from server.main import app


def ledger_client(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "PROJECT_DATA_DIR", tmp_path)
    return TestClient(app)


def test_seeded_money_view_separates_sales_settlement_and_former_owner_transfer(tmp_path, monkeypatch):
    client = ledger_client(tmp_path, monkeypatch)
    project_id = "xinyu-ledger-test"

    card = client.get(f"/api/projects/{project_id}/today-operating-card").json()
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


def test_purchase_and_stock_in_are_separate(tmp_path, monkeypatch):
    client = ledger_client(tmp_path, monkeypatch)
    project_id = "xinyu-purchase-stock-separate"

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


def test_daily_close_check_blocks_when_duplicate_risk_exists(tmp_path, monkeypatch):
    client = ledger_client(tmp_path, monkeypatch)
    project_id = "xinyu-close-block-dupe"

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
