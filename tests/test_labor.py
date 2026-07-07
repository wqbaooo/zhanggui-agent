#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from fastapi.testclient import TestClient

import models.labor as labor_model
import models.project as project_model
from models.labor import LaborTracking, StaffMember, WorkRecord
from server.main import app


def test_wage_rules_cover_hourly_monthly_overtime_and_owner_cost(tmp_path, monkeypatch):
    monkeypatch.setattr(labor_model, "PROJECT_DATA_DIR", tmp_path)
    tracking = LaborTracking.create("wage-rules-store")

    hourly = tracking.add_staff(StaffMember(
        name="兼职",
        pay_type="hourly",
        hourly_wage=20,
    ))
    monthly = tracking.add_staff(StaffMember(
        name="店员",
        pay_type="monthly",
        monthly_base=5200,
        standard_monthly_work_days=26,
    ))
    owner = tracking.add_staff(StaffMember(
        name="老板",
        role="老板",
        pay_type="owner",
        monthly_base=6000,
    ))

    tracking.record_work(WorkRecord(
        staff_id=hourly.id,
        date="2026-06-01",
        hours=8,
        overtime_hours=2,
    ))
    for day in range(1, 14):
        tracking.record_work(WorkRecord(
            staff_id=monthly.id,
            date=f"2026-06-{day:02d}",
            hours=8,
            overtime_hours=2 if day == 1 else 0,
        ))

    hourly_wage = tracking.monthly_wage(hourly.id, "2026-06")
    assert hourly_wage["regular_pay"] == 160
    assert hourly_wage["overtime_pay"] == 60
    assert hourly_wage["total_wage"] == 220

    monthly_wage = tracking.monthly_wage(monthly.id, "2026-06")
    assert monthly_wage["attendance_ratio"] == 0.5
    assert monthly_wage["base_pay"] == 2600
    assert monthly_wage["overtime_pay"] == 75
    assert monthly_wage["total_wage"] == 2675

    owner_wage = tracking.monthly_wage(owner.id, "2026-06")
    assert owner_wage["cost_basis"] == "owner_opportunity_cost"
    assert owner_wage["work_days"] == 0
    assert owner_wage["total_wage"] == 6000


def test_labor_api_validates_records_and_finalizes_month_to_operations(tmp_path, monkeypatch):
    monkeypatch.setattr(labor_model, "PROJECT_DATA_DIR", tmp_path)
    monkeypatch.setattr(project_model, "PROJECT_DATA_DIR", tmp_path)
    client = TestClient(app)
    project_id = "labor-finalize-store"

    staff_res = client.post(f"/api/projects/{project_id}/labor/staff", json={
        "name": "兼职",
        "role": "兼职",
        "pay_type": "hourly",
        "hourly_wage": 25,
    })
    assert staff_res.status_code == 200
    staff_id = staff_res.json()["staff"]["id"]

    missing_staff = client.post(f"/api/projects/{project_id}/labor/records", json={
        "staff_id": "missing",
        "date": "2026-06-01",
        "hours": 8,
    })
    assert missing_staff.status_code == 404

    invalid_record = client.post(f"/api/projects/{project_id}/labor/records", json={
        "staff_id": staff_id,
        "date": "2026-06-01",
        "hours": -1,
    })
    assert invalid_record.status_code == 422

    for date in ("2026-06-01", "2026-06-02"):
        record_res = client.post(f"/api/projects/{project_id}/labor/records", json={
            "staff_id": staff_id,
            "date": date,
            "hours": 8,
        })
        assert record_res.status_code == 200
        operation_res = client.post(f"/api/projects/{project_id}/operations", json={
            "date": date,
            "revenue": 1000,
            "orders": 40,
        })
        assert operation_res.status_code == 200

    finalize = client.post(
        f"/api/projects/{project_id}/labor/wages/finalize",
        params={"year_month": "2026-06"},
    )
    assert finalize.status_code == 200
    payload = finalize.json()
    assert payload["total_wage"] == 400
    assert payload["operation_days"] == 2
    assert payload["daily_labor_allocated"] == 200

    operations = client.get(f"/api/projects/{project_id}/operations?days=30").json()["entries"]
    assert [entry["labor"] for entry in operations] == [200, 200]

    # 重试应覆盖同月人工成本，而不是重复累加。
    retry = client.post(
        f"/api/projects/{project_id}/labor/wages/finalize",
        params={"year_month": "2026-06"},
    )
    assert retry.status_code == 200
    operations = client.get(f"/api/projects/{project_id}/operations?days=30").json()["entries"]
    assert sum(entry["labor"] for entry in operations) == 400
