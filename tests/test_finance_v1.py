#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from fastapi.testclient import TestClient
import config
import models.project as project_model
from server.main import app


def test_finance_statements_basic(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "PROJECT_DATA_DIR", tmp_path)
    monkeypatch.setattr(project_model, "PROJECT_DATA_DIR", tmp_path)
    client = TestClient(app)
    project_id = "finance-v1-test"

    client.put(f"/api/projects/{project_id}/profile", json={
        "profile": {"city": "新余", "brand": "大口章鱼烧", "mode": "加盟"}
    })

    client.post(f"/api/projects/{project_id}/finance/capital-events", json={
        "date": "2026-05-20",
        "event_type": "owner_investment",
        "amount": 50000,
        "reference": "startup-fund",
        "description": "老板投入启动资金",
    })

    client.post(f"/api/projects/{project_id}/finance/entries", json={
        "entry_date": "2026-05-27",
        "description": "现金销售收入",
        "lines": [
            {"account_code": "1001", "debit_minor": 100000},
            {"account_code": "4001", "credit_minor": 100000},
        ],
    })

    client.post(f"/api/projects/{project_id}/finance/entries", json={
        "entry_date": "2026-05-27",
        "description": "食材成本",
        "lines": [
            {"account_code": "5001", "debit_minor": 38000},
            {"account_code": "1001", "credit_minor": 38000},
        ],
    })

    client.post(f"/api/projects/{project_id}/finance/entries", json={
        "entry_date": "2026-05-27",
        "description": "员工工资",
        "lines": [
            {"account_code": "6001", "debit_minor": 20000},
            {"account_code": "1001", "credit_minor": 20000},
        ],
    })

    pl = client.get(f"/api/projects/{project_id}/finance/statements/profit-and-loss")
    assert pl.status_code == 200
    pl_data = pl.json()
    assert pl_data["period_start"] is not None
    assert pl_data["period_end"] is not None
    assert "sections" in pl_data
    assert any(section["label"] == "营业毛利" for section in pl_data["sections"])

    bs = client.get(f"/api/projects/{project_id}/finance/statements/balance-sheet")
    assert bs.status_code == 200
    bs_data = bs.json()
    assert "assets" in bs_data
    assert "liabilities" in bs_data
    assert "equity" in bs_data

    cf = client.get(f"/api/projects/{project_id}/finance/statements/cash-flow")
    assert cf.status_code == 200
    cf_data = cf.json()
    assert "sections" in cf_data
    assert any(section["label"] == "经营活动现金流" for section in cf_data["sections"])


def test_finance_metrics_query(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "PROJECT_DATA_DIR", tmp_path)
    monkeypatch.setattr(project_model, "PROJECT_DATA_DIR", tmp_path)
    client = TestClient(app)
    project_id = "metrics-test"

    client.put(f"/api/projects/{project_id}/profile", json={
        "profile": {"city": "新余", "brand": "大口章鱼烧", "mode": "加盟"}
    })

    client.post(f"/api/projects/{project_id}/finance/capital-events", json={
        "date": "2026-05-20",
        "event_type": "owner_investment",
        "amount": 50000,
        "reference": "startup-fund",
        "description": "老板投入启动资金",
    })

    client.post(f"/api/projects/{project_id}/finance/entries", json={
        "entry_date": "2026-05-27",
        "description": "现金销售收入",
        "lines": [
            {"account_code": "1001", "debit_minor": 100000},
            {"account_code": "4001", "credit_minor": 100000},
        ],
    })

    metrics_list = client.get(f"/api/projects/{project_id}/finance/metrics")
    assert metrics_list.status_code == 200
    assert len(metrics_list.json()["metrics"]) > 0

    revenue = client.get(f"/api/projects/{project_id}/finance/metrics/revenue")
    assert revenue.status_code == 200
    revenue_data = revenue.json()
    assert revenue_data["metric_code"] == "revenue"
    assert revenue_data["value"] is not None


def test_finance_query_with_keywords(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "PROJECT_DATA_DIR", tmp_path)
    monkeypatch.setattr(project_model, "PROJECT_DATA_DIR", tmp_path)
    client = TestClient(app)
    project_id = "query-test"

    client.put(f"/api/projects/{project_id}/profile", json={
        "profile": {"city": "新余", "brand": "大口章鱼烧", "mode": "加盟"}
    })

    client.post(f"/api/projects/{project_id}/finance/capital-events", json={
        "date": "2026-05-20",
        "event_type": "owner_investment",
        "amount": 50000,
        "reference": "startup-fund",
        "description": "老板投入启动资金",
    })

    client.post(f"/api/projects/{project_id}/finance/entries", json={
        "entry_date": "2026-05-27",
        "description": "现金销售收入",
        "lines": [
            {"account_code": "1001", "debit_minor": 100000},
            {"account_code": "4001", "credit_minor": 100000},
        ],
    })

    profit_query = client.post(f"/api/projects/{project_id}/finance/query", json={
        "query": "这个月利润怎么样"
    })
    assert profit_query.status_code == 200
    result = profit_query.json()
    assert "answer" in result
    assert "metrics" in result
    assert "completeness" in result
    assert "formula_trace" in result

    revenue_query = client.post(f"/api/projects/{project_id}/finance/query", json={
        "query": "营业收入是多少"
    })
    assert revenue_query.status_code == 200
    result = revenue_query.json()
    assert any(m["metric_code"] == "revenue" for m in result["metrics"])


def test_reconciliation_endpoints(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "PROJECT_DATA_DIR", tmp_path)
    monkeypatch.setattr(project_model, "PROJECT_DATA_DIR", tmp_path)
    client = TestClient(app)
    project_id = "recon-test"

    client.put(f"/api/projects/{project_id}/profile", json={
        "profile": {"city": "新余", "brand": "大口章鱼烧", "mode": "加盟"}
    })

    client.post(f"/api/projects/{project_id}/operations", json={
        "date": "2026-05-27",
        "revenue": 1000,
        "orders": 40,
        "food_cost": 380,
        "labor": 200,
        "rent_allocated": 150,
        "utility": 30,
        "other_cost": 20,
        "cost_status": "confirmed",
    })

    platforms = client.get(f"/api/projects/{project_id}/finance/reconciliation/platforms")
    assert platforms.status_code == 200

    cash = client.get(f"/api/projects/{project_id}/finance/reconciliation/cash?date=2026-05-27")
    assert cash.status_code == 200

    receivables = client.get(f"/api/projects/{project_id}/finance/reconciliation/receivables")
    assert receivables.status_code == 200


def test_finance_alerts_basic(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "PROJECT_DATA_DIR", tmp_path)
    monkeypatch.setattr(project_model, "PROJECT_DATA_DIR", tmp_path)
    client = TestClient(app)
    project_id = "alerts-test"

    client.put(f"/api/projects/{project_id}/profile", json={
        "profile": {"city": "新余", "brand": "大口章鱼烧", "mode": "加盟"}
    })

    alerts = client.get(f"/api/projects/{project_id}/finance/alerts")
    assert alerts.status_code == 200
    assert isinstance(alerts.json()["alerts"], list)
