"""Deterministic channel order planning from confirmed daily operating data."""

from __future__ import annotations

import math
import re
from typing import Any, Iterable


GOAL_PATTERNS = (
    r"(?:实收|营收|营业额|收入)?\s*(?:目标|做到|达到|卖到|卖)\s*(?:为|是)?\s*[¥￥]?\s*(\d+(?:\.\d+)?)",
    r"[¥￥]\s*(\d+(?:\.\d+)?)",
)


def find_goal_amount(message: str) -> float | None:
    """Extract a revenue target only when the owner explicitly asks for one."""
    for pattern in GOAL_PATTERNS:
        match = re.search(pattern, message.replace(",", ""))
        if match:
            amount = float(match.group(1))
            return amount if amount > 0 else None
    return None


def analyze_channel_goal(
    entries: Iterable[dict[str, Any]],
    target_revenue: float,
    date: str | None = None,
) -> dict[str, Any]:
    """Plan dine-in and delivery orders from the latest complete channel split.

    This deliberately does not infer customer traffic. It answers the narrower,
    evidence-backed question: at the observed channel mix and receipts, how many
    paid orders are needed to reach a revenue target?
    """
    selected = _select_complete_snapshot(entries, date)
    if selected is None:
        return {
            "status": "needs_channel_split",
            "target_revenue": round(float(target_revenue), 2),
            "gaps": ["缺少同一天已确认的堂食/外卖订单和实收，不能把未知渠道拆分当成 0。"],
        }

    dine_orders = int(selected["dine_in_orders"])
    delivery_orders = int(selected["delivery_orders"])
    dine_revenue = float(selected["dine_in_revenue"])
    delivery_revenue = float(selected["delivery_revenue"])
    total_orders = dine_orders + delivery_orders
    total_revenue = dine_revenue + delivery_revenue
    dine_aov = dine_revenue / dine_orders
    delivery_aov = delivery_revenue / delivery_orders
    blended_aov = total_revenue / total_orders

    target_total_orders = math.ceil(float(target_revenue) / blended_aov)
    dine_share = dine_orders / total_orders
    target_dine = round(target_total_orders * dine_share)
    target_delivery = target_total_orders - target_dine
    estimated = target_dine * dine_aov + target_delivery * delivery_aov
    if estimated + 1e-9 < target_revenue:
        if dine_aov >= delivery_aov:
            target_dine += 1
        else:
            target_delivery += 1
        target_total_orders += 1
        estimated = target_dine * dine_aov + target_delivery * delivery_aov

    return {
        "status": "ready",
        "source_date": selected["date"],
        "target_revenue": round(float(target_revenue), 2),
        "channels": {
            "dine_in": {
                "orders": dine_orders,
                "revenue": round(dine_revenue, 2),
                "order_share": round(dine_share, 4),
                "avg_receipt": round(dine_aov, 2),
            },
            "delivery": {
                "orders": delivery_orders,
                "revenue": round(delivery_revenue, 2),
                "order_share": round(delivery_orders / total_orders, 4),
                "avg_receipt": round(delivery_aov, 2),
            },
        },
        "blended_avg_receipt": round(blended_aov, 2),
        "target_total_orders": target_total_orders,
        "target_orders": {"dine_in": target_dine, "delivery": target_delivery},
        "estimated_target_revenue": round(estimated, 2),
        "formula": "目标订单 = 目标实收 ÷ 当前堂食/外卖组合后的实收客单价；订单按当天渠道订单占比分配。",
        "limits": [
            "这是订单目标，不是线上曝光或线下进店客流目标。",
            "堂食/外卖渠道拆分缺失时，不输出伪造的订单计划。",
        ],
    }


def render_channel_goal_answer(result: dict[str, Any]) -> str:
    """Render the deterministic analysis in an owner-readable form."""
    if result.get("status") != "ready":
        gap = (result.get("gaps") or ["缺少渠道拆分数据"])[0]
        return f"这题暂时不能按真实数据反推：{gap}"

    dine = result["channels"]["dine_in"]
    delivery = result["channels"]["delivery"]
    target = result["target_revenue"]
    orders = result["target_orders"]
    return (
        f"按 {result['source_date']} 最近一份渠道拆分完整的日报计算，目标实收 ¥{target:,.0f}：\n"
        f"- 堂食：实收 ¥{dine['revenue']:,.2f} / {dine['orders']} 单 = ¥{dine['avg_receipt']:,.2f}/单；占 {dine['order_share'] * 100:.1f}%\n"
        f"- 外卖：实收 ¥{delivery['revenue']:,.2f} / {delivery['orders']} 单 = ¥{delivery['avg_receipt']:,.2f}/单；占 {delivery['order_share'] * 100:.1f}%\n"
        f"- 当前组合实收客单价：¥{result['blended_avg_receipt']:,.2f}/单\n"
        f"- 目标订单：共 {result['target_total_orders']} 单，其中堂食 {orders['dine_in']} 单、外卖 {orders['delivery']} 单；"
        f"按当前客单价预计实收 ¥{result['estimated_target_revenue']:,.2f}。\n\n"
        "这是成交订单目标，不等于线上曝光或线下进店客流；客流需要另有平台访客/线下进店数据才能继续反推。"
    )


def _select_complete_snapshot(entries: Iterable[dict[str, Any]], date: str | None) -> dict[str, Any] | None:
    candidates = [entry for entry in entries if not date or entry.get("date") == date]
    for entry in reversed(candidates):
        unknown = set(entry.get("unknown_fields") or [])
        required = {"dine_in_orders", "dine_in_revenue", "delivery_orders", "delivery_revenue"}
        if unknown.intersection(required):
            continue
        if (
            int(entry.get("dine_in_orders", 0) or 0) > 0
            and int(entry.get("delivery_orders", 0) or 0) > 0
            and float(entry.get("dine_in_revenue", 0) or 0) > 0
            and float(entry.get("delivery_revenue", 0) or 0) > 0
        ):
            return entry
    return None
