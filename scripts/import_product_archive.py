#!/usr/bin/env python3
"""把老板的商品档案合并进正式 SKU 主档。

设计约束：
- 原 Excel 只读，先复制到门店资料目录作为来源证据；
- 保留现有 SKU id、库存、采购和流水，不重建历史；
- 目录报价仅补缺，不覆盖真实采购形成的单位成本；
- 平替是同一物料的采购来源/规格，不创建第二份库存。
"""

from __future__ import annotations

import json
import re
import shutil
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
PROJECT_ID = "xinyu-hengtai-dakou"
PROJECT_DIR = ROOT / "project_data" / PROJECT_ID
SKU_FILE = PROJECT_DIR / "skus.json"
NORMALIZED_FILE = ROOT / "outputs" / "inventory-module-audit-20260726" / "商品档案.normalized.json"
SOURCE_XLSX = Path.home() / "Desktop" / "大口章鱼烧" / "商品档案.xlsx"
SOURCE_DIR = PROJECT_DIR / "documents" / "source"
MASTER_FILE = SOURCE_DIR / "product_master_20260726.json"
EVIDENCE_FILE = SOURCE_DIR / "商品档案_20260726.xlsx"
BACKUP_FILE = ROOT / "outputs" / "inventory-module-audit-20260726" / "skus.before-product-master.json"


PREFERRED_IDS = {
    "章鱼预拌粉": "sku-hq-001",
    "玉米粒": "sku-hq-006",
    "章鱼烧盒子（4粒）": "sku-1782927596019-27",
    "外卖无纺布袋": "sku-hq-009",
    "竹签": "sku-hq-011",
    "海苔肉松": "sku-hq-014",
    "培根丁": "sku-hq-016",
    "肉肠": "sku-hq-017",
    "调料包": "sku-1782927595984-17",
    "原味酱": "sku-1782927595988-18",
    "香甜酱": "sku-1782927595991-19",
    "藤椒酱": "sku-1782927595994-20",
    "蛋黄酱": "sku-1782927595998-21",
    "章鱼粒": "sku-1782927596005-23",
    "章鱼花": "sku-1782927596008-24",
    "木鱼花": "sku-1782927596013-25",
    "章鱼烧盒子（6粒）": "sku-1782927596017-26",
    "外卖塑料袋": "sku-1782927596022-28",
    "收银纸57*50": "sku-1782927596025-29",
    "标签纸": "sku-1782927596032-30",
    "全家福打包盒": "sku-1782927596035-31",
    "全家福打包盒塑料盖": "sku-1782927596038-32",
    "蛤蜊": "sku-1783274150713-33",
    "纸巾": "sku-1783274150727-34",
    "咸蛋黄": "sku-1783274150741-35",
    "切丝海苔": "sku-1783274150752-36",
}

# 每日表不是“所有库存物料”的缩小版，而是老板确认过、员工每天实际会
# 按开封/领用整数记录的营业物料。其余物料仍保留在主档、进货和阶段盘点中。
DAILY_USAGE_NAMES = {
    "章鱼预拌粉", "调料包", "原味酱", "香甜酱", "藤椒酱", "蛋黄酱", "番茄酱", "芥末酱",
    "木鱼花", "切丝海苔", "青海苔粉", "海苔肉松",
    "章鱼粒", "章鱼花", "玉米粒", "培根丁", "肉肠", "麻辣鲜蛤", "咸蛋黄", "奶酪酱", "芝士", "蟹柳",
    "章鱼烧盒子（4粒）", "章鱼烧盒子（6粒）", "全家福打包盒", "全家福打包盒塑料盖",
    "外卖塑料袋", "外卖无纺布袋", "纸巾", "竹签", "外卖贴纸", "标签纸",
    "收银纸80*80", "收银纸57*50", "烤肠竹签",
}


def clean(value: Any) -> str:
    text = str(value or "").strip()
    return "" if text in {"/", "None", "null"} else text


def number(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def stable_id(sequence: str) -> str:
    return f"sku-master-{int(sequence):03d}"


def inventory_unit_and_conversion(name: str, spec: str, price_unit: str) -> tuple[str, list[dict[str, Any]], float]:
    """返回核算单位、计数换算、报价单位到核算单位的换算数。"""
    # 高频包装按个/根/张核算，才能和销量及每日使用量对接。
    for unit in ("个", "根", "张", "只", "贴"):
        match = re.search(rf"(\d+(?:\.\d+)?)\s*{unit}", spec)
        if match and name not in {"效期贴", "标签纸", "外卖贴纸"}:
            qty = float(match.group(1))
            return unit, [{"unit": price_unit or spec.split("/")[0], "conversion": qty, "base_unit": unit}], qty

    # 食材以开封包/袋/盒为核算单位；箱价折成单包成本。
    if price_unit == "箱":
        match = re.search(r"箱\s*/\s*(\d+(?:\.\d+)?)\s*(包|袋|盒|瓶|桶)", spec)
        if match:
            qty, inner = float(match.group(1)), match.group(2)
            return inner, [{"unit": "箱", "conversion": qty, "base_unit": inner}], qty

    # 已按包/袋/盒等报价时，报价单位就是核算单位。
    if price_unit and price_unit not in {"箱", "件"}:
        return price_unit, [], 1.0

    first = clean(spec.split("/")[0] if spec else "")
    unit = first if first in {"包", "袋", "盒", "瓶", "桶", "卷", "捆", "把", "件", "台", "个", "双", "条"} else (price_unit or "个")
    return unit, [], 1.0


def main() -> None:
    archive = json.loads(NORMALIZED_FILE.read_text(encoding="utf-8"))
    payload = json.loads(SKU_FILE.read_text(encoding="utf-8"))
    BACKUP_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not BACKUP_FILE.exists():
        shutil.copy2(SKU_FILE, BACKUP_FILE)

    SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    if SOURCE_XLSX.exists() and not EVIDENCE_FILE.exists():
        shutil.copy2(SOURCE_XLSX, EVIDENCE_FILE)

    skus = payload.setdefault("skus", [])
    by_id = {item.get("id"): item for item in skus}
    by_name = {clean(item.get("name")): item for item in skus}
    aliases = payload.setdefault("aliases", [])
    alias_keys = {(item.get("sku_id"), clean(item.get("alias")), clean(item.get("supplier"))) for item in aliases}
    now = time.time()
    gaps: list[dict[str, Any]] = []
    archive_ids: set[str] = set()

    for row in archive:
        name = clean(row.get("name"))
        spec = clean(row.get("hq_spec"))
        price_unit = clean(row.get("hq_price_unit"))
        hq_price = number(row.get("hq_price"))
        # 档案中另有一行无规格、无单位、无价格的“收银纸”。它与已完整的
        # “收银纸57*50”无法证明是另一种物料，先作为待确认目录行保留，
        # 不制造第二份库存，也不覆盖完整主档。
        if name == "收银纸" and not spec and not price_unit and hq_price is None:
            gaps.append({
                "sequence": row["sequence"],
                "name": name,
                "missing": ["是否为独立物料", "规格", "总部计价单位", "总部价格"],
                "source_row": row.get("row"),
            })
            continue
        sku_id = PREFERRED_IDS.get(name, stable_id(row["sequence"]))
        sku = by_id.get(sku_id) or by_name.get(name)
        if sku is None:
            sku = {
                "id": sku_id,
                "current_stock": 0.0,
                "stock_by_location": {},
                "safety_stock": 0.0,
                "consumption_per_day": 0.0,
                "last_purchase_date": "",
                "next_purchase_est": "",
                "status": "待建账",
                "created_at": now,
            }
            skus.append(sku)
            by_id[sku_id] = sku

        archive_ids.add(sku["id"])
        unit, count_units, price_conversion = inventory_unit_and_conversion(name, spec, price_unit)
        quoted_unit_cost = round(hq_price / price_conversion, 6) if hq_price is not None and price_conversion > 0 else None
        is_asset = row.get("category") == "设备用品"

        sku.update({
            "name": name,
            "hq_name": name,
            "hq_category": row.get("category", ""),
            "category": row.get("category", "其他"),
            "unit": unit,
            "display_unit": unit,
            "standard_unit": price_unit,
            "spec": spec,
            "count_units": count_units,
            "pack_quantity": price_conversion if price_conversion > 1 else 0.0,
            "supplier": sku.get("supplier") or "总部",
            "batch_cycle_days": int(sku.get("batch_cycle_days", 14) or 14),
            "supplier_lead_days": int(sku.get("supplier_lead_days", 3) or 3),
            "tracking_mode": "asset_registry" if is_asset else ("daily_usage" if name in DAILY_USAGE_NAMES else "periodic_count"),
            "asset_class": "equipment" if is_asset else "inventory",
            "master_source": "商品档案.xlsx",
            "master_source_row": row.get("row"),
            "master_data_status": "needs_review" if not spec or hq_price is None or not price_unit else "complete",
            "catalog_prices": {
                "headquarters": {
                    "spec": spec,
                    "quote_unit": price_unit,
                    "quote_price": hq_price,
                    "normalized_unit": unit,
                    "normalized_unit_cost": quoted_unit_cost,
                },
                "alternate": {
                    "source": clean(row.get("alternate_source")),
                    "spec": clean(row.get("alternate_spec")),
                    "quote_unit": clean(row.get("alternate_price_unit")),
                    "quote_price": number(row.get("alternate_price")),
                },
            },
            "active": True,
            "updated_at": now,
        })
        if float(sku.get("unit_cost", 0) or 0) <= 0 and quoted_unit_cost is not None:
            sku["unit_cost"] = quoted_unit_cost
            sku["unit_cost_source"] = "总部商品档案报价（尚无真实采购成本）"

        alternate_source = clean(row.get("alternate_source"))
        alternate_spec = clean(row.get("alternate_spec"))
        if alternate_source:
            alias_name = f"{name}（{alternate_spec or '规格待补'}）"
            key = (sku["id"], alias_name, alternate_source)
            if key not in alias_keys:
                aliases.append({
                    "id": f"alias-master-{row['sequence']}",
                    "sku_id": sku["id"],
                    "alias": alias_name,
                    "supplier": alternate_source,
                    "unit_conversion": 1.0,
                    "alias_unit": clean(row.get("alternate_price_unit")) or unit,
                    "source": "商品档案.xlsx",
                    "usage_count": 0,
                    "created_at": now,
                    "updated_at": now,
                })
                alias_keys.add(key)

        missing = [field for field, value in (("规格", spec), ("总部计价单位", price_unit), ("总部价格", hq_price)) if value in {None, ""}]
        if missing:
            gaps.append({"sequence": row["sequence"], "name": name, "missing": missing, "source_row": row.get("row")})

    # 旧档案不删除，保留历史库存与流水；明确标记为“商品档案未收录”，避免混作已核验主档。
    for sku in skus:
        if sku.get("id") not in archive_ids:
            sku["master_data_status"] = "legacy_not_in_product_archive"
            sku["master_source"] = sku.get("master_source") or "历史总部截图/接店资料"

    payload["updated_at"] = now
    SKU_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    MASTER_FILE.write_text(json.dumps({
        "project_id": PROJECT_ID,
        "source": str(EVIDENCE_FILE),
        "source_original": str(SOURCE_XLSX),
        "source_file_preserved": SOURCE_XLSX.exists(),
        "imported_at": now,
        "catalog_item_count": len(archive),
        "category_counts": {
            category: sum(1 for item in archive if item.get("category") == category)
            for category in sorted({item.get("category") for item in archive})
        },
        "data_gaps": gaps,
        "items": archive,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "catalog_items": len(archive),
        "formal_skus": len(skus),
        "aliases": len(aliases),
        "data_gaps": len(gaps),
        "source_copy": str(EVIDENCE_FILE),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
