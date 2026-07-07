#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from fastapi.testclient import TestClient

import config
import models.project as project_model
import models.utilities as utilities_model
from server.main import app


def test_project_profile_and_operation_lifecycle(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "PROJECT_DATA_DIR", tmp_path)
    monkeypatch.setattr(project_model, "PROJECT_DATA_DIR", tmp_path)

    client = TestClient(app)
    project_id = "test-xinyu-store"

    profile_res = client.put(f"/api/projects/{project_id}/profile", json={
        "profile": {"city": "新余", "brand": "大口章鱼烧", "mode": "加盟"}
    })
    assert profile_res.status_code == 200
    assert profile_res.json()["project"]["profile"]["city"] == "新余"

    transfer_res = client.put(f"/api/projects/{project_id}/site-transfer", json={
        "site_transfer": {"transfer_fee": 30000, "deposit": 10000, "location": "恒太城美食城"}
    })
    assert transfer_res.status_code == 200
    assert transfer_res.json()["project"]["site_transfer"]["transfer_fee"] == 30000

    operation_res = client.post(f"/api/projects/{project_id}/operations", json={
        "date": "2026-05-27",
        "revenue": 1000,
        "orders": 40,
        "bad_reviews": 2,
        "food_cost": 380,
        "labor": 200,
        "rent_allocated": 150,
        "utility": 30,
        "other_cost": 20,
        "takeout_orders": 25,
        "platform_fee": 90,
        "marketing_cost": 50,
        "inventory_loss": 10,
        "notes": "试营业",
    })
    assert operation_res.status_code == 200
    summary = operation_res.json()["summary"]
    assert summary["entry_count"] == 1
    assert summary["net_profit"] == 70
    assert summary["food_cost_rate"] == 0.38
    assert summary["labor_cost_rate"] == 0.2
    assert summary["prime_cost"] == 580
    assert summary["prime_cost_rate"] == 0.58
    assert summary["platform_fee_rate"] == 0.09
    assert summary["total_bad_reviews"] == 2
    assert summary["bad_review_rate"] == 0.05
    assert any("差评率" in alert["message"] for alert in summary["alerts"])

    list_res = client.get(f"/api/projects/{project_id}/operations?days=7")
    assert list_res.status_code == 200
    assert len(list_res.json()["entries"]) == 1

    cockpit_res = client.get(f"/api/projects/{project_id}/cockpit?days=7")
    assert cockpit_res.status_code == 200
    cockpit = cockpit_res.json()
    assert cockpit["operations"]["net_profit"] == 70
    assert cockpit["data_quality"]["has_real_operations"] is True
    assert any(stage["label"] == "选址诊断" for stage in cockpit["stages"])
    assert cockpit["next_actions"]

    action = cockpit["next_actions"][0]
    task_res = client.post(f"/api/projects/{project_id}/tasks", json={
        "title": action["title"],
        "target": action["target"],
        "priority": action["priority"],
        "source": action["source"],
    })
    assert task_res.status_code == 200
    task = task_res.json()["task"]
    assert task["status"] == "todo"

    cockpit_with_task = task_res.json()["cockpit"]
    matching = [
        item for item in cockpit_with_task["next_actions"]
        if item["title"] == action["title"] and item["target"] == action["target"]
    ]
    assert matching
    assert matching[0]["task_id"] == task["id"]
    assert matching[0]["status"] == "todo"

    update_res = client.patch(f"/api/projects/{project_id}/tasks/{task['id']}", json={
        "status": "done",
        "notes": "已完成核验",
    })
    assert update_res.status_code == 200
    assert update_res.json()["task"]["status"] == "done"

    list_tasks_res = client.get(f"/api/projects/{project_id}/tasks")
    assert list_tasks_res.status_code == 200
    assert list_tasks_res.json()["tasks"][0]["notes"] == "已完成核验"

    integrations_res = client.get(f"/api/projects/{project_id}/integrations")
    assert integrations_res.status_code == 200
    integrations = integrations_res.json()["integrations"]
    assert {item["id"] for item in integrations} >= {"meituan", "taobao_flash", "douyin", "pos"}
    assert next(item for item in integrations if item["id"] == "meituan")["status"] == "pending_auth"

    update_integration_res = client.patch(f"/api/projects/{project_id}/integrations/meituan", json={
        "status": "csv_ready",
        "status_label": "可导入报表",
        "notes": "先用商家后台导出",
    })
    assert update_integration_res.status_code == 200
    updated = update_integration_res.json()["integration"]
    assert updated["status"] == "csv_ready"
    assert updated["notes"] == "先用商家后台导出"

    cockpit_after_integration = client.get(f"/api/projects/{project_id}/cockpit?days=7").json()
    meituan = next(item for item in cockpit_after_integration["integrations"] if item["id"] == "meituan")
    assert meituan["status_label"] == "可导入报表"


def test_monthly_operating_history_keeps_revenue_and_profit_separate(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "PROJECT_DATA_DIR", tmp_path)
    monkeypatch.setattr(project_model, "PROJECT_DATA_DIR", tmp_path)
    client = TestClient(app)
    project_id = "monthly-history-store"

    response = client.put(f"/api/projects/{project_id}/monthly", json={
        "entries": [
            {"year": 2025, "month": 1, "net_profit": 12000, "source_file_name": "history.jpg"},
            {"year": 2025, "month": 2, "net_profit": 22000, "source_file_name": "history.jpg"},
            {"year": 2026, "month": 1, "revenue": 37720, "source_file_name": "history.jpg"},
            {"year": 2026, "month": 2, "revenue": 52716, "source_file_name": "history.jpg"},
        ],
        "monthly_rent": 6500,
        "monthly_utility_min": 1500,
        "monthly_utility_max": 1700,
        "wage_per_person": 3500,
        "previous_staff_count": 4,
        "current_staff_count": 1,
        "owner_operates": True,
    })

    assert response.status_code == 200
    summary = response.json()["summary"]
    january = summary["months"][0]
    assert summary["current_year"] == 2026
    assert summary["baseline_year"] == 2025
    assert january["revenue"] == 37720
    assert january["last_year_profit"] == 12000
    assert january["yoy_pct"] is None
    assert january["estimated_profit"] is None
    assert summary["labor"] == 3500
    assert summary["previous_staff_count"] == 4
    assert response.json()["cockpit"]["monthly_comparison"]["comparison_metric"] == "net_profit"

    persisted = project_model.ProjectMemory.load(project_id)
    assert persisted is not None
    assert persisted.profile["previous_monthly_labor"] == 14000
    assert len(persisted.monthly_revenue) == 4


def test_monthly_operating_upsert_is_idempotent_and_validated(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "PROJECT_DATA_DIR", tmp_path)
    monkeypatch.setattr(project_model, "PROJECT_DATA_DIR", tmp_path)
    client = TestClient(app)
    project_id = "monthly-upsert-store"
    url = f"/api/projects/{project_id}/monthly"

    first = client.put(url, json={
        "entries": [{"year": 2026, "month": 1, "revenue": 10000}],
    })
    assert first.status_code == 200
    second = client.put(url, json={
        "entries": [{"year": 2026, "month": 1, "revenue": 12000}],
    })
    assert second.status_code == 200
    assert second.json()["summary"]["records"] == [{
        "year": 2026,
        "month": 1,
        "revenue": 12000.0,
        "net_profit": None,
        "review_status": "confirmed",
        "source_type": "image_confirmed",
        "source_file_name": "",
        "source_raw_text": "",
    }]

    invalid_month = client.put(url, json={
        "entries": [{"year": 2026, "month": 13, "revenue": 1}],
    })
    assert invalid_month.status_code == 422
    missing_metric = client.put(url, json={
        "entries": [{"year": 2026, "month": 1}],
    })
    assert missing_metric.status_code == 400


def test_utilities_are_real_persisted_and_idempotent(tmp_path, monkeypatch):
    monkeypatch.setattr(utilities_model, "PROJECT_DATA_DIR", tmp_path)
    client = TestClient(app)
    project_id = "utility-store"
    url = f"/api/projects/{project_id}/utilities/2026-06"

    first = client.put(url, json={
        "month": "2026-06",
        "water": 195,
        "electricity": 1120,
        "notes": "电费账单已确认",
    })
    assert first.status_code == 200
    assert first.json()["record"]["electricity"] == 1120

    second = client.put(url, json={
        "month": "2026-06",
        "water": 200,
        "electricity": 1090,
        "notes": "按最终账单修正",
    })
    assert second.status_code == 200
    assert len(second.json()["records"]) == 1
    assert second.json()["records"][0]["water"] == 200

    listed = client.get(f"/api/projects/{project_id}/utilities")
    assert listed.status_code == 200
    assert listed.json()["records"][0]["notes"] == "按最终账单修正"

    mismatch = client.put(url, json={
        "month": "2026-07",
        "water": 1,
        "electricity": 1,
    })
    assert mismatch.status_code == 400

    invalid = client.put(f"/api/projects/{project_id}/utilities/2026-13", json={
        "month": "2026-13",
        "water": -1,
        "electricity": 1,
    })
    assert invalid.status_code == 422
