"""Evidence-backed daily priorities for the independent Finance Agent."""

from __future__ import annotations

from datetime import date
from typing import Any

from models.finance_ledger import FinanceLedger


TOPIC_LABELS = {
    "daily_completeness": "缺账与日结",
    "funds_settlement": "平台到账与对账",
    "profit_cost": "成本与利润",
    "cash_safety": "资金安全",
    "evidence_reconciliation": "凭证与流水",
    "revenue_channels": "营业与渠道",
}


def classify_finance_topic(query: str, intent: str = "") -> str:
    text = query.strip()
    if intent == "date_coverage" or any(word in text for word in ("哪些天", "没录", "漏录", "日结", "缺账")):
        return "daily_completeness"
    if intent == "funds_status" or any(word in text for word in ("到账", "结算", "平台钱包", "对账", "工商银行")):
        return "funds_settlement"
    if intent == "profit_readiness" or any(word in text for word in ("成本", "利润", "赚", "亏", "毛利")):
        return "profit_cost"
    if any(word in text for word in ("资金够不够", "现金", "工资", "房租", "借款", "还款")):
        return "cash_safety"
    if any(word in text for word in ("凭证", "流水", "截图", "原图")):
        return "evidence_reconciliation"
    return "revenue_channels"


def _ranges(days: list[str]) -> str:
    if not days:
        return ""
    ordered = sorted(set(days))
    return "、".join(item[5:].replace("-", "/") for item in ordered[:4]) + ("…" if len(ordered) > 4 else "")


def build_finance_agent_insights(
    ledger: FinanceLedger,
    store_id: str,
    as_of: str,
    preferences: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    date.fromisoformat(as_of)
    month_start = f"{as_of[:7]}-01"
    analytics = ledger.finance_analytics(store_id, month_start, as_of)
    checklist = ledger.daily_revenue_checklist(store_id, as_of, as_of)
    forecast = ledger.cash_chain_forecast(store_id, as_of)
    alerts = ledger.alerts(store_id, month_start, as_of)
    preference_map = {str(item["topic"]): int(item["count"]) for item in (preferences or [])}
    items: list[dict[str, Any]] = []

    def add(topic: str, severity: str, title: str, summary: str, why_now: str, action_query: str, base: int) -> None:
        boost = min(preference_map.get(topic, 0) * 3, 12)
        items.append({
            "id": f"{topic}:{len(items) + 1}", "topic": topic,
            "topic_label": TOPIC_LABELS[topic], "severity": severity,
            "title": title, "summary": summary, "why_now": why_now,
            "action_query": action_query, "priority_score": base + boost,
            "preference_boosted": boost > 0,
        })

    today = checklist["days"][0]
    if today["missing_count"]:
        missing = [item["channel"] for item in today["channels"] if item["status"] == "missing"]
        add("daily_completeness", "critical", f"今天还有 {len(missing)} 个收入渠道未录", "、".join(missing), "今天的营业收入尚未形成完整口径，不会按0元处理。", f"告诉我 {as_of} 还缺哪些收入资料，按平台列出", 96)
    elif today["not_available_count"]:
        add("daily_completeness", "info", "今天的平台数据尚未全部出账", f"{today['not_available_count']} 个渠道已标记为暂未出数", "系统会保留待补状态，不需要填假0元。", f"哪些平台的 {as_of} 数据需要稍后补录？", 62)

    if analytics.get("missing_days"):
        days = list(analytics["missing_days"])
        add("daily_completeness", "warning", f"本月有 {len(days)} 天资料空缺", f"日期：{_ranges(days)}", "空缺日会影响累计营收、成本和利润判断。", "我还有哪些天的账没有录入？", 88)

    pending_minor = int(analytics.get("kpis", {}).get("pending_collection_minor") or 0)
    pending_rows = [item for item in analytics.get("settlement_timeline", []) if item.get("status") != "completed"]
    if pending_minor > 0:
        add("funds_settlement", "warning", f"{len(pending_rows)} 笔平台资金尚未闭环", f"待到店铺工商银行 ¥{pending_minor / 100:,.2f}", "这些是已发生收入的资金位置，不能重复计为新收入。", "哪些钱还没到店铺工商银行？", 84)

    missing_inputs = list(analytics.get("missing_inputs") or [])
    if missing_inputs:
        labels = {"daily_close": "完整日结", "food_cost": "食材实际耗用", "packaging_cost": "包装耗用", "labor": "人工成本", "rent": "房租", "utility": "水电燃气", "other_cost": "其他经营费用"}
        readable = [labels.get(item, item) for item in missing_inputs]
        add("profit_cost", "warning", "真实净利润尚不能确认", "还缺：" + "、".join(readable[:4]), "当前只能展示已知收支差额，不会冒充真实净利润。", "目前最缺哪些成本资料？", 78)

    if forecast.get("status") in {"at_risk", "partial"}:
        reasons = forecast.get("blocking_reasons") or []
        summary = "资金预测资料待补" if reasons else f"首个风险日：{forecast.get('first_risk_date')}"
        add("cash_safety", "critical" if forecast.get("status") == "at_risk" else "info", "现金安全性尚未完全确认", summary, "银行可用资金与未来工资、房租等必须在同一时间线上判断。", "资金够不够支付未来的工资和房租？", 72)

    severity_rank = {"critical": 3, "warning": 2, "info": 1, "good": 0}
    items.sort(key=lambda item: (-int(item["priority_score"]), -severity_rank[item["severity"]], item["title"]))
    learned = [
        {**item, "label": TOPIC_LABELS.get(str(item["topic"]), str(item["topic"]))}
        for item in (preferences or [])
    ]
    return {
        "schema_version": "finance_agent_insights_v1",
        "agent": {"id": "finance", "label": "财务 Agent", "scope": "finance", "role": "店铺会计与资金守门人"},
        "as_of": as_of,
        "period": {"start": month_start, "end": as_of},
        "daily_brief": {
            "headline": "今天先看这三件事" if items else "今天暂无新的财务待办",
            "summary": "按账目风险、截止日和你近期关注点动态排序。",
            "items": items[:3],
        },
        "learned_focus": learned,
        "alert_count": len(alerts),
        "completeness": "partial" if analytics.get("data_completeness") != "confirmed" or missing_inputs else "confirmed",
    }
