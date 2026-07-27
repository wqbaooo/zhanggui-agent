from fastapi.testclient import TestClient

import config
import models.sku as sku_model
from models.finance_ledger import FinanceLedger
from server.main import app


def inventory_client(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "PROJECT_DATA_DIR", tmp_path)
    monkeypatch.setattr(sku_model, "PROJECT_DATA_DIR", tmp_path)
    return TestClient(app)


def create_test_sku(client: TestClient, project_id: str, stock: float = 10):
    response = client.post(f"/api/projects/{project_id}/skus", json={
        "name": "测试预拌粉",
        "category": "食材",
        "unit": "包",
        "display_unit": "包",
        "tracking_mode": "open_pack",
        "daily_usage_group": "基础粉料",
        "daily_usage_sort": 1,
        "current_stock": stock,
        "unit_cost": 26.5,
    })
    assert response.status_code == 200
    return response.json()["sku"]


def test_inventory_baseline_counts_allocate_legacy_stock_without_duplication(tmp_path, monkeypatch):
    client = inventory_client(tmp_path, monkeypatch)
    project_id = "inventory-baseline"
    sku = create_test_sku(client, project_id)

    initial = client.get(f"/api/projects/{project_id}/skus/inventory-summary").json()
    assert initial["unallocated_skus"] == 1

    store_count = client.post(f"/api/projects/{project_id}/skus/counts", json={
        "date": "2026-07-03",
        "location": "store",
        "count_type": "weekly",
        "lines": [{"sku_id": sku["id"], "counted_quantity": 4}],
    })
    assert store_count.status_code == 200

    warehouse_count = client.post(f"/api/projects/{project_id}/skus/counts", json={
        "date": "2026-07-03",
        "location": "warehouse",
        "count_type": "biweekly",
        "lines": [{"sku_id": sku["id"], "counted_quantity": 6}],
    })
    assert warehouse_count.status_code == 200

    persisted = client.get(f"/api/projects/{project_id}/skus/{sku['id']}").json()["sku"]
    assert persisted["daily_usage_group"] == "基础粉料"
    assert persisted["daily_usage_sort"] == 1
    assert persisted["stock_by_location"] == {
        "unallocated": 0.0,
        "store": 4.0,
        "warehouse": 6.0,
    }
    assert persisted["current_stock"] == 10.0


def test_paper_inventory_sheet_reconciles_unallocated_baseline_to_actual_total(tmp_path, monkeypatch):
    client = inventory_client(tmp_path, monkeypatch)
    project_id = "paper-inventory-count"
    sku = create_test_sku(client, project_id, stock=10)

    response = client.post(f"/api/projects/{project_id}/skus/counts", json={
        "date": "2026-07-03",
        "location": "store",
        "count_type": "spot",
        "source": "paper_inventory_sheet",
        "notes": "员工纸质物料盘点表人工复核",
        "lines": [{"sku_id": sku["id"], "counted_quantity": 3}],
    })

    assert response.status_code == 200
    line = response.json()["count"]["lines"][0]
    assert line["expected_quantity"] == 10
    assert line["counted_quantity"] == 3
    assert line["variance_quantity"] == -7

    persisted = client.get(f"/api/projects/{project_id}/skus/{sku['id']}").json()["sku"]
    assert persisted["stock_by_location"] == {
        "unallocated": 0.0,
        "store": 3.0,
    }
    assert persisted["current_stock"] == 3.0


def test_usage_transfer_count_and_purchase_order_form_auditable_inventory_flow(tmp_path, monkeypatch):
    client = inventory_client(tmp_path, monkeypatch)
    project_id = "inventory-events"
    sku = create_test_sku(client, project_id)

    allocation = client.post(f"/api/projects/{project_id}/skus/transfer", json={
        "date": "2026-07-03",
        "from_location": "unallocated",
        "to_location": "store",
        "items": [{"sku_id": sku["id"], "quantity": 4}],
    })
    assert allocation.status_code == 200

    usage = client.post(f"/api/projects/{project_id}/skus/usage-logs", json={
        "date": "2026-07-03",
        "location": "store",
        "items": [{"sku_id": sku["id"], "quantity": 2}],
        "source": "paper_ledger",
    })
    assert usage.status_code == 200

    count = client.post(f"/api/projects/{project_id}/skus/counts", json={
        "date": "2026-07-03",
        "location": "store",
        "count_type": "weekly",
        "lines": [{"sku_id": sku["id"], "counted_quantity": 1}],
    })
    assert count.status_code == 200
    line = count.json()["count"]["lines"][0]
    assert line["expected_quantity"] == 2
    assert line["counted_quantity"] == 1
    assert line["variance_quantity"] == -1

    purchase = client.post(f"/api/projects/{project_id}/skus/purchase", json={
        "date": "2026-07-03",
        "supplier": "总部",
        "payment_status": "已付款",
        "items": [{
            "sku_id": sku["id"],
            "name": "测试预拌粉",
            "quantity": 5,
            "unit_cost": 25,
        }],
    })
    assert purchase.status_code == 200

    persisted = client.get(f"/api/projects/{project_id}/skus/{sku['id']}").json()["sku"]
    assert persisted["stock_by_location"]["store"] == 1
    assert persisted["stock_by_location"]["unallocated"] == 6
    assert persisted["current_stock"] == 7

    receipt = client.post(
        f"/api/projects/{project_id}/skus/purchases/{purchase.json()['purchase']['id']}/receive",
        json={
            "date": "2026-07-04",
            "items": [{
                "sku_id": sku["id"],
                "received_quantity": 5,
                "allocations": {"warehouse": 2, "freezer": 2, "store": 1},
            }],
            "source": "owner_confirmed",
        },
    )
    assert receipt.status_code == 200

    persisted = client.get(f"/api/projects/{project_id}/skus/{sku['id']}").json()["sku"]
    assert persisted["stock_by_location"]["store"] == 2
    assert persisted["stock_by_location"]["warehouse"] == 2
    assert persisted["stock_by_location"]["freezer"] == 2
    assert persisted["stock_by_location"]["unallocated"] == 6
    assert persisted["current_stock"] == 12

    events = client.get(f"/api/projects/{project_id}/skus/inventory-events").json()["events"]
    assert {event["event_type"] for event in events} >= {
        "transfer",
        "usage",
        "count_adjustment",
        "receipt",
    }


def test_purchase_receipt_rejects_allocation_mismatch_and_duplicate_receipt(tmp_path, monkeypatch):
    client = inventory_client(tmp_path, monkeypatch)
    project_id = "receipt-guard"
    sku = create_test_sku(client, project_id, stock=0)

    purchase = client.post(f"/api/projects/{project_id}/skus/purchase", json={
        "date": "2026-07-05",
        "supplier": "总部供应链",
        "external_order_id": "2516935156879672320",
        "payment_status": "已付款",
        "paid_amount": 132.5,
        "items": [{
            "sku_id": sku["id"],
            "name": "测试预拌粉",
            "quantity": 5,
            "unit_cost": 26.5,
        }],
    }).json()["purchase"]

    mismatch = client.post(
        f"/api/projects/{project_id}/skus/purchases/{purchase['id']}/receive",
        json={
            "date": "2026-07-06",
            "items": [{
                "sku_id": sku["id"],
                "received_quantity": 5,
                "allocations": {"warehouse": 4},
            }],
        },
    )
    assert mismatch.status_code == 400

    accepted = client.post(
        f"/api/projects/{project_id}/skus/purchases/{purchase['id']}/receive",
        json={
            "date": "2026-07-06",
            "items": [{
                "sku_id": sku["id"],
                "received_quantity": 5,
                "allocations": {"warehouse": 4, "store": 1},
            }],
        },
    )
    assert accepted.status_code == 200
    assert accepted.json()["purchase"]["fulfillment_status"] == "received"

    duplicate = client.post(
        f"/api/projects/{project_id}/skus/purchases/{purchase['id']}/receive",
        json={
            "date": "2026-07-06",
            "items": [{
                "sku_id": sku["id"],
                "received_quantity": 5,
                "allocations": {"warehouse": 4, "store": 1},
            }],
        },
    )
    assert duplicate.status_code == 400


def test_production_batch_consumes_raw_material_and_tracks_work_in_process(tmp_path, monkeypatch):
    client = inventory_client(tmp_path, monkeypatch)
    project_id = "production-batch"
    flour = create_test_sku(client, project_id, stock=2)
    seasoning = client.post(f"/api/projects/{project_id}/skus", json={
        "name": "调味料",
        "category": "食材",
        "unit": "包",
        "current_stock": 2,
    }).json()["sku"]

    for sku in (flour, seasoning):
        response = client.post(f"/api/projects/{project_id}/skus/transfer", json={
            "date": "2026-07-06",
            "from_location": "unallocated",
            "to_location": "store",
            "items": [{"sku_id": sku["id"], "quantity": 2}],
        })
        assert response.status_code == 200

    created = client.post(f"/api/projects/{project_id}/production-batches", json={
        "date": "2026-07-06",
        "name": "章鱼烧半桶面浆",
        "location": "store",
        "inputs": [
            {"sku_id": flour["id"], "quantity": 1},
            {"sku_id": seasoning["id"], "quantity": 1},
        ],
        "output_quantity": 1,
        "output_unit": "半桶",
        "pan_cycle_minutes": 10,
        "source": "owner_observation",
    })
    assert created.status_code == 200
    batch = created.json()["batch"]
    assert batch["status"] == "open"
    assert batch["remaining_quantity"] == 1

    summary = client.get(f"/api/projects/{project_id}/skus/inventory-summary").json()
    assert summary["work_in_process"]["open_batches"] == 1
    assert summary["work_in_process"]["items"][0]["remaining_quantity"] == 1

    closed = client.post(
        f"/api/projects/{project_id}/production-batches/{batch['id']}/close",
        json={"used_quantity": 0.8, "waste_quantity": 0.2, "actual_pan_cycles": 18},
    )
    assert closed.status_code == 200
    assert closed.json()["batch"]["status"] == "closed"
    assert closed.json()["batch"]["actual_pan_cycles"] == 18


def test_transfer_rejects_insufficient_stock_without_partial_write(tmp_path, monkeypatch):
    client = inventory_client(tmp_path, monkeypatch)
    project_id = "inventory-transfer-guard"
    sku = create_test_sku(client, project_id, stock=2)

    response = client.post(f"/api/projects/{project_id}/skus/transfer", json={
        "date": "2026-07-03",
        "from_location": "unallocated",
        "to_location": "store",
        "items": [{"sku_id": sku["id"], "quantity": 3}],
    })
    assert response.status_code == 400

    persisted = client.get(f"/api/projects/{project_id}/skus/{sku['id']}").json()["sku"]
    assert persisted["current_stock"] == 2
    assert persisted["stock_by_location"] == {"unallocated": 2.0}


def test_count_normalizes_pack_unit_to_base_unit(tmp_path, monkeypatch):
    """盘点输入「11 捆」应自动换算为 550 个（核算单位）。"""
    client = inventory_client(tmp_path, monkeypatch)
    project_id = "count-unit-conversion"
    sku = create_test_sku(client, project_id, stock=1000)

    # 修正 SKU：display_unit 为捆，1 捆 = 50 个
    client.patch(f"/api/projects/{project_id}/skus/{sku['id']}", json={
        "display_unit": "捆",
        "count_units": [{"unit": "捆", "conversion": 50, "base_unit": "包"}],
    })

    # 先把库存调到门店，避免走首次迁移逻辑
    client.post(f"/api/projects/{project_id}/skus/transfer", json={
        "date": "2026-07-03",
        "from_location": "unallocated",
        "to_location": "store",
        "items": [{"sku_id": sku["id"], "quantity": 1000}],
    })

    response = client.post(f"/api/projects/{project_id}/skus/counts", json={
        "date": "2026-07-03",
        "location": "store",
        "count_type": "weekly",
        "lines": [{"sku_id": sku["id"], "counted_quantity": 11, "counted_unit": "捆"}],
    })
    assert response.status_code == 200
    line = response.json()["count"]["lines"][0]
    assert line["input_quantity"] == 11
    assert line["input_unit"] == "捆"
    assert line["counted_quantity"] == 550
    assert line["unit"] == "包"
    assert line["variance_quantity"] == -450

    persisted = client.get(f"/api/projects/{project_id}/skus/{sku['id']}").json()["sku"]
    assert persisted["current_stock"] == 550


def test_count_uses_display_unit_when_counted_unit_is_empty(tmp_path, monkeypatch):
    """未传 counted_unit 时，使用 SKU 的 display_unit 自动换算。"""
    client = inventory_client(tmp_path, monkeypatch)
    project_id = "display-unit-conversion"
    sku = create_test_sku(client, project_id, stock=500)

    client.patch(f"/api/projects/{project_id}/skus/{sku['id']}", json={
        "display_unit": "把",
        "count_units": [{"unit": "把", "conversion": 100, "base_unit": "包"}],
    })

    client.post(f"/api/projects/{project_id}/skus/transfer", json={
        "date": "2026-07-03",
        "from_location": "unallocated",
        "to_location": "store",
        "items": [{"sku_id": sku["id"], "quantity": 500}],
    })

    response = client.post(f"/api/projects/{project_id}/skus/counts", json={
        "date": "2026-07-03",
        "location": "store",
        "count_type": "weekly",
        "lines": [{"sku_id": sku["id"], "counted_quantity": 3}],
    })
    assert response.status_code == 200
    line = response.json()["count"]["lines"][0]
    assert line["input_quantity"] == 3
    assert line["input_unit"] == "把"
    assert line["counted_quantity"] == 300
    assert line["variance_quantity"] == -200


def test_consumption_variance_marks_missing_bom(tmp_path, monkeypatch):
    """没有 BOM 时，差异分析应标记为 no_bom，不伪造结论。"""
    client = inventory_client(tmp_path, monkeypatch)
    project_id = "consumption-variance"
    sku = create_test_sku(client, project_id, stock=10)

    # 期初盘点 10 -> 采购 5 -> 期末盘点 8：实际消耗 = 10 + 5 - 8 = 7
    client.post(f"/api/projects/{project_id}/skus/counts", json={
        "date": "2026-07-01",
        "location": "store",
        "count_type": "weekly",
        "lines": [{"sku_id": sku["id"], "counted_quantity": 10}],
    })
    purchase = client.post(f"/api/projects/{project_id}/skus/purchase", json={
        "date": "2026-07-02",
        "supplier": "总部",
        "items": [{"sku_id": sku["id"], "name": "测试预拌粉", "quantity": 5, "unit_cost": 25}],
    }).json()["purchase"]
    client.post(f"/api/projects/{project_id}/skus/purchases/{purchase['id']}/receive", json={
        "date": "2026-07-02",
        "items": [{"sku_id": sku["id"], "received_quantity": 5, "allocations": {"store": 5}}],
    })
    client.post(f"/api/projects/{project_id}/skus/counts", json={
        "date": "2026-07-03",
        "location": "store",
        "count_type": "weekly",
        "lines": [{"sku_id": sku["id"], "counted_quantity": 8}],
    })

    from models.sku import SkuCatalog

    catalog = SkuCatalog.load(project_id)
    result = catalog.consumption_variance_analysis("2026-07-01", "2026-07-03")
    row = next(r for r in result["rows"] if r["sku_id"] == sku["id"])
    assert row["actual_consumption"] == 7
    assert row["theoretical_consumption"] is None
    assert row["verification_status"] == "no_bom"


def test_consumption_variance_with_bom_and_sales(tmp_path, monkeypatch):
    """有 BOM 和销量时，计算实际 vs 理论差异。"""
    client = inventory_client(tmp_path, monkeypatch)
    project_id = "consumption-variance-bom"
    sku = create_test_sku(client, project_id, stock=10)

    client.post(f"/api/projects/{project_id}/skus/counts", json={
        "date": "2026-07-01",
        "location": "store",
        "count_type": "weekly",
        "lines": [{"sku_id": sku["id"], "counted_quantity": 10}],
    })
    purchase = client.post(f"/api/projects/{project_id}/skus/purchase", json={
        "date": "2026-07-02",
        "supplier": "总部",
        "items": [{"sku_id": sku["id"], "name": "测试预拌粉", "quantity": 5, "unit_cost": 25}],
    }).json()["purchase"]
    client.post(f"/api/projects/{project_id}/skus/purchases/{purchase['id']}/receive", json={
        "date": "2026-07-02",
        "items": [{"sku_id": sku["id"], "received_quantity": 5, "allocations": {"store": 5}}],
    })
    client.post(f"/api/projects/{project_id}/skus/counts", json={
        "date": "2026-07-03",
        "location": "store",
        "count_type": "weekly",
        "lines": [{"sku_id": sku["id"], "counted_quantity": 8}],
    })

    from models.sku import SkuCatalog

    catalog = SkuCatalog.load(project_id)
    result = catalog.consumption_variance_analysis(
        "2026-07-01", "2026-07-03",
        bom={sku["id"]: 0.5},
        sales_by_sku={sku["id"]: 10},
    )
    row = next(r for r in result["rows"] if r["sku_id"] == sku["id"])
    assert row["actual_consumption"] == 7
    assert row["theoretical_consumption"] == 5
    assert row["variance_quantity"] == 2
    assert row["verification_status"] == "over_consumption"


def test_consumption_variance_does_not_double_subtract_logged_usage(tmp_path, monkeypatch):
    """每日开包已改变账面库存，期间耗用闭合时不能再次扣除。"""
    client = inventory_client(tmp_path, monkeypatch)
    project_id = "consumption-variance-no-double-count"
    sku = create_test_sku(client, project_id, stock=10)

    client.post(f"/api/projects/{project_id}/skus/counts", json={
        "date": "2026-07-01",
        "location": "store",
        "count_type": "spot",
        "lines": [{"sku_id": sku["id"], "counted_quantity": 10}],
    })
    purchase = client.post(f"/api/projects/{project_id}/skus/purchase", json={
        "date": "2026-07-02",
        "supplier": "总部",
        "items": [{"sku_id": sku["id"], "name": sku["name"], "quantity": 5, "unit_cost": 25}],
    }).json()["purchase"]
    client.post(f"/api/projects/{project_id}/skus/purchases/{purchase['id']}/receive", json={
        "date": "2026-07-02",
        "items": [{"sku_id": sku["id"], "received_quantity": 5, "allocations": {"store": 5}}],
    })
    client.post(f"/api/projects/{project_id}/skus/usage-logs", json={
        "date": "2026-07-02",
        "location": "store",
        "items": [{"sku_id": sku["id"], "quantity": 2}],
    })
    client.post(f"/api/projects/{project_id}/skus/counts", json={
        "date": "2026-07-03",
        "location": "store",
        "count_type": "spot",
        "lines": [{"sku_id": sku["id"], "counted_quantity": 8}],
    })

    from models.sku import SkuCatalog

    result = SkuCatalog.load(project_id).consumption_variance_analysis(
        "2026-07-01",
        "2026-07-03",
    )
    row = next(item for item in result["rows"] if item["sku_id"] == sku["id"])
    assert row["usage_logged"] == 2
    assert row["actual_consumption"] == 7
    assert "不重复扣减" in result["method"]


def test_consumption_variance_requires_opening_and_closing_counts(tmp_path, monkeypatch):
    client = inventory_client(tmp_path, monkeypatch)
    project_id = "consumption-variance-missing-opening"
    sku = create_test_sku(client, project_id, stock=10)

    client.post(f"/api/projects/{project_id}/skus/counts", json={
        "date": "2026-07-03",
        "location": "store",
        "count_type": "spot",
        "lines": [{"sku_id": sku["id"], "counted_quantity": 8}],
    })

    from models.sku import SkuCatalog

    result = SkuCatalog.load(project_id).consumption_variance_analysis(
        "2026-07-01",
        "2026-07-03",
    )
    row = next(r for r in result["rows"] if r["sku_id"] == sku["id"])
    assert row["actual_consumption"] is None
    assert row["verification_status"] == "missing_opening_count"


def test_receipt_uses_moving_weighted_average_cost(tmp_path, monkeypatch):
    client = inventory_client(tmp_path, monkeypatch)
    project_id = "receipt-weighted-cost"
    sku = create_test_sku(client, project_id, stock=10)

    purchase = client.post(f"/api/projects/{project_id}/skus/purchase", json={
        "date": "2026-07-10",
        "supplier": "平替供应商",
        "items": [{"sku_id": sku["id"], "name": sku["name"], "quantity": 5, "unit_cost": 25}],
    }).json()["purchase"]
    response = client.post(f"/api/projects/{project_id}/skus/purchases/{purchase['id']}/receive", json={
        "date": "2026-07-11",
        "items": [{"sku_id": sku["id"], "received_quantity": 5, "allocations": {"warehouse": 5}}],
    })

    assert response.status_code == 200
    persisted = client.get(f"/api/projects/{project_id}/skus/{sku['id']}").json()["sku"]
    assert persisted["current_stock"] == 15
    assert persisted["unit_cost"] == 26.0
    assert persisted["unit_cost_source"] == "移动加权平均（库存账）"


def test_waste_is_separate_from_normal_usage_and_deducts_stock(tmp_path, monkeypatch):
    client = inventory_client(tmp_path, monkeypatch)
    project_id = "waste-ledger"
    sku = create_test_sku(client, project_id, stock=10)
    client.post(f"/api/projects/{project_id}/skus/transfer", json={
        "date": "2026-07-12",
        "from_location": "unallocated",
        "to_location": "store",
        "items": [{"sku_id": sku["id"], "quantity": 10}],
    })

    rejected = client.post(f"/api/projects/{project_id}/skus/waste", json={
        "date": "2026-07-12",
        "location": "store",
        "items": [{"sku_id": sku["id"], "quantity": 11}],
        "reason": "撒漏",
    })
    assert rejected.status_code == 400

    accepted = client.post(f"/api/projects/{project_id}/skus/waste", json={
        "date": "2026-07-12",
        "location": "store",
        "items": [{"sku_id": sku["id"], "quantity": 2}],
        "reason": "撒漏",
        "notes": "打翻一包",
    })
    assert accepted.status_code == 200
    assert accepted.json()["events"][0]["event_type"] == "waste"
    assert accepted.json()["events"][0]["metadata"]["reason"] == "撒漏"

    persisted = client.get(f"/api/projects/{project_id}/skus/{sku['id']}").json()["sku"]
    assert persisted["stock_by_location"]["store"] == 8
    assert persisted["current_stock"] == 8


def test_daily_usage_is_integer_only_and_duplicate_post_requires_overwrite(tmp_path, monkeypatch):
    client = inventory_client(tmp_path, monkeypatch)
    project_id = "daily-usage-guard"
    sku = create_test_sku(client, project_id, stock=10)

    decimal = client.post(f"/api/projects/{project_id}/skus/usage-logs", json={
        "date": "2026-07-27",
        "location": "operational",
        "items": [{"sku_id": sku["id"], "quantity": 0.3}],
        "source": "paper_daily_usage",
    })
    assert decimal.status_code == 400
    assert "只能填写整数" in decimal.json()["detail"]

    accepted = client.post(f"/api/projects/{project_id}/skus/usage-logs", json={
        "date": "2026-07-27",
        "location": "operational",
        "items": [{"sku_id": sku["id"], "quantity": 2}],
        "source": "paper_daily_usage",
    })
    assert accepted.status_code == 200

    duplicate = client.post(f"/api/projects/{project_id}/skus/usage-logs", json={
        "date": "2026-07-27",
        "location": "operational",
        "items": [{"sku_id": sku["id"], "quantity": 3}],
        "source": "paper_daily_usage",
    })
    assert duplicate.status_code == 400
    assert "覆盖保存" in duplicate.json()["detail"]


def test_daily_usage_overwrite_restores_old_deduction_and_updates_cost_summary(tmp_path, monkeypatch):
    client = inventory_client(tmp_path, monkeypatch)
    project_id = "daily-usage-overwrite"
    sku = create_test_sku(client, project_id, stock=10)
    category_update = client.patch(f"/api/projects/{project_id}/skus/{sku['id']}", json={
        "category": "常温食材",
    })
    assert category_update.status_code == 200
    client.post(f"/api/projects/{project_id}/skus/transfer", json={
        "date": "2026-07-27",
        "from_location": "unallocated",
        "to_location": "store",
        "items": [{"sku_id": sku["id"], "quantity": 3}],
    })
    client.post(f"/api/projects/{project_id}/skus/transfer", json={
        "date": "2026-07-27",
        "from_location": "unallocated",
        "to_location": "warehouse",
        "items": [{"sku_id": sku["id"], "quantity": 7}],
    })

    first = client.put(f"/api/projects/{project_id}/skus/usage-logs/2026-07-27", json={
        "date": "2026-07-27",
        "location": "operational",
        "items": [{"sku_id": sku["id"], "quantity": 5}],
        "source": "paper_daily_usage",
    })
    assert first.status_code == 200
    current = client.get(f"/api/projects/{project_id}/skus/{sku['id']}").json()["sku"]
    assert current["stock_by_location"]["store"] == 0
    assert current["stock_by_location"]["warehouse"] == 5

    corrected = client.put(f"/api/projects/{project_id}/skus/usage-logs/2026-07-27", json={
        "date": "2026-07-27",
        "location": "operational",
        "items": [{"sku_id": sku["id"], "quantity": 2}],
        "source": "paper_daily_usage",
    })
    assert corrected.status_code == 200
    current = client.get(f"/api/projects/{project_id}/skus/{sku['id']}").json()["sku"]
    assert current["stock_by_location"]["store"] == 1
    assert current["stock_by_location"]["warehouse"] == 7
    assert current["current_stock"] == 8

    summary = client.get(
        f"/api/projects/{project_id}/skus/usage-summary/2026-07-27"
    ).json()
    assert summary["recorded_sku_count"] == 1
    assert summary["rows"][0]["quantity"] == 2
    assert summary["usage_cost"] == 53.0
    assert "不等于已确认商品毛利" in summary["cost_basis"]

    price_change = client.patch(f"/api/projects/{project_id}/skus/{sku['id']}", json={
        "unit_cost": 99,
    })
    assert price_change.status_code == 200
    summary_after_price_change = client.get(
        f"/api/projects/{project_id}/skus/usage-summary/2026-07-27"
    ).json()
    assert summary_after_price_change["usage_cost"] == 53.0
    assert summary_after_price_change["rows"][0]["unit_cost"] == 26.5

    period_cost = sku_model.SkuCatalog.load(project_id).period_usage_cost_summary(
        "2026-07-27", "2026-07-27"
    )
    assert period_cost["food_cost"] == 53.0
    assert period_cost["status"] == "estimated_from_daily_usage"

    ledger = FinanceLedger(tmp_path / "finance.db")
    ledger.initialize()
    ledger.ensure_store(project_id, "test", "2026-07-01")
    finance = ledger.finance_overview(project_id, "2026-07-27", "2026-07-27")
    assert finance["known_operating_cost_minor"] == 0
    assert finance["estimated_adjustments_minor"]["food_cost"] == 5300
    assert finance["inventory_usage_bridge"]["food_cost"] == 53.0
    assert "不自动过账" in finance["inventory_usage_bridge"]["accounting_boundary"]


def test_daily_usage_overwrite_rolls_back_when_correction_is_invalid(tmp_path, monkeypatch):
    client = inventory_client(tmp_path, monkeypatch)
    project_id = "daily-usage-invalid-correction"
    sku = create_test_sku(client, project_id, stock=6)

    first = client.put(f"/api/projects/{project_id}/skus/usage-logs/2026-07-27", json={
        "date": "2026-07-27",
        "location": "operational",
        "items": [{"sku_id": sku["id"], "quantity": 2}],
        "source": "paper_daily_usage",
    })
    assert first.status_code == 200

    rejected = client.put(f"/api/projects/{project_id}/skus/usage-logs/2026-07-27", json={
        "date": "2026-07-27",
        "location": "operational",
        "items": [{"sku_id": sku["id"], "quantity": 0.3}],
        "source": "paper_daily_usage",
    })
    assert rejected.status_code == 400

    persisted = client.get(f"/api/projects/{project_id}/skus/{sku['id']}").json()["sku"]
    assert persisted["current_stock"] == 4
    summary = client.get(f"/api/projects/{project_id}/skus/usage-summary/2026-07-27").json()
    assert summary["rows"][0]["quantity"] == 2


def test_operational_usage_records_shortfall_without_creating_negative_stock(tmp_path, monkeypatch):
    client = inventory_client(tmp_path, monkeypatch)
    project_id = "daily-usage-shortfall"
    sku = create_test_sku(client, project_id, stock=2)

    response = client.put(f"/api/projects/{project_id}/skus/usage-logs/2026-07-27", json={
        "date": "2026-07-27",
        "location": "operational",
        "items": [{"sku_id": sku["id"], "quantity": 5}],
        "source": "paper_daily_usage",
    })
    assert response.status_code == 200

    persisted = client.get(f"/api/projects/{project_id}/skus/{sku['id']}").json()["sku"]
    assert persisted["current_stock"] == 0
    summary = client.get(f"/api/projects/{project_id}/skus/usage-summary/2026-07-27").json()
    assert summary["shortfall_sku_count"] == 1
    assert summary["rows"][0]["shortfall"] == 3


def test_forecast_excludes_non_replenishable_low_value_items(tmp_path, monkeypatch):
    client = inventory_client(tmp_path, monkeypatch)
    project_id = "forecast-reorder-boundary"
    sku = create_test_sku(client, project_id, stock=10)
    update = client.patch(f"/api/projects/{project_id}/skus/{sku['id']}", json={
        "reorder_enabled": False,
    })
    assert update.status_code == 200

    forecast = client.get(f"/api/projects/{project_id}/skus/forecast").json()["forecast"]
    assert all(row["sku_id"] != sku["id"] for row in forecast)
