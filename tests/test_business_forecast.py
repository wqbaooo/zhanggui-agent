import asyncio
from datetime import date, timedelta

from fastapi.testclient import TestClient

from core.business_forecast import build_business_forecast
from server.main import app
from server.routes import analyze


PROJECT_ID = "xinyu-hengtai-dakou"


def _revenue_rows(start: date, values: list[int]) -> list[dict]:
    return [
        {
            "business_date": (start + timedelta(days=index)).isoformat(),
            "revenue_minor": value,
            "orders": max(1, round(value / 1500)),
        }
        for index, value in enumerate(values)
    ]


def _weather(start: date, kinds: list[str]) -> dict:
    return {
        "status": "live",
        "forecast_source": "weather.com.cn",
        "forecast_updated_at": f"{start.isoformat()} 08:00",
        "forecast": [
            {
                "date": (start + timedelta(days=index)).isoformat(),
                "weather": kind,
                "weather_text": {
                    "sunny": "晴",
                    "light_rain": "小雨",
                    "heavy_rain": "暴雨",
                }.get(kind, kind),
                "temp_high": 36 if kind == "sunny" and index == 2 else 31,
                "temp_low": 25,
            }
            for index, kind in enumerate(kinds)
        ],
    }


def test_forecast_uses_confirmed_revenue_and_keeps_weather_as_range_risk():
    as_of = date(2026, 7, 21)
    revenue_rows = _revenue_rows(
        date(2026, 7, 7),
        [
            100_000,
            100_000,
            98_000,
            101_000,
            130_000,
            140_000,
            100_000,
            100_000,
            100_000,
            98_000,
            101_000,
            130_000,
            140_000,
            100_000,
        ],
    )
    result = build_business_forecast(
        project_id=PROJECT_ID,
        as_of=as_of,
        revenue_rows=revenue_rows,
        sku_forecast=[],
        inventory_fact_date=None,
        weather=_weather(as_of, ["sunny", "heavy_rain", "sunny", "sunny", "sunny", "sunny", "sunny"]),
    )

    revenue = result["revenue"]
    assert result["permission"] == "read_only"
    assert revenue["status"] == "partial"
    assert revenue["confidence"] == "low"
    assert revenue["sample_days"] == 14
    assert len(revenue["forecast_days"]) == 7
    assert revenue["weather_adjustment"] == "range_only_not_directional"
    assert revenue["forecast_days"][0]["predicted_minor"] == revenue["forecast_days"][1]["predicted_minor"]
    assert (
        revenue["forecast_days"][1]["high_minor"] - revenue["forecast_days"][1]["low_minor"]
        > revenue["forecast_days"][0]["high_minor"] - revenue["forecast_days"][0]["low_minor"]
    )
    assert revenue["total_low_minor"] <= revenue["total_predicted_minor"] <= revenue["total_high_minor"]
    assert any("天气没有历史校准" in gap for gap in result["gaps"])


def test_forecast_never_invents_revenue_or_inventory_when_facts_are_missing():
    as_of = date(2026, 7, 21)
    result = build_business_forecast(
        project_id=PROJECT_ID,
        as_of=as_of,
        revenue_rows=_revenue_rows(date(2026, 7, 18), [100_000, 110_000, 90_000]),
        sku_forecast=[
            {
                "sku_id": "sku-octopus",
                "name": "章鱼粒",
                "unit": "包",
                "action": "not_enough_data",
                "risk_level": "unknown",
                "current_stock": 2,
                "safety_stock": 0,
                "days_remaining": None,
                "stockout_date": None,
                "recommend_qty": None,
                "recommend_amount": None,
                "observed_daily_consumption": 0,
                "consumption_per_day": 0,
            }
        ],
        inventory_fact_date=date(2026, 7, 3),
        weather={"status": "unavailable", "forecast": []},
    )

    revenue = result["revenue"]
    inventory = result["inventory"]
    assert revenue["status"] == "insufficient"
    assert revenue["forecast_days"] == []
    assert revenue["total_predicted_minor"] is None
    assert inventory["status"] == "insufficient"
    assert inventory["modelled_skus"] == 0
    assert inventory["unknown_skus"] == 1
    assert inventory["risks"] == []
    assert any("不能计算断货日" in gap for gap in inventory["gaps"])
    assert any(alert["kind"] == "data_gap" for alert in result["alerts"])


def test_inventory_alerts_only_use_skus_with_consumption_and_safety_facts():
    as_of = date(2026, 7, 21)
    result = build_business_forecast(
        project_id=PROJECT_ID,
        as_of=as_of,
        revenue_rows=_revenue_rows(date(2026, 7, 14), [100_000] * 8),
        sku_forecast=[
            {
                "sku_id": "sku-box",
                "name": "6粒盒",
                "unit": "个",
                "action": "urgent",
                "risk_level": "high",
                "current_stock": 80,
                "safety_stock": 100,
                "days_remaining": 0,
                "stockout_date": "2026-07-21",
                "recommend_qty": 300,
                "recommend_amount": 108,
                "observed_daily_consumption": 30,
                "consumption_per_day": 0,
            },
            {
                "sku_id": "sku-powder",
                "name": "章鱼烧粉",
                "unit": "包",
                "action": "not_enough_data",
                "risk_level": "unknown",
                "current_stock": 3,
                "safety_stock": 0,
                "days_remaining": None,
                "stockout_date": None,
                "recommend_qty": None,
                "recommend_amount": None,
                "observed_daily_consumption": 0,
                "consumption_per_day": 0,
            },
        ],
        inventory_fact_date=as_of,
        weather=_weather(as_of, ["sunny"] * 7),
    )

    inventory = result["inventory"]
    assert inventory["status"] == "partial"
    assert inventory["modelled_skus"] == 1
    assert inventory["unknown_skus"] == 1
    assert [item["sku_id"] for item in inventory["risks"]] == ["sku-box"]
    assert any(alert["kind"] == "inventory" and alert["level"] == "high" for alert in result["alerts"])


def test_business_forecast_endpoint_rejects_invalid_scope_and_date():
    client = TestClient(app)

    assert client.get("/api/projects/demo-store/analyze/business-forecast").status_code == 403
    response = client.get(
        f"/api/projects/{PROJECT_ID}/analyze/business-forecast",
        params={"as_of": "2026/07/21"},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "as_of 必须是 YYYY-MM-DD"


def test_slow_weather_degrades_without_blocking_business_facts(monkeypatch):
    async def slow_weather():
        await asyncio.sleep(0.05)
        return {"status": "live", "forecast": []}

    monkeypatch.setattr(analyze, "get_weather", slow_weather)
    monkeypatch.setattr(analyze, "FORECAST_WEATHER_TIMEOUT_SECONDS", 0.01)
    monkeypatch.setattr(analyze, "_FORECAST_WEATHER_CACHE", None)
    monkeypatch.setattr(analyze, "_FORECAST_WEATHER_CACHED_AT", 0.0)

    weather = asyncio.run(analyze._weather_for_business_forecast())

    assert weather["status"] == "unavailable"
    assert weather["forecast"] == []
