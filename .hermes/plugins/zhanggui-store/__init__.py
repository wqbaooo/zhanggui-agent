"""Read-only store fact tools for the product-facing Hermes runtime."""

from . import schemas, tools


_TOOLS = (
    ("store_finance_overview", schemas.FINANCE_OVERVIEW, tools.finance_overview),
    ("store_finance_date_coverage", schemas.FINANCE_DATE_COVERAGE, tools.finance_date_coverage),
    ("store_daily_finance", schemas.DAILY_FINANCE, tools.daily_finance),
    ("store_cash_forecast", schemas.CASH_FORECAST, tools.cash_forecast),
    ("store_inventory_summary", schemas.INVENTORY_SUMMARY, tools.inventory_summary),
    ("store_operations_summary", schemas.OPERATIONS_SUMMARY, tools.operations_summary),
)


def register(ctx) -> None:
    for name, schema, handler in _TOOLS:
        ctx.register_tool(
            name=name,
            toolset="zhanggui-store",
            schema=schema,
            handler=handler,
            description=schema["description"],
            emoji="🏪",
        )
