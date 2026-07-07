#!/usr/bin/env python3
"""数据溯源与导入审计闭环测试。"""

import csv
import io
import json
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

import config
import models.project as project_model
from server.main import app


def _make_csv(rows: list[dict]) -> io.BytesIO:
    if not rows:
        return io.BytesIO(b"")
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    return io.BytesIO(output.getvalue().encode("utf-8-sig"))


def test_csv_preview_does_not_write(tmp_path, monkeypatch):
    """CSV preview 只解析不写入 daily_operations。"""
    monkeypatch.setattr(config, "PROJECT_DATA_DIR", tmp_path)
    monkeypatch.setattr(project_model, "PROJECT_DATA_DIR", tmp_path)
    client = TestClient(app)
    pid = "test-csv-preview"

    csv_file = _make_csv([
        {"日期": "2026-06-01", "营收": "2000", "订单数": "50"},
        {"日期": "2026-06-02", "营收": "2200", "订单数": "55"},
    ])

    preview_res = client.post(
        f"/api/projects/{pid}/import-csv/preview",
        files={"file": ("test.csv", csv_file, "text/csv")},
    )
    assert preview_res.status_code == 200
    preview = preview_res.json()
    assert preview["success"] is True
    assert preview["preview_count"] == 2
    assert len(preview["preview_rows"]) == 2
    assert preview["preview_rows"][0]["date"] == "2026-06-01"

    # 确认预览没写入
    ops_res = client.get(f"/api/projects/{pid}/operations?days=30")
    assert ops_res.status_code == 200
    assert len(ops_res.json()["entries"]) == 0


def test_csv_confirm_writes_with_source_trace(tmp_path, monkeypatch):
    """CSV confirm 写入且附带 source_trace。"""
    monkeypatch.setattr(config, "PROJECT_DATA_DIR", tmp_path)
    monkeypatch.setattr(project_model, "PROJECT_DATA_DIR", tmp_path)
    client = TestClient(app)
    pid = "test-csv-confirm"

    csv_file = _make_csv([
        {"日期": "2026-06-01", "营收": "2000", "订单数": "50"},
    ])

    confirm_res = client.post(
        f"/api/projects/{pid}/import-csv/confirm?strategy=overwrite",
        files={"file": ("test.csv", csv_file, "text/csv")},
    )
    assert confirm_res.status_code == 200
    data = confirm_res.json()
    assert data["imported"] == 1
    assert data["strategy"] == "overwrite"

    # 验证 source_trace 已写入
    ops_res = client.get(f"/api/projects/{pid}/operations?days=30")
    entries = ops_res.json()["entries"]
    assert len(entries) == 1
    entry = entries[0]
    assert entry["source_type"] == "csv"
    assert entry["source_platform"] == "unknown"
    assert entry["source_file_name"] == "test.csv"
    assert entry["source_confidence"] == "high"
    assert entry["source_quality_score"] in ("A", "B", "C", "D")


def test_csv_overwrite_vs_merge_vs_skip(tmp_path, monkeypatch):
    """overwrite / merge / skip_duplicates 三种策略行为正确。"""
    monkeypatch.setattr(config, "PROJECT_DATA_DIR", tmp_path)
    monkeypatch.setattr(project_model, "PROJECT_DATA_DIR", tmp_path)
    client = TestClient(app)
    pid = "test-csv-strategies"

    # 先用手动录入创建一条
    manual_res = client.post(f"/api/projects/{pid}/operations", json={
        "date": "2026-06-01", "revenue": 1000, "orders": 30,
        "food_cost": 400, "labor": 200,
        "source_type": "manual",
    })
    assert manual_res.status_code == 200

    # skip_duplicates: 不覆盖
    csv1 = _make_csv([{"日期": "2026-06-01", "营收": "9999", "订单数": "99"}])
    skip_res = client.post(
        f"/api/projects/{pid}/import-csv/confirm?strategy=skip_duplicates",
        files={"file": ("skip.csv", csv1, "text/csv")},
    )
    assert skip_res.status_code == 200
    assert skip_res.json()["imported"] == 1  # add_daily_operation 被调用但 skip 后不写入

    ops = client.get(f"/api/projects/{pid}/operations?days=30").json()["entries"]
    assert len(ops) == 1
    assert ops[0]["revenue"] == 1000  # 原始值保留
    assert ops[0]["source_type"] == "manual"

    # overwrite: 直接替换
    csv2 = _make_csv([{"日期": "2026-06-01", "营收": "3000", "订单数": "80"}])
    overwrite_res = client.post(
        f"/api/projects/{pid}/import-csv/confirm?strategy=overwrite",
        files={"file": ("overwrite.csv", csv2, "text/csv")},
    )
    assert overwrite_res.status_code == 200

    ops = client.get(f"/api/projects/{pid}/operations?days=30").json()["entries"]
    assert len(ops) == 1
    assert ops[0]["revenue"] == 3000
    assert ops[0]["orders"] == 80
    assert ops[0]["source_type"] == "csv"  # source_type 被覆盖

    # merge: 保留旧非零字段（新数据质量低时旧数据优先）
    csv3 = _make_csv([{"日期": "2026-06-01", "订单数": "90", "营收": "3200"}])  # 有营收+订单，质量够
    merge_res = client.post(
        f"/api/projects/{pid}/import-csv/confirm?strategy=merge",
        files={"file": ("merge.csv", csv3, "text/csv")},
    )
    assert merge_res.status_code == 200

    ops = client.get(f"/api/projects/{pid}/operations?days=30").json()["entries"]
    assert len(ops) == 1
    # 旧营收 3000 被覆盖（新数据有营收且同质量分 csv>csv）
    assert ops[0]["revenue"] == 3200
    # 新订单覆盖旧值
    assert ops[0]["orders"] == 90


def test_source_quality_score(tmp_path, monkeypatch):
    """source_quality_score 计算正确。"""
    monkeypatch.setattr(config, "PROJECT_DATA_DIR", tmp_path)
    monkeypatch.setattr(project_model, "PROJECT_DATA_DIR", tmp_path)
    from models.project import _compute_source_quality

    # A: csv + high + 4核心字段
    assert _compute_source_quality({
        "source_type": "csv", "source_confidence": "high",
        "revenue": 1000, "orders": 50, "food_cost": 400, "labor": 200,
    }) == "A"

    # B: ocr + medium + 2核心字段
    assert _compute_source_quality({
        "source_type": "ocr", "source_confidence": "medium",
        "revenue": 1000, "orders": 50, "food_cost": 0, "labor": 0,
    }) == "B"

    # C: manual + 2字段
    assert _compute_source_quality({
        "source_type": "manual", "source_confidence": "low",
        "revenue": 1000, "orders": 50, "food_cost": 0, "labor": 0,
    }) == "C"

    # D: estimated 无字段
    assert _compute_source_quality({
        "source_type": "estimated",
        "revenue": 0, "orders": 0, "food_cost": 0, "labor": 0,
    }) == "D"


def test_csv_warning_revenue_lt_delivery(tmp_path, monkeypatch):
    """总营收 < 外卖营收时返回 warning。"""
    monkeypatch.setattr(config, "PROJECT_DATA_DIR", tmp_path)
    monkeypatch.setattr(project_model, "PROJECT_DATA_DIR", tmp_path)
    client = TestClient(app)
    pid = "test-csv-warning"

    csv_file = _make_csv([
        {"日期": "2026-06-01", "营收": "1000", "美团实收": "1500", "订单数": "30"},
    ])

    preview_res = client.post(
        f"/api/projects/{pid}/import-csv/preview",
        files={"file": ("warn.csv", csv_file, "text/csv")},
    )
    assert preview_res.status_code == 200
    warnings = preview_res.json()["warnings"]
    assert any("外卖营收" in w for w in warnings)
