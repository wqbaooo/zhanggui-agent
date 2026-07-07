#!/usr/bin/env python3
"""修正经营数据的成本字段，基于老板提供的真实信息。

关键修正：
1. 房租：7月不算，rent_allocated=0（8月起5000/月）
2. 人工：8865.38/30=295.51元/天（之前错误地除以5天）
3. 垃圾费：30元/月，分摊到每天1元
4. 水电：暂不确定，保留估算值20元/天但标注
5. 转租费4万：一次性投资，不进入日常利润计算
6. 进货1.4万：库存采购，已有采购单记录，不进入当日食材成本
"""

from __future__ import annotations

import json
from pathlib import Path

PROJECT_ID = "xinyu-hengtai-dakou"
PROJECT_DATA_DIR = Path(__file__).parent.parent / "project_data" / PROJECT_ID


def load_memory() -> dict:
    with open(PROJECT_DATA_DIR / "memory.json", "r", encoding="utf-8") as f:
        return json.load(f)


def load_skus() -> dict:
    with open(PROJECT_DATA_DIR / "skus.json", "r", encoding="utf-8") as f:
        return json.load(f)


def get_sku_cost(skus: dict, name: str) -> float:
    for sku in skus.get("skus", []):
        if sku.get("name") == name:
            return float(sku.get("unit_cost", 0))
    return 0.0


def calculate_food_cost(entry: dict, skus: dict) -> float:
    product_sales = entry.get("product_sales", [])
    if not product_sales:
        return float(entry.get("actual_revenue", entry.get("revenue", 0))) * 0.32

    total_food_cost = 0.0
    octopus_powder_cost = get_sku_cost(skus, "章鱼烧粉")
    corn_cost = get_sku_cost(skus, "玉米")
    meat_floss_cost = get_sku_cost(skus, "肉松")

    for product in product_sales:
        name = product.get("name", "")
        quantity = float(product.get("quantity", 0))
        amount = float(product.get("amount", 0))

        if "经典必吃" in name:
            powder_cost = (200 / 2000) * octopus_powder_cost * quantity
            octopus_cost = quantity * 1.5
            sauce_cost = quantity * 0.8
            total_food_cost += powder_cost + octopus_cost + sauce_cost
        elif "夹心大丸" in name:
            powder_cost = (300 / 2000) * octopus_powder_cost * quantity
            filling_cost = quantity * 2.0
            total_food_cost += powder_cost + filling_cost
        elif "外部商品" in name:
            total_food_cost += amount * 0.30
        else:
            total_food_cost += amount * 0.32

    return round(total_food_cost, 2)


def calculate_packaging_cost(entry: dict) -> float:
    dine_in_orders = int(entry.get("dine_in_orders", 0))
    delivery_orders = int(entry.get("delivery_orders", 0))

    dine_in_pack_cost = dine_in_orders * 0.3
    delivery_pack_cost = delivery_orders * 1.2

    return round(dine_in_pack_cost + delivery_pack_cost, 2)


def main():
    memory = load_memory()
    skus = load_skus()

    monthly_labor = float(memory["profile"].get("monthly_labor", 8865.38))
    daily_labor = round(monthly_labor / 30, 2)

    monthly_rent = 5000.0
    monthly_garbage_fee = 30.0
    monthly_utility_estimated = 600.0

    daily_garbage = round(monthly_garbage_fee / 30, 2)
    daily_utility = round(monthly_utility_estimated / 30, 2)

    transfer_fee = 40000.0
    inventory_purchase = 14000.0

    print(f"=== 成本参数 ===")
    print(f"月人工: ¥{monthly_labor:.2f} → 日人工: ¥{daily_labor:.2f}")
    print(f"月房租: ¥{monthly_rent:.2f}（8月起算）")
    print(f"月垃圾费: ¥{monthly_garbage_fee:.2f} → 日垃圾费: ¥{daily_garbage:.2f}")
    print(f"月水电估算: ¥{monthly_utility_estimated:.2f} → 日水电: ¥{daily_utility:.2f}")
    print(f"一次性投资 - 转租费: ¥{transfer_fee:.2f}")
    print(f"一次性投资 - 进货: ¥{inventory_purchase:.2f}")
    print()

    updated_count = 0
    for entry in memory.get("daily_operations", []):
        date = entry.get("date", "")
        print(f"处理 {date}:")

        food_cost = calculate_food_cost(entry, skus)
        packaging_cost = calculate_packaging_cost(entry)
        rent_allocated = 0.0
        labor = daily_labor
        utility = daily_utility
        other_cost = daily_garbage

        total_revenue = entry.get("actual_revenue", entry.get("revenue", 0))
        total_cost = food_cost + packaging_cost + labor + rent_allocated + utility + other_cost
        net_profit = total_revenue - total_cost

        print(f"  营收: ¥{total_revenue:.2f}")
        print(f"  订单: {entry.get('orders', 0)} (堂食{entry.get('dine_in_orders', 0)} + 外卖{entry.get('delivery_orders', 0)})")
        print(f"  食材成本: ¥{food_cost:.2f}")
        print(f"  包装成本: ¥{packaging_cost:.2f}")
        print(f"  人工: ¥{labor:.2f}")
        print(f"  房租: ¥{rent_allocated:.2f}（7月不算）")
        print(f"  水电: ¥{utility:.2f}（暂估算）")
        print(f"  垃圾费: ¥{other_cost:.2f}")
        print(f"  总成本: ¥{total_cost:.2f}")
        print(f"  净利润: ¥{net_profit:.2f}")

        entry["food_cost"] = food_cost
        entry["packaging_cost"] = packaging_cost
        entry["labor"] = labor
        entry["rent_allocated"] = rent_allocated
        entry["utility"] = utility
        entry["other_cost"] = other_cost
        entry["cost_status"] = "estimated"
        updated_count += 1
        print()

    print(f"总计更新 {updated_count} 条经营记录")

    memory["profile"]["monthly_rent"] = monthly_rent
    memory["profile"]["monthly_rent_start_date"] = "2026-08-01"
    memory["profile"]["monthly_garbage_fee"] = monthly_garbage_fee
    memory["profile"]["monthly_utility_min"] = 300.0
    memory["profile"]["monthly_utility_max"] = 900.0
    memory["profile"]["transfer_fee"] = transfer_fee
    memory["profile"]["initial_inventory_purchase"] = inventory_purchase

    with open(PROJECT_DATA_DIR / "memory.json", "w", encoding="utf-8") as f:
        json.dump(memory, f, ensure_ascii=False, indent=2)

    print("\nmemory.json 已更新")


if __name__ == "__main__":
    main()