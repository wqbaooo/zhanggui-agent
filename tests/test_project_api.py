#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from fastapi.testclient import TestClient

import config
import models.project as project_model
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
