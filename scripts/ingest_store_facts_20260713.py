"""Idempotently ingest owner-confirmed 2026-07-11/12 store facts."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from models.finance_ledger import FinanceLedger
from models.project import ProjectMemory
from models.store_facts import StoreFactBook

PROJECT_ID = "xinyu-hengtai-dakou"

FACTS = [
    {
        "date": "2026-07-11", "revenue": 1232.88, "actual_revenue": 1232.88,
        "original_amount": 1601.36, "merchant_discount": 156.45,
        "refund_amount": 15.0, "refund_orders": 1, "orders": 80,
        "sales_transactions": 79, "visitors": 82, "dining_customers": 81,
        "avg_order_value_before_discount": 19.77, "avg_order_value_after_discount": 15.22,
        "payment_methods": [
            {"method": "微信", "orders": 44, "amount": 740.0},
            {"method": "美团外卖", "orders": 12, "amount": 158.02},
            {"method": "淘宝闪购餐饮", "orders": 8, "amount": 101.63},
            {"method": "现金", "orders": 5, "amount": 84.0},
            {"method": "抖音团购券", "orders": 6, "amount": 73.41},
            {"method": "支付宝", "orders": 3, "amount": 47.0},
            {"method": "美团团购券", "orders": 2, "amount": 28.82},
        ],
        "order_sources": [
            {"source": "Android收银终端", "amount": 995.80, "share": 0.6218},
            {"source": "美团外卖", "amount": 367.65, "share": 0.2296},
            {"source": "淘宝闪购餐饮", "amount": 237.91, "share": 0.1486},
        ],
        "revenue_basis": "keruyun_operating_income", "cost_status": "unknown",
        "source_type": "owner_uploaded_screenshot", "source_platform": "keyun",
        "source_file_name": "8d4f74b98fefc1cbc1cdb92efd0740cd.jpg",
        "source_confidence": "high", "source_quality_score": "A",
        "notes": "客如云截图核验；订单80笔含79笔销售、1笔退款。成本尚未闭合。",
    },
    {
        "date": "2026-07-12", "revenue": 1658.82, "actual_revenue": 1658.82,
        "original_amount": 1964.97, "merchant_discount": 105.85,
        "refund_amount": 19.84, "refund_orders": 1, "orders": 102,
        "sales_transactions": 101, "visitors": 101, "dining_customers": 100,
        "avg_order_value_before_discount": 19.65, "avg_order_value_after_discount": 16.59,
        "payment_methods": [
            {"method": "微信", "orders": 48, "amount": 878.0},
            {"method": "支付宝", "orders": 17, "amount": 288.0},
            {"method": "淘宝闪购餐饮", "orders": 16, "amount": 188.83},
            {"method": "抖音团购券", "orders": 11, "amount": 161.0},
            {"method": "美团外卖", "orders": 5, "amount": 50.34},
            {"method": "现金", "orders": 2, "amount": 47.0},
            {"method": "美团团购券", "orders": 3, "amount": 45.65},
        ],
        "order_sources": [
            {"source": "Android收银终端", "amount": 1457.60, "share": 0.7418},
            {"source": "淘宝闪购餐饮", "amount": 428.73, "share": 0.2182},
            {"source": "美团外卖", "amount": 78.64, "share": 0.04},
        ],
        "revenue_basis": "keruyun_operating_income", "cost_status": "unknown",
        "source_type": "owner_uploaded_screenshot", "source_platform": "keyun",
        "source_file_name": "66c53fbc299cad0b92935c075e25b8c9.jpg",
        "source_confidence": "high", "source_quality_score": "A",
        "notes": "客如云截图核验；订单102笔含101笔销售、1笔退款。7月12日现金未实点。",
    },
]


def main():
    memory = ProjectMemory.load(PROJECT_ID)
    if not memory:
        raise SystemExit("project memory not found")
    memory.profile.update({
        "owner_management_salary_target": 4000.0,
        "owner_management_salary_status": "owner_confirmed_policy_not_accrued",
        "bank_account_separation_status": "mixed_personal_and_store",
        "dedicated_store_bank_account_status": "planned",
        "monthly_communication_fee": 69.0,
        "broadband_installation_fee": 200.0,
        "phone_topup_paid": 100.0,
        "inventory_baseline_date": "2026-07-05",
        "inventory_baseline_basis": "hq_restock_plus_unpriced_inherited_stock_difference",
        "initial_inventory_purchase_status": "paid_received_posted",
    })
    by_date = {str(item.get("date")): item for item in memory.daily_operations}
    for fact in FACTS:
        by_date[fact["date"]] = fact
    memory.daily_operations = sorted(by_date.values(), key=lambda item: str(item.get("date", "")))
    memory.artifacts = [a for a in memory.artifacts if a.get("id") != "store-fact-manual-20260713"]
    memory.artifacts.append({
        "id": "store-fact-manual-20260713",
        "type": "store_fact_manual",
        "title": "门店经营事实手册 2026-07-13",
        "path": "docs/store_manual/新余恒太城大口章鱼烧_门店经营事实手册_20260713.docx",
        "status": "verified_source_of_truth",
    })
    memory.save()

    ledger = FinanceLedger.for_project(PROJECT_ID)
    posted = {fact["date"]: ledger.record_confirmed_daily_revenue(PROJECT_ID, fact) for fact in FACTS}
    book = StoreFactBook(project_id=PROJECT_ID)
    book.cash_counts = [{
        "date": "2026-07-12", "amount_minor": 4700, "source": "owner_confirmed",
        "definition": "打烊时POS机内实际现金；早班为开门时POS现金，晚班为当天现金收款，合计为POS机内现金总额。",
    }]
    book.settlements = [{
        "type": "former_owner_collection_transfer", "date": "2026-07-07",
        "amount_minor": 257080, "direction": "former_owner_to_current_owner",
        "breakdown": {"keruyun": 132194, "meituan": 54377, "eleme": 37996, "douyin": 32513, "jd": 0, "meituan_group": 0},
        "source": "b17520a087419a2029034163b9c75bbd.jpg+owner_confirmation",
    }]
    book.capital_payments = [{
        "type": "hq_inventory_purchase", "order_date": "2026-07-05", "amount_minor": 1379100,
        "payment_status": "paid_in_three_bank_transfers", "payee": "林雄杰",
        "daily_transfer_limit_minor": 500000,
        "payments": [
            {"date": "2026-07-03", "amount_minor": 400000},
            {"date": "2026-07-04", "amount_minor": 499900},
            {"date": "2026-07-05", "amount_minor": 479200},
        ],
        "note": "银行流水逐笔显示转账-林雄杰（4739）；三笔合计与总部订单¥13,791完全一致。",
        "source": "1ecf708a1083ac615d94ccf673ebc876.jpg+owner_confirmation",
    }]
    book.supplier_invoices = [
        {"date": "2026-07-02", "supplier": "新余素源生态农业科技有限公司", "total_minor": 810, "payment_status": "on_account_unsettled", "source": "5789bd7f4b0b91c68c65562dbf154c58.jpg", "items": [{"name": "包菜", "quantity": 5.4, "unit": "斤", "unit_price_minor": 150, "subtotal_minor": 810, "accounting_treatment": "direct_use_food_cost"}]},
        {"date": "2026-07-03", "supplier": "新余素源生态农业科技有限公司", "total_minor": 1515, "payment_status": "on_account_unsettled", "source": "ab914c6529daacf987642bea8ca835bf.jpg", "items": [
            {"name": "包菜", "quantity": 7.7, "unit": "斤", "unit_price_minor": 150, "subtotal_minor": 1155, "accounting_treatment": "direct_use_food_cost"},
            {"name": "大葱", "quantity": 0.5, "unit": "斤", "unit_price_minor": 250, "subtotal_minor": 125, "accounting_treatment": "direct_use_food_cost"},
            {"name": "洋葱", "quantity": 0.7, "unit": "斤", "unit_price_minor": 150, "subtotal_minor": 105, "accounting_treatment": "direct_use_food_cost"},
            {"name": "萝卜", "quantity": 1.3, "unit": "斤", "unit_price_minor": 100, "subtotal_minor": 130, "accounting_treatment": "direct_use_food_cost"}]},
        {"date": "2026-07-05", "supplier": "新余素源生态农业科技有限公司", "total_minor": 22740, "payment_status": "on_account_unsettled", "source": "42bf598dfbc0501b7ad6b07a21b62429.jpg", "items": [
            {"name": "鸡蛋", "quantity": 1, "unit": "箱", "unit_price_minor": 21600, "subtotal_minor": 21600, "accounting_treatment": "inventory_purchase"},
            {"name": "包菜", "quantity": 5.6, "unit": "斤", "unit_price_minor": 150, "subtotal_minor": 840, "accounting_treatment": "direct_use_food_cost"},
            {"name": "白萝卜", "quantity": 1, "unit": "斤", "unit_price_minor": 100, "subtotal_minor": 100, "accounting_treatment": "direct_use_food_cost"},
            {"name": "大葱", "quantity": 0.5, "unit": "斤", "unit_price_minor": 250, "subtotal_minor": 125, "accounting_treatment": "direct_use_food_cost"},
            {"name": "洋葱", "quantity": 0.5, "unit": "斤", "unit_price_minor": 150, "subtotal_minor": 75, "accounting_treatment": "direct_use_food_cost"}]},
        {"date": "2026-07-07", "supplier": "新余素源生态农业科技有限公司", "total_minor": 870, "payment_status": "on_account_unsettled", "source": "3f29e4ee40d219f1debd8ddb1ac12df8.jpg", "items": [
            {"name": "包菜", "quantity": 3.5, "unit": "斤", "unit_price_minor": 150, "subtotal_minor": 525, "accounting_treatment": "direct_use_food_cost"},
            {"name": "大葱", "quantity": 0.4, "unit": "斤", "unit_price_minor": 250, "subtotal_minor": 100, "accounting_treatment": "direct_use_food_cost"},
            {"name": "洋葱", "quantity": 0.7, "unit": "斤", "unit_price_minor": 150, "subtotal_minor": 105, "accounting_treatment": "direct_use_food_cost"},
            {"name": "萝卜", "quantity": 1.4, "unit": "斤", "unit_price_minor": 100, "subtotal_minor": 140, "accounting_treatment": "direct_use_food_cost"}]},
        {"date": "2026-07-08", "supplier": "新余素源生态农业科技有限公司", "total_minor": 1035, "payment_status": "on_account_unsettled", "source": "b187b516011ba77b8e86535c9ac83a08.jpg", "items": [{"name": "包菜", "quantity": 6.9, "unit": "斤", "unit_price_minor": 150, "subtotal_minor": 1035, "accounting_treatment": "direct_use_food_cost"}]},
        {"date": "2026-07-09", "supplier": "新余素源生态农业科技有限公司", "total_minor": 410, "payment_status": "on_account_unsettled", "source": "28e881e21eae464f766b3f7068e42c14.jpg", "items": [
            {"name": "大葱", "quantity": 0.6, "unit": "斤", "unit_price_minor": 250, "subtotal_minor": 150, "accounting_treatment": "direct_use_food_cost"},
            {"name": "洋葱", "quantity": 0.8, "unit": "斤", "unit_price_minor": 150, "subtotal_minor": 120, "accounting_treatment": "direct_use_food_cost"},
            {"name": "萝卜", "quantity": 1.4, "unit": "斤", "unit_price_minor": 100, "subtotal_minor": 140, "accounting_treatment": "direct_use_food_cost"}]},
        {"date": "2026-07-10", "supplier": "新余素源生态农业科技有限公司", "total_minor": 630, "payment_status": "on_account_unsettled", "source": "25b12fd405016ee66e15494e10898c0b.jpg", "items": [{"name": "包菜", "quantity": 4.2, "unit": "斤", "unit_price_minor": 150, "subtotal_minor": 630, "accounting_treatment": "direct_use_food_cost"}]},
    ]
    rows = [
        (1, "原味章鱼烧(标准)", 372, 558000, "6粒", "cross_platform_official_consensus"),
        (2, "肉松章鱼烧(标准)", 103, 174250, "6粒", "cross_platform_official_consensus"),
        (3, "招牌全家福（9粒）", 53, 116600, "9粒", "official_name"),
        (4, "大口全家福章鱼烧6个(默认)", 41, 67404, "6粒", "official_name"),
        (5, "超级双拼章鱼烧(3粒)(标准)", 41, 90200, "3粒大丸子", "official_name"),
        (6, "培根芝士章鱼烧(标准)", 40, 72000, "6粒", "cross_platform_official_consensus"),
        (7, "【大口】DIY双拼章鱼烧(8粒)", 37, 69930, "8粒_两盒四粒", "official_name+owner_box_rule"),
        (13, "经典原味章鱼烧", 34, 88060, None, "official_spec_unresolved"),
        (14, "玉米奶酪章鱼烧(标准)", 23, 39100, "6粒", "cross_platform_official_consensus"),
        (15, "芥末章鱼烧(标准)", 22, 33000, "6粒", "cross_platform_official_consensus"),
        (16, "藤椒蛤蜊章鱼烧(标准)", 22, 39600, "6粒", "cross_platform_official_consensus"),
        (17, "经典招牌｜原味章鱼烧（6粒）(默认)", 20, 29320, "6粒", "official_name"),
        (18, "全家福套餐(默认)", 15, 30915, "9粒", "official_menu_consensus"),
        (19, "大口章鱼烧·章鱼烧全家福", 15, 49350, "9粒", "official_menu_consensus"),
        (20, "打包盒(标准)", 13, 1300, "non_food_packaging_sale", "official_name"),
        (21, "经典原味章鱼烧(6粒)", 13, 30170, "6粒", "official_name"),
        (22, "【仅限每周三使用】品牌会员日套餐", 11, 14190, None, "official_spec_unresolved"),
    ]
    book.product_sales_periods = [{
        "period": {"start": "2026-07-01", "end": "2026-07-12"},
        "total_quantity": 989, "gross_sales_minor": 1815061, "refund_quantity": 12,
        "refund_minor": 24816, "recognized_revenue_minor": 1477148,
        "source_basis": "keruyun_product_gross_sales_vs_keruyun_operating_income",
        "ranked_products": [
            {"rank": rank, "name": name, "quantity": quantity, "amount_minor": amount,
             "official_spec": spec, "spec_source": source}
            for rank, name, quantity, amount, spec, source in rows
        ],
    }]
    book.inventory_policy = {
        "tracking_rule": "opened_package_counts_as_used", "default_open_quantity": 1,
        "employee_action": "选择物料后点击开封1包；系统立即减1并记录成本。",
        "exception": "盘点只用于纠正实际剩余数量，不要求员工记录在用余量。",
    }
    book.operational_forms = [
        {"id": "daily-cash", "name": "每日现金交接表", "frequency": "每日早晚", "fields": ["日期", "早班POS现金", "当天现金收款", "现金支出", "打烊实点", "与客如云差异", "交接人"]},
        {"id": "daily-open-pack", "name": "每日物料开封表", "frequency": "随开随记", "fields": ["日期时间", "物料", "开封数量(默认1)", "操作员工", "备注"]},
        {"id": "daily-attendance", "name": "员工上班与加班登记表", "frequency": "每日", "fields": ["员工", "上班", "下班", "休息", "加班小时", "签名"]},
        {"id": "daily-core-count", "name": "核心物料日盘表", "frequency": "每日打烊", "fields": ["预拌粉", "章鱼粒", "鸡蛋", "盒子", "主要酱料", "异常"]},
        {"id": "weekly-full-count", "name": "每周全量盘点表", "frequency": "每周", "fields": ["物料", "系统数", "实盘数", "差异", "原因", "复核人"]},
        {"id": "supplier-reconciliation", "name": "供应商月结对账表", "frequency": "月度", "fields": ["供应商", "发票日期", "应付", "已付", "未付", "付款凭证"]},
    ]
    book.save()

    # Cash count is an observed fact; other close inputs remain unknown, so the day stays awaiting inputs.
    ledger.save_daily_close(PROJECT_ID, "2026-07-12", {
        "counted_cash_minor": 4700, "reserve_cash_minor": 4700,
        "food_cost_minor": None, "packaging_cost_minor": None, "overtime_hours": None,
        "rent_minor": 0, "utility_minor": None, "other_cost_minor": None,
    })
    ledger.record_former_owner_transfer(PROJECT_ID, "2026-07-07", 257080, "icbc-20260707-257080")
    ledger.record_owner_paid_inventory_purchase(
        PROJECT_ID,
        fact_id=f"fact:{PROJECT_ID}:profile:initial_inventory_purchase",
        receipt_date="2026-07-05",
        payments=[
            {"date": "2026-07-03", "amount_minor": 400000},
            {"date": "2026-07-04", "amount_minor": 499900},
            {"date": "2026-07-05", "amount_minor": 479200},
        ],
        supplier="总部/林雄杰",
        reference="hq-order-XS...20260705-13791",
    )
    for invoice in book.supplier_invoices:
        inventory_minor = sum(int(item["subtotal_minor"]) for item in invoice["items"] if item["accounting_treatment"] == "inventory_purchase")
        direct_minor = sum(int(item["subtotal_minor"]) for item in invoice["items"] if item["accounting_treatment"] == "direct_use_food_cost")
        lines = []
        if inventory_minor:
            lines.append(("1401", inventory_minor, 0))
        if direct_minor:
            lines.append(("5001", direct_minor, 0))
        lines.append(("2001", 0, int(invoice["total_minor"])))
        ledger.post_entry(
            store_id=PROJECT_ID, entry_date=invoice["date"],
            posting_key=f"local-supplier:{invoice['date']}:{invoice['total_minor']}",
            description=f"{invoice['supplier']} 月结进货", lines=lines,
        )
    print({"daily_operations": len(memory.daily_operations), "posted": posted, "store_facts": book.finance_summary()})


if __name__ == "__main__":
    main()
