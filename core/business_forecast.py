"""Fact-grounded revenue and inventory forecast assembly.

The module is deliberately deterministic. It only predicts from confirmed daily
sales and inventory rows that already contain consumption and safety-stock
facts. Weather can widen uncertainty and create operating alerts, but it never
changes the revenue direction until the store has paired weather/sales history.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime
from statistics import mean, pstdev
from typing import Any
from zoneinfo import ZoneInfo


SHANGHAI = ZoneInfo("Asia/Shanghai")
WEEKDAYS_CN = ("周一", "周二", "周三", "周四", "周五", "周六", "周日")
WEATHER_RANGE_RISK = {
    "light_rain": 0.05,
    "heavy_rain": 0.10,
    "thunderstorm": 0.12,
    "snow": 0.10,
    "fog": 0.06,
}


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def _normalise_revenue_rows(rows: list[dict[str, Any]], as_of: date) -> list[dict[str, Any]]:
    by_date: dict[date, dict[str, int]] = defaultdict(lambda: {"revenue_minor": 0, "orders": 0})
    for row in rows:
        try:
            business_date = date.fromisoformat(str(row.get("business_date")))
            revenue_minor = int(row.get("revenue_minor"))
            orders = int(row.get("orders") or 0)
        except (TypeError, ValueError):
            continue
        if business_date > as_of or revenue_minor < 0:
            continue
        by_date[business_date]["revenue_minor"] += revenue_minor
        by_date[business_date]["orders"] += max(orders, 0)
    return [
        {
            "business_date": business_date,
            "revenue_minor": values["revenue_minor"],
            "orders": values["orders"],
        }
        for business_date, values in sorted(by_date.items())
    ][-56:]


def _weather_risk(row: dict[str, Any] | None) -> tuple[float, list[str]]:
    if not row:
        return 0.0, []
    weather_kind = str(row.get("weather") or "unknown")
    margin = WEATHER_RANGE_RISK.get(weather_kind, 0.0)
    labels: list[str] = []
    if weather_kind in {"heavy_rain", "thunderstorm"}:
        labels.append("强降雨")
    elif weather_kind == "light_rain":
        labels.append("降雨")
    elif weather_kind in {"snow", "fog"}:
        labels.append(str(row.get("weather_text") or "能见度风险"))
    try:
        if float(row.get("temp_high")) >= 35:
            margin = max(margin, 0.08)
            labels.append("高温")
    except (TypeError, ValueError):
        pass
    return margin, labels


def _build_revenue_forecast(
    *,
    as_of: date,
    revenue_rows: list[dict[str, Any]],
    weather: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, str]], list[str]]:
    rows = _normalise_revenue_rows(revenue_rows, as_of)
    values = [int(row["revenue_minor"]) for row in rows]
    alerts: list[dict[str, str]] = []
    gaps: list[str] = []

    if len(rows) < 7:
        gaps.append(f"只有 {len(rows)} 个已确认营业日，至少需要连续 7 天才能形成收入区间")
        if weather.get("status") == "unavailable":
            gaps.append("联网天气暂不可用，无法标记未来一周天气风险")
        alerts.append({
            "kind": "data_gap",
            "level": "medium",
            "title": "收入样本不足",
            "body": "先补齐连续 7 天客如云或已确认营业收入，再生成收入预测。",
            "target": "/capture",
        })
        return ({
            "status": "insufficient",
            "confidence": "unavailable",
            "sample_start": rows[0]["business_date"].isoformat() if rows else None,
            "sample_end": rows[-1]["business_date"].isoformat() if rows else None,
            "sample_days": len(rows),
            "days_stale": (as_of - rows[-1]["business_date"]).days if rows else None,
            "average_daily_minor": round(mean(values)) if values else None,
            "historical_low_minor": min(values) if values else None,
            "historical_high_minor": max(values) if values else None,
            "method": "至少 7 个已确认营业日后，按星期基线生成区间",
            "weather_adjustment": "range_only_not_directional",
            "forecast_days": [],
            "total_predicted_minor": None,
            "total_low_minor": None,
            "total_high_minor": None,
            "demand_factor": None,
        }, alerts, gaps)

    sample_start = rows[0]["business_date"]
    sample_end = rows[-1]["business_date"]
    days_stale = max((as_of - sample_end).days, 0)
    overall_mean = mean(values)
    volatility = pstdev(values) / overall_mean if len(values) > 1 and overall_mean > 0 else 0.0
    weekday_values: dict[int, list[int]] = defaultdict(list)
    weekend_values: list[int] = []
    workday_values: list[int] = []
    for row in rows:
        weekday = row["business_date"].weekday()
        value = int(row["revenue_minor"])
        weekday_values[weekday].append(value)
        (weekend_values if weekday >= 5 else workday_values).append(value)

    weekend_factor = 1.0
    if len(weekend_values) >= 2 and len(workday_values) >= 4 and mean(workday_values) > 0:
        weekend_factor = min(max(mean(weekend_values) / mean(workday_values), 0.75), 1.35)

    weather_by_date = {
        str(row.get("date")): row
        for row in weather.get("forecast", [])
        if isinstance(row, dict) and row.get("date")
    }
    base_margin = min(max(volatility, 0.15), 0.45)
    sample_penalty = 0.12 if len(rows) < 14 else 0.08 if len(rows) < 28 else 0.04
    stale_penalty = min(days_stale * 0.02, 0.20)
    forecast_days: list[dict[str, Any]] = []

    for offset in range(7):
        forecast_date = as_of.fromordinal(as_of.toordinal() + offset)
        same_weekday = weekday_values.get(forecast_date.weekday(), [])
        if len(same_weekday) >= 2:
            predicted = mean(same_weekday[-8:])
            basis = f"历史 {len(same_weekday[-8:])} 个{WEEKDAYS_CN[forecast_date.weekday()]}均值"
        else:
            factor = weekend_factor if forecast_date.weekday() >= 5 else 1.0
            predicted = overall_mean * factor
            basis = "已确认营业日均值" + (" × 周末历史系数" if factor != 1.0 else "")

        weather_row = weather_by_date.get(forecast_date.isoformat())
        weather_margin, weather_labels = _weather_risk(weather_row)
        margin = min(base_margin + sample_penalty + stale_penalty + weather_margin, 0.70)
        point = max(round(predicted), 0)
        spread = round(point * margin)
        forecast_days.append({
            "date": forecast_date.isoformat(),
            "weekday": WEEKDAYS_CN[forecast_date.weekday()],
            "predicted_minor": point,
            "low_minor": max(point - spread, 0),
            "high_minor": point + spread,
            "basis": basis,
            "weather": (weather_row or {}).get("weather_text") or None,
            "weather_kind": (weather_row or {}).get("weather") or "unknown",
            "weather_risks": weather_labels,
        })
        if weather_labels:
            alerts.append({
                "kind": "weather",
                "level": "medium",
                "title": f"{forecast_date.strftime('%m/%d')} {'、'.join(weather_labels)}",
                "body": "天气只扩大收入不确定区间；请按实时客流滚动调整备料和外卖包装。",
                "target": "/calendar",
            })

    total_predicted = sum(item["predicted_minor"] for item in forecast_days)
    total_low = sum(item["low_minor"] for item in forecast_days)
    total_high = sum(item["high_minor"] for item in forecast_days)
    projected_daily = total_predicted / 7
    demand_factor = min(max(projected_daily / overall_mean, 0.70), 1.30) if overall_mean else None
    confidence = "medium" if len(rows) >= 28 and days_stale <= 1 else "low"
    status = "ready" if confidence == "medium" and weather.get("status") == "live" else "partial"

    if len(rows) < 28:
        gaps.append(f"当前只有 {len(rows)} 个营业日，满 28 天后才能形成更稳定的星期基线")
    if days_stale > 2:
        gaps.append(f"最近营业事实停在 {sample_end.isoformat()}，距预测日 {days_stale} 天")
        alerts.append({
            "kind": "data_gap",
            "level": "medium",
            "title": "营业数据已过期",
            "body": f"最新已确认营业数据是 {sample_end.isoformat()}，先补齐最近 {days_stale} 天再用于备货决策。",
            "target": "/capture",
        })
    if weather.get("status") == "unavailable":
        gaps.append("联网天气暂不可用，收入区间未加入天气风险")
    else:
        gaps.append("天气没有历史校准样本，本轮只扩大区间和提示风险，不直接增减收入")

    return ({
        "status": status,
        "confidence": confidence,
        "sample_start": sample_start.isoformat(),
        "sample_end": sample_end.isoformat(),
        "sample_days": len(rows),
        "days_stale": days_stale,
        "average_daily_minor": round(overall_mean),
        "historical_low_minor": min(values),
        "historical_high_minor": max(values),
        "method": "已确认日收入的星期基线；波动、样本量和数据新鲜度共同决定区间",
        "weather_adjustment": "range_only_not_directional",
        "forecast_days": forecast_days,
        "total_predicted_minor": total_predicted,
        "total_low_minor": total_low,
        "total_high_minor": total_high,
        "demand_factor": round(demand_factor, 4) if demand_factor is not None else None,
    }, alerts, gaps)


def _inventory_fact_staleness(as_of: date, inventory_fact_date: date | None) -> int | None:
    return max((as_of - inventory_fact_date).days, 0) if inventory_fact_date else None


def _build_inventory_forecast(
    *,
    as_of: date,
    sku_forecast: list[dict[str, Any]],
    inventory_fact_date: date | None,
    demand_factor: float | None,
) -> tuple[dict[str, Any], list[dict[str, str]], list[str]]:
    alerts: list[dict[str, str]] = []
    gaps: list[str] = []
    modelled = [
        row
        for row in sku_forecast
        if row.get("action") != "not_enough_data"
        and row.get("days_remaining") is not None
        and (
            float(row.get("observed_daily_consumption") or 0) > 0
            or float(row.get("consumption_per_day") or 0) > 0
        )
    ]
    unknown = [row for row in sku_forecast if row not in modelled]
    risk_rows = [
        row
        for row in modelled
        if row.get("action") in {"urgent", "recommend"}
    ]
    risk_rows.sort(key=lambda row: (
        0 if row.get("action") == "urgent" else 1,
        float(row.get("days_remaining") or 9999),
    ))
    risks = [
        {
            "sku_id": row.get("sku_id"),
            "name": row.get("name"),
            "unit": row.get("unit"),
            "risk_level": row.get("risk_level"),
            "action": row.get("action"),
            "current_stock": row.get("current_stock"),
            "safety_stock": row.get("safety_stock"),
            "days_remaining": row.get("days_remaining"),
            "stockout_date": row.get("stockout_date"),
            "recommend_qty": row.get("recommend_qty"),
            "recommend_amount": row.get("recommend_amount"),
            "consumption_basis": (
                "实际领用/开包记录"
                if float(row.get("observed_daily_consumption") or 0) > 0
                else "已确认日耗"
            ),
        }
        for row in risk_rows[:12]
    ]
    days_stale = _inventory_fact_staleness(as_of, inventory_fact_date)

    if not modelled:
        status = "insufficient"
    elif unknown or days_stale is None or days_stale > 2:
        status = "partial"
    else:
        status = "ready"

    if unknown:
        gaps.append(f"{len(unknown)} 个 SKU 缺少日耗或安全库存事实，不能计算断货日和采购量")
    if inventory_fact_date is None:
        gaps.append("没有可追溯的库存盘点或入库日期")
    elif days_stale and days_stale > 2:
        gaps.append(f"最近库存事实停在 {inventory_fact_date.isoformat()}，距预测日 {days_stale} 天")
    if not modelled:
        alerts.append({
            "kind": "data_gap",
            "level": "medium",
            "title": "库存暂不能预测",
            "body": "当前库存有数量，但缺少连续开包/领用与安全库存，不能把旧数量当作今天可售库存。",
            "target": "/inventory",
        })
    elif unknown:
        alerts.append({
            "kind": "data_gap",
            "level": "medium",
            "title": "部分库存不能预测",
            "body": f"还有 {len(unknown)} 个 SKU 缺日耗或安全库存，先补齐高频物料。",
            "target": "/inventory",
        })

    for row in risks:
        level = "high" if row["action"] == "urgent" else "medium"
        quantity = row.get("recommend_qty")
        unit = row.get("unit") or ""
        alerts.append({
            "kind": "inventory",
            "level": level,
            "title": f"{row.get('name')}{'需要立即补货' if level == 'high' else '进入补货窗口'}",
            "body": (
                f"预计 {row.get('stockout_date') or '近日'} 到安全线；"
                f"建议量 {quantity:g}{unit}。"
                if isinstance(quantity, (int, float))
                else "已进入补货窗口，但采购量仍需补成本或包装规格。"
            ),
            "target": "/inventory",
        })

    return ({
        "status": status,
        "data_fact_date": inventory_fact_date.isoformat() if inventory_fact_date else None,
        "days_stale": days_stale,
        "active_skus": len(sku_forecast),
        "modelled_skus": len(modelled),
        "unknown_skus": len(unknown),
        "demand_factor": demand_factor,
        "demand_basis": "收入星期基线，仅在 SKU 已有日耗事实时调整；天气不直接改采购量",
        "risks": risks,
        "gaps": gaps,
    }, alerts, gaps)


def build_business_forecast(
    *,
    project_id: str,
    as_of: date,
    revenue_rows: list[dict[str, Any]],
    sku_forecast: list[dict[str, Any]],
    inventory_fact_date: date | None,
    weather: dict[str, Any] | None,
) -> dict[str, Any]:
    """Build one read-only forecast contract from already confirmed inputs."""
    weather = weather or {"status": "unavailable", "forecast": []}
    revenue, revenue_alerts, revenue_gaps = _build_revenue_forecast(
        as_of=as_of,
        revenue_rows=revenue_rows,
        weather=weather,
    )
    inventory, inventory_alerts, inventory_gaps = _build_inventory_forecast(
        as_of=as_of,
        sku_forecast=sku_forecast,
        inventory_fact_date=inventory_fact_date,
        demand_factor=revenue.get("demand_factor"),
    )
    statuses = {revenue["status"], inventory["status"]}
    status = (
        "ready"
        if statuses == {"ready"}
        else "insufficient"
        if statuses == {"insufficient"}
        else "partial"
    )
    evidence = []
    if revenue["sample_days"]:
        evidence.append({
            "kind": "revenue",
            "label": f"财务账本 {revenue['sample_days']} 个已确认营业日",
            "source": "finance.db / sales_daily",
            "period": f"{revenue['sample_start']} 至 {revenue['sample_end']}",
        })
    if inventory_fact_date:
        evidence.append({
            "kind": "inventory",
            "label": f"库存盘点、入库或领用事实至 {inventory_fact_date.isoformat()}",
            "source": "skus.json / inventory events",
            "period": inventory_fact_date.isoformat(),
        })
    if weather.get("status") != "unavailable":
        evidence.append({
            "kind": "weather",
            "label": "未来 7 天天气风险",
            "source": str(weather.get("forecast_source") or weather.get("source") or "联网天气"),
            "period": str(weather.get("forecast_updated_at") or "更新时间未知"),
        })

    return {
        "project_id": project_id,
        "as_of_date": as_of.isoformat(),
        "generated_at": datetime.now(SHANGHAI).isoformat(timespec="seconds"),
        "permission": "read_only",
        "status": status,
        "revenue": revenue,
        "inventory": inventory,
        "alerts": revenue_alerts + inventory_alerts,
        "evidence": evidence,
        "gaps": _unique(revenue_gaps + inventory_gaps),
    }
