"""日结营业数据一致性校验。

验证 2026-07-01 ~ 2026-07-05 真实客如云数据：
- 五日数据均已入库
- 原价 - 商户优惠 - 退款 = 实收
- 渠道汇总与堂食/外卖字段一致
- 支付方式汇总与实收一致
"""

import math
from pathlib import Path

import pytest

from server.main import app
from fastapi.testclient import TestClient

PROJECT_ID = "xinyu-hengtai-dakou"


@pytest.fixture
def client():
    return TestClient(app)


def _load_memory():
    path = Path(__file__).resolve().parent.parent / "project_data" / PROJECT_ID / "memory.json"
    if not path.exists():
        return None
    import json
    return json.loads(path.read_text(encoding="utf-8"))


def test_five_days_operations_exist(client):
    res = client.get(f"/api/projects/{PROJECT_ID}/operations?days=30")
    assert res.status_code == 200
    data = res.json()
    dates = {e["date"] for e in data["entries"]}
    assert {
        "2026-07-01",
        "2026-07-02",
        "2026-07-03",
        "2026-07-04",
        "2026-07-05",
    }.issubset(dates), f"缺失日期: {dates}"


def test_revenue_reconciliation():
    """日结对账基本不变式：实收 + 优惠 +退款 不超过订单金额。

    客如云营业收入还会扣服务费、配送支出、附加费及损益金额，
    因此不强制 exact 相等，只保证金额不溢出。
    """
    memory = _load_memory()
    assert memory is not None, "memory.json 不存在"
    entries = {e["date"]: e for e in memory.get("daily_operations", [])}
    for date in ["2026-07-01", "2026-07-02", "2026-07-03", "2026-07-04", "2026-07-05"]:
        e = entries.get(date)
        assert e, f"{date} 不存在"
        accounted = e["actual_revenue"] + e["merchant_discount"] + e["refund_amount"]
        assert accounted <= e["original_amount"] * 1.001, (
            f"{date} 对账溢出: 实收{e['actual_revenue']} + 优惠{e['merchant_discount']} + 退款{e['refund_amount']} = {accounted}, 大于订单金额 {e['original_amount']}"
        )


def test_channel_breakdown_matches_dine_delivery():
    memory = _load_memory()
    assert memory is not None
    entries = {e["date"]: e for e in memory.get("daily_operations", [])}
    for date in ["2026-07-01", "2026-07-02"]:
        e = entries[date]
        channels = e.get("channel_breakdown", [])
        by_name = {c["channel"]: c for c in channels}
        dine = by_name.get("堂食", {})
        delivery = by_name.get("外卖", {})
        assert dine.get("orders", 0) == e["dine_in_orders"], f"{date} 堂食订单数不一致"
        assert delivery.get("orders", 0) == e["delivery_orders"], f"{date} 外卖订单数不一致"
        assert math.isclose(dine.get("actual_revenue", 0), e["dine_in_revenue"], rel_tol=1e-3), f"{date} 堂食收入不一致"
        assert math.isclose(delivery.get("actual_revenue", 0), e["delivery_revenue"], rel_tol=1e-3), f"{date} 外卖收入不一致"


def test_payment_methods_sum_matches_actual():
    memory = _load_memory()
    assert memory is not None
    entries = {e["date"]: e for e in memory.get("daily_operations", [])}
    for date in ["2026-07-01", "2026-07-02", "2026-07-03", "2026-07-04", "2026-07-05"]:
        e = entries[date]
        payments = e.get("payment_methods", [])
        total = sum(p["amount"] for p in payments)
        assert math.isclose(total, e["actual_revenue"], rel_tol=1e-3), (
            f"{date} 支付方式合计 {total} 与实收 {e['actual_revenue']} 不一致"
        )


def test_july_third_order_sources_match_gross_sales():
    memory = _load_memory()
    assert memory is not None
    entry = next(e for e in memory["daily_operations"] if e["date"] == "2026-07-03")
    channels = entry["channel_breakdown"]
    assert sum(item["orders"] for item in channels) == entry["orders"]
    assert math.isclose(
        sum(item["original_amount"] for item in channels),
        entry["original_amount"],
        abs_tol=0.01,
    )
    assert entry["sales_transactions"] == 76
    assert entry["visitors"] == 76
    assert entry["dining_customers"] == 75


def test_july_fourth_and_fifth_product_sales_and_settlement_ownership():
    memory = _load_memory()
    assert memory is not None
    entries = {e["date"]: e for e in memory.get("daily_operations", [])}

    july_fourth = entries["2026-07-04"]
    assert july_fourth["product_sales"][0] == {
        "name": "经典必吃",
        "quantity": 82,
        "amount": 1338.0,
    }
    assert math.isclose(
        sum(item["amount"] for item in july_fourth["settlement_breakdown"]),
        july_fourth["actual_revenue"],
        abs_tol=0.01,
    )

    july_fifth = entries["2026-07-05"]
    assert july_fifth["product_sales"][0]["quantity"] == 64
    former_owner = next(
        item for item in july_fifth["settlement_breakdown"]
        if item["owner"] == "former_owner"
    )
    assert former_owner["amount"] == 474.62
    assert former_owner["status"] == "pending_reconciliation"


def test_operation_summary_has_settlement_fields(client):
    res = client.get(f"/api/projects/{PROJECT_ID}/operations/summary?days=30")
    assert res.status_code == 200
    s = res.json()
    assert s["entry_count"] >= 3
    assert s["total_original_amount"] > 0
    assert s["total_merchant_discount"] >= 0
    assert s["total_refund_amount"] >= 0
    assert s["total_revenue"] > 0
    assert s["settlement_summary"]["former_owner"] == 2245.18
    assert s["settlement_summary"]["cash_on_hand"] == 676.0
    assert s["product_sales"][0]["name"] == "经典必吃"


def test_incomplete_costs_do_not_claim_profit(client):
    res = client.get(f"/api/projects/{PROJECT_ID}/operations/summary?days=30")
    assert res.status_code == 200
    summary = res.json()

    assert summary["profit_ready"] is False
    assert summary["profit_status"] == "missing_costs"
    assert {"food_cost", "labor", "rent_allocated"}.issubset(
        set(summary["missing_cost_fields"])
    )
    assert not any("亏损" in item["message"] for item in summary["alerts"])
