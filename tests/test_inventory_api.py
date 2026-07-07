from fastapi.testclient import TestClient

import config
import models.sku as sku_model
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
