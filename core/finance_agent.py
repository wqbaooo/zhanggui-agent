"""Read-only finance Agent orchestration.

The language model may understand a question and choose from an allowlisted set
of read-only tools.  All amounts, dates and accounting states still come from
``FinanceLedger``; the model can neither mutate the ledger nor invent a formal
finance fact.
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass
from datetime import date
from typing import Any, Callable

from config import DEEPSEEK_API_KEY
from core.finance_skills import READ_ONLY_FINANCE_SKILLS, compact_skill_catalog, public_skill_records
from models.finance_ledger import FinanceLedger
from server.model_routing import chat_route


logger = logging.getLogger(__name__)

READ_ONLY_TOOLS = {skill.tool for skill in READ_ONLY_FINANCE_SKILLS}

_PUBLIC_LABELS = {
    "daily_close": "当日关账",
    "food_cost": "食材成本",
    "packaging_cost": "包装成本",
    "labor": "人工成本",
    "rent": "房租",
    "utility": "水电费",
    "other_cost": "其他费用",
}


@dataclass(frozen=True)
class FinanceAgentPlan:
    intent: str
    tools: tuple[str, ...]
    period_interpretation: str


class FinanceModelGateway:
    """Small OpenAI-compatible gateway shared by DeepSeek/OpenAI routes."""

    def __init__(self) -> None:
        route = chat_route()
        self.route = route
        if not route.configured:
            raise RuntimeError("文本推理模型未配置")
        if route.provider == "deepseek":
            api_key = DEEPSEEK_API_KEY
        else:
            api_key = os.environ.get("OPENAI_API_KEY", "")
        from openai import OpenAI

        self.client = OpenAI(api_key=api_key, base_url=route.base_url, timeout=18.0)

    def json_completion(self, system: str, user: str, *, max_tokens: int = 900) -> dict[str, Any]:
        response = self.client.chat.completions.create(
            model=self.route.model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            response_format={"type": "json_object"},
            temperature=0.1,
            max_tokens=max_tokens,
        )
        content = response.choices[0].message.content or "{}"
        payload = json.loads(content)
        if not isinstance(payload, dict):
            raise ValueError("模型没有返回 JSON 对象")
        return payload


def _range_text(days: list[str]) -> str:
    if not days:
        return "无"
    parsed = sorted(date.fromisoformat(item) for item in set(days))
    ranges: list[tuple[date, date]] = []
    start = previous = parsed[0]
    for current in parsed[1:]:
        if (current - previous).days == 1:
            previous = current
            continue
        ranges.append((start, previous))
        start = previous = current
    ranges.append((start, previous))
    return "、".join(
        item_start.strftime("%m月%d日")
        if item_start == item_end
        else f"{item_start.strftime('%m月%d日')}至{item_end.strftime('%m月%d日')}"
        for item_start, item_end in ranges
    )


def _date_coverage(ledger: FinanceLedger, store_id: str, start: str, end: str) -> dict[str, Any]:
    analytics = ledger.finance_analytics(store_id, start, end)
    empty_days: list[str] = []
    activity_without_sales: list[str] = []
    platform_only_days: list[str] = []
    open_close_days: list[str] = []
    for row in analytics.get("daily_series", []):
        day = str(row["business_date"])
        if row["state"] == "missing":
            empty_days.append(day)
        elif row.get("accounting_revenue_minor") is None:
            if row.get("merchant_net_minor") is not None:
                platform_only_days.append(day)
            else:
                activity_without_sales.append(day)
        elif row["state"] != "closed":
            open_close_days.append(day)
    return {
        "tool": "finance_date_coverage",
        "period": {"start": start, "end": end},
        "empty_days": empty_days,
        "activity_without_sales": activity_without_sales,
        "platform_only_days": platform_only_days,
        "open_close_days": open_close_days,
        "recorded_days": len(analytics.get("daily_series", [])) - len(empty_days),
        "natural_days": len(analytics.get("daily_series", [])),
    }


def _execute_tool(
    tool: str, ledger: FinanceLedger, store_id: str, query: str, start: str, end: str,
) -> dict[str, Any]:
    if tool == "finance_date_coverage":
        return _date_coverage(ledger, store_id, start, end)
    if tool == "finance_funds_status":
        return {"tool": tool, "result": ledger.finance_query(store_id, "哪些钱还没到店铺账户", start, end)}
    if tool == "finance_profit_readiness":
        overview = ledger.finance_overview(store_id, start, end)
        return {
            "tool": tool,
            "profit_status": overview.get("profit_status"),
            "missing_inputs": [_PUBLIC_LABELS.get(item, item) for item in overview.get("missing_inputs", [])],
            "known_operating_cost_minor": overview.get("known_operating_cost_minor"),
            "provisional_net_profit_minor": overview.get("provisional_net_profit_minor"),
        }
    if tool == "finance_metric_summary":
        return {"tool": tool, "result": ledger.finance_query(store_id, query, start, end)}
    if tool == "finance_evidence_audit":
        vouchers = ledger.list_evidence_vouchers(store_id, start, end)
        status_counts: dict[str, int] = {}
        for voucher in vouchers:
            status = str(voucher.get("status") or "unknown")
            status_counts[status] = status_counts.get(status, 0) + 1
        return {
            "tool": tool,
            "voucher_count": len(vouchers),
            "status_counts": status_counts,
            "undated_count": sum(1 for item in vouchers if not item.get("business_date")),
            "missing_file_count": sum(1 for item in vouchers if not item.get("original_path")),
        }
    if tool == "finance_settlement_reconciliation":
        return {
            "tool": tool,
            "platforms": ledger.reconcile_platforms(store_id, start, end),
            "receivables": ledger.reconcile_receivables(store_id, start, end),
        }
    raise ValueError(f"未授权的财务工具：{tool}")


def _fallback_plan(query: str) -> FinanceAgentPlan:
    has_day_scope = any(token in query for token in ("哪些天", "哪几天", "多少天", "日期", "空缺"))
    has_record_gap = any(token in query for token in ("没录", "未录", "没有录入", "漏录", "不完整"))
    if has_day_scope and has_record_gap:
        return FinanceAgentPlan("date_coverage", ("finance_date_coverage",), "按所选日期范围逐日核对")
    if any(token in query for token in ("没到账", "未到账", "钱在哪", "应收", "前老板", "平台钱包")):
        return FinanceAgentPlan("funds_status", ("finance_funds_status",), "按所选日期范围核对资金位置")
    if any(token in query for token in ("缺哪些成本", "成本资料", "利润资料", "真实利润")):
        return FinanceAgentPlan("profit_readiness", ("finance_profit_readiness",), "按所选日期范围核对利润资料")
    return FinanceAgentPlan("metric_summary", ("finance_metric_summary",), "按所选日期范围分析")


def _plan_with_model(
    query: str, start: str, end: str, gateway: FinanceModelGateway,
    conversation_history: list[dict[str, str]] | None = None,
) -> FinanceAgentPlan:
    payload = gateway.json_completion(
        f"""你是单店财务 Agent 的规划器。采用 Hermes 的按需技能加载和 Pi 的模型驱动工具循环：只理解问题、选择必要的只读财务 Skill，不直接回答，不输出思维过程。
可用财务 Skills：
{compact_skill_catalog()}
综合分析财务情况时应覆盖业绩、资金位置、利润完整性和数据缺口；只问单一事实时只选最少技能。
严格返回 JSON：{{"intent":"...","tools":["..."],"period_interpretation":"..."}}。最多选4个工具。""",
        f"最近财务对话：{json.dumps((conversation_history or [])[-6:], ensure_ascii=False)}\n当前问题：{query}\n分析范围：{start} 至 {end}",
        max_tokens=1200,
    )
    tools = tuple(dict.fromkeys(str(item) for item in payload.get("tools", [])))[:4]
    if not tools or any(item not in READ_ONLY_TOOLS for item in tools):
        raise ValueError("模型选择了空工具或越权工具")
    intent_by_tool = {
        "finance_date_coverage": "date_coverage",
        "finance_funds_status": "funds_status",
        "finance_profit_readiness": "profit_readiness",
        "finance_metric_summary": "metric_summary",
    }
    requested_intent = str(payload.get("intent") or "").strip()
    intent = (
        "comprehensive_analysis"
        if len(tools) > 1
        else intent_by_tool[tools[0]]
    )
    return FinanceAgentPlan(
        intent=intent,
        tools=tools,
        period_interpretation=str(payload.get("period_interpretation") or "按所选日期范围分析")[:120],
    )


def _deterministic_answer(plan: FinanceAgentPlan, results: list[dict[str, Any]], end: str) -> str:
    coverage = next((item for item in results if item.get("tool") == "finance_date_coverage"), None)
    nested_results = [item["result"] for item in results if isinstance(item.get("result"), dict)]
    if plan.intent == "comprehensive_analysis":
        metrics = {
            str(metric.get("metric_code")): metric
            for nested in nested_results
            for metric in nested.get("metrics", [])
            if isinstance(metric, dict) and metric.get("metric_code")
        }
        revenue = metrics.get("revenue")
        net_profit = metrics.get("operating_net_profit")
        gross_profit = metrics.get("gross_profit")
        former_owner = metrics.get("former_owner_receivable")
        unsettled = metrics.get("platform_unsettled")
        controlled = metrics.get("store_controlled_funds")
        parts = ["**财务结论**", ""]
        if revenue and revenue.get("value") is not None:
            parts.append(f"- **营业收入**：¥{float(revenue['value']):,.2f}")
        if gross_profit and gross_profit.get("value") is None:
            parts.append("- **营业毛利**：暂不能确认，食材或包装成本尚未完整归集")
        if net_profit and net_profit.get("value") is None:
            parts.append("- **经营净利润**：暂不能确认，不能把缺失成本按 0 元处理")
        if former_owner and former_owner.get("value") is not None:
            parts.append(f"- **前老板代收待转**：¥{float(former_owner['value']):,.2f}")
        if unsettled and unsettled.get("value") is not None:
            parts.append(f"- **平台待结算**：¥{float(unsettled['value']):,.2f}")
        if controlled and controlled.get("value") is not None:
            parts.append(
                f"- **账面可追溯店铺资金**：¥{float(controlled['value']):,.2f}，"
                "这不是工商银行卡实际余额"
            )
        if coverage:
            missing_days = sorted({
                day
                for key in ("empty_days", "activity_without_sales", "platform_only_days", "open_close_days")
                for day in coverage.get(key, [])
            })
            if missing_days:
                parts.extend(["", "**数据完整性**", ""])
                if coverage.get("empty_days"):
                    parts.append(f"- 完全空缺：{_range_text(coverage['empty_days'])}")
                if coverage.get("activity_without_sales"):
                    parts.append(f"- 缺营业收入：{_range_text(coverage['activity_without_sales'])}")
                if coverage.get("platform_only_days"):
                    parts.append(f"- 缺收入或订单明细：{_range_text(coverage['platform_only_days'])}")
                if coverage.get("open_close_days"):
                    parts.append(f"- 未完成日结：{_range_text(coverage['open_close_days'])}")
        parts.extend([
            "",
            "**下一步**",
            "",
            "先补完全空缺日与食材、包装、人工、房租和水电等成本，再核算真实净利润。",
        ])
        return "\n".join(parts)
    if coverage:
        missing_days = sorted({
            day
            for key in ("empty_days", "activity_without_sales", "platform_only_days", "open_close_days")
            for day in coverage.get(key, [])
        })
        parts = ["**核对结论**", ""]
        if missing_days:
            parts.append(f"截至 {end}，共 **{len(missing_days)} 天**存在待补项：")
        else:
            parts.append(f"截至 {end}，所选范围内每天都有记录，没有发现待补的日账状态。")
        if coverage["empty_days"]:
            parts.append(f"- **完全空缺**：{_range_text(coverage['empty_days'])}")
        if coverage["activity_without_sales"]:
            parts.append(f"- **缺营业收入**：{_range_text(coverage['activity_without_sales'])}")
        if coverage["platform_only_days"]:
            parts.append(f"- **缺收入或订单明细**：{_range_text(coverage['platform_only_days'])}")
        if coverage["open_close_days"]:
            parts.append(f"- **未完成日结**：{_range_text(coverage['open_close_days'])}")
        if missing_days:
            parts.extend([
                "",
                "**建议先补**",
                "",
                "先补“完全空缺”和“缺营业收入”的日期，再补平台明细并完成日结。",
            ])
        return "\n".join(parts)
    for nested in nested_results:
        if nested.get("answer"):
            return str(nested["answer"])
    readiness = next((item for item in results if item.get("tool") == "finance_profit_readiness"), None)
    if readiness:
        missing = readiness.get("missing_inputs") or []
        return "当前影响真实利润确认的资料是：" + ("、".join(missing) if missing else "无") + "。"
    return "已核对所选期间的财务记录，但当前工具结果不足以形成可靠结论。"


def _answer_with_model(
    query: str, start: str, end: str, plan: FinanceAgentPlan,
    results: list[dict[str, Any]], gateway: FinanceModelGateway,
    conversation_history: list[dict[str, str]] | None = None,
) -> str:
    payload = gateway.json_completion(
        """你是新余恒太城五楼大口章鱼烧的财务 Agent。根据只读工具结果直接回答老板的问题。
规则：不得补造数字或日期；不同缺口必须分开表达；不得暴露 daily_close 等内部字段名；不要输出思维过程；不把累计到账当银行卡余额；个人消费不进入店铺利润。回答必须结论优先、简短可扫描：先用一个短标题和一句结论，再用 Markdown 列表分组事实，最后只给一个最重要的下一步；避免连续长段落和重复解释。返回 JSON：{"answer":"..."}。""",
        json.dumps({"recent_finance_conversation": (conversation_history or [])[-6:], "question": query, "period": {"start": start, "end": end}, "plan": plan.__dict__, "tool_results": results}, ensure_ascii=False),
        max_tokens=2000,
    )
    return str(payload.get("answer") or "").strip()


def _sanitize_answer(answer: str) -> str:
    sanitized = answer
    for internal, public in _PUBLIC_LABELS.items():
        sanitized = sanitized.replace(internal, public)
    return sanitized


def _answer_is_grounded(answer: str, plan: FinanceAgentPlan, results: list[dict[str, Any]]) -> bool:
    if not answer:
        return False
    if plan.intent == "date_coverage" or "finance_date_coverage" in plan.tools:
        coverage = next((item for item in results if item.get("tool") == "finance_date_coverage"), {})
        normalized = re.sub(r"[年月日/\-.]", "", answer)
        for key in ("empty_days", "activity_without_sales", "platform_only_days", "open_close_days"):
            days = coverage.get(key, [])
            if not days:
                continue
            endpoints = (days[0],) if len(days) == 1 else (days[0], days[-1])
            if not all(date.fromisoformat(day).strftime("%m%d") in normalized for day in endpoints):
                return False
        return True
    return True


def answer_finance_question(
    ledger: FinanceLedger,
    store_id: str,
    query: str,
    start: str,
    end: str,
    *,
    gateway_factory: Callable[[], FinanceModelGateway] = FinanceModelGateway,
    use_model: bool = True,
    conversation_history: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Run the finance Agent and return a user-visible, auditable result."""
    model_gateway: FinanceModelGateway | None = None
    model_error: str | None = None
    plan_source = "规则兜底"
    try:
        if not use_model:
            raise RuntimeError("模型通道已关闭")
        model_gateway = gateway_factory()
        plan = _plan_with_model(query, start, end, model_gateway, conversation_history)
        plan_source = "模型规划"
    except Exception as exc:
        logger.warning("财务 Agent 规划降级: %s", exc)
        model_error = str(exc)
        model_gateway = None
        plan = _fallback_plan(query)

    results = [_execute_tool(tool, ledger, store_id, query, start, end) for tool in plan.tools]
    deterministic = _deterministic_answer(plan, results, end)
    answer = deterministic
    if model_gateway is not None:
        try:
            candidate = _sanitize_answer(_answer_with_model(query, start, end, plan, results, model_gateway, conversation_history))
            if _answer_is_grounded(candidate, plan, results):
                answer = candidate
            else:
                model_error = "模型回答未通过事实完整性校验"
        except Exception as exc:
            logger.warning("财务 Agent 回答生成降级: %s", exc)
            model_error = str(exc)

    answer = _sanitize_answer(answer)
    nested_results = [item["result"] for item in results if isinstance(item.get("result"), dict)]
    legacy = nested_results[0] if nested_results else {}
    merged_metrics = list({
        str(metric.get("metric_code")): metric
        for nested in nested_results
        for metric in nested.get("metrics", [])
        if isinstance(metric, dict) and metric.get("metric_code")
    }.values())
    merged_formula_trace = list(dict.fromkeys(
        str(item) for nested in nested_results for item in nested.get("formula_trace", [])
    ))
    evidence_ids = list(dict.fromkeys(
        str(item) for nested in nested_results for item in nested.get("evidence_ids", [])
    ))
    coverage = next((item for item in results if item.get("tool") == "finance_date_coverage"), None)
    warnings = list(dict.fromkeys(
        str(item) for nested in nested_results for item in nested.get("warnings", [])
    ))
    if coverage:
        warnings = []
        if coverage["empty_days"]:
            warnings.append(f"完全空缺：{_range_text(coverage['empty_days'])}")
        if coverage["activity_without_sales"]:
            warnings.append(f"有资金记录但缺营业收入：{_range_text(coverage['activity_without_sales'])}")
        if coverage["platform_only_days"]:
            warnings.append(f"有平台销售但营业台账待补：{_range_text(coverage['platform_only_days'])}")
        if coverage["open_close_days"]:
            warnings.append(f"营业数据已录入但未完成关账：{_range_text(coverage['open_close_days'])}")

    route = chat_route()
    intent_labels = {
        "date_coverage": "日期完整性核对",
        "funds_status": "资金位置核对",
        "profit_readiness": "利润资料完整性核对",
        "metric_summary": "财务指标分析",
        "comprehensive_analysis": "综合财务分析",
    }
    trace = [
        {"step": "理解问题", "status": "completed", "detail": f"{plan.period_interpretation}；识别为{intent_labels.get(plan.intent, '财务问题')}"},
        *[
            {"step": "核对财务事实", "status": "completed", "tool": tool, "detail": {
                "finance_date_coverage": "逐日核对营业、资金活动与关账状态",
                "finance_funds_status": "核对平台、前老板代收与店铺账户资金位置",
                "finance_profit_readiness": "核对真实利润所需成本资料",
                "finance_metric_summary": "按台账公式计算所问指标",
            }[tool]}
            for tool in plan.tools
        ],
        {"step": "一致性检查", "status": "completed", "detail": "已检查日期、金额和内部字段，未通过时自动使用事实答案"},
    ]
    sources = [
        {"type": "ledger", "label": "专业资金台账", "reference": f"{start} 至 {end}"},
        {"type": "calendar", "label": "每日营业与资金记录", "reference": f"{start} 至 {end}"},
    ]
    return {
        "answer": answer,
        "period": {"start": start, "end": end},
        "intent": plan.intent,
        "metrics": merged_metrics,
        "formula_trace": merged_formula_trace,
        "evidence_ids": evidence_ids,
        "completeness": "partial" if warnings else legacy.get("completeness", "confirmed"),
        "warnings": [_sanitize_answer(str(item)) for item in warnings],
        "follow_up_inputs": legacy.get("follow_up_inputs", []),
        "execution_trace": trace,
        "sources": sources,
        "skills_used": public_skill_records(plan.tools),
        "agent": {
            "id": "finance",
            "scope": "finance",
            "label": "财务 Agent",
            "role": "店铺会计与资金守门人",
            "provider": route.provider,
            "model": route.model,
            "mode": plan_source,
            "model_used": model_gateway is not None,
            "fallback_reason": model_error,
        },
    }
