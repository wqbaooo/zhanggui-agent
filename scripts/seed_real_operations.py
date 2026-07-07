#!/usr/bin/env python3
"""录入 2026-07-01 ~ 2026-07-03 真实客如云营业数据。

数据来源：
- 7月1日、7月2日：Desktop/2026.7.1到7.2客如云统计.docx（已解压截图到 /tmp/kry_070102/）
- 7月3日：用户在本轮对话中提供的客如云日报关键字段
- 7月3日盘点表：project_data/xinyu-hengtai-dakou/uploads/2026-07/2026-07-03-员工物料盘点表.jpg

策略：
- 只追加/覆盖 daily_operations 与 capture_audit_log，不覆盖 SKU、员工、水电等已有真实数据。
- 成本字段（food_cost / labor 等）在无真实凭证时置 0，由页面明确标记为“待补录”。
"""

import json
import shutil
import time
from datetime import datetime
from pathlib import Path

PROJECT_ID = "xinyu-hengtai-dakou"
PROJECT_DIR = Path(__file__).resolve().parent.parent / "project_data" / PROJECT_ID
MEMORY_PATH = PROJECT_DIR / "memory.json"
UPLOADS_DIR = PROJECT_DIR / "uploads" / "2026-07"


def now() -> float:
    return time.time()


def iso_now() -> str:
    return datetime.now().isoformat()


def make_entry(
    date: str,
    original_amount: float,
    actual_revenue: float,
    merchant_discount: float,
    refund_amount: float,
    refund_orders: int,
    service_fee: float,
    delivery_fee: float,
    surcharge: float,
    orders: int,
    dine_in_orders: int,
    dine_in_revenue: float,
    delivery_orders: int,
    delivery_revenue: float,
    items_sold: int,
    customers: int,
    avg_order_value_before_discount: float,
    avg_order_value_after_discount: float,
    payment_methods: list,
    channel_breakdown: list,
    notes: str,
    source_file_name: str,
    source_raw_text: str = "",
) -> dict:
    return {
        "date": date,
        # 向后兼容：revenue 等于实际到账收入
        "revenue": actual_revenue,
        # 日结清算字段
        "original_amount": original_amount,
        "actual_revenue": actual_revenue,
        "merchant_discount": merchant_discount,
        "refund_amount": refund_amount,
        "refund_orders": refund_orders,
        "service_fee": service_fee,
        "delivery_fee": delivery_fee,
        "surcharge": surcharge,
        # 旧模型字段映射：service_fee 视为平台费，merchant_discount 视为营销/满减成本
        "platform_fee": service_fee,
        "marketing_cost": merchant_discount,
        "food_cost": 0,
        "packaging_cost": 0,
        "labor": 0,
        "rent_allocated": 0,
        "utility": 0,
        "other_cost": 0,
        "inventory_loss": 0,
        "orders": orders,
        "dine_in_orders": dine_in_orders,
        "dine_in_revenue": dine_in_revenue,
        "delivery_orders": delivery_orders,
        "delivery_revenue": delivery_revenue,
        "takeout_orders": delivery_orders,
        "items_sold": items_sold,
        "customers": customers,
        "avg_order_value_before_discount": avg_order_value_before_discount,
        "avg_order_value_after_discount": avg_order_value_after_discount,
        "payment_methods": payment_methods,
        "channel_breakdown": channel_breakdown,
        "bad_reviews": 0,
        "repeat_orders": 0,
        "new_members": 0,
        "notes": notes,
        # 溯源
        "source_type": "ocr",
        "source_platform": "keyun",
        "source_file_name": source_file_name,
        "source_raw_text": source_raw_text,
        "source_confidence": "high",
        "source_imported_at": iso_now(),
        "source_quality_score": "B",
        "created_at": now(),
        "updated_at": now(),
    }


# ── 7月1日（周三）──
entry_0701 = make_entry(
    date="2026-07-01",
    original_amount=1444.03,
    actual_revenue=1141.72,
    merchant_discount=115.95,
    refund_amount=0.0,
    refund_orders=0,
    service_fee=124.76,
    delivery_fee=56.0,
    surcharge=43.0,
    orders=73,
    dine_in_orders=56,
    dine_in_revenue=913.95,
    delivery_orders=17,
    delivery_revenue=227.77,
    items_sold=74,
    customers=0,  # 截图未拍到就餐人数
    avg_order_value_before_discount=19.0,
    avg_order_value_after_discount=16.29,
    payment_methods=[
        {"method": "抖音团购券", "orders": 15, "amount": 186.31},
        {"method": "美团团购券", "orders": 2, "amount": 31.64},
        {"method": "现金", "orders": 7, "amount": 110.0},
        {"method": "微信", "orders": 31, "amount": 568.0},
        {"method": "支付宝", "orders": 1, "amount": 18.0},
        {"method": "淘宝闪购餐饮", "orders": 8, "amount": 106.09},
        {"method": "美团外卖", "orders": 9, "amount": 121.68},
    ],
    channel_breakdown=[
        {"channel": "堂食", "orders": 56, "original_amount": 955.20, "actual_revenue": 913.95},
        {"channel": "外卖", "orders": 17, "original_amount": 488.83, "actual_revenue": 227.77},
    ],
    notes="客如云营业日报：订单金额¥1444.03，商户优惠¥115.95，服务费¥124.76，配送支出¥56，附加费¥43；成本字段待补录。",
    source_file_name="2026.7.1到7.2客如云统计.docx",
    source_raw_text="7月1日营业日报：商品销售金额1401.03，附加费43，订单金额1444.03，商户优惠115.95，订单配送支出56，服务费124.76，营业收入1141.72；收款统计：销售收款1141.72，订单73笔，堂食56笔，外卖17笔。",
)

# ── 7月2日（周四）──
entry_0702 = make_entry(
    date="2026-07-02",
    original_amount=1520.17,
    actual_revenue=1303.03,
    merchant_discount=76.97,
    refund_amount=34.0,
    refund_orders=1,
    service_fee=102.86,
    delivery_fee=25.75,
    surcharge=14.0,
    orders=82,
    dine_in_orders=68,
    dine_in_revenue=1100.45,
    delivery_orders=14,
    delivery_revenue=202.58,
    items_sold=89,
    customers=80,
    avg_order_value_before_discount=19.0,
    avg_order_value_after_discount=16.29,
    payment_methods=[
        {"method": "抖音团购券", "orders": 8, "amount": 106.07},
        {"method": "美团团购券", "orders": 4, "amount": 59.38},
        {"method": "现金", "orders": 10, "amount": 194.0},
        {"method": "微信", "orders": 42, "amount": 679.0},
        {"method": "支付宝", "orders": 4, "amount": 62.0},
        {"method": "淘宝闪购餐饮", "orders": 8, "amount": 128.94},
        {"method": "美团外卖", "orders": 6, "amount": 73.64},
    ],
    channel_breakdown=[
        {"channel": "堂食", "orders": 68, "original_amount": 1133.60, "actual_revenue": 1100.45},
        {"channel": "外卖", "orders": 14, "original_amount": 386.57, "actual_revenue": 202.58},
    ],
    notes="客如云营业日报：订单金额¥1520.17，商户优惠¥76.97，退款¥34（1笔），服务费¥102.86，配送支出¥25.75，附加费¥14；成本字段待补录。",
    source_file_name="2026.7.1到7.2客如云统计.docx",
    source_raw_text="7月2日营业日报：商品销售金额1506.17，附加费14，订单金额1520.17，商户优惠76.97，订单配送支出25.75，服务费102.86，营业收入1303.03；收款统计：销售收款1303.03，订单82笔（81销1退），堂食68笔（67销1退），外卖14笔；就餐人数80。",
)

# ── 7月3日（周五）──
# 本轮仅用户提供关键字段，无完整截图文件，质量分标记为 C。
entry_0703 = make_entry(
    date="2026-07-03",
    original_amount=1406.46,
    actual_revenue=1107.01,
    merchant_discount=102.68,
    refund_amount=22.0,
    refund_orders=1,
    service_fee=0.0,  # 用户未提供，待补录
    delivery_fee=0.0,
    surcharge=0.0,
    orders=77,
    dine_in_orders=0,  # 待补录
    dine_in_revenue=0.0,
    delivery_orders=0,  # 待补录
    delivery_revenue=0.0,
    items_sold=76,
    customers=0,
    avg_order_value_before_discount=0.0,
    avg_order_value_after_discount=0.0,
    payment_methods=[],
    channel_breakdown=[],
    notes="用户提供：订单原价¥1406.46，实际收入¥1107.01，商户优惠¥102.68，退款¥22，77笔订单/76笔销货；渠道与支付方式待补录。",
    source_file_name="用户口述/待补截图",
    source_raw_text="7月3日：订单原价1406.46，实际收入1107.01，商户优惠102.68，退款22，77笔订单，76笔销货。",
)
entry_0703["source_confidence"] = "medium"
entry_0703["source_quality_score"] = "C"

# ── 盘点表审计日志（7月3日已有）──
count_audit = {
    "id": f"cap-count-0703-{int(now())}",
    "timestamp": now(),
    "source_type": "image",
    "file_name": "2026-07-03-员工物料盘点表.jpg",
    "capture_kind": "inventory_count",
    "recognized_fields": [],
    "human_modified_fields": [],
    "review_status": "confirmed",
    "write_target": "inventory_counts",
    "date": "2026-07-03",
    "error_message": "",
}

# ── 营业日报审计日志 ──
op_audits = [
    {
        "id": f"cap-op-0701-{int(now())}",
        "timestamp": now(),
        "source_type": "image",
        "file_name": "2026.7.1到7.2客如云统计.docx / image18-19",
        "capture_kind": "operation",
        "recognized_fields": [
            {"key": "date", "value": "2026-07-01"},
            {"key": "original_amount", "value": 1444.03},
            {"key": "actual_revenue", "value": 1141.72},
            {"key": "orders", "value": 73},
        ],
        "human_modified_fields": [],
        "review_status": "confirmed",
        "write_target": "daily_operations",
        "date": "2026-07-01",
        "error_message": "",
    },
    {
        "id": f"cap-op-0702-{int(now())}",
        "timestamp": now(),
        "source_type": "image",
        "file_name": "2026.7.1到7.2客如云统计.docx / image1-4",
        "capture_kind": "operation",
        "recognized_fields": [
            {"key": "date", "value": "2026-07-02"},
            {"key": "original_amount", "value": 1520.17},
            {"key": "actual_revenue", "value": 1303.03},
            {"key": "orders", "value": 82},
        ],
        "human_modified_fields": [],
        "review_status": "confirmed",
        "write_target": "daily_operations",
        "date": "2026-07-02",
        "error_message": "",
    },
    {
        "id": f"cap-op-0703-{int(now())}",
        "timestamp": now(),
        "source_type": "text",
        "file_name": "用户口述",
        "capture_kind": "operation",
        "recognized_fields": [
            {"key": "date", "value": "2026-07-03"},
            {"key": "original_amount", "value": 1406.46},
            {"key": "actual_revenue", "value": 1107.01},
            {"key": "orders", "value": 77},
        ],
        "human_modified_fields": [],
        "review_status": "needs_human_review",
        "write_target": "daily_operations",
        "date": "2026-07-03",
        "error_message": "缺少营业日报截图，渠道与支付方式待补录",
    },
]


def load_memory() -> dict:
    if MEMORY_PATH.exists():
        return json.loads(MEMORY_PATH.read_text(encoding="utf-8"))
    return {
        "project_id": PROJECT_ID,
        "created_at": now(),
        "updated_at": now(),
        "profile": {"store_name": "新余恒太城五楼大口章鱼烧"},
        "daily_operations": [],
        "capture_audit_log": [],
    }


def upsert_operations(memory: dict, entries: list) -> None:
    indexed = {e["date"]: e for e in memory.get("daily_operations", [])}
    for e in entries:
        indexed[e["date"]] = e
    memory["daily_operations"] = sorted(indexed.values(), key=lambda x: x["date"])


def main() -> None:
    memory = load_memory()
    upsert_operations(memory, [entry_0701, entry_0702, entry_0703])

    existing_audit_ids = {a.get("id") for a in memory.get("capture_audit_log", [])}
    for audit in [count_audit] + op_audits:
        if audit["id"] not in existing_audit_ids:
            memory.setdefault("capture_audit_log", []).append(audit)
    memory["capture_audit_log"].sort(key=lambda x: x.get("timestamp", 0), reverse=True)

    memory["updated_at"] = now()
    MEMORY_PATH.write_text(json.dumps(memory, ensure_ascii=False, indent=2), encoding="utf-8")

    # 顺手把截图证据复制到项目目录，方便前端展示
    evidence_dir = PROJECT_DIR / "uploads" / "2026-07"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    source_docx = Path.home() / "Desktop" / "2026.7.1到7.2客如云统计.docx"
    if source_docx.exists():
        shutil.copy2(source_docx, evidence_dir / "2026.7.1-7.2客如云统计.docx")

    print("✅ 已写入 3 天真实营业数据")
    print(f"   daily_operations: {len(memory['daily_operations'])} 条")
    print(f"   capture_audit_log: {len(memory['capture_audit_log'])} 条")
    print(f"   证据目录: {evidence_dir}")


if __name__ == "__main__":
    main()
