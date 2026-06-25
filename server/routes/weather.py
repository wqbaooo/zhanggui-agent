#!/usr/bin/env python3
"""天气商圈路由：Open-Meteo 真实天气 + 经营建议 + 商圈事件。"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta

import httpx
from fastapi import APIRouter

logger = logging.getLogger("weather")

router = APIRouter(prefix="/api", tags=["weather"])

# ── Open-Meteo 配置 ──
OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
# 新余坐标
LAT = 27.83
LON = 114.93
TIMEOUT = 5.0

# WMO 天气码 → 内部 weather 类型 + 中文
WMO_MAP: dict[int, tuple[str, str]] = {
    0:  ("sunny",        "晴"),
    1:  ("sunny",        "晴"),
    2:  ("cloudy",       "多云"),
    3:  ("overcast",     "阴"),
    45: ("fog",          "雾"),
    48: ("fog",          "雾"),
    51: ("light_rain",   "小雨"),
    53: ("light_rain",   "小雨"),
    55: ("light_rain",   "小雨"),
    61: ("light_rain",   "小雨"),
    63: ("heavy_rain",   "大雨"),
    65: ("heavy_rain",   "大雨"),
    71: ("snow",         "雪"),
    73: ("snow",         "雪"),
    75: ("snow",         "雪"),
    80: ("light_rain",   "阵雨"),
    81: ("heavy_rain",   "大雨"),
    82: ("heavy_rain",   "大雨"),
    85: ("snow",         "雪"),
    86: ("snow",         "雪"),
    95: ("thunderstorm", "雷阵雨"),
    96: ("thunderstorm", "雷阵雨"),
    99: ("thunderstorm", "雷阵雨"),
}

WEEKDAYS_CN = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

# ── 新余本地商圈事件（业务知识，不来自 API） ──
LOCAL_EVENTS: list[dict] = [
    {"date": "2026-06-28", "title": "恒太城年中庆", "type": "商场活动", "impact": "客流+30%，备货上调"},
    {"date": "2026-07-01", "title": "暑假开始", "type": "节假日", "impact": "工作日午餐客流增加"},
    {"date": "2026-07-05", "title": "新余一中放假", "type": "学校", "impact": "学生客流减少"},
    {"date": "2026-07-10", "title": "恒太城美食节", "type": "商场活动", "impact": "全天客流高峰，建议加人"},
    {"date": "2026-07-15", "title": "暑期电影档", "type": "影院活动", "impact": "晚间客流增加，备小吃外卖"},
    {"date": "2026-09-01", "title": "开学", "type": "学校", "impact": "工作日客流恢复常态"},
    {"date": "2026-10-01", "title": "国庆黄金周", "type": "节假日", "impact": "全天高峰，全员上岗，备货上调50%"},
    {"date": "2026-10-08", "title": "节后回落", "type": "周期", "impact": "客流回落，恢复正常排班和备货"},
]


def _generate_tips(weather: str, temp_high: int, is_weekend: bool) -> list[str]:
    """根据天气和温度生成经营建议。"""
    tips: list[str] = []

    if weather in ("light_rain", "heavy_rain", "thunderstorm"):
        tips.append("外卖上调备货，堂食保守排班")
        tips.append("注意包装防漏，检查封口")
    if weather in ("heavy_rain", "thunderstorm"):
        tips.append("客流下降，可减少备料20%")
    if weather == "sunny" and is_weekend:
        tips.append("周末好天气，预计客流高峰，建议全员上岗")
    if weather == "sunny" and not is_weekend:
        tips.append("好天气，正常排班")
    if temp_high > 35:
        tips.append("高温天气，多备饮品和冷食，减少热汤")
    if temp_high > 32:
        tips.append("温度偏高，章鱼烧口感关注，缩短出餐到取餐时间")
    if temp_high < 10:
        tips.append("低温天气，热食热饮主推")
    if not tips:
        tips.append("正常备货，维持标准排班")

    return tips


async def _fetch_open_meteo() -> dict | None:
    """调用 Open-Meteo API 获取 7 日天气预报。失败返回 None。"""
    params = {
        "latitude": LAT,
        "longitude": LON,
        "daily": "weathercode,temperature_2m_max,temperature_2m_min,precipitation_probability_max",
        "timezone": "Asia/Shanghai",
        "forecast_days": 7,
    }
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.get(OPEN_METEO_URL, params=params)
            resp.raise_for_status()
            return resp.json()
    except Exception as exc:
        logger.warning("Open-Meteo request failed: %s", exc)
        return None


@router.get("/weather")
async def get_weather():
    """返回新余当前天气 + 7 日预报 + 商圈事件。优先 Open-Meteo，降级为静态兜底。"""
    today = datetime.now()
    meteo = await _fetch_open_meteo()

    if meteo and "daily" in meteo:
        daily = meteo["daily"]
        dates = daily.get("time", [])
        codes = daily.get("weathercode", [])
        highs = daily.get("temperature_2m_max", [])
        lows = daily.get("temperature_2m_min", [])
        precips = daily.get("precipitation_probability_max", [])
    else:
        dates, codes, highs, lows, precips = [], [], [], [], []

    # ── 构建 7 日预报 ──
    forecast = []
    for i in range(7):
        date_obj = today + timedelta(days=i)
        date_str = date_obj.strftime("%Y-%m-%d")
        dow = (today.weekday() + i) % 7
        is_weekend = dow >= 5

        if i < len(codes) and i < len(highs) and i < len(lows):
            wmo_code = int(codes[i])
            weather, _ = WMO_MAP.get(wmo_code, ("cloudy", "多云"))
            temp_high = int(round(highs[i]))
            temp_low = int(round(lows[i]))
            humidity = precips[i] if i < len(precips) else 65
            wind = f"{'强' if precips[i] > 50 else '弱' if precips[i] < 20 else '中'}风" if i < len(precips) else "2级"
        else:
            # 降级：基于季节的合理静态值
            month = date_obj.month
            if month in (6, 7, 8):
                weather, temp_high, temp_low, humidity, wind = "sunny", 33, 25, 70, "2级"
            elif month in (12, 1, 2):
                weather, temp_high, temp_low, humidity, wind = "cloudy", 10, 3, 60, "3级"
            else:
                weather, temp_high, temp_low, humidity, wind = "cloudy", 22, 14, 65, "2级"

        tips = _generate_tips(weather, temp_high, is_weekend)

        forecast.append({
            "date": date_str,
            "weekday": WEEKDAYS_CN[dow],
            "weather": weather,
            "temp_high": temp_high,
            "temp_low": temp_low,
            "humidity": humidity,
            "wind": wind,
            "is_weekend": is_weekend,
            "tips": tips,
        })

    # ── 当前天气 = 预报第一天 ──
    current = forecast[0]

    # ── 商圈事件（30 天内） ──
    events = [
        e for e in LOCAL_EVENTS
        if e["date"] >= today.strftime("%Y-%m-%d")
        and e["date"] <= (today + timedelta(days=30)).strftime("%Y-%m-%d")
    ]

    return {
        "city": "新余",
        "district": "渝水区",
        "location": "恒太城五楼美食城",
        "source": "open-meteo" if meteo else "fallback",
        "current": {
            "weather": current["weather"],
            "temperature": current["temp_high"],
            "temp_high": current["temp_high"],
            "temp_low": current["temp_low"],
            "humidity": current["humidity"],
            "wind": current["wind"],
            "tips": current["tips"],
        },
        "forecast": forecast,
        "events": events,
        "updated_at": today.strftime("%Y-%m-%d %H:%M"),
    }


# ── 天气类型中文映射（供前端参考） ──
WEATHER_CN = {
    "sunny": "晴",
    "cloudy": "多云",
    "overcast": "阴",
    "light_rain": "小雨",
    "heavy_rain": "大雨",
    "thunderstorm": "雷阵雨",
    "snow": "雪",
    "fog": "雾",
}
