#!/usr/bin/env python3
"""门店水电记录：兼容旧数组格式并提供幂等月度写入。"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from config import PROJECT_DATA_DIR
from models.json_store import atomic_write_json, load_json


def _path(project_id: str) -> Path:
    return PROJECT_DATA_DIR / project_id / "utilities.json"


def load_utilities(project_id: str) -> list[dict[str, Any]]:
    path = _path(project_id)
    payload = load_json(path, expected_type=(dict, list))
    if payload is None:
        return []
    records = payload.get("records", []) if isinstance(payload, dict) else payload
    return sorted(records, key=lambda item: str(item.get("month", "")))


def upsert_utility(project_id: str, record: dict[str, Any]) -> list[dict[str, Any]]:
    records = load_utilities(project_id)
    updated = False
    for index, existing in enumerate(records):
        if existing.get("month") == record["month"]:
            records[index] = record
            updated = True
            break
    if not updated:
        records.append(record)
    records.sort(key=lambda item: str(item.get("month", "")))

    path = _path(project_id)
    atomic_write_json(
        path,
        {"project_id": project_id, "records": records, "updated_at": time.time()},
    )
    return records
