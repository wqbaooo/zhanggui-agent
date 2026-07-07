#!/usr/bin/env python3
"""将接店初始库存迁移为总部规格一致、老板可读的库存单位。

只转换能够从总部资料和接店盘存明确确认的项目。未知的收银纸、标签纸等
保留原数量并标记待首次实盘，避免为了“统一”而伪造数据。
"""

from __future__ import annotations

import time
from pathlib import Path
import sys
from typing import Any, Dict

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import PROJECT_DATA_DIR
from models.json_store import atomic_write_json, load_json


PROJECT_ID = "xinyu-hengtai-dakou"
DATA_FILE = PROJECT_DATA_DIR / PROJECT_ID / "skus.json"


SKU_RULES: Dict[str, Dict[str, Any]] = {
    "sku-hq-001": {
        "image": "/hq-skus/product-11.jpg", "spec": "箱/10包/2kg", "unit": "包",
        "standard_unit": "包", "tracking": "open_pack", "from_unit": "kg", "factor": 0.5,
    },
    "sku-hq-006": {
        "image": "/hq-skus/product-24.jpg", "spec": "箱/10包/1kg", "unit": "包",
        "standard_unit": "包", "tracking": "open_pack", "from_unit": "kg", "factor": 1.0,
    },
    "sku-hq-009": {
        "image": "/hq-skus/product-02.jpg", "spec": "件/20捆/50个", "unit": "个",
        "standard_unit": "捆", "tracking": "periodic_count",
    },
    "sku-hq-014": {
        "image": "/hq-skus/product-19.jpg", "spec": "箱/8包/2kg", "unit": "包",
        "standard_unit": "包", "tracking": "open_pack", "from_unit": "kg", "factor": 1.0,
    },
    "sku-1782927595984-17": {
        "image": "/hq-skus/product-14.jpg", "spec": "箱/50包", "unit": "包",
        "standard_unit": "包", "tracking": "open_pack",
    },
    "sku-1782927595988-18": {
        "image": "/hq-skus/product-12.jpg", "spec": "箱/10袋/1kg", "unit": "袋",
        "standard_unit": "袋", "tracking": "open_pack", "from_unit": "箱", "factor": 10.0,
    },
    "sku-1782927595991-19": {
        "image": "/hq-skus/product-13.jpg", "spec": "箱/10袋/1kg", "unit": "袋",
        "standard_unit": "袋", "tracking": "open_pack", "from_unit": "箱", "factor": 10.0,
    },
    "sku-1782927595994-20": {
        "image": "/hq-skus/product-16.jpg", "spec": "箱/12包/1kg", "unit": "包",
        "standard_unit": "包", "tracking": "open_pack",
    },
    "sku-1782927595998-21": {
        "image": "/hq-skus/product-17.jpg", "spec": "箱/12包/1kg", "unit": "包",
        "standard_unit": "包", "tracking": "open_pack",
    },
    "sku-1782927596001-22": {
        "spec": "包/1kg", "unit": "包", "standard_unit": "包", "tracking": "open_pack",
    },
    "sku-1782927596005-23": {
        "image": "/hq-skus/product-23.jpg", "spec": "箱/10包/1kg", "unit": "包",
        "standard_unit": "包", "tracking": "open_pack",
    },
    "sku-1782927596008-24": {
        "image": "/hq-skus/product-22.jpg", "spec": "箱/4包/2.5kg", "unit": "包",
        "standard_unit": "包", "tracking": "open_pack",
    },
    "sku-1782927596013-25": {
        "image": "/hq-skus/product-20.jpg", "spec": "箱/5包/500g", "unit": "包",
        "standard_unit": "包", "tracking": "open_pack",
    },
    "sku-1782927596017-26": {
        "image": "/hq-skus/product-01.jpg", "spec": "箱/1000个", "unit": "个",
        "standard_unit": "箱", "tracking": "periodic_count", "from_unit": "箱", "factor": 1000.0,
    },
    "sku-1782927596019-27": {
        "image": "/hq-skus/product-03.jpg", "spec": "箱/1500个", "unit": "个",
        "standard_unit": "箱", "tracking": "periodic_count", "from_unit": "箱", "factor": 1500.0,
    },
    "sku-1782927596022-28": {
        "image": "/hq-skus/product-04.jpg", "spec": "件/50把/100个", "unit": "个",
        "standard_unit": "把", "tracking": "periodic_count", "from_unit": "捆", "factor": 100.0,
    },
    "sku-1782927596025-29": {
        "image": "/hq-skus/product-08.jpg", "spec": "箱/50卷", "tracking": "periodic_count",
    },
    "sku-1782927596032-30": {
        "image": "/hq-skus/product-09.jpg", "spec": "箱/100卷", "tracking": "periodic_count",
    },
    "sku-1782927596035-31": {
        "image": "/hq-skus/product-10.jpg", "spec": "箱/600个", "unit": "个",
        "standard_unit": "箱", "tracking": "periodic_count", "from_unit": "批", "factor": 300.0,
        "name": "全家福盒",
    },
    "sku-1782927596038-32": {
        "image": "/hq-skus/product-05.jpg", "spec": "箱/600个", "unit": "个",
        "standard_unit": "箱", "tracking": "periodic_count", "from_unit": "批", "factor": 600.0,
    },
}


def migrate() -> None:
    payload = load_json(DATA_FILE)
    if payload is None:
        raise SystemExit(f"missing inventory data: {DATA_FILE}")

    conversion_by_id: Dict[str, float] = {}
    now = time.time()
    for sku in payload.get("skus", []):
        rule = SKU_RULES.get(sku.get("id"))
        if not rule:
            # 历史总部目录中零库存且没有接店盘存证据的项目不进入当前盘点清单。
            if float(sku.get("current_stock", 0) or 0) == 0 and sku.get("id", "").startswith("sku-hq-"):
                sku["active"] = False
            continue

        old_unit = sku.get("unit", "")
        factor = 1.0
        if rule.get("from_unit") == old_unit:
            factor = float(rule.get("factor", 1.0))
            sku["current_stock"] = round(float(sku.get("current_stock", 0) or 0) * factor, 4)
            if factor:
                sku["unit_cost"] = round(float(sku.get("unit_cost", 0) or 0) / factor, 6)
            conversion_by_id[sku["id"]] = factor

        if rule.get("name"):
            sku["name"] = rule["name"]
        if rule.get("image"):
            sku["hq_image"] = rule["image"]
        if rule.get("spec"):
            sku["spec"] = rule["spec"]
        if rule.get("unit"):
            sku["unit"] = rule["unit"]
            sku["display_unit"] = rule["unit"]
        else:
            sku["display_unit"] = sku.get("unit", "")
        if rule.get("standard_unit"):
            sku["standard_unit"] = rule["standard_unit"]
        sku["tracking_mode"] = rule.get("tracking", "periodic_count")
        sku["active"] = True
        sku["stock_by_location"] = {
            "unallocated": round(float(sku.get("current_stock", 0) or 0), 4),
        } if float(sku.get("current_stock", 0) or 0) else {}
        sku["updated_at"] = now

    for purchase in payload.get("purchases", []):
        for item in purchase.get("items", []):
            factor = conversion_by_id.get(item.get("sku_id"))
            if not factor:
                continue
            item["quantity"] = round(float(item.get("quantity", 0) or 0) * factor, 4)
            item["unit_cost"] = round(float(item.get("unit_cost", 0) or 0) / factor, 6)
            item["subtotal"] = round(item["quantity"] * item["unit_cost"], 2)
        purchase["total_cost"] = round(sum(
            float(item.get("subtotal", 0) or 0) for item in purchase.get("items", [])
        ), 2)

    payload.setdefault("inventory_events", [])
    payload.setdefault("inventory_counts", [])
    payload.setdefault("usage_logs", [])
    payload["updated_at"] = now
    atomic_write_json(DATA_FILE, payload)


if __name__ == "__main__":
    migrate()
    print(f"inventory v2 migrated: {DATA_FILE}")
