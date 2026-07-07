#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""分析路由 — 首页智能解读。"""

from __future__ import annotations

import logging
import os
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL
from models.project import ProjectMemory

logger = logging.getLogger(__name__)

router = APIRouter(tags=["analyze"])


class TodayInsightResponse(BaseModel):
    insight: str
    health_status: str  # "good" | "watch" | "risk"
    key_concern: str | None


def _build_analysis_prompt(summary: dict, today_entry: dict | None, prev_summary: dict | None) -> str:
    """构建 LLM 分析提示词。"""

    # 基础统计
    revenue = summary.get("total_revenue", 0)
    net_profit = summary.get("net_profit", 0)
    profit_ready = summary.get("profit_ready", True)
    orders = summary.get("total_orders", 0)
    prime_cost_rate = summary.get("prime_cost_rate", 0)
    food_cost_rate = summary.get("food_cost_rate", 0)
    delivery_rate = summary.get("delivery_rate", 0)
    avg_order = summary.get("avg_order_value", 0)
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
    prompt = f"""你是新余恒太城五楼大口章鱼烧的单店经营 Agent。请根据以下数据，用2-3句话给老板一个简洁、可执行的经营判断。

【已确认的{entry_count}天数据】
- 营收：¥{revenue:,.0f}（环比{revenue_change:+.0f}%）
{profit_line}
- 订单：{orders} 单
- 客单价：¥{avg_order:.0f}
- 食材成本率：{food_cost_rate*100:.0f}%
- 人工+食材成本率：{prime_cost_rate*100:.0f}%
- 外卖营收占比：{delivery_rate*100:.0f}%
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
        net_profit = summary.get("net_profit", 0)
        prime_cost_rate = summary.get("prime_cost_rate", 0)

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
        elif summary.get("delivery_rate", 0) > 0.6:
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
        net_profit = summary.get("net_profit", 0)
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
