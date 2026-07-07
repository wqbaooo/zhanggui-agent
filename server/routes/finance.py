#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""财务测算路由 — POST /api/finance。

⚠️ 已废弃：此端点为筹备期口径（投资回本测算），与当前单店经营 Agent 口径冲突。
当前产品定位为"AI 单店经营 Agent"（参见 AGENTS.md），不应再使用此端点。
保留路由仅为向后兼容，新功能请使用 /api/analyze 或 /api/reports 端点。
"""

from __future__ import annotations

import logging

from fastapi import APIRouter
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(tags=["finance"])


class FinanceRequest(BaseModel):
    investment: str = Field("10万", description="总投资额")
    daily_revenue: str = Field("1000", description="日均营业额（元）")
    daily_cost_rate: str = Field("0.35", description="食材成本率")
    rent_monthly: str = Field("3000", description="月租金（元）")
    labor_monthly: str = Field("5000", description="月人工（元）")
    other_monthly: str = Field("1000", description="月其他费用（元）")


@router.post("/finance", deprecated=True)
async def finance_endpoint(req: FinanceRequest):
    """财务测算端点 — 返回结构化 JSON。

    ⚠️ 已废弃：筹备期投资回本测算口径，请使用 /api/analyze 或 /api/reports。
    """
    logger.warning("POST /api/finance is deprecated (筹备期口径残留). Use /api/analyze or /api/reports instead.")
    try:
        invest = float(req.investment.replace("万", "")) * 10000 if "万" in req.investment else float(req.investment)
        rev = float(req.daily_revenue)
        cost_r = float(req.daily_cost_rate)
        rent = float(req.rent_monthly)
        labor = float(req.labor_monthly)
        other = float(req.other_monthly)

        daily_cost = rev * cost_r
        daily_gross = rev - daily_cost
        monthly_fixed = rent + labor + other
        monthly_net = (daily_gross * 30) - monthly_fixed
        break_even = monthly_fixed / (1 - cost_r) / 30 if cost_r < 1 else float('inf')
        payback = invest / monthly_net if monthly_net > 0 else float('inf')
        net_margin = monthly_net / (rev * 30) * 100 if rev > 0 else 0

        return {
            "success": True,
            "data": {
                "investment": round(invest),
                "daily_revenue": round(rev, 1),
                "daily_gross_profit": round(daily_gross),
                "monthly_fixed_cost": round(monthly_fixed),
                "monthly_net_profit": round(monthly_net),
                "break_even_daily_revenue": round(break_even),
                "payback_months": round(payback, 1) if payback != float('inf') else None,
                "net_margin_pct": round(net_margin, 1),
                "profitable": monthly_net > 0,
            },
        }
    except Exception as exc:
        return {"success": False, "error": str(exc)}
