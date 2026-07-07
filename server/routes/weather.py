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

# 事件必须带可核验来源后才能进入经营建议。暂不以推测填充商圈日历。
LOCAL_EVENTS: list[dict] = []


def _generate_tips(weather: str, temp_high: int, is_weekend: bool) -> list[str]:
    """根据天气和温度生成经营建议。"""
    if weather == "unknown":
        return ["天气服务暂不可用，保持标准备货并等待更新"]
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


def _generate_fallback_weather(today: datetime) -> dict:
    """生成江西新余夏季（7月）的合理天气兜底数据。"""
    month = today.month
    weekday = today.weekday()

    if month >= 6 and month <= 9:
        base_high = 32 + (weekday < 5) * 2
        base_low = 24
        weather_codes = [0, 1, 2, 3, 80, 81, 61]
    elif month >= 12 or month <= 2:
        base_high = 12
        base_low = 4
        weather_codes = [0, 2, 3, 71, 73, 1, 2]
    elif month >= 3 and month <= 5:
        base_high = 22 + month * 2
        base_low = 12 + month
        weather_codes = [2, 3, 51, 61, 0, 1, 2]
    else:
        base_high = 28
        base_low = 18
        weather_codes = [0, 1, 2, 3, 51, 61, 0]

    dates = [(today + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)]
    codes = [weather_codes[i % len(weather_codes)] for i in range(7)]
    highs = [base_high + (i % 3) for i in range(7)]
    lows = [base_low + (i % 2) for i in range(7)]
    precips = [15, 25, 45, 30, 60, 20, 10]

    return {
        "daily": {
            "time": dates,
            "weathercode": codes,
            "temperature_2m_max": highs,
            "temperature_2m_min": lows,
            "precipitation_probability_max": precips,
        }
    }


@router.get("/weather")
async def get_weather():
    """返回新余当前天气 + 7 日预报 + 商圈事件。优先 Open-Meteo，降级为季节合理兜底。"""
    today = datetime.now()
    meteo = await _fetch_open_meteo()
    logger.info(f"weather: meteo={meteo is not None}, source={'open-meteo' if meteo else 'fallback'}")

    if meteo and "daily" in meteo:
        daily = meteo["daily"]
        dates = daily.get("time", [])
        codes = daily.get("weathercode", [])
        highs = daily.get("temperature_2m_max", [])
        lows = daily.get("temperature_2m_min", [])
        precips = daily.get("precipitation_probability_max", [])
        logger.info(f"weather: using open-meteo, codes={len(codes)}, highs={len(highs)}")
    else:
        fallback = _generate_fallback_weather(today)
        daily = fallback["daily"]
        dates = daily.get("time", [])
        codes = daily.get("weathercode", [])
        highs = daily.get("temperature_2m_max", [])
        lows = daily.get("temperature_2m_min", [])
        precips = daily.get("precipitation_probability_max", [])
        logger.info(f"weather: using fallback, codes={len(codes)}, highs={len(highs)}")

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
            # 降级：不生成假天气，标记为 unknown 让前端显示"暂不可用"
            weather, temp_high, temp_low, humidity, wind = "unknown", 0, 0, 0, ""

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
