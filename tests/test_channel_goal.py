from models.channel_goal import analyze_channel_goal, find_goal_amount, render_channel_goal_answer


def test_channel_goal_uses_real_channel_orders_and_receipts():
    result = analyze_channel_goal(
        [
            {
                "date": "2026-07-10",
                "dine_in_orders": 40,
                "dine_in_revenue": 623.71,
                "delivery_orders": 23,
                "delivery_revenue": 284.82,
            }
        ],
        target_revenue=1000,
    )

    assert result["status"] == "ready"
    assert result["source_date"] == "2026-07-10"
    assert result["channels"]["dine_in"]["avg_receipt"] == 15.59
    assert result["channels"]["delivery"]["avg_receipt"] == 12.38
    assert result["blended_avg_receipt"] == 14.42
    assert result["target_total_orders"] == 70
    assert result["target_orders"]["dine_in"] == 44
    assert result["target_orders"]["delivery"] == 26
    assert result["estimated_target_revenue"] >= 1000


def test_channel_goal_refuses_zero_when_channel_split_is_unknown():
    result = analyze_channel_goal(
        [{
            "date": "2026-07-10",
            "orders": 70,
            "actual_revenue": 1052.78,
            "dine_in_orders": 0,
            "delivery_orders": 0,
            "unknown_fields": ["dine_in_orders", "delivery_orders"],
        }],
        target_revenue=1000,
    )

    assert result["status"] == "needs_channel_split"
    assert "堂食/外卖" in result["gaps"][0]


def test_goal_amount_parser_supports_owner_language():
    assert find_goal_amount("实收目标1000元需要多少堂食单和外卖单") == 1000
    assert find_goal_amount("今天卖到 ¥1288，要做多少单") == 1288
    assert find_goal_amount("今天堂食和外卖怎么样") is None


def test_channel_goal_answer_names_its_data_source_and_limits():
    result = analyze_channel_goal([
        {"date": "2026-07-10", "dine_in_orders": 40, "dine_in_revenue": 623.71, "delivery_orders": 23, "delivery_revenue": 284.82}
    ], target_revenue=1000)

    answer = render_channel_goal_answer(result)

    assert "2026-07-10" in answer
    assert "堂食 44 单、外卖 26 单" in answer
    assert "不等于线上曝光或线下进店客流" in answer
