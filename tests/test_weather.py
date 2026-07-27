from fastapi.testclient import TestClient

from server.main import app
from server.routes import weather as weather_route


def _china_forecast():
    rows = []
    for index, (date, weather, high, low) in enumerate(
        [
            ("2026-07-20", "heavy_rain", 28, 25),
            ("2026-07-21", "heavy_rain", 28, 25),
            ("2026-07-22", "thunderstorm", 34, 26),
            ("2026-07-23", "cloudy", 35, 28),
            ("2026-07-24", "cloudy", 35, 28),
            ("2026-07-25", "cloudy", 37, 28),
            ("2026-07-26", "cloudy", 37, 27),
        ]
    ):
        rows.append(
            {
                "date": date,
                "weather": weather,
                "weather_text": "暴雨" if index == 0 else "多云",
                "temp_high": high,
                "temp_low": low,
                "humidity": None,
                "wind": "西南风 <3级",
                "precipitation_probability": None,
            }
        )
    return {
        "forecast": rows,
        "updated_at": "2026-07-19 20:00",
        "source": "weather.com.cn",
    }


def _amap_weather():
    return {
        "current": {
            "weather": "light_rain",
            "weather_text": "小雨",
            "temperature": 25,
            "humidity": 98,
            "wind": "南风 ≤3级",
            "observed_at": "2026-07-20 02:03",
        },
        "forecast": [
            {
                "date": "2026-07-20",
                "weather": "heavy_rain",
                "weather_text": "暴雨",
                "temp_high": 28,
                "temp_low": 25,
                "humidity": None,
                "wind": "西南风 1-3级",
                "precipitation_probability": None,
            }
        ],
        "updated_at": "2026-07-20 02:03",
        "source": "amap",
    }


def test_weather_uses_verified_location_live_temperature_and_seven_dates(monkeypatch):
    async def fake_amap():
        return _amap_weather()

    async def fake_china_weather():
        return _china_forecast()

    async def open_meteo_must_not_run():
        raise AssertionError("完整的高德实时天气和中国天气网预报不应再等待 Open-Meteo")

    monkeypatch.setattr(weather_route, "_weather_now", lambda: weather_route.datetime.fromisoformat("2026-07-20T02:20:00+08:00"))
    monkeypatch.setattr(weather_route, "_fetch_amap_weather", fake_amap)
    monkeypatch.setattr(weather_route, "_fetch_china_weather", fake_china_weather)
    monkeypatch.setattr(weather_route, "_fetch_open_meteo", open_meteo_must_not_run)

    response = TestClient(app).get("/api/weather")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "live"
    assert payload["coordinates"] == {"latitude": 27.822376, "longitude": 114.910923}
    assert payload["address"] == "江西省新余市渝水区北湖西路158号恒太城(南门)"
    assert payload["current_source"] == "amap"
    assert payload["forecast_source"] == "weather.com.cn"
    assert payload["current"]["temperature"] == 25
    assert payload["current"]["temp_high"] == 28
    assert payload["current"]["humidity"] == 98
    assert [item["date"] for item in payload["forecast"]] == [
        "2026-07-20",
        "2026-07-21",
        "2026-07-22",
        "2026-07-23",
        "2026-07-24",
        "2026-07-25",
        "2026-07-26",
    ]
    assert all(item["weather"] != "unknown" for item in payload["forecast"])


def test_weather_never_fabricates_values_when_all_sources_fail(monkeypatch):
    async def unavailable():
        return None

    monkeypatch.setattr(weather_route, "_weather_now", lambda: weather_route.datetime.fromisoformat("2026-07-20T02:20:00+08:00"))
    monkeypatch.setattr(weather_route, "_fetch_amap_weather", unavailable)
    monkeypatch.setattr(weather_route, "_fetch_china_weather", unavailable)
    monkeypatch.setattr(weather_route, "_fetch_open_meteo", unavailable)

    response = TestClient(app).get("/api/weather")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "unavailable"
    assert payload["current"]["weather"] == "unknown"
    assert payload["current"]["temperature"] is None
    assert payload["current"]["humidity"] is None
    assert len(payload["forecast"]) == 7
    assert all(item["temp_high"] is None for item in payload["forecast"])
    assert all(item["temp_low"] is None for item in payload["forecast"])
    assert payload["warnings"]


def test_china_weather_parser_combines_seven_and_extended_pages():
    seven_day_html = """
    <div id="7d">
      <input id="fc_24h_internal_update_time" value="2026071920"/>
      <ul class="t clearfix">
        <li class="sky"><h1>25日（周六）</h1><p class="wea" title="多云">多云</p>
          <p class="tem"><span>37℃</span>/<i>28℃</i></p>
          <p class="win"><em><span title="南风"></span></em><i>&lt;3级</i></p>
        </li>
      </ul>
    </div>
    """
    extended_html = """
    <div id="15d">
      <input id="fc_15d_24h_internal_update_time" value="2026071920"/>
      <ul class="t clearfix">
        <li><span class="time">周日（26日）</span><span class="wea">多云</span>
          <span class="tem"><em>37℃</em>/27℃</span>
          <span class="wind">东南风转东风</span><span class="wind1">&lt;3级</span>
        </li>
      </ul>
    </div>
    """

    parsed = weather_route._parse_china_weather_pages(seven_day_html, extended_html)

    assert parsed["updated_at"] == "2026-07-19 20:00"
    assert parsed["forecast"] == [
        {
            "date": "2026-07-25",
            "weather": "cloudy",
            "weather_text": "多云",
            "temp_high": 37,
            "temp_low": 28,
            "humidity": None,
            "wind": "南风 <3级",
            "precipitation_probability": None,
        },
        {
            "date": "2026-07-26",
            "weather": "cloudy",
            "weather_text": "多云",
            "temp_high": 37,
            "temp_low": 27,
            "humidity": None,
            "wind": "东南风转东风 <3级",
            "precipitation_probability": None,
        },
    ]
