#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""财务测算工具 v2.0：修复预算推导、使用行业真实参数。

修复内容：
1. 预算→月租金推导逻辑（原：budget*0.2/12，严重低估）
2. 初始投入计算（原：未关联预算总额）
3. 默认参数调整（日单量/客单价/毛利率使用行业保守值）
4. 增加成本数据库查询（城市级别调整）
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

from tools.base import BaseTool, ToolMeta, ToolResult


# ============ 行业基准数据（保守值） ============

CATEGORY_DEFAULTS = {
    "早餐": {"avg_price": 10, "daily_orders": 60, "gross_margin": 0.52, "staff": 2},
    "粉面": {"avg_price": 15, "daily_orders": 50, "gross_margin": 0.55, "staff": 2},
    "小吃": {"avg_price": 12, "daily_orders": 55, "gross_margin": 0.58, "staff": 1},
    "饮品": {"avg_price": 12, "daily_orders": 80, "gross_margin": 0.65, "staff": 1},
    "快餐": {"avg_price": 20, "daily_orders": 45, "gross_margin": 0.55, "staff": 2},
    "烘焙": {"avg_price": 15, "daily_orders": 40, "gross_margin": 0.60, "staff": 2},
}

CITY_RENT_RATIO = {
    "一线": 0.08,      # 月租金 ≈ 预算的8%
    "新一线": 0.06,
    "二线": 0.05,
    "三线": 0.04,
    "县城": 0.03,
    "乡镇": 0.025,
}

# 城市分级映射
CITY_TIER = {
    "北京": "一线", "上海": "一线", "广州": "一线", "深圳": "一线",
    "杭州": "新一线", "成都": "新一线", "重庆": "新一线", "武汉": "新一线", "南京": "新一线", "苏州": "新一线",
    "西安": "二线", "长沙": "二线", "郑州": "二线", "天津": "二线", "青岛": "二线", "宁波": "二线",
    "厦门": "二线", "福州": "二线", "合肥": "二线", "无锡": "二线",
}


def _get_city_tier(city: str) -> str:
    """判断城市级别。"""
    return CITY_TIER.get(city, "县城")  # 默认县城


@dataclass
class FinancialInputs:
    """财务测算输入参数。"""
    category: str = "早餐"
    monthly_rent: float = 0.0
    area_sqm: float = 0.0
    transfer_fee: float = 0.0
    decoration: float = 0.0
    equipment: float = 0.0
    initial_materials: float = 0.0
    reserve_fund: float = 0.0
    staff_count: int = 1
    monthly_salary_per_person: float = 3500.0
    avg_unit_price: float = 10.0
    daily_orders_estimate: float = 60.0
    gross_margin: float = 0.52
    platform_rate: float = 0.0
    delivery_ratio: float = 0.0
    budget: float = 0.0  # 新增：总预算
    city: str = ""

    @classmethod
    def from_profile(cls, profile: Dict[str, Any]) -> "FinancialInputs":
        """从画像字典构建输入。"""
        inputs = cls()
        inputs.category = profile.get("品类", "早餐")
        inputs.city = profile.get("城市", "")

        # 提取品类默认参数
        defaults = CATEGORY_DEFAULTS.get(inputs.category, CATEGORY_DEFAULTS["早餐"])
        inputs.avg_unit_price = defaults["avg_price"]
        inputs.daily_orders_estimate = defaults["daily_orders"]
        inputs.gross_margin = defaults["gross_margin"]
        inputs.staff_count = defaults["staff"]

        # 提取预算
        if "预算" in profile:
            inputs.budget = _parse_number(profile["预算"])

        # 提取月租金（如果用户提供了）
        if "月租金" in profile:
            inputs.monthly_rent = _parse_number(profile["月租金"])

        # 提取面积
        if "面积" in profile or "店铺面积" in profile:
            inputs.area_sqm = _parse_number(profile.get("面积") or profile.get("店铺面积", 0))

        # 提取日单量/客单价（如果用户提供了）
        if "日单量" in profile:
            inputs.daily_orders_estimate = _parse_number(profile["日单量"])
        if "客单价" in profile:
            inputs.avg_unit_price = _parse_number(profile["客单价"])

        # 城市级别调整薪资
        tier = _get_city_tier(inputs.city)
        if tier == "一线":
            inputs.monthly_salary_per_person = 4500
        elif tier == "新一线":
            inputs.monthly_salary_per_person = 4000
        elif tier == "二线":
            inputs.monthly_salary_per_person = 3500
        else:
            inputs.monthly_salary_per_person = 3000

        # ===== 关键修复：预算→月租金推导 =====
        if inputs.monthly_rent == 0 and inputs.budget > 0:
            # 根据城市级别，月租金 = 预算的对应比例
            rent_ratio = CITY_RENT_RATIO.get(tier, 0.03)
            inputs.monthly_rent = inputs.budget * rent_ratio
            # 但月租金不能超过预算的合理范围
            # 假设：月租金 + 3个月押金 = 预算的 15%
            # 所以月租金 ≈ 预算的 3.75%（押一付二）
            # 但我们已经按城市级别设定了比例

        return inputs

    def get_initial_investment(self) -> float:
        """计算初始投入。
        
        如果用户给了细项，用细项；
        如果没给细项，用预算分配。
        """
        # 用户提供的细项
        detail_sum = (
            self.transfer_fee
            + self.decoration
            + self.equipment
            + self.initial_materials
            + self.reserve_fund
        )

        if detail_sum > 0:
            # 用户给了细项，加上押金
            return detail_sum + self.monthly_rent * 3  # 押一付二

        # 用户没给细项，基于预算分配
        if self.budget > 0:
            # 预算分配比例（保守估计）
            # 转让费：预算的10%（如果有）
            # 装修：预算的20%
            # 设备：预算的15%
            # 首批物料：预算的5%
            # 备用金：预算的25%
            # 押金：3个月租金
            self.transfer_fee = self.budget * 0.10
            self.decoration = self.budget * 0.20
            self.equipment = self.budget * 0.15
            self.initial_materials = self.budget * 0.05
            self.reserve_fund = self.budget * 0.25
            
            return (
                self.transfer_fee
                + self.decoration
                + self.equipment
                + self.initial_materials
                + self.reserve_fund
                + self.monthly_rent * 3
            )

        # 既没有预算也没有细项
        return self.monthly_rent * 12 if self.monthly_rent > 0 else 0


class FinanceTool(BaseTool):
    """财务测算工具 v2.0。"""

    meta = ToolMeta(
        name="finance_calculator",
        description="计算盈亏平衡、回本周期、月现金流、敏感性分析（使用行业保守参数）",
        applicable_intents=["财务测算", "开店规划"],
        required_profile_fields=["品类"],
        optional_profile_fields=["城市", "预算", "月租金", "店铺面积", "日单量", "客单价"],
        priority=80,
    )

    def execute(self, params: Dict[str, Any]) -> ToolResult:
        if "profile" in params:
            inputs = FinancialInputs.from_profile(params["profile"])
        else:
            inputs = FinancialInputs(
                category=params.get("category", "早餐"),
                city=params.get("city", ""),
                budget=params.get("budget", 0),
                monthly_rent=params.get("monthly_rent", 0),
                area_sqm=params.get("area_sqm", 0),
                avg_unit_price=params.get("avg_unit_price", 0),
                daily_orders_estimate=params.get("daily_orders_estimate", 0),
                gross_margin=params.get("gross_margin", 0.52),
                staff_count=params.get("staff_count", 1),
                monthly_salary_per_person=params.get("monthly_salary_per_person", 3500),
            )

        result = self._calculate(inputs)
        return ToolResult(success=True, data=result)

    def _calculate(self, inputs: FinancialInputs) -> Dict[str, Any]:
        """核心计算逻辑 v2.0。"""
        # 初始投入
        initial_investment = inputs.get_initial_investment()

        # 月固定成本
        monthly_labor = inputs.staff_count * inputs.monthly_salary_per_person
        
        # 水电杂费：县城20元/平，城市30元/平
        utilities_rate = 30 if _get_city_tier(inputs.city) in ["一线", "新一线", "二线"] else 20
        monthly_utilities = inputs.area_sqm * utilities_rate if inputs.area_sqm > 0 else utilities_rate * 30
        
        # 其他杂费（维修、消耗品等）
        monthly_misc = 500  # 固定杂费
        
        monthly_fixed = inputs.monthly_rent + monthly_labor + monthly_utilities + monthly_misc

        # 三档测算
        scenarios = {}
        for scenario_name, order_multiplier in [("保守", 0.6), ("基准", 0.85), ("乐观", 1.1)]:
            daily_orders = inputs.daily_orders_estimate * order_multiplier
            monthly_revenue = daily_orders * inputs.avg_unit_price * 30
            monthly_gross_profit = monthly_revenue * inputs.gross_margin
            platform_cost = monthly_revenue * inputs.platform_rate * inputs.delivery_ratio
            monthly_net = monthly_gross_profit - monthly_fixed - platform_cost

            # 盈亏平衡日单量
            breakeven_daily_orders = 0.0
            if inputs.avg_unit_price * inputs.gross_margin > 0:
                breakeven_daily_orders = monthly_fixed / (inputs.avg_unit_price * inputs.gross_margin)

            # 回本周期
            payback_months = 0.0
            if monthly_net > 0 and initial_investment > 0:
                payback_months = initial_investment / monthly_net

            scenarios[scenario_name] = {
                "日单量": round(daily_orders, 0),
                "月营业额": round(monthly_revenue, 0),
                "月毛利": round(monthly_gross_profit, 0),
                "月净利": round(monthly_net, 0),
                "盈亏平衡日单量": round(breakeven_daily_orders, 0),
                "回本周期_月": round(payback_months, 1) if payback_months > 0 and payback_months < 120 else "无法回本或超10年",
            }

        # 敏感性分析
        sensitivity = self._sensitivity(inputs, monthly_fixed)

        # 租金营收比
        base_revenue = inputs.daily_orders_estimate * inputs.avg_unit_price * 30
        rent_revenue_ratio = inputs.monthly_rent / base_revenue if base_revenue > 0 else 0

        # 判断租金是否合理
        rent_assessment = ""
        if rent_revenue_ratio > 0.25:
            rent_assessment = "租金过高（>25%营收），建议寻找更低价铺位或提高客单价"
        elif rent_revenue_ratio > 0.20:
            rent_assessment = "租金偏高（20-25%营收），需要确保高周转"
        elif rent_revenue_ratio > 0.15:
            rent_assessment = "租金合理（15-20%营收）"
        else:
            rent_assessment = "租金较低（<15%营收），有成本优势"

        return {
            "初始投入": round(initial_investment, 0),
            "投入明细": {
                "转让费": round(inputs.transfer_fee, 0),
                "装修": round(inputs.decoration, 0),
                "设备": round(inputs.equipment, 0),
                "首批物料": round(inputs.initial_materials, 0),
                "备用金": round(inputs.reserve_fund, 0),
                "押金": round(inputs.monthly_rent * 3, 0),
            },
            "月固定成本": round(monthly_fixed, 0),
            "月固定成本明细": {
                "租金": round(inputs.monthly_rent, 0),
                "人力": round(monthly_labor, 0),
                "水电杂费": round(monthly_utilities, 0),
                "其他": monthly_misc,
            },
            "三档测算": scenarios,
            "租金营收比": round(rent_revenue_ratio, 3),
            "租金评估": rent_assessment,
            "敏感性分析": sensitivity,
            "止损建议": self._stop_loss_advice(scenarios),
            "假设说明": [
                f"品类: {inputs.category}, 城市级别: {_get_city_tier(inputs.city)}",
                f"保守情景为基准（日单量{inputs.daily_orders_estimate}的60%）",
                f"毛利率{inputs.gross_margin:.0%}为行业保守值",
                f"人力成本: {inputs.staff_count}人 × {inputs.monthly_salary_per_person:.0f}元/月",
                "未计入平台满减补贴、食材损耗、季节性波动",
                "实际回本周期通常比测算长20-30%",
            ],
        }

    def _sensitivity(self, inputs: FinancialInputs, monthly_fixed: float) -> Dict[str, Any]:
        """敏感性分析。"""
        base_daily_revenue = inputs.daily_orders_estimate * inputs.avg_unit_price
        base_monthly_net = base_daily_revenue * 30 * inputs.gross_margin - monthly_fixed

        results = {}
        # 日单量敏感性
        for delta_pct in [-30, -15, 15, 30]:
            new_orders = inputs.daily_orders_estimate * (1 + delta_pct / 100)
            new_net = new_orders * inputs.avg_unit_price * 30 * inputs.gross_margin - monthly_fixed
            results[f"日单量{delta_pct:+d}%"] = round(new_net - base_monthly_net, 0)

        # 客单价敏感性
        for delta_pct in [-15, 15, 30]:
            new_price = inputs.avg_unit_price * (1 + delta_pct / 100)
            new_net = inputs.daily_orders_estimate * new_price * 30 * inputs.gross_margin - monthly_fixed
            results[f"客单价{delta_pct:+d}%"] = round(new_net - base_monthly_net, 0)

        # 租金敏感性
        for delta_pct in [-20, 20, 50]:
            new_rent = inputs.monthly_rent * (1 + delta_pct / 100)
            delta_cost = new_rent - inputs.monthly_rent
            results[f"租金{delta_pct:+d}%"] = round(-delta_cost, 0)

        return results

    def _stop_loss_advice(self, scenarios: Dict[str, Any]) -> str:
        """止损建议。"""
        conservative = scenarios.get("保守", {})
        monthly_net = conservative.get("月净利", 0)
        
        if isinstance(monthly_net, str):
            return "保守情景下无法盈利，强烈建议重新评估项目可行性或降低成本结构。"
        
        if monthly_net <= 0:
            return "保守情景下无法盈利，建议：1)寻找更低租金铺位 2)提高客单价 3)减少人力成本"
        elif monthly_net < 2000:
            return "保守情景下月净利不足2000元，抗风险能力极弱。建议设定2个月观察期，若连续低于盈亏平衡则止损。"
        elif monthly_net < 5000:
            return "保守情景下月净利不足5000元，抗风险能力弱。建议设定3个月观察期，做好成本控制。"
        else:
            return "建议设定止损线：连续3个月日单量低于盈亏平衡点的80%时启动调整。"


def _parse_number(value: Any) -> float:
    """从各种格式中提取数字。"""
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, str):
        return 0.0
    import re
    match = re.search(r"(\d+(?:\.\d+)?)", value.replace(",", ""))
    if not match:
        return 0.0
    num = float(match.group(1))
    if "万" in value or "w" in value.lower():
        num *= 10000
    return num
