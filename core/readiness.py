#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Readiness triage for high-risk first-time franchise users."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List


NOVICE_PATTERNS = ("没有开店", "没开过店", "新手", "不会算账", "不会营销", "不懂餐饮")
FRANCHISE_PATTERNS = ("加盟", "品牌")
ASK_SOLVE_PATTERNS = ("能否", "能不能", "是否能", "解决", "帮我")


@dataclass
class ReadinessCase:
    city: str = ""
    brand: str = ""
    category: str = ""
    is_novice: bool = False
    is_franchise: bool = False
    asks_solution_fit: bool = False
    gaps: List[str] = field(default_factory=list)

    @property
    def applies(self) -> bool:
        return self.is_novice and self.is_franchise and self.asks_solution_fit


def detect_readiness_case(text: str) -> ReadinessCase:
    """Detect whether the user needs a first-turn franchise readiness triage."""
    normalized = text or ""
    case = ReadinessCase(
        city=_extract_city(normalized),
        brand=_extract_brand(normalized),
        category=_extract_category(normalized),
        is_novice=any(p in normalized for p in NOVICE_PATTERNS),
        is_franchise=any(p in normalized for p in FRANCHISE_PATTERNS),
        asks_solution_fit=any(p in normalized for p in ASK_SOLVE_PATTERNS),
    )
    case.gaps = _missing_gaps(normalized)
    return case


def build_readiness_overlay(text: str) -> str:
    """Build a deterministic execution guardrail for first-time franchise cases."""
    case = detect_readiness_case(text)
    if not case.applies:
        return ""

    city = case.city or "目标城市"
    brand = case.brand or "该加盟品牌"
    category = case.category or "目标品类"
    gaps = "\n".join(f"- {gap}" for gap in case.gaps)

    return f"""## 项目审查补齐：新手加盟最低闭环

**当前判断**: Needs More Data。这个 Agent 可以帮你把 `{city} / {brand} / {category}` 拆成可执行任务，但现在不能直接给 Go。原因是你同时缺三块能力：算账、营销获客、加盟尽调；这三块没补齐前，不应交大额费用或签不可退合同。

**缺口清单**
{gaps}

**必须先跑的 5 条线**
| 线索 | Agent 应交付什么 | 通过条件 |
|------|------------------|----------|
| 加盟尽调 | 商务部备案、两店一年、直营店/加盟店访谈、合同红线清单 | 查不到备案或总部不让访店，则 No-Go |
| 财务测算 | 总投资、月固定成本、盈亏平衡日营收、保守/中性/乐观三档 | 最差情景能撑 3 个月现金流 |
| 新余选址 | 商圈、竞品、租金、客流、学校/商场/夜市场景匹配 | 至少比较 3 个候选点位 |
| 获客运营 | 不依赖个人主播 IP 的开业方案：团购、试吃、同城短视频、私域复购 | 能列出 14 天开业动作表 |
| 日常经营 | 每日记账、外卖运营、库存损耗、排班、复购和月度复盘 | 每天知道赚没赚钱，每周知道哪里要调 |

**加盟后的生命周期不是一句"会运营"，而是 6 个账本/看板**
1. 开店执行看板：证照、装修、设备、首批料、试营业、开业节点。
2. 每日经营账：营业额、订单数、客单价、毛利、固定成本摊销、现金余额。
3. 外卖运营账：平台扣点、配送费、满减成本、曝光、进店、下单转化、差评处理。
4. 库存损耗账：原料进货、日耗用、报损、临期、总部强制采购价格对比。
5. 营销复盘账：团购核销、同城短视频、试吃转化、私域复购，不默认要求你做主播 IP。
6. 止损预警账：连续 7/14/30 天低于盈亏平衡线时，触发降本、调品、换活动或止损。

**接下来 72 小时只做这些**
1. 先查 `{brand}` 是否有商务部特许经营备案，并让总部提供直营店和加盟店名单。
2. 把总部报价拆成：加盟费、保证金、设备、装修、首批料、管理费、强制采购、租金押金、流动资金。
3. 在新余拍 3 个候选位置，每个位置记录租金、面积、转让费、门口 30 分钟人流、周边同类小吃价格。
4. 把开业后前 30 天按"日账本 + 外卖看板 + 库存损耗 + 营销复盘"建成跟踪表。
5. 先不要承诺做主播 IP。你的营销 MVP 是开业前 14 天低成本获客脚本，而不是先把自己包装成达人。

**下一轮请直接给这 7 个信息**
A. 总预算  B. 加盟费/保证金  C. 总部设备报价  D. 预计店租/面积  E. 候选商圈  F. 堂食/外卖/档口带走模式  G. 总部承诺的回本或月利润话术"""


def build_readiness_structured(text: str) -> Dict[str, Any]:
    """Structured response fields for assistant integrations."""
    case = detect_readiness_case(text)
    if not case.applies:
        return {}

    brand = case.brand or "该加盟品牌"
    city = case.city or "目标城市"
    category = case.category or "目标品类"
    return {
        "decision": "needs_more_data",
        "facts": [
            f"用户计划在{city}开店",
            f"用户自述没有开店经验，且不会算账或营销",
            f"用户计划加盟{brand}",
        ],
        "assumptions": [
            f"{category}属于小吃轻餐饮，仍需要用实际合同、选址和成本数据验证",
        ],
        "risks": [
            {"level": "critical", "message": "加盟备案、两店一年、闭店率和合同红线未核实前，不应付款或签不可退合同。"},
            {"level": "high", "message": "用户财务素养不足，若没有每日记账和盈亏平衡线，现金流容易失控。"},
            {"level": "high", "message": "加盟后若没有外卖、库存、损耗、复购和月度复盘看板，开业后会进入盲飞状态。"},
            {"level": "medium", "message": "不会营销不等于必须做主播IP，应先验证低成本本地获客动作。"},
        ],
        "next_actions": [
            f"查询{brand}商务部特许经营备案，并要求总部提供直营店和加盟店名单。",
            "拆分总部报价和三个月现金流，计算盈亏平衡日营业额。",
            f"在{city}比较至少3个候选点位，记录租金、面积、人流和同类小吃价格。",
            "建立开业后30天经营看板：每日营收、订单、毛利、外卖、库存损耗、营销复盘和止损线。",
            "制定14天开业获客动作表，先避开重投入个人IP路线。",
        ],
        "questions_for_user": [
            "你的总预算是多少？",
            "加盟费、保证金、设备、装修、首批料分别是多少钱？",
            "新余候选商圈或铺位在哪里，租金和面积是多少？",
            "你准备做堂食、外卖，还是档口带走为主？",
            "总部有没有承诺几个月回本或月利润？",
        ],
        "memory_updates": {
            "城市": city,
            "品类": category,
            "品牌": brand,
            "经验": "新手",
            "经营方式": "加盟",
        },
    }


def merge_readiness_overlay(user_input: str, response_text: str) -> str:
    """Append the readiness overlay once when the base response lacks it."""
    overlay = build_readiness_overlay(user_input)
    if not overlay:
        return response_text
    if "项目审查补齐：新手加盟最低闭环" in response_text:
        return response_text
    return (response_text.rstrip() + "\n\n---\n\n" + overlay).strip()


def _extract_city(text: str) -> str:
    labeled = re.search(r"(?:城市|目标城市)[:：]\s*([\u4e00-\u9fa5]{2,6})", text)
    if labeled:
        return labeled.group(1)

    province_city = re.search(r"(?:江西)([\u4e00-\u9fa5]{2,4}?)(?:市)?(?:开店|开一家|做|加盟|，|。|,|\.|\s)", text)
    if province_city:
        return province_city.group(1)

    match = re.search(r"(?:去|在|到)([\u4e00-\u9fa5]{2,4})(?:开店|开一家)", text)
    if not match:
        return ""
    city = match.group(1)
    if city in {"之前", "相关", "目前", "项目", "请帮我"}:
        return ""
    return city


def _extract_brand(text: str) -> str:
    patterns = [
        r"品牌叫([\u4e00-\u9fa5A-Za-z0-9·\-]{2,20})",
        r"加盟的是(?:[^叫，。,.]{0,12}叫)?([\u4e00-\u9fa5A-Za-z0-9·\-]{2,20})",
        r"加盟([\u4e00-\u9fa5A-Za-z0-9·\-]{2,20})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            brand = match.group(1).strip("，。,. 的")
            return brand
    return ""


def _extract_category(text: str) -> str:
    known = ("章鱼烧", "早餐", "冰粉", "奶茶", "咖啡", "烧烤", "小吃", "快餐")
    for item in known:
        if item in text:
            return item
    return ""


def _missing_gaps(text: str) -> List[str]:
    gaps = []
    if not re.search(r"\d+\s*万|\d+\s*元|预算", text):
        gaps.append("预算未知：无法判断总投资、现金流和回本压力。")
    if not any(k in text for k in ("租", "面积", "商圈", "位置", "铺")):
        gaps.append("选址未知：无法判断新余具体客流、竞品和租金合理性。")
    if not any(k in text for k in ("加盟费", "保证金", "设备", "管理费", "原料")):
        gaps.append("加盟成本未知：无法识别隐性收费和强制采购风险。")
    if not any(k in text for k in ("备案", "直营", "闭店", "合同")):
        gaps.append("品牌合规未知：还没验证备案、两店一年、合同红线和闭店率。")
    return gaps or ["关键数据不足：需要预算、合同、选址和品牌合规证据。"]
