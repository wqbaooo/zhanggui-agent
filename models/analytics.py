#!/usr/bin/env python3
"""DuckDB 数据分析层：用 SQL 对经营数据做聚合、对比、异常检测。"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import duckdb


def _ops_to_rows(entries: List[Dict[str, Any]]) -> List[tuple]:
    """将 ProjectMemory.daily_operations 转为 DuckDB 行。"""
    rows = []
    for e in entries:
        rows.append((
            e.get("date", ""),
            float(e.get("revenue", 0) or 0),
            int(e.get("orders", 0) or 0),
            float(e.get("food_cost", 0) or 0),
            float(e.get("labor", 0) or 0),
            float(e.get("rent_allocated", 0) or 0),
            float(e.get("utility", 0) or 0),
            float(e.get("other_cost", 0) or 0),
            int(e.get("takeout_orders", 0) or 0),
            float(e.get("platform_fee", 0) or 0),
            float(e.get("marketing_cost", 0) or 0),
            float(e.get("inventory_loss", 0) or 0),
            int(e.get("bad_reviews", 0) or 0),
        ))
    return rows


class StoreAnalytics:
    """门店经营数据分析引擎。"""

    def __init__(self):
        self.db = duckdb.connect(":memory:")
        self.db.execute("""
            CREATE TABLE ops (
                date VARCHAR,
                revenue DOUBLE,
                orders INTEGER,
                food_cost DOUBLE,
                labor DOUBLE,
                rent DOUBLE,
                utility DOUBLE,
                other_cost DOUBLE,
                takeout_orders INTEGER,
                platform_fee DOUBLE,
                marketing_cost DOUBLE,
                inventory_loss DOUBLE,
                bad_reviews INTEGER
            )
        """)

    def load(self, daily_operations: List[Dict[str, Any]]):
        """加载经营数据到内存表。"""
        rows = _ops_to_rows(daily_operations)
        if not rows:
            return
        self.db.execute("DELETE FROM ops")
        self.db.executemany(
            "INSERT INTO ops VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", rows
        )

    def period_summary(self, start: str, end: str) -> Dict[str, Any]:
        """单周期汇总。"""
        result = self.db.execute("""
            SELECT
                COUNT(*) as days,
                COALESCE(SUM(revenue), 0) as total_revenue,
                COALESCE(SUM(orders), 0) as total_orders,
                CASE WHEN SUM(orders) > 0 THEN SUM(revenue) / SUM(orders) ELSE 0 END as avg_order_value,
                COALESCE(SUM(revenue) - SUM(food_cost) - SUM(labor) - SUM(rent)
                    - SUM(utility) - SUM(other_cost) - SUM(platform_fee)
                    - SUM(marketing_cost) - SUM(inventory_loss), 0) as net_profit,
                CASE WHEN SUM(revenue) > 0 THEN SUM(food_cost) / SUM(revenue) ELSE 0 END as food_cost_rate,
                CASE WHEN SUM(revenue) > 0 THEN SUM(labor) / SUM(revenue) ELSE 0 END as labor_cost_rate,
                CASE WHEN SUM(revenue) > 0 THEN (SUM(food_cost) + SUM(labor)) / SUM(revenue) ELSE 0 END as prime_cost_rate,
                COALESCE(SUM(takeout_orders), 0) as takeout_orders,
                CASE WHEN SUM(orders) > 0 THEN CAST(SUM(takeout_orders) AS DOUBLE) / SUM(orders) ELSE 0 END as takeout_ratio,
                COALESCE(SUM(platform_fee), 0) as platform_fee,
                COALESCE(SUM(marketing_cost), 0) as marketing_cost,
                COALESCE(SUM(bad_reviews), 0) as bad_reviews,
                CASE WHEN SUM(orders) > 0 THEN CAST(SUM(bad_reviews) AS DOUBLE) / SUM(orders) ELSE 0 END as bad_review_rate
            FROM ops
            WHERE date >= ? AND date <= ?
        """, (start, end)).fetchone()

        if not result or result[0] == 0:
            return {"days": 0}

        return {
            "days": result[0],
            "total_revenue": round(result[1], 2),
            "total_orders": result[2],
            "avg_order_value": round(result[3], 2),
            "net_profit": round(result[4], 2),
            "food_cost_rate": round(result[5], 4),
            "labor_cost_rate": round(result[6], 4),
            "prime_cost_rate": round(result[7], 4),
            "takeout_orders": result[8],
            "takeout_ratio": round(result[9], 4),
            "platform_fee": round(result[10], 2),
            "marketing_cost": round(result[11], 2),
            "bad_reviews": result[12],
            "bad_review_rate": round(result[13], 4),
        }

    def compare_periods(self, current_start: str, current_end: str, prev_start: str, prev_end: str) -> Dict[str, Any]:
        """两周期对比，返回当前数据和变化率。"""
        curr = self.period_summary(current_start, current_end)
        prev = self.period_summary(prev_start, prev_end)

        if curr.get("days", 0) == 0:
            return {"current": curr, "previous": prev, "changes": []}

        changes = []
        for key in ["total_revenue", "total_orders", "net_profit", "food_cost_rate",
                     "labor_cost_rate", "takeout_ratio", "platform_fee", "bad_reviews"]:
            cv = curr.get(key, 0) or 0
            pv = prev.get(key, 0) or 0
            if pv != 0 and cv != 0:
                pct = round((cv - pv) / abs(pv) * 100, 1)
            elif cv != 0 and pv == 0:
                pct = 100.0
            else:
                pct = 0.0
            changes.append({"key": key, "current": cv, "previous": pv, "change_pct": pct})

        return {"current": curr, "previous": prev, "changes": changes}

    def daily_trend(self, start: str, end: str) -> List[Dict[str, Any]]:
        """日趋势数据。"""
        rows = self.db.execute("""
            SELECT date, revenue, orders,
                revenue - food_cost - labor - rent - utility - other_cost - platform_fee - marketing_cost - inventory_loss as profit
            FROM ops WHERE date >= ? AND date <= ? ORDER BY date
        """, (start, end)).fetchall()
        return [{"date": r[0], "revenue": round(r[1], 2), "orders": r[2], "profit": round(r[3], 2)} for r in rows]

    def weekday_breakdown(self, start: str, end: str) -> List[Dict[str, Any]]:
        """按周几汇总。"""
        rows = self.db.execute("""
            SELECT
                CASE CAST(strftime(date, '%w') AS INTEGER)
                    WHEN 0 THEN '周日' WHEN 1 THEN '周一' WHEN 2 THEN '周二'
                    WHEN 3 THEN '周三' WHEN 4 THEN '周四' WHEN 5 THEN '周五' WHEN 6 THEN '周六'
                END as weekday,
                ROUND(AVG(revenue), 0) as avg_revenue,
                ROUND(AVG(orders), 0) as avg_orders,
                COUNT(*) as days
            FROM ops WHERE date >= ? AND date <= ?
            GROUP BY weekday ORDER BY MIN(date)
        """, (start, end)).fetchall()
        return [{"weekday": r[0], "avg_revenue": r[1], "avg_orders": r[2], "days": r[3]} for r in rows]

    def find_anomalies(self, start: str, end: str) -> List[Dict[str, Any]]:
        """异常检测：连续下降、突降等。"""
        anomalies = []
        # 食材率检查
        s = self.period_summary(start, end)
        if s.get("food_cost_rate", 0) > 0.40:
            anomalies.append({
                "type": "food_cost_high",
                "level": "risk",
                "title": f"食材成本率 {s['food_cost_rate']:.0%}",
                "body": f"超过 40% 警戒线。累计食材成本 ¥{s.get('total_revenue', 0) * s.get('food_cost_rate', 0):,.0f}。",
                "target": "/inventory",
            })
        if s.get("prime_cost_rate", 0) > 0.65:
            anomalies.append({
                "type": "prime_cost_high",
                "level": "risk",
                "title": f"Prime Cost {s['prime_cost_rate']:.0%}",
                "body": "食材+人工合计超 65%，几乎没有利润空间。",
                "target": "/profit",
            })
        if s.get("net_profit", 0) < 0:
            anomalies.append({
                "type": "loss",
                "level": "risk",
                "title": f"当期亏损 ¥{abs(s['net_profit']):,.0f}",
                "body": "优先检查食材、人工、平台活动是否拉低毛利。",
                "target": "/profit",
            })
        if s.get("takeout_ratio", 0) > 0.45 and s.get("platform_fee", 0) / max(s.get("total_revenue", 1), 1) > 0.10:
            anomalies.append({
                "type": "takeout_margin",
                "level": "watch",
                "title": f"外卖占比 {s['takeout_ratio']:.0%}，平台费率偏高",
                "body": f"平台费 ¥{s.get('platform_fee', 0):,.0f} 占总营收 {s.get('platform_fee', 0) / max(s.get('total_revenue', 1), 1) * 100:.0f}%，检查满减活动。",
                "target": "/channels",
            })
        if s.get("bad_review_rate", 0) > 0.03:
            anomalies.append({
                "type": "bad_reviews",
                "level": "watch",
                "title": f"差评率 {s['bad_review_rate']:.1%}",
                "body": f"{s.get('bad_reviews', 0)} 条差评，拆解出餐、口味、包装原因。",
                "target": "/channels",
            })

        be = self.break_even_analysis(start, end)
        if be.get("daily_breakeven_revenue") and not be.get("is_profitable"):
            gap = be.get("gap_to_breakeven", 0) or 0
            anomalies.append({
                "type": "below_breakeven",
                "level": "risk",
                "title": f"日均营收低于保本线 ¥{abs(gap):,.0f}",
                "body": f"日保本营收 ¥{be['daily_breakeven_revenue']:,.0f}，实际日均 ¥{be['daily_revenue']:,.0f}，达保本线 {be.get('breakeven_pct', 0):.0%}。",
                "target": "/profit",
            })

        return anomalies

    def break_even_analysis(self, start: str, end: str) -> Dict[str, Any]:
        """保本点分析：固定/变动成本拆分 + 边际贡献率 + 日保本营收。"""
        row = self.db.execute("""
            SELECT
                COALESCE(SUM(revenue), 0),
                COUNT(*),
                COALESCE(SUM(labor + rent + utility), 0),
                COALESCE(SUM(food_cost + platform_fee + marketing_cost + inventory_loss + other_cost), 0)
            FROM ops WHERE date >= ? AND date <= ?
        """, (start, end)).fetchone()

        if not row or row[1] == 0:
            return {"days": 0}

        total_revenue, days, fixed_cost, variable_cost = row

        variable_cost_rate = variable_cost / total_revenue if total_revenue > 0 else 0
        contribution_margin_rate = 1 - variable_cost_rate
        daily_revenue = total_revenue / days if days > 0 else 0
        daily_fixed = fixed_cost / days if days > 0 else 0
        monthly_fixed = daily_fixed * 30

        if contribution_margin_rate > 0:
            monthly_breakeven = monthly_fixed / contribution_margin_rate
            daily_breakeven = monthly_breakeven / 30
        else:
            monthly_breakeven = None
            daily_breakeven = None

        is_profitable = daily_breakeven is not None and daily_revenue > daily_breakeven
        gap = round(daily_revenue - daily_breakeven, 2) if daily_breakeven is not None else None
        breakeven_pct = round(daily_revenue / daily_breakeven, 4) if daily_breakeven and daily_breakeven > 0 else None

        return {
            "days": days,
            "total_revenue": round(total_revenue, 2),
            "daily_revenue": round(daily_revenue, 2),
            "fixed_cost": round(fixed_cost, 2),
            "variable_cost": round(variable_cost, 2),
            "daily_fixed_cost": round(daily_fixed, 2),
            "monthly_fixed_cost": round(monthly_fixed, 2),
            "variable_cost_rate": round(variable_cost_rate, 4),
            "contribution_margin_rate": round(contribution_margin_rate, 4),
            "monthly_breakeven_revenue": round(monthly_breakeven, 2) if monthly_breakeven is not None else None,
            "daily_breakeven_revenue": round(daily_breakeven, 2) if daily_breakeven is not None else None,
            "is_profitable": is_profitable,
            "gap_to_breakeven": gap,
            "breakeven_pct": breakeven_pct,
        }


def detect_monthly_anomalies(monthly_revenue: List[Dict[str, Any]], profile: Dict[str, Any]) -> List[Dict[str, Any]]:
    """月度营收异常检测：同比暴跌、连续下滑、利润率异常。"""
    anomalies: List[Dict[str, Any]] = []
    if not monthly_revenue:
        return anomalies

    # 成本基线
    rent = profile.get("monthly_rent", 0)
    labor = profile.get("monthly_labor", 0)
    utility_avg = (
        (profile.get("monthly_utility_min", 0) + profile.get("monthly_utility_max", 0)) / 2
    )
    est_fixed_cost = rent + labor + utility_avg

    # 找有营收的月份
    months_with_revenue = [e for e in monthly_revenue if e.get("revenue") is not None]

    # 1. 同比暴跌检测（今年某月 vs 去年同月，下降超 30%）
    for e in months_with_revenue:
        revenue = e.get("revenue", 0)
        last_profit = e.get("last_year_profit", 0)
        if last_profit > 0 and revenue < last_profit * 0.7:
            yoy_pct = round((revenue - last_profit) / last_profit * 100, 1)
            anomalies.append({
                "type": "monthly_revenue_drop",
                "level": "risk",
                "title": f"{e['month']}月营收同比暴跌{yoy_pct}%",
                "body": f"今年¥{revenue:,} vs 去年¥{last_profit:,}，下降{yoy_pct}%。检查是否受天气、竞争、渠道影响。",
                "target": "/monthly",
            })

    # 2. 连续下滑检测（最近 2 个有数据月份连续下降）
    if len(months_with_revenue) >= 3:
        recent = months_with_revenue[-3:]
        if (recent[2]["revenue"] < recent[1]["revenue"] and
                recent[1]["revenue"] < recent[0]["revenue"]):
            anomalies.append({
                "type": "monthly_revenue_decline",
                "level": "watch",
                "title": "连续2个月营收下滑",
                "body": f"{recent[1]['month']}月¥{recent[1]['revenue']:,} → {recent[2]['month']}月¥{recent[2]['revenue']:,}，需关注趋势。",
                "target": "/monthly",
            })

    # 3. 月营收异常高（同比暴涨超 100%），可能是数据录入错误
    for e in months_with_revenue:
        revenue = e.get("revenue", 0)
        last_profit = e.get("last_year_profit", 0)
        if last_profit > 0 and revenue > last_profit * 2.0:
            yoy_pct = round((revenue - last_profit) / last_profit * 100, 1)
            anomalies.append({
                "type": "monthly_revenue_spike",
                "level": "watch",
                "title": f"{e['month']}月营收异常增长{yoy_pct}%",
                "body": f"同比增长超100%，请确认数据准确性。今年¥{revenue:,} vs 去年¥{last_profit:,}。",
                "target": "/monthly",
            })

    # 4. 估算利润率异常（低于 10%）
    for e in months_with_revenue:
        revenue = e.get("revenue", 0)
        if revenue <= 0:
            continue
        est_profit = revenue - est_fixed_cost
        margin = est_profit / revenue
        if margin < 0.10:
            anomalies.append({
                "type": "monthly_margin_thin",
                "level": "risk" if margin < 0 else "watch",
                "title": f"{e['month']}月估算利润率仅{margin:.0%}",
                "body": f"营收¥{revenue:,}，估算固定成本¥{est_fixed_cost:,.0f}（未含食材），利润率极薄。",
                "target": "/profit",
            })

    # 5. 有营收的月份数不足 3 个月
    if len(months_with_revenue) < 3:
        anomalies.append({
            "type": "insufficient_monthly_data",
            "level": "info",
            "title": f"仅有{len(months_with_revenue)}个月度营收数据",
            "body": "至少需要3个月数据才能进行可靠的趋势分析。",
            "target": "/monthly",
        })

    return anomalies
