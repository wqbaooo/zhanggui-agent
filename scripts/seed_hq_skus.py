#!/usr/bin/env python3
"""总部 SKU 目录导入脚本。

读取总部商品目录 JSON，与现有 SKU 匹配：
- 名称匹配上的：补全总部字段（hq_name/hq_category/spec/standard_unit 等）
- 没匹配上的：新建 SKU
- 支持重复执行（幂等）
"""

import json
import sys
import time
from pathlib import Path
from typing import List, Dict, Optional

PROJECT_ID = "xinyu-hengtai-dakou"
PROJECT_DIR = Path(__file__).resolve().parent.parent / "project_data" / PROJECT_ID
HQ_SKU_FILE = PROJECT_DIR / "hq_skus" / "hq_sku_catalog.json"
SKU_FILE = PROJECT_DIR / "skus.json"


def name_similar(a: str, b: str) -> bool:
    """简单名称匹配：去掉空格和常见后缀后，判断是否互相包含。"""
    def normalize(s: str) -> str:
        for ch in [" ", "（", "）", "(", ")", "·", "、", "/"]:
            s = s.replace(ch, "")
        return s.lower()
    na, nb = normalize(a), normalize(b)
    if not na or not nb:
        return False
    return na in nb or nb in na


def find_match(hq_name: str, existing_skus: List[Dict]) -> Optional[Dict]:
    """在现有 SKU 中找名称匹配的。"""
    for sku in existing_skus:
        if name_similar(hq_name, sku.get("name", "")):
            return sku
    return None


def main():
    if not HQ_SKU_FILE.exists():
        print(f"错误：找不到总部SKU文件 {HQ_SKU_FILE}")
        sys.exit(1)

    with open(HQ_SKU_FILE, "r", encoding="utf-8") as f:
        hq_data = json.load(f)
    hq_skus = hq_data.get("skus", [])
    print(f"读取到 {len(hq_skus)} 个总部SKU")

    if SKU_FILE.exists():
        with open(SKU_FILE, "r", encoding="utf-8") as f:
            sku_data = json.load(f)
    else:
        sku_data = {"project_id": PROJECT_ID, "skus": []}
    existing = sku_data.get("skus", [])
    print(f"现有 {len(existing)} 个 SKU")

    now = time.time()
    matched_count = 0
    new_count = 0
    matched_ids = set()

    for hq in hq_skus:
        hq_name = hq.get("hq_name", "")
        if not hq_name:
            continue

        match = find_match(hq_name, existing)
        if match:
            match["hq_name"] = hq_name
            match["hq_category"] = hq.get("hq_category", "")
            match["hq_image"] = hq.get("hq_image", "")
            match["standard_unit"] = hq.get("standard_unit", "")
            match["spec"] = hq.get("spec", "")
            match["pack_quantity"] = hq.get("pack_quantity", 0.0)
            if hq.get("internal_category"):
                match["category"] = hq["internal_category"]
            if hq.get("internal_unit") and not match.get("unit"):
                match["unit"] = hq["internal_unit"]
            if not match.get("supplier"):
                match["supplier"] = "总部"
            match["updated_at"] = now
            matched_count += 1
            matched_ids.add(match["id"])
            print(f"  匹配: {hq_name} → {match['name']}")
        else:
            new_id = f"sku-hq-{new_count + 1:03d}"
            new_sku = {
                "id": new_id,
                "name": hq_name,
                "category": hq.get("internal_category", "其他"),
                "unit": hq.get("internal_unit", "个"),
                "safety_stock": 0.0,
                "current_stock": 0.0,
                "unit_cost": 0.0,
                "supplier": "总部",
                "batch_cycle_days": 14,
                "consumption_per_day": 0.0,
                "last_purchase_date": "",
                "next_purchase_est": "",
                "status": "正常",
                "notes": hq.get("notes", ""),
                "hq_name": hq_name,
                "hq_category": hq.get("hq_category", ""),
                "hq_image": hq.get("hq_image", ""),
                "standard_unit": hq.get("standard_unit", ""),
                "spec": hq.get("spec", ""),
                "pack_quantity": hq.get("pack_quantity", 0.0),
                "created_at": now,
                "updated_at": now,
            }
            existing.append(new_sku)
            new_count += 1
            print(f"  新增: {hq_name}")

    sku_data["skus"] = existing
    with open(SKU_FILE, "w", encoding="utf-8") as f:
        json.dump(sku_data, f, ensure_ascii=False, indent=2)

    print(f"\n完成：匹配 {matched_count} 个，新增 {new_count} 个，总计 {len(existing)} 个 SKU")


if __name__ == "__main__":
    main()
