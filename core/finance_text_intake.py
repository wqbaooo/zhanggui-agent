"""Natural-language prefill for finance intake. This module never writes books."""

from __future__ import annotations

import re
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

from core.finance_categories import find_finance_category


SCHEMA_VERSION = "finance_text_parse_v1"


def _extract_amount(text: str) -> float | None:
    patterns = (
        r"(?:花了|付了|支付|消费|金额是?|共计)\s*[¥￥]?\s*(\d+(?:\.\d{1,2})?)",
        r"[¥￥]\s*(\d+(?:\.\d{1,2})?)",
        r"(\d+(?:\.\d{1,2})?)\s*(?:元|块钱?)(?!\d)",
    )
    for pattern in patterns:
        match = re.search(pattern, text)
        if not match:
            continue
        try:
            value = Decimal(match.group(1))
        except InvalidOperation:
            continue
        if value > 0:
            return float(value)
    return None


def _extract_date(text: str, today: str) -> str | None:
    base = date.fromisoformat(today)
    if "前天" in text:
        return (base - timedelta(days=2)).isoformat()
    if "昨天" in text:
        return (base - timedelta(days=1)).isoformat()
    if "今天" in text:
        return base.isoformat()
    full = re.search(r"(20\d{2})[-/.年](\d{1,2})[-/.月](\d{1,2})日?", text)
    if full:
        try:
            return date(int(full.group(1)), int(full.group(2)), int(full.group(3))).isoformat()
        except ValueError:
            return None
    short = re.search(r"(?<!\d)(\d{1,2})月(\d{1,2})日?", text)
    if short:
        try:
            candidate = date(base.year, int(short.group(1)), int(short.group(2)))
            if (candidate - base).days > 31:
                candidate = date(base.year - 1, candidate.month, candidate.day)
            return candidate.isoformat()
        except ValueError:
            return None
    return None


def _account_key(text: str, accounts: list[dict[str, Any]]) -> tuple[str | None, str | None]:
    active = [item for item in accounts if item.get("status", "active") == "active"]
    if "现金" in text:
        candidate = next((item for item in active if item.get("account_kind") == "cash" or "现金" in str(item.get("name"))), None)
        return (str(candidate["account_key"]), str(candidate["name"])) if candidate else (None, None)
    if "招商" in text or "招行" in text:
        candidate = next((item for item in active if "招商" in f"{item.get('institution', '')}{item.get('name', '')}"), None)
        return (str(candidate["account_key"]), str(candidate["name"])) if candidate else (None, None)
    if "工商" in text or "工行" in text:
        owner = "former_owner" if "前老板" in text else "store"
        candidate = next((item for item in active if item.get("owner_kind") == owner and "工商" in f"{item.get('institution', '')}{item.get('name', '')}"), None)
        return (str(candidate["account_key"]), str(candidate["name"])) if candidate else (None, None)
    return None, None


def _purpose(text: str) -> str | None:
    match = re.search(r"买(?:了)?(.+?)(?:花了|花|用了|用|付了|支付|[，,。\s]|$)", text)
    if match and match.group(1).strip():
        return f"购买{match.group(1).strip()}"
    for word, label in (
        ("挂号", "看病挂号"), ("水费", "店铺水费"), ("电费", "店铺电费"),
        ("电网", "店铺电费"), ("电力", "店铺电费"),
        ("房租", "店铺房租"), ("工资", "员工工资"), ("垃圾费", "垃圾处理费"),
    ):
        if word in text:
            return label
    return None


def parse_finance_text(text: str, *, today: str, accounts: list[dict[str, Any]]) -> dict[str, Any]:
    normalized = re.sub(r"\s+", " ", text.strip())
    amount = _extract_amount(normalized)
    business_date = _extract_date(normalized, today)
    account_key, account_name = _account_key(normalized, accounts)
    purpose = _purpose(normalized)
    counterparty = next((name for name in ("江西省电力", "淘宝", "美团", "京东", "抖音", "客如云") if name in normalized), None)

    personal_markers = ("个人", "自己用", "袜子", "衣服", "看病", "挂号", "日用品")
    inventory_markers = ("进货", "采购", "原料", "食材", "章鱼", "面粉", "鸡蛋", "包装盒", "耗材")
    store_expense_markers = ("店铺", "房租", "水费", "电费", "电网", "电力", "水电", "燃气", "垃圾费", "员工工资", "维修", "清洁", "推广费")
    if "前老板" in normalized and any(word in normalized for word in ("转给", "转回", "到账")):
        fact_type, scope = "former_owner_transfer", "store"
    elif any(word in normalized for word in ("借款到账", "借了", "借款")):
        fact_type, scope = "loan_in", "store"
    elif any(word in normalized for word in inventory_markers):
        fact_type, scope = "inventory_purchase", "store"
    elif any(word in normalized for word in store_expense_markers):
        fact_type, scope = "operating_expense", "store"
    elif any(word in normalized for word in personal_markers) or ("淘宝" in normalized and "买" in normalized):
        fact_type, scope = "personal_spending", "personal"
    elif any(word in normalized for word in ("营业额", "营业收入", "销售", "卖了")):
        fact_type, scope = "merchant_net_sale", "store"
    else:
        fact_type, scope = None, "unknown"

    # The owner confirmed that every store receipt belongs in the ICBC store
    # account.  Former-owner repayments may omit the receiving bank in a short
    # sentence, so use that explicit store rule instead of leaving the field
    # blank or falling back to the personal CMB account.
    if fact_type == "former_owner_transfer" and account_key is None:
        store_icbc = next(
            (
                item for item in accounts
                if item.get("status", "active") == "active"
                and item.get("owner_kind") == "store"
                and "工商" in f"{item.get('institution', '')}{item.get('name', '')}"
            ),
            None,
        )
        if store_icbc:
            account_key = str(store_icbc["account_key"])
            account_name = str(store_icbc["name"])

    category_key: str | None = None
    if fact_type == "personal_spending":
        category_key = "personal_spending_personal_account"
    elif fact_type == "inventory_purchase":
        category_key = "packaging_purchase" if any(word in normalized for word in ("包装盒", "包装", "餐盒")) else "food_purchase"
    elif fact_type == "operating_expense":
        if any(word in normalized for word in ("水费", "电费", "电网", "电力", "水电", "燃气")):
            category_key = "utilities"
        elif any(word in normalized for word in ("垃圾费", "物业费")):
            category_key = "waste_property_fee"
        elif "房租" in normalized:
            category_key = "rent_mall_fee"
        elif any(word in normalized for word in ("加班", "临时工")):
            category_key = "overtime_temp_labor"
        elif "工资" in normalized:
            category_key = "employee_wage"
        else:
            category_key = "other_operating_expense"
    elif fact_type == "former_owner_transfer":
        category_key = "former_owner_transfer"
    elif fact_type == "loan_in":
        category_key = "loan_received"

    category = find_finance_category(category_key)
    category_code = category.get("account_code") if category else None
    category_name = category.get("name") if category else None

    fields = {
        "fact_type": fact_type,
        "business_date": business_date,
        "amount": amount,
        "account_key": account_key,
        "counterparty": counterparty,
        "category_code": category_code,
        "category_name": category_name,
        "business_category_key": category_key,
        "source_basis": "自然语言自动识别",
        "notes": purpose or normalized,
    }
    missing_fields = [key for key in ("fact_type", "business_date", "amount", "account_key") if not fields.get(key)]
    return {
        "schema_version": SCHEMA_VERSION,
        "original_text": normalized,
        "fields": fields,
        "account_name": account_name,
        "business_scope": scope,
        "profit_treatment": (
            "excluded_personal" if scope == "personal"
            else "inventory_not_expensed" if fact_type == "inventory_purchase"
            else "store_profit_effect" if fact_type == "operating_expense"
            else "separate_from_revenue" if fact_type in {"former_owner_transfer", "loan_in"}
            else "revenue" if fact_type == "merchant_net_sale"
            else "unknown"
        ),
        "missing_fields": missing_fields,
        "can_confirm": not missing_fields,
        "confidence": {
            key: "high" if value not in (None, "") else "missing"
            for key, value in fields.items()
            if key in {"fact_type", "business_date", "amount", "account_key", "counterparty", "category_name"}
        },
    }
