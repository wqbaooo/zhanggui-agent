#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""分析路由 — 首页智能解读。"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL
from core.agent_permissions import DEFAULT_PROJECT_ID, enforce_project_scope
from core.business_forecast import build_business_forecast
from core.domain_intelligence import build_domain_context
from models.finance_ledger import FinanceLedger
from models.project import ProjectMemory
from models.sku import SkuCatalog
from server.routes.weather import get_weather

logger = logging.getLogger(__name__)

router = APIRouter(tags=["analyze"])
_FORECAST_WEATHER_CACHE: dict[str, Any] | None = None
_FORECAST_WEATHER_CACHED_AT = 0.0
FORECAST_WEATHER_CACHE_SECONDS = 600
FORECAST_WEATHER_TIMEOUT_SECONDS = 5.5


class TodayInsightResponse(BaseModel):
    insight: str
    health_status: str  # "good" | "watch" | "risk"
    key_concern: str | None


ADVISOR_QUERY = (
    "分析利润现金流账、外卖美团平台佣金、库存补货采购、"
    "员工工资排班、SOP打烊流程、食品安全卫生风险"
)


def _latest_business_date(project_id: str) -> str | None:
    """返回最近一条真实经营/财务事实日期，不用今天冒充数据日期。"""
    candidates: list[str] = []
    memory = ProjectMemory.load(project_id)
    if memory:
        candidates.extend(
            str(item.get("date"))
            for item in memory.daily_operations
            if item.get("date")
        )
    try:
        from models.finance_ledger import FinanceLedger

        overview = FinanceLedger.for_project(project_id).finance_overview(project_id)
        if int(overview.get("sales_days") or 0) > 0 and overview.get("last_data_date"):
            candidates.append(str(overview["last_data_date"]))
    except Exception as exc:
        logger.warning("经营参谋读取财务事实日期失败: %s", exc)
    return max(candidates) if candidates else None


def _latest_inventory_fact_date(catalog: SkuCatalog | None) -> date | None:
    """Use dated inventory events, never a file-modification timestamp, as evidence."""
    if catalog is None:
        return None
    candidates: list[date] = []
    for collection in (
        catalog.inventory_counts,
        catalog.inventory_events,
        catalog.usage_logs,
    ):
        for item in collection:
            try:
                candidates.append(date.fromisoformat(str(item.get("date"))))
            except (TypeError, ValueError):
                continue
    return max(candidates) if candidates else None


async def _weather_for_business_forecast() -> dict[str, Any]:
    global _FORECAST_WEATHER_CACHE, _FORECAST_WEATHER_CACHED_AT
    cache_age = time.monotonic() - _FORECAST_WEATHER_CACHED_AT
    if _FORECAST_WEATHER_CACHE and cache_age < FORECAST_WEATHER_CACHE_SECONDS:
        return dict(_FORECAST_WEATHER_CACHE)
    try:
        weather = await asyncio.wait_for(
            get_weather(),
            timeout=FORECAST_WEATHER_TIMEOUT_SECONDS,
        )
        if weather.get("status") != "unavailable":
            _FORECAST_WEATHER_CACHE = dict(weather)
            _FORECAST_WEATHER_CACHED_AT = time.monotonic()
        return weather
    except Exception as exc:
        logger.warning("经营预测读取联网天气失败: %s", exc)
        if _FORECAST_WEATHER_CACHE:
            cached = dict(_FORECAST_WEATHER_CACHE)
            cached["status"] = "partial"
            cached["is_stale"] = True
            cached["warnings"] = [
                *cached.get("warnings", []),
                "本次天气刷新超时，经营预测暂用最近一次联网天气",
            ]
            return cached
        return {
            "status": "unavailable",
            "forecast_source": None,
            "forecast_updated_at": None,
            "forecast": [],
        }


def _money(value: Any) -> str:
    try:
        return f"¥{float(value):,.2f}"
    except (TypeError, ValueError):
        return "待确认"


def _advisor_fact(domain: str, fact: dict[str, Any]) -> dict[str, str]:
    """把领域模块的结构化事实翻译成老板能核对的短句。"""
    title = str(fact.get("fact") or "已确认事实")
    source = str(fact.get("source") or "门店经营档案")
    values = fact.get("values") if isinstance(fact.get("values"), dict) else {}
    items = fact.get("items") if isinstance(fact.get("items"), list) else []

    if domain == "finance" and values:
        parts: list[str] = []
        if values.get("entry_count") is not None:
            parts.append(f"已确认 {values['entry_count']} 天")
        if values.get("total_revenue") is not None:
            parts.append(f"营业收入 {_money(values['total_revenue'])}")
        if values.get("total_orders") is not None:
            parts.append(f"{values['total_orders']} 单")
        net_profit = values.get("net_profit")
        parts.append(
            f"净利润 {_money(net_profit)}"
            if net_profit is not None
            else "净利润暂不能确认"
        )
        summary = "；".join(parts)
    elif domain == "channel" and values:
        parts = []
        if values.get("entry_count") is not None:
            parts.append(f"近 {values['entry_count']} 个经营日")
        if values.get("total_revenue") is not None:
            parts.append(f"全店营业收入 {_money(values['total_revenue'])}")
        if values.get("total_orders") is not None:
            parts.append(f"{values['total_orders']} 单")
        summary = "；".join(parts) or "已读取经营台账，渠道利润仍需按平台拆分"
        title = "渠道分析所用的全店经营背景"
    elif domain == "procurement_inventory" and items:
        unknown = sum(
            1
            for item in items
            if item.get("quantity_status") == "unknown"
            or item.get("status") in {"待盘点", "未盘点", "unknown"}
        )
        summary = f"已关联 {len(items)} 项"
        if unknown:
            summary += f"；其中 {unknown} 项数量待盘点"
    elif domain == "labor" and fact.get("count") is not None:
        summary = f"已记录 {fact['count']} 条"
    elif items:
        summary = f"已关联 {len(items)} 项记录"
    elif values:
        summary = "；".join(f"{key}：{value}" for key, value in values.items())
    else:
        summary = title

    return {"title": title, "summary": summary, "source": source}


def _build_advisor_brief(project_id: str) -> dict[str, Any]:
    context = build_domain_context(project_id, ADVISOR_QUERY)
    sections: list[dict[str, Any]] = []
    priority_actions: list[dict[str, str]] = []
    seen_actions: set[tuple[str, str]] = set()
    fact_count = 0
    gap_count = 0
    conflict_count = 0

    for report in context.get("reports", []):
        facts = [
            _advisor_fact(str(report.get("domain") or ""), fact)
            for fact in report.get("known_facts", [])
        ]
        gaps = [str(item) for item in report.get("gaps", [])]
        conflicts = list(report.get("conflicts", []))
        fact_count += len(facts)
        gap_count += len(gaps)
        conflict_count += len(conflicts)
        status = (
            "conflict"
            if conflicts
            else "unknown"
            if not facts
            else "partial"
            if gaps
            else "verified"
        )
        sections.append({
            "key": report.get("domain"),
            "label": report.get("label"),
            "status": status,
            "facts": facts,
            "gaps": gaps,
            "conflicts": conflicts,
            "guidance": [str(item) for item in report.get("professional_guidance", [])],
            "evidence": list(report.get("evidence", [])),
        })
        if gaps or conflicts:
            for action in report.get("proposed_actions", []):
                key = (str(action.get("label") or ""), str(action.get("target") or ""))
                if all(key) and key not in seen_actions:
                    seen_actions.add(key)
                    priority_actions.append({"label": key[0], "target": key[1]})

    if fact_count == 0:
        data_status = "empty"
        headline = "当前证据不足，暂不能形成经营判断"
    elif conflict_count:
        data_status = "conflict"
        headline = f"已读取 {fact_count} 组事实，发现 {conflict_count} 项需要先核对"
    elif gap_count:
        data_status = "partial"
        headline = f"已读取 {fact_count} 组事实，仍有 {gap_count} 项关键数据待补齐"
    else:
        data_status = "ready"
        headline = f"已根据 {fact_count} 组已确认事实生成经营简报"

    return {
        "project_id": project_id,
        "role": "经营参谋",
        "permission": "read_only",
        "calendar_date": date.today().isoformat(),
        "latest_fact_date": _latest_business_date(project_id),
        "data_status": data_status,
        "headline": headline,
        "consulted_modules": context.get("route", {}).get("consulted_modules", []),
        "sections": sections,
        "priority_actions": priority_actions[:5],
    }


@router.get("/projects/{project_id}/analyze/advisor-brief")
async def get_advisor_brief(project_id: str):
    """只读汇总各专业模块；未知、缺口和冲突必须原样保留。"""
    try:
        project_id = enforce_project_scope(project_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return _build_advisor_brief(project_id)


@router.get("/projects/{project_id}/analyze/business-forecast")
async def get_business_forecast(project_id: str, as_of: str | None = None):
    """只读经营预测：收入给区间，库存只在日耗事实齐全时给采购量。"""
    try:
        project_id = enforce_project_scope(project_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    try:
        as_of_date = (
            date.fromisoformat(as_of)
            if as_of
            else datetime.now(ZoneInfo("Asia/Shanghai")).date()
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="as_of 必须是 YYYY-MM-DD") from exc

    weather_task = asyncio.create_task(_weather_for_business_forecast())
    ledger = FinanceLedger.for_project(project_id)
    first_date, last_date = ledger.period_bounds(project_id)
    revenue_rows: list[dict[str, Any]] = []
    if first_date and last_date and first_date <= as_of_date.isoformat():
        revenue_rows = ledger.daily_revenue(
            project_id,
            first_date,
            min(last_date, as_of_date.isoformat()),
        )

    catalog = SkuCatalog.load(project_id)
    inventory_fact_date = _latest_inventory_fact_date(catalog)
    weather = await weather_task

    sku_forecast = catalog.forecast() if catalog else []
    draft = build_business_forecast(
        project_id=project_id,
        as_of=as_of_date,
        revenue_rows=revenue_rows,
        sku_forecast=sku_forecast,
        inventory_fact_date=inventory_fact_date,
        weather=weather,
    )
    demand_factor = draft["revenue"].get("demand_factor")
    if catalog and isinstance(demand_factor, (int, float)):
        sku_forecast = catalog.forecast(revenue_growth_factor=float(demand_factor))

    return build_business_forecast(
        project_id=project_id,
        as_of=as_of_date,
        revenue_rows=revenue_rows,
        sku_forecast=sku_forecast,
        inventory_fact_date=inventory_fact_date,
        weather=weather,
    )


def _build_analysis_prompt(summary: dict, today_entry: dict | None, prev_summary: dict | None) -> str:
    """构建 LLM 分析提示词。"""

    # 基础统计
    revenue = float(summary.get("total_revenue") or 0)
    net_profit = float(summary.get("net_profit") or 0)
    profit_ready = summary.get("profit_ready", True)
    orders = int(summary.get("total_orders") or 0)
    prime_cost_rate = summary.get("prime_cost_rate")
    food_cost_rate = summary.get("food_cost_rate")
    delivery_rate = summary.get("delivery_rate")
    avg_order = summary.get("avg_order_value")
    entry_count = summary.get("entry_count", 0)
    settlement = summary.get("settlement_summary", {})
    products = summary.get("product_sales", [])

    # 环比数据
    prev_revenue = prev_summary.get("total_revenue", 0) if prev_summary else 0
    prev_net_profit = prev_summary.get("net_profit", 0) if prev_summary else 0
    prev_orders = prev_summary.get("total_orders", 0) if prev_summary else 0

    revenue_change = ((revenue - prev_revenue) / prev_revenue * 100) if prev_revenue > 0 else 0
    profit_change = ((net_profit - prev_net_profit) / abs(prev_net_profit) * 100) if prev_net_profit != 0 else 0

    # 今日数据
    today_revenue = today_entry.get("revenue", 0) if today_entry else 0
    today_orders = today_entry.get("orders", 0) if today_entry else 0
    today_delivery = today_entry.get("delivery_revenue", 0) if today_entry else 0

    profit_line = (
        f"- 净利：¥{net_profit:,.0f}（环比{profit_change:+.0f}%）"
        if profit_ready
        else "- 净利：暂不可计算（食材、包装、人工、房租或水电尚未补齐）"
    )
    product_line = "、".join(
        f"{item.get('name')} {item.get('quantity', 0):g}份/¥{item.get('amount', 0):,.0f}"
        for item in products[:3]
    ) or "商品明细不足"

    def rate_text(value: object) -> str:
        return f"{float(value) * 100:.0f}%" if value is not None else "待确认"

    avg_order_text = f"¥{float(avg_order):.0f}" if avg_order is not None else "待确认"
    prompt = f"""你是新余恒太城五楼大口章鱼烧的单店经营 Agent。请根据以下数据，用2-3句话给老板一个简洁、可执行的经营判断。

【已确认的{entry_count}天数据】
- 营收：¥{revenue:,.0f}（环比{revenue_change:+.0f}%）
{profit_line}
- 订单：{orders} 单
- 客单价：{avg_order_text}
- 食材成本率：{rate_text(food_cost_rate)}
- 人工+食材成本率：{rate_text(prime_cost_rate)}
- 外卖营收占比：{rate_text(delivery_rate)}
- 待前老板对账：¥{settlement.get('former_owner', 0):,.2f}
- 收银机现金：¥{settlement.get('cash_on_hand', 0):,.2f}
- 已识别商品：{product_line}

【今日数据】{f"营收¥{today_revenue:,.0f}，{today_orders}单" if today_revenue else "暂无录入"}

请给出：
1. 一句话经营状态判断（趋势向上/稳定/需关注）
2. 最重要的问题或亮点（如果有问题，给出具体建议）
3. 明天最需要关注的一件事

格式：使用中文，简洁有力，老板能立刻看懂。不要用报告格式。"""

    return prompt


async def _call_llm(prompt: str) -> str:
    """调用 DeepSeek LLM。"""
    if not DEEPSEEK_API_KEY:
        raise RuntimeError("DeepSeek API key 未配置")

    try:
        from openai import OpenAI
        client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)
        response = client.chat.completions.create(
            model=DEEPSEEK_MODEL or "deepseek-chat",
            messages=[
                {"role": "system", "content": "你是一个专业的餐饮门店经营顾问，用简洁易懂的语言给老板提供经营建议。"},
                {"role": "user", "content": prompt},
            ],
            max_tokens=300,
            temperature=0.7,
        )
        return response.choices[0].message.content or ""
    except Exception as e:
        logger.error(f"LLM 调用失败: {e}")
        raise RuntimeError(f"LLM 调用失败: {e}")


@router.get("/projects/{project_id}/analyze/today-insight", response_model=TodayInsightResponse)
async def get_today_insight(project_id: str):
    """生成首页今日经营智能解读。"""

    memory = ProjectMemory.load(project_id)
    if memory is None:
        raise HTTPException(status_code=404, detail="项目不存在")

    # 获取本周汇总
    summary = memory.operation_summary(days=7)

    # 获取上周汇总（用于环比）
    prev_summary = None
    if len(memory.daily_operations) >= 14:
        # 计算上周同期的数据
        recent_ops = memory.daily_operations[-7:]
        prev_ops = memory.daily_operations[-14:-7]

        if prev_ops and recent_ops:
            prev_revenue = sum(float(e.get("revenue", 0) or 0) for e in prev_ops)
            prev_orders = sum(int(e.get("orders", 0) or 0) for e in prev_ops)
            prev_food = sum(float(e.get("food_cost", 0) or 0) for e in prev_ops)
            prev_labor = sum(float(e.get("labor", 0) or 0) for e in prev_ops)
            prev_other = sum(
                float(e.get("rent_allocated", 0) or 0) + float(e.get("utility", 0) or 0) +
                float(e.get("other_cost", 0) or 0) + float(e.get("marketing_cost", 0) or 0) +
                float(e.get("platform_fee", 0) or 0) + float(e.get("inventory_loss", 0) or 0)
                for e in prev_ops
            )
            prev_cost = prev_food + prev_labor + prev_other
            prev_net_profit = prev_revenue - prev_cost

            prev_summary = {
                "total_revenue": prev_revenue,
                "total_orders": prev_orders,
                "net_profit": prev_net_profit,
            }

    # 检查今日是否有录入
    from datetime import date
    today_str = date.today().isoformat()
    today_entry = None
    for op in reversed(memory.daily_operations):
        if op.get("date") == today_str:
            today_entry = op
            break

    # 构建提示词
    prompt = _build_analysis_prompt(summary, today_entry, prev_summary)

    # 调用 LLM
    try:
        response = await _call_llm(prompt)

        # 简单解析 LLM 返回
        lines = response.strip().split("\n")
        insight_lines = [l for l in lines if l.strip()]
        insight = " ".join(insight_lines[:3]) if insight_lines else "已确认经营数据已加载，请查看详情。"

        # 判断健康状态
        net_profit = float(summary.get("net_profit") or 0)
        prime_cost_rate = float(summary.get("prime_cost_rate") or 0)

        if not summary.get("profit_ready", True):
            health_status = "watch"
        elif net_profit < 0:
            health_status = "risk"
        elif prime_cost_rate > 0.65:
            health_status = "watch"
        elif net_profit > 0 and prime_cost_rate < 0.55:
            health_status = "good"
        else:
            health_status = "watch"

        # 提取关注点
        key_concern = None
        if not summary.get("profit_ready", True):
            key_concern = "成本尚未补齐，暂不能判断真实利润"
        elif float(summary.get("delivery_rate") or 0) > 0.6:
            key_concern = "外卖占比偏高，建议加强堂食引流"
        elif prime_cost_rate > 0.65:
            key_concern = "成本率偏高，需检查食材损耗"
        elif net_profit < 0:
            key_concern = "本周亏损，需查明原因"

        return TodayInsightResponse(
            insight=insight,
            health_status=health_status,
            key_concern=key_concern,
        )

    except Exception as e:
        logger.error(f"LLM analysis failed: {e}")
        # 降级返回简单判断
        net_profit = float(summary.get("net_profit") or 0)
        if not summary.get("profit_ready", True):
            return TodayInsightResponse(
                insight=f"{summary.get('entry_count', 0)}天营业收入¥{summary.get('total_revenue', 0):,.0f}已确认；成本尚未补齐，暂不判断净利。",
                health_status="watch",
                key_concern="补录食材、包装、人工、房租和水电",
            )
        return TodayInsightResponse(
            insight=f"{summary.get('entry_count', 0)}天营收¥{summary.get('total_revenue', 0):,.0f}，净利¥{net_profit:,.0f}。",
            health_status="good" if net_profit > 0 else "risk",
            key_concern=None,
        )


@router.get("/projects/{project_id}/analyze/break-even")
async def get_break_even_analysis(project_id: str, days: int = 30):
    """保本点分析：固定/变动成本拆分 + 边际贡献率 + 日保本营收。"""
    from datetime import date, timedelta
    from models.analytics import StoreAnalytics

    memory = ProjectMemory.load(project_id)
    if memory is None:
        raise HTTPException(status_code=404, detail="项目不存在")

    if not memory.daily_operations:
        raise HTTPException(status_code=404, detail="暂无经营数据")
    if not memory.operation_summary(days=days).get("profit_ready", True):
        raise HTTPException(status_code=409, detail="成本未补齐，暂不能计算保本点")

    end = date.today().isoformat()
    start = (date.today() - timedelta(days=days)).isoformat()

    ana = StoreAnalytics()
    ana.load(memory.daily_operations)

    return ana.break_even_analysis(start, end)
