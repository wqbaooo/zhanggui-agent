"""Store-specific finance taxonomy shared by intake, ledger, exports and Agent answers.

Business categories describe what happened in the store.  ``account_code`` is
the accounting destination when one is known; the two concepts deliberately
remain separate so a platform settlement cannot be mistaken for new revenue.
"""

from __future__ import annotations

from typing import Any


FINANCE_CATEGORY_GROUPS: tuple[dict[str, Any], ...] = (
    {
        "key": "sales",
        "name": "营业收入与调整",
        "items": (
            ("dine_in_sales", "到店销售", "sales_receipt", "inflow", "store", "4001", "revenue"),
            ("delivery_sales", "外卖销售", "sales_receipt", "inflow", "store", "4002", "revenue"),
            ("group_buy_sales", "团购核销", "sales_receipt", "inflow", "store", "4003", "revenue"),
            ("cash_sales", "现金销售", "sales_receipt", "inflow", "store", "4001", "revenue"),
            ("sales_adjustment", "退款与销售调整", "sales_adjustment", "outflow", "store", "4004", "contra_revenue"),
        ),
    },
    {
        "key": "inventory",
        "name": "进货与库存",
        "items": (
            ("food_purchase", "食材原料采购", "inventory_purchase", "outflow", "store", "1401", "inventory"),
            ("packaging_purchase", "包装耗材采购", "inventory_purchase", "outflow", "store", "1402", "inventory"),
            ("low_value_consumables", "低值经营耗材", "inventory_purchase", "outflow", "store", "1402", "inventory"),
            ("purchase_freight", "采购运输费", "operating_expense", "outflow", "store", "6005", "expense"),
            ("inventory_usage", "库存领用", "inventory_usage", "outflow", "store", "5001", "cost"),
            ("inventory_loss", "报损盘亏", "inventory_loss", "outflow", "store", "5005", "cost"),
            ("supplier_return", "供应商退货", "inventory_return", "inflow", "store", "1401", "inventory_adjustment"),
        ),
    },
    {
        "key": "operating_expense",
        "name": "经营费用",
        "items": (
            ("employee_wage", "员工工资", "operating_expense", "outflow", "store", "6001", "expense"),
            ("overtime_temp_labor", "加班与临时用工", "operating_expense", "outflow", "store", "6001", "expense"),
            ("rent_mall_fee", "房租与商场费", "operating_expense", "outflow", "store", "6002", "expense"),
            ("utilities", "水电燃气", "operating_expense", "outflow", "store", "6003", "expense"),
            ("waste_property_fee", "垃圾及物业费", "operating_expense", "outflow", "store", "6005", "expense"),
            ("telecom_network", "通信网络", "operating_expense", "outflow", "store", "6004", "expense"),
            ("platform_fee_delivery", "平台佣金与配送", "operating_expense", "outflow", "store", "5003", "expense"),
            ("promotion", "活动推广", "operating_expense", "outflow", "store", "5004", "expense"),
            ("store_drinking_water", "店铺饮用水", "operating_expense", "outflow", "store", "6005", "expense"),
            ("cleaning_hygiene", "清洁卫生", "operating_expense", "outflow", "store", "6005", "expense"),
            ("license_health_training", "证照健康培训", "operating_expense", "outflow", "store", "6007", "expense"),
            ("system_service", "系统服务", "operating_expense", "outflow", "store", "6004", "expense"),
            ("repair_maintenance", "维修维护", "operating_expense", "outflow", "store", "6005", "expense"),
            ("office_printing", "办公打印", "operating_expense", "outflow", "store", "6005", "expense"),
            ("business_transport", "日常交通", "operating_expense", "outflow", "store", "6005", "expense"),
            ("taxes", "税费", "operating_expense", "outflow", "store", "6009", "expense"),
            ("other_operating_expense", "其他经营费用", "operating_expense", "outflow", "store", "6005", "expense"),
        ),
    },
    {
        "key": "store_acquisition",
        "name": "接店与长期投入",
        "items": (
            ("transfer_fee", "接店转让费", "long_term_investment", "outflow", "store", "1801", "asset"),
            ("deposit", "押金", "asset_purchase", "outflow", "store", "1801", "asset"),
            ("equipment_tools", "设备工具", "asset_purchase", "outflow", "store", "1601", "asset"),
            ("renovation", "装修改造", "long_term_investment", "outflow", "store", "1801", "asset"),
            ("long_term_deferred", "长期待摊", "long_term_investment", "outflow", "store", "1801", "asset"),
        ),
    },
    {
        "key": "debt_financing",
        "name": "借款与融资",
        "items": (
            ("loan_received", "借款到账", "loan_in", "inflow", "store", "2003", "liability"),
            ("loan_principal_repayment", "偿还借款本金", "loan_repayment", "outflow", "store", "2003", "liability"),
            ("interest_financing_fee", "利息与融资费用", "operating_expense", "outflow", "store", "6010", "expense"),
        ),
    },
    {
        "key": "owner_current",
        "name": "老板往来",
        "items": (
            ("owner_investment", "老板投入", "owner_investment", "inflow", "store", "3001", "equity"),
            ("owner_advance", "老板垫付", "owner_advance", "inflow", "store", None, "liability_to_owner"),
            ("owner_advance_repayment", "归还老板垫付款", "owner_advance_repayment", "outflow", "store", None, "liability_to_owner"),
            ("owner_draw", "老板取用", "owner_draw", "outflow", "store", "3002", "equity"),
            ("owner_compensation", "老板报酬", "owner_compensation", "outflow", "store", "6001", "expense_when_accrued"),
            ("personal_spending_from_store", "使用店铺资金的个人消费", "personal_spending", "outflow", "personal", None, "excluded_personal"),
            ("personal_spending_personal_account", "个人账户消费", "personal_spending", "outflow", "personal", None, "excluded_personal"),
        ),
    },
    {
        "key": "fund_settlement",
        "name": "资金调拨与结算",
        "items": (
            ("platform_wallet_credit", "平台钱包入账", "platform_settlement", "inflow", "store", None, "fund_transfer"),
            ("platform_withdrawal", "平台提现到账", "platform_settlement", "outflow", "store", None, "fund_transfer"),
            ("former_owner_collection", "前老板代收", "former_owner_collection", "outflow", "store", "1013", "receivable"),
            ("former_owner_transfer", "前老板转回", "former_owner_transfer", "inflow", "store", "1013", "receivable_settlement"),
            ("cash_deposit", "现金存行", "account_transfer", "outflow", "store", None, "fund_transfer"),
            ("account_transfer", "账户间转账", "account_transfer", "outflow", "store", None, "fund_transfer"),
            ("test_transaction", "测试交易", "test_transaction", "outflow", "store", None, "excluded"),
            ("unidentified_transaction", "未识别款项", "unidentified", "inflow", "unknown", "1019", "pending_classification"),
        ),
    },
)


def finance_category_catalog() -> dict[str, Any]:
    groups = []
    for group in FINANCE_CATEGORY_GROUPS:
        items = [
            {
                "key": key,
                "name": name,
                "transaction_kind": kind,
                "direction": direction,
                "business_scope": scope,
                "account_code": account_code,
                "accounting_treatment": treatment,
            }
            for key, name, kind, direction, scope, account_code, treatment in group["items"]
        ]
        groups.append({"key": group["key"], "name": group["name"], "items": items})
    return {"schema_version": "finance_category_catalog_v1", "groups": groups}


def find_finance_category(key: str | None) -> dict[str, Any] | None:
    if not key:
        return None
    for group in finance_category_catalog()["groups"]:
        for item in group["items"]:
            if item["key"] == key:
                return {**item, "group_key": group["key"], "group_name": group["name"]}
    return None
