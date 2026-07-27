from server.routes.analyze import _build_analysis_prompt


def test_analysis_prompt_keeps_unknown_cost_rates_out_of_arithmetic():
    prompt = _build_analysis_prompt(
        {
            "total_revenue": 14771.48,
            "net_profit": None,
            "profit_ready": False,
            "total_orders": 0,
            "prime_cost_rate": None,
            "food_cost_rate": None,
            "delivery_rate": None,
            "avg_order_value": None,
            "entry_count": 12,
            "settlement_summary": {},
            "product_sales": [],
        },
        today_entry=None,
        prev_summary=None,
    )

    assert "净利：暂不可计算" in prompt
    assert "食材成本率：待确认" in prompt
    assert "人工+食材成本率：待确认" in prompt
    assert "外卖营收占比：待确认" in prompt
