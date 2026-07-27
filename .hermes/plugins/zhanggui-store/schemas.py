"""Schemas exposed to Hermes. Every tool is read-only and evidence-backed."""

_DATE = {"type": "string", "description": "YYYY-MM-DD 格式的业务日期"}
_PERIOD = {
    "type": "object",
    "properties": {"start": _DATE, "end": _DATE},
}

FINANCE_OVERVIEW = {
    "name": "store_finance_overview",
    "description": (
        "查询门店已确认财务概览、收入、支出、到账、利润及资料完整度。"
        "回答金额、利润、资金位置或整体财务问题前必须调用。"
    ),
    "parameters": _PERIOD,
}

FINANCE_DATE_COVERAGE = {
    "name": "store_finance_date_coverage",
    "description": (
        "逐日查询客如云、美团外卖、淘宝闪购、京东外卖、抖音团购、美团团购和现金的录入完整度。"
        "用于回答哪些天没录、哪个平台缺失、日结是否完整。"
    ),
    "parameters": {
        "type": "object",
        "properties": {"start": _DATE, "end": _DATE},
        "required": ["start", "end"],
    },
}

DAILY_FINANCE = {
    "name": "store_daily_finance",
    "description": "查询指定日期的营业收入、支出、资金流、平台录入和凭证状态。",
    "parameters": {
        "type": "object",
        "properties": {"date": _DATE},
        "required": ["date"],
    },
}

CASH_FORECAST = {
    "name": "store_cash_forecast",
    "description": "查询门店资金链、可用现金、平台待到账和现金可支撑天数。",
    "parameters": {"type": "object", "properties": {"as_of": _DATE}},
}

INVENTORY_SUMMARY = {
    "name": "store_inventory_summary",
    "description": "查询门店库存校准进度、物料数、库存价值、短缺和采购风险。",
    "parameters": {"type": "object", "properties": {}},
}

OPERATIONS_SUMMARY = {
    "name": "store_operations_summary",
    "description": "查询最近 N 天门店经营汇总，包括营收、订单、成本、评价等已有事实。",
    "parameters": {
        "type": "object",
        "properties": {"days": {"type": "integer", "minimum": 1, "maximum": 366, "default": 30}},
    },
}
