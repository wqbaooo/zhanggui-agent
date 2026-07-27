#!/usr/bin/env python3
"""天气商圈路由：恒太城准确定位 + 高德实况 + 中国天气网 7 日预报。"""

from __future__ import annotations

import asyncio
import calendar
import logging
import re
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import httpx
from bs4 import BeautifulSoup
from fastapi import APIRouter

import config

logger = logging.getLogger("weather")

router = APIRouter(prefix="/api", tags=["weather"])

SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")
TIMEOUT = 5.0
OPEN_METEO_TIMEOUT = 3.0

# 门店位置由高德地理编码核验（兴趣点级），避免继续使用新余市中心坐标。
STORE_CITY = "新余市"
STORE_DISTRICT = "渝水区"
STORE_LOCATION = "恒太城五楼美食城"
STORE_ADDRESS = "江西省新余市渝水区北湖西路158号恒太城(南门)"
STORE_LAT = 27.822376
STORE_LON = 114.910923
STORE_AMAP_ADCODE = "360502"
STORE_WEATHER_COM_ID = "101241003"

AMAP_WEATHER_URL = "https://restapi.amap.com/v3/weather/weatherInfo"
OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
CHINA_WEATHER_7D_URL = f"https://www.weather.com.cn/weather/{STORE_WEATHER_COM_ID}.shtml"
CHINA_WEATHER_15D_URL = f"https://www.weather.com.cn/weather15d/{STORE_WEATHER_COM_ID}.shtml"

WEEKDAYS_CN = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

# WMO 天气码 → 内部 weather 类型
WMO_MAP: dict[int, str] = {
    0: "sunny",
    1: "sunny",
    2: "cloudy",
    3: "overcast",
    45: "fog",
    48: "fog",
    51: "light_rain",
    53: "light_rain",
    55: "light_rain",
    61: "light_rain",
    63: "heavy_rain",
    65: "heavy_rain",
    71: "snow",
    73: "snow",
    75: "snow",
    80: "light_rain",
    81: "heavy_rain",
    82: "heavy_rain",
    85: "snow",
    86: "snow",
    95: "thunderstorm",
    96: "thunderstorm",
    99: "thunderstorm",
}

WEATHER_CN = {
    "sunny": "晴",
    "cloudy": "多云",
    "overcast": "阴",
    "light_rain": "小雨",
    "heavy_rain": "大雨",
    "thunderstorm": "雷阵雨",
    "snow": "雪",
    "fog": "雾",
    "unknown": "暂不可用",
}

# 事件必须带可核验来源后才能进入经营建议。暂不以推测填充商圈日历。
LOCAL_EVENTS: list[dict] = []


def _weather_now() -> datetime:
    return datetime.now(SHANGHAI_TZ)


def _number(value) -> int | float | None:
    if value in (None, "", "null"):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return int(number) if number.is_integer() else round(number, 1)


def _weather_type_from_text(text: str) -> str:
    """把中文天气描述归一化；复合天气按更需要预警的一侧处理。"""
    value = (text or "").strip()
    if not value:
        return "unknown"
    if "雷" in value:
        return "thunderstorm"
    if "雪" in value:
        return "snow"
    if "雾" in value or "霾" in value:
        return "fog"
    if any(keyword in value for keyword in ("暴雨", "大雨", "中雨")):
        return "heavy_rain"
    if "雨" in value:
        return "light_rain"
    if "阴" in value:
        return "overcast"
    if "多云" in value:
        return "cloudy"
    if "晴" in value:
        return "sunny"
    return "unknown"


def _generate_tips(weather: str, temp_high: int | float | None, is_weekend: bool) -> list[str]:
    """只根据已取得的天气事实给动作，不生成客流或备货百分比。"""
    if weather == "unknown":
        return ["天气服务暂不可用，按实时订单和现场客流滚动调整"]

    tips: list[str] = []
    if weather in ("light_rain", "heavy_rain", "thunderstorm"):
        tips.append("提前检查外卖包装、防漏和骑手取餐区")
    if weather in ("heavy_rain", "thunderstorm"):
        tips.append("关注商场到店客流，按实时订单滚动备料")
    if weather == "sunny" and is_weekend:
        tips.append("周末天气较好，提前检查高峰时段备料与排班")
    if temp_high is not None and temp_high > 35:
        tips.append("高温天气，关注食材冷藏、成品等待和员工补水")
    elif temp_high is not None and temp_high > 32:
        tips.append("温度偏高，缩短出餐到取餐等待时间")
    if temp_high is not None and temp_high < 10:
        tips.append("低温天气，检查热食保温和打包温度")
    if not tips:
        tips.append("天气未触发额外风险，维持标准作业并观察实时客流")
    return tips


def _next_month(year: int, month: int) -> tuple[int, int]:
    if month == 12:
        return year + 1, 1
    return year, month + 1


def _resolve_dates(report_date: date, day_numbers: list[int]) -> list[date]:
    """把网页中的“26日”还原成完整日期，并正确处理跨月。"""
    year, month = report_date.year, report_date.month
    previous_day = report_date.day
    resolved: list[date] = []
    for day_number in day_numbers:
        if day_number < previous_day:
            year, month = _next_month(year, month)
        max_day = calendar.monthrange(year, month)[1]
        if not 1 <= day_number <= max_day:
            continue
        resolved.append(date(year, month, day_number))
        previous_day = day_number
    return resolved


def _report_timestamp(soup: BeautifulSoup, *element_ids: str) -> tuple[datetime, str] | None:
    for element_id in element_ids:
        node = soup.find(id=element_id)
        raw = node.get("value", "") if node else ""
        if re.fullmatch(r"\d{10,12}", raw):
            parsed = datetime.strptime(raw[:10], "%Y%m%d%H").replace(tzinfo=SHANGHAI_TZ)
            return parsed, parsed.strftime("%Y-%m-%d %H:%M")
    return None


def _parse_temperature(node) -> tuple[int | None, int | None]:
    if node is None:
        return None, None
    values = [int(item) for item in re.findall(r"-?\d+", node.get_text(" ", strip=True))]
    if len(values) >= 2:
        return values[0], values[1]
    if len(values) == 1:
        # 中国天气网当天已经过白天高温时可能只保留最低温。
        return None, values[0]
    return None, None


def _parse_china_weather_pages(seven_day_html: str, extended_html: str) -> dict | None:
    """解析中国天气网 7 日与 8-15 日页面，补齐跨午夜后的连续 7 天。"""
    seven_soup = BeautifulSoup(seven_day_html or "", "html.parser")
    extended_soup = BeautifulSoup(extended_html or "", "html.parser")
    report = _report_timestamp(
        seven_soup,
        "fc_24h_internal_update_time",
    ) or _report_timestamp(
        extended_soup,
        "fc_15d_24h_internal_update_time",
    )
    if report is None:
        return None
    report_datetime, updated_at = report

    rows: list[dict] = []
    seven_container = seven_soup.find(id="7d")
    seven_nodes = seven_container.select("ul.t > li") if seven_container else []
    seven_days = []
    for node in seven_nodes:
        label = node.select_one("h1")
        match = re.search(r"(\d{1,2})日", label.get_text(" ", strip=True) if label else "")
        if match:
            seven_days.append(int(match.group(1)))
    seven_dates = _resolve_dates(report_datetime.date(), seven_days)

    for node, forecast_date in zip(seven_nodes, seven_dates):
        weather_node = node.select_one(".wea")
        weather_text = (
            weather_node.get("title")
            if weather_node and weather_node.get("title")
            else weather_node.get_text(" ", strip=True) if weather_node else ""
        )
        temp_high, temp_low = _parse_temperature(node.select_one(".tem"))
        directions = []
        for direction in node.select(".win span[title]"):
            title = direction.get("title", "").strip()
            if title and title not in directions:
                directions.append(title)
        wind_power = node.select_one(".win > i")
        wind = "转".join(directions)
        if wind_power:
            wind = f"{wind} {wind_power.get_text(' ', strip=True)}".strip()
        rows.append(
            {
                "date": forecast_date.isoformat(),
                "weather": _weather_type_from_text(weather_text),
                "weather_text": weather_text,
                "temp_high": temp_high,
                "temp_low": temp_low,
                "humidity": None,
                "wind": wind,
                "precipitation_probability": None,
            }
        )

    extended_container = extended_soup.find(id="15d")
    extended_nodes = extended_container.select("ul.t > li") if extended_container else []
    extended_days = []
    for node in extended_nodes:
        label = node.select_one(".time")
        match = re.search(r"(\d{1,2})日", label.get_text(" ", strip=True) if label else "")
        if match:
            extended_days.append(int(match.group(1)))
    extended_dates = _resolve_dates(report_datetime.date(), extended_days)

    for node, forecast_date in zip(extended_nodes, extended_dates):
        weather_node = node.select_one(".wea")
        weather_text = weather_node.get_text(" ", strip=True) if weather_node else ""
        temp_high, temp_low = _parse_temperature(node.select_one(".tem"))
        wind_parts = [
            part.get_text(" ", strip=True)
            for part in (node.select_one(".wind"), node.select_one(".wind1"))
            if part and part.get_text(" ", strip=True)
        ]
        rows.append(
            {
                "date": forecast_date.isoformat(),
                "weather": _weather_type_from_text(weather_text),
                "weather_text": weather_text,
                "temp_high": temp_high,
                "temp_low": temp_low,
                "humidity": None,
                "wind": " ".join(wind_parts),
                "precipitation_probability": None,
            }
        )

    unique_rows = {row["date"]: row for row in rows}
    if not unique_rows:
        return None
    return {
        "forecast": [unique_rows[key] for key in sorted(unique_rows)],
        "updated_at": updated_at,
        "source": "weather.com.cn",
    }


async def _fetch_china_weather() -> dict | None:
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; ZhangguiAgent/1.0; +local-store-weather)",
        "Accept-Language": "zh-CN,zh;q=0.9",
    }
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=True, headers=headers) as client:
            results = await asyncio.gather(
                client.get(CHINA_WEATHER_7D_URL),
                client.get(CHINA_WEATHER_15D_URL),
                return_exceptions=True,
            )
        html_pages: list[str] = []
        for result in results:
            if isinstance(result, Exception):
                logger.warning("China Weather request failed: %s", result)
                html_pages.append("")
                continue
            result.raise_for_status()
            html_pages.append(result.text)
        parsed = _parse_china_weather_pages(*html_pages)
        if parsed is None:
            logger.warning("China Weather returned no parseable forecast")
        return parsed
    except Exception as exc:
        logger.warning("China Weather request failed: %s", exc)
        return None


async def _fetch_amap_weather() -> dict | None:
    """高德提供渝水区实时温湿度、风力和未来 4 天预报。"""
    if not config.AMAP_WEBSERVICE_KEY:
        logger.warning("AMAP_WEBSERVICE_KEY is not configured")
        return None
    params = {
        "key": config.AMAP_WEBSERVICE_KEY,
        "city": STORE_AMAP_ADCODE,
        "output": "JSON",
    }
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            live_result, forecast_result = await asyncio.gather(
                client.get(AMAP_WEATHER_URL, params={**params, "extensions": "base"}),
                client.get(AMAP_WEATHER_URL, params={**params, "extensions": "all"}),
            )
        live_result.raise_for_status()
        forecast_result.raise_for_status()
        live_payload = live_result.json()
        forecast_payload = forecast_result.json()
        if live_payload.get("status") != "1" or not live_payload.get("lives"):
            raise ValueError(live_payload.get("info") or "高德实时天气无数据")
        if forecast_payload.get("status") != "1" or not forecast_payload.get("forecasts"):
            raise ValueError(forecast_payload.get("info") or "高德天气预报无数据")

        live = live_payload["lives"][0]
        forecast_meta = forecast_payload["forecasts"][0]
        forecast_rows = []
        for item in forecast_meta.get("casts", []):
            day_weather = str(item.get("dayweather") or "")
            night_weather = str(item.get("nightweather") or "")
            weather_text = day_weather
            if night_weather and night_weather != day_weather:
                weather_text = f"{day_weather}转{night_weather}"
            direction = str(item.get("daywind") or "").strip()
            power = str(item.get("daypower") or "").strip()
            forecast_rows.append(
                {
                    "date": str(item.get("date") or ""),
                    "weather": _weather_type_from_text(weather_text),
                    "weather_text": weather_text,
                    "temp_high": _number(item.get("daytemp")),
                    "temp_low": _number(item.get("nighttemp")),
                    "humidity": None,
                    "wind": f"{direction}风 {power}级".strip() if direction or power else "",
                    "precipitation_probability": None,
                }
            )

        weather_text = str(live.get("weather") or "")
        direction = str(live.get("winddirection") or "").strip()
        power = str(live.get("windpower") or "").strip()
        observed_at = str(live.get("reporttime") or "")
        return {
            "current": {
                "weather": _weather_type_from_text(weather_text),
                "weather_text": weather_text,
                "temperature": _number(live.get("temperature")),
                "humidity": _number(live.get("humidity")),
                "wind": f"{direction}风 {power}级".strip() if direction or power else "",
                "observed_at": observed_at,
            },
            "forecast": forecast_rows,
            "updated_at": str(forecast_meta.get("reporttime") or observed_at),
            "source": "amap",
        }
    except Exception as exc:
        logger.warning("AMap weather request failed: %s", exc)
        return None


async def _fetch_open_meteo() -> dict | None:
    """备用天气源；只有主源不完整时才调用。"""
    params = {
        "latitude": STORE_LAT,
        "longitude": STORE_LON,
        "current": "temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m",
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,wind_speed_10m_max",
        "timezone": "Asia/Shanghai",
        "forecast_days": 7,
    }
    try:
        async with httpx.AsyncClient(timeout=OPEN_METEO_TIMEOUT) as client:
            response = await client.get(OPEN_METEO_URL, params=params)
            response.raise_for_status()
            payload = response.json()
    except Exception as exc:
        logger.warning("Open-Meteo request failed: %s", exc)
        return None

    current_payload = payload.get("current") or {}
    daily = payload.get("daily") or {}
    dates = daily.get("time") or []
    codes = daily.get("weather_code") or daily.get("weathercode") or []
    highs = daily.get("temperature_2m_max") or []
    lows = daily.get("temperature_2m_min") or []
    precips = daily.get("precipitation_probability_max") or []
    winds = daily.get("wind_speed_10m_max") or []
    forecast_rows = []
    for index, forecast_date in enumerate(dates):
        code = int(codes[index]) if index < len(codes) and codes[index] is not None else -1
        weather = WMO_MAP.get(code, "unknown")
        forecast_rows.append(
            {
                "date": forecast_date,
                "weather": weather,
                "weather_text": WEATHER_CN[weather],
                "temp_high": _number(highs[index]) if index < len(highs) else None,
                "temp_low": _number(lows[index]) if index < len(lows) else None,
                "humidity": None,
                "wind": f"{_number(winds[index])} km/h" if index < len(winds) and _number(winds[index]) is not None else "",
                "precipitation_probability": _number(precips[index]) if index < len(precips) else None,
            }
        )

    current_code = int(current_payload.get("weather_code", -1))
    current_weather = WMO_MAP.get(current_code, "unknown")
    return {
        "current": {
            "weather": current_weather,
            "weather_text": WEATHER_CN[current_weather],
            "temperature": _number(current_payload.get("temperature_2m")),
            "humidity": _number(current_payload.get("relative_humidity_2m")),
            "wind": (
                f"{_number(current_payload.get('wind_speed_10m'))} km/h"
                if _number(current_payload.get("wind_speed_10m")) is not None
                else ""
            ),
            "observed_at": str(current_payload.get("time") or ""),
        },
        "forecast": forecast_rows,
        "updated_at": str(current_payload.get("time") or ""),
        "source": "open-meteo",
    }


def _valid_forecast_row(row: dict | None) -> bool:
    return bool(
        row
        and row.get("weather") != "unknown"
        and row.get("temp_high") is not None
        and row.get("temp_low") is not None
    )


def _fill_missing(primary: dict, fallback: dict) -> dict:
    merged = dict(primary)
    for key in (
        "weather",
        "weather_text",
        "temp_high",
        "temp_low",
        "humidity",
        "wind",
        "precipitation_probability",
    ):
        value = merged.get(key)
        if value in (None, "", "unknown", "暂不可用"):
            merged[key] = fallback.get(key)
    return merged


def _parse_source_time(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.replace("T", " ").replace("+08:00", "")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    return parsed.replace(tzinfo=SHANGHAI_TZ) if parsed.tzinfo is None else parsed.astimezone(SHANGHAI_TZ)


def _is_stale(value: str | None, now: datetime, max_hours: int) -> bool:
    parsed = _parse_source_time(value)
    return bool(parsed and now - parsed > timedelta(hours=max_hours))


def _unknown_forecast_row(forecast_date: date) -> dict:
    return {
        "date": forecast_date.isoformat(),
        "weather": "unknown",
        "weather_text": "暂不可用",
        "temp_high": None,
        "temp_low": None,
        "humidity": None,
        "wind": "",
        "precipitation_probability": None,
    }


@router.get("/weather")
async def get_weather():
    """返回恒太城实时天气、连续 7 日预报、来源与数据新鲜度。"""
    now = _weather_now()
    today = now.date()
    target_dates = [(today + timedelta(days=index)).isoformat() for index in range(7)]

    amap, china_weather = await asyncio.gather(
        _fetch_amap_weather(),
        _fetch_china_weather(),
    )

    initial_rows = {}
    for provider in (china_weather, amap):
        for row in (provider or {}).get("forecast", []):
            if row.get("date") in target_dates:
                existing = initial_rows.get(row["date"])
                initial_rows[row["date"]] = _fill_missing(existing, row) if existing else dict(row)

    has_current = bool(
        amap
        and amap.get("current", {}).get("weather") != "unknown"
        and amap.get("current", {}).get("temperature") is not None
    )
    needs_backup = not has_current or sum(_valid_forecast_row(initial_rows.get(day)) for day in target_dates) < 7
    open_meteo = await _fetch_open_meteo() if needs_backup else None

    forecast_by_date: dict[str, dict] = {}
    forecast_source_names: list[str] = []
    for provider in (china_weather, amap, open_meteo):
        if not provider:
            continue
        contributed = False
        for row in provider.get("forecast", []):
            forecast_date = row.get("date")
            if forecast_date not in target_dates:
                continue
            existing = forecast_by_date.get(forecast_date)
            if existing:
                merged = _fill_missing(existing, row)
                contributed = contributed or merged != existing
                forecast_by_date[forecast_date] = merged
            else:
                forecast_by_date[forecast_date] = dict(row)
                contributed = True
        if contributed:
            forecast_source_names.append(provider["source"])

    forecast = []
    for forecast_date_text in target_dates:
        forecast_date = date.fromisoformat(forecast_date_text)
        row = forecast_by_date.get(forecast_date_text) or _unknown_forecast_row(forecast_date)
        row["weekday"] = WEEKDAYS_CN[forecast_date.weekday()]
        row["is_weekend"] = forecast_date.weekday() >= 5
        row["tips"] = _generate_tips(row["weather"], row["temp_high"], row["is_weekend"])
        forecast.append(row)

    current_provider = amap if has_current else open_meteo
    current_source = current_provider.get("source") if current_provider else None
    current_data = dict((current_provider or {}).get("current") or {})
    today_forecast = forecast[0]
    current_data.setdefault("weather", today_forecast["weather"])
    current_data.setdefault("weather_text", today_forecast["weather_text"])
    current_data.setdefault("temperature", None)
    current_data.setdefault("humidity", None)
    current_data.setdefault("wind", "")
    current_data.setdefault("observed_at", None)
    current_data["temp_high"] = today_forecast["temp_high"]
    current_data["temp_low"] = today_forecast["temp_low"]
    current_data["tips"] = _generate_tips(
        current_data["weather"],
        today_forecast["temp_high"],
        today_forecast["is_weekend"],
    )

    forecast_available = sum(_valid_forecast_row(row) for row in forecast)
    current_available = current_data["weather"] != "unknown" and current_data["temperature"] is not None
    forecast_source = "+".join(forecast_source_names) or None
    current_stale = _is_stale(current_data.get("observed_at"), now, 4)
    forecast_updated_at = (
        (china_weather or {}).get("updated_at")
        or (amap or {}).get("updated_at")
        or (open_meteo or {}).get("updated_at")
    )
    forecast_stale = _is_stale(forecast_updated_at, now, 18)
    is_stale = current_stale or forecast_stale

    if current_available and forecast_available == 7 and not is_stale:
        status = "live"
    elif current_available or forecast_available > 0:
        status = "partial"
    else:
        status = "unavailable"

    warnings: list[str] = []
    if not current_available:
        warnings.append("实时天气暂不可用")
    elif current_source != "amap":
        warnings.append("高德实时天气暂不可用，已切换备用源")
    if forecast_available < 7:
        warnings.append(f"一周预报仅获取到 {forecast_available}/7 天")
    elif not china_weather:
        warnings.append("中国天气网预报暂不可用，已切换备用源")
    if current_stale:
        warnings.append("实时天气超过 4 小时未更新")
    if forecast_stale:
        warnings.append("天气预报超过 18 小时未更新")

    events = [
        event
        for event in LOCAL_EVENTS
        if target_dates[0] <= event["date"] <= (today + timedelta(days=30)).isoformat()
    ]
    source_names = [name for name in (current_source, forecast_source) if name]

    logger.info(
        "weather status=%s current_source=%s forecast_source=%s forecast_days=%s",
        status,
        current_source,
        forecast_source,
        forecast_available,
    )
    return {
        "city": STORE_CITY,
        "district": STORE_DISTRICT,
        "location": STORE_LOCATION,
        "address": STORE_ADDRESS,
        "coordinates": {
            "latitude": STORE_LAT,
            "longitude": STORE_LON,
        },
        "location_source": "amap_geocode",
        "location_accuracy": "point_of_interest",
        "source": "+".join(dict.fromkeys(source_names)) or "unavailable",
        "current_source": current_source,
        "forecast_source": forecast_source,
        "status": status,
        "is_stale": is_stale,
        "warnings": warnings,
        "current": current_data,
        "forecast": forecast,
        "events": events,
        "intelligence_sources": [
            {
                "name": "新余市教育局通知公告",
                "url": "http://jyj.xinyu.gov.cn",
                "topic": "学校放假与开学",
                "status": "awaiting_verified_update",
            },
            {
                "name": "恒太城官方活动",
                "url": "",
                "topic": "商场活动与客流",
                "status": "source_pending",
            },
        ],
        "observed_at": current_data.get("observed_at"),
        "forecast_updated_at": forecast_updated_at,
        "updated_at": now.strftime("%Y-%m-%d %H:%M"),
    }
