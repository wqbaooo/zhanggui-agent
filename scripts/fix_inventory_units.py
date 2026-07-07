#!/usr/bin/env python3
"""修复 2026-07-03 接店盘点中的单位换算错误。

问题：员工纸质盘点表把「外卖无纺布袋 11 捆」「塑料袋 3 把」按总部包装单位记录，
旧迁移逻辑直接把 11/3 当成核算单位「个」，导致 98%–99% 虚假盘亏。

本脚本：
1. 给相关 SKU 补 count_units/display_unit；
2. 把 current_stock / stock_by_location 修正为核算单位数量；
3. 修正 2026-07-03 盘点记录与事件中的数量、差异。
"""

import json
from pathlib import Path

PROJECT_ID = "xinyu-hengtai-dakou"
DATA_DIR = Path(__file__).resolve().parent.parent / "project_data" / PROJECT_ID
SKUS_PATH = DATA_DIR / "skus.json"


def load() -> dict:
    return json.loads(SKUS_PATH.read_text(encoding="utf-8"))


def save(data: dict):
    SKUS_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def find_sku(skus: list, sku_id: str) -> dict:
    for s in skus:
        if s.get("id") == sku_id:
            return s
    raise ValueError(f"sku {sku_id} not found")


def fix_bag(skus: list, events: list, counts: list):
    """外卖无纺布袋：1 捆 = 50 个。盘点 11 捆 = 550 个。"""
    sku = find_sku(skus, "sku-hq-009")
    sku["display_unit"] = "捆"
    sku["count_units"] = [{"unit": "捆", "conversion": 50, "base_unit": "个"}]
    sku["current_stock"] = 550.0
    sku["stock_by_location"] = {"unallocated": 0.0, "store": 550.0}
    sku["notes"] = "2026-07-03 员工物料盘点表：11 捆 = 550 个；已修正单位换算"

    expected = 1000.0
    counted = 550.0
    variance = round(counted - expected, 4)
    for line in counts[0]["lines"]:
        if line["sku_id"] == sku["id"]:
            line["display_unit"] = "捆"
            line["input_quantity"] = 11.0
            line["input_unit"] = "捆"
            line["expected_quantity"] = expected
            line["counted_quantity"] = counted
            line["variance_quantity"] = variance
            line["variance_rate"] = round(variance / expected, 4)
            line["notes"] = "已修正：盘点表「11」为 11 捆，1 捆=50 个"

    for event in events:
        if event.get("sku_id") == sku["id"] and event.get("event_type") == "count_adjustment":
            event["quantity"] = abs(variance)
            event["metadata"]["expected_quantity"] = expected
            event["metadata"]["counted_quantity"] = counted
            event["metadata"]["signed_variance"] = variance
            event["metadata"]["input_quantity"] = 11.0
            event["metadata"]["input_unit"] = "捆"
            event["metadata"]["base_unit"] = "个"
            event["notes"] = "已修正单位换算：11 捆 = 550 个"


def fix_plastic_bag(skus: list, events: list, counts: list):
    """塑料袋：1 把 = 100 个。盘点 3 把 = 300 个。"""
    sku = find_sku(skus, "sku-1782927596022-28")
    sku["display_unit"] = "把"
    sku["count_units"] = [{"unit": "把", "conversion": 100, "base_unit": "个"}]
    sku["current_stock"] = 300.0
    sku["stock_by_location"] = {"unallocated": 0.0, "store": 300.0}
    sku["notes"] = "2026-07-03 员工物料盘点表：3 把 = 300 个；已修正单位换算"

    expected = 500.0
    counted = 300.0
    variance = round(counted - expected, 4)
    for line in counts[0]["lines"]:
        if line["sku_id"] == sku["id"]:
            line["display_unit"] = "把"
            line["input_quantity"] = 3.0
            line["input_unit"] = "把"
            line["expected_quantity"] = expected
            line["counted_quantity"] = counted
            line["variance_quantity"] = variance
            line["variance_rate"] = round(variance / expected, 4)
            line["notes"] = "已修正：盘点表「3」为 3 把，1 把=100 个"

    for event in events:
        if event.get("sku_id") == sku["id"] and event.get("event_type") == "count_adjustment":
            event["quantity"] = abs(variance)
            event["metadata"]["expected_quantity"] = expected
            event["metadata"]["counted_quantity"] = counted
            event["metadata"]["signed_variance"] = variance
            event["metadata"]["input_quantity"] = 3.0
            event["metadata"]["input_unit"] = "把"
            event["metadata"]["base_unit"] = "个"
            event["notes"] = "已修正单位换算：3 把 = 300 个"


def main():
    data = load()
    skus = data["skus"]
    events = data["inventory_events"]
    counts = data["inventory_counts"]

    if not counts:
        print("⚠️ 没有盘点记录可修复")
        return

    fix_bag(skus, events, counts)
    fix_plastic_bag(skus, events, counts)

    save(data)
    print("✅ 已修正库存单位换算：")
    print("  - 外卖无纺布袋：11 捆 = 550 个，盘亏从 -989 修正为 -450")
    print("  - 塑料袋：3 把 = 300 个，盘亏从 -497 修正为 -200")


if __name__ == "__main__":
    main()
