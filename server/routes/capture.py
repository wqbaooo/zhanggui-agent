#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""拍照录入路由 — 图片上传 + LLM 字段提取。"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import re
import shutil
import subprocess
import tempfile
import urllib.error
import urllib.request
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from config import DEEPSEEK_API_KEY, PROJECT_DATA_DIR
from core.finance_intake import classify_finance_transaction
from models.finance_ledger import FinanceLedger, money_to_minor
from server.model_routing import local_vision_route, paid_vision_route

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/capture", tags=["capture"])

MAX_IMAGE_BYTES = 5 * 1024 * 1024  # 5MB


class CaptureConfirmRequest(BaseModel):
    file_name: str = ""
    image_url: str = ""
    source_type: str
    capture_kind: str = "document"
    recognized_fields: list[dict[str, Any]] = Field(default_factory=list)
    human_modified_fields: list[str] = Field(default_factory=list)
    write_target: str
    date: str = ""
    structured_artifact: dict[str, Any] = Field(default_factory=dict)


FINANCE_FIELD_ACCOUNTS = {
    "food_cost": "5001",
    "packaging_cost": "5002",
    "platform_fee": "5003",
    "service_fee": "5003",
    "delivery_fee": "5003",
    "marketing_cost": "5004",
    "merchant_discount": "5004",
    "inventory_loss": "5005",
    "labor": "6001",
    "rent_allocated": "6002",
    "utility": "6003",
}


def _confirmed_capture_expenses(req: CaptureConfirmRequest) -> list[tuple[str, int, str]]:
    """Return confirmed expense lines without treating inventory purchases as period cost."""
    source = req.source_type.strip()
    target = req.write_target.strip()
    if any(token in source or token in target for token in ("进货", "采购", "供应商", "库存入库", "应付账款")):
        return []

    expenses: list[tuple[str, int, str]] = []
    explicit_cost_found = False
    for field in req.recognized_fields:
        key = str(field.get("key") or "").strip()
        account = FINANCE_FIELD_ACCOUNTS.get(key)
        if not account:
            continue
        try:
            amount_minor = money_to_minor(field.get("value"))
        except Exception:
            continue
        if amount_minor <= 0:
            continue
        explicit_cost_found = True
        expenses.append((account, amount_minor, key))

    # 水电单经常只识别为“金额”；只有来源明确时才允许自动归类。
    if not explicit_cost_found and any(token in source for token in ("水电", "电费", "水费", "燃气")):
        for field in req.recognized_fields:
            if str(field.get("key") or "").strip() != "amount":
                continue
            try:
                amount_minor = money_to_minor(field.get("value"))
            except Exception:
                continue
            if amount_minor > 0:
                expenses.append(("6003", amount_minor, "amount"))
                break
    return expenses

CAPTURE_SYSTEM_PROMPT = """你是一个经营数据提取助手。用户会上传一张餐饮经营相关的截图或照片（客如云日报、美团后台、进货单、库存照片、水电单等）。

请从图片中提取所有可见的经营数据字段，以 JSON 格式返回。

返回格式：
{
  "source_type": "识别到的来源类型（如：客如云日报/美团后台/进货单/库存照片/水电单/投诉异常截图/未知）",
  "fields": [
    {"key": "date", "label": "日期", "value": "2026-01-15", "confidence": "high"},
    {"key": "revenue", "label": "营收", "value": 1234, "confidence": "high"}
  ]
}

可提取的字段（只返回图片中实际存在的字段）：
- date: 报表日期
- revenue: 营业额/流水/收入（数字）
- orders: 订单数（整数）
- delivery_revenue: 外卖营收/美团实收/闪购实收（数字）
- delivery_orders: 外卖单数/有效订单/平台订单（整数）
- dine_in_revenue: 堂食营收/线下实收（数字）
- dine_in_orders: 堂食单数（整数）
- food_cost: 食材成本/物料成本（数字）
- packaging_cost: 包装费/餐盒费/打包费（数字）
- labor: 人工成本/工资（数字）
- rent_allocated: 房租（数字）
- utility: 水电费（数字）
- platform_fee: 平台扣点/佣金/服务费/抽成（数字）
- marketing_cost: 营销/满减/推广费/推广通/美团券（数字）
- inventory_loss: 损耗/报损（数字）
- amount: 转账、账单或票据金额（数字）
- transaction_direction: 资金方向，只能是 inflow、outflow 或 unknown
- counterparty: 交易对方、收款人或付款人
- transaction_reference: 流水号、订单号或凭证号
- balance: 交易后余额
- bad_reviews: 差评数（整数）
- repeat_orders: 复购订单数（整数）
- new_members: 新增会员数（整数）
- notes: 图片中值得记录的备注文字

特别说明：
- 如果识别到美团/淘宝闪购后台截图，优先提取 delivery_revenue（外卖实收）、platform_fee（佣金）、marketing_cost（推广费）
- 有效订单 = delivery_orders，平台总金额 = delivery_revenue，佣金 = platform_fee
- 满减补贴/推广通/美团券费用 = marketing_cost
- 餐盒/打包耗材 = packaging_cost
- 经营日报中的"退款"是正常业务字段，不是投诉异常；只有当图片明确是差评、投诉、罚款、整改等风险事件时才返回"投诉异常截图"

confidence 标注：
- high: 数字清晰可读，确定正确
- medium: 可分辨但不够清晰，或需结合上下文推断
- low: 模糊猜测，需要人工确认

只返回 JSON 对象，不要额外文字或 markdown 代码块。"""

LOCAL_VISION_PROMPT = """你是新余恒太城五楼大口章鱼烧的多模态经营 Agent。请直接理解这张图片，只返回 JSON。

要求：
- 只返回图片里真实可见的字段，不要猜测，不要使用示例值。
- 先理解这是什么经营证据、对应哪个营业日、能证明什么、不能证明什么。
- 金额必须保留图中口径：营业收入、订单金额、实收、优惠、退款、平台费不得混为同一数。
- 如果日期、合计或口径不确定，在 questions 中给出最少数量、可以直接问老板的问题。
- 先判断 source_type，可选：客如云日报、美团外卖后台、美团团购后台、淘宝闪购后台、京东外卖后台、抖音团购后台、银行转账凭证、
  POS销售小票、进货单、出餐标签、水电单、合同/协议资料、总部/SOP资料、证照资料、库存照片、
  投诉异常截图、未知。
- 单笔 POS 小票、出餐标签和转账凭证不是当日经营汇总，不能把单笔金额写成 revenue。
- document_facts 返回清晰可见的关键事实；表格或商品明细放入 line_items。
- 如果图片包含多个月份的营业额、利润或成本，source_type 返回“历史月度经营表”，fields 留空，
  raw_text 按“年份/月份/指标/金额/置信度”转写可辨认内容，parse_error 返回“需要人工确认月度数据”。
- 如果没有看到经营数据，返回 {"source_type":"未知","fields":[],"raw_text":"","parse_error":"未识别到经营数据"}。
- fields 中只允许这些 key：date, revenue, orders, delivery_revenue, delivery_orders, dine_in_revenue, dine_in_orders, food_cost, packaging_cost, labor, rent_allocated, utility, platform_fee, marketing_cost, inventory_loss, bad_reviews, repeat_orders, new_members, amount, transaction_direction, counterparty, transaction_reference, balance, notes。
- confidence 只能是 high、medium、low。
- 经营日报中的"退款"是正常业务字段，不是投诉异常；只有当图片明确是差评、投诉、罚款、整改等风险事件时才返回"投诉异常截图"。

返回结构：
{
  "source_type": "进货单",
  "fields": [],
  "document_facts": [{"label":"单据日期","value":"2026-06-21","confidence":"medium"}],
  "line_items": [{"name":"商品名","quantity":1,"unit_cost":10,"total":10}],
  "analysis_summary": "这张图能确认的经营事实和口径",
  "questions": ["只在必须确认时提问"],
  "raw_text": "图片中可辨认的原文",
  "parse_error": null
}
"""

FIELD_LABELS = {
    "date": "日期",
    "order_amount": "订单金额",
    "operating_income": "营业收入",
    "revenue": "营收",
    "orders": "订单数",
    "takeout_orders": "外卖订单",
    "delivery_revenue": "外卖营收",
    "delivery_orders": "外卖单",
    "dine_in_revenue": "堂食营收",
    "dine_in_orders": "堂食单",
    "food_cost": "食材成本",
    "packaging_cost": "包装成本",
    "labor": "人工成本",
    "rent_allocated": "房租",
    "utility": "水电费",
    "platform_fee": "平台费",
    "service_fee": "服务费",
    "delivery_fee": "配送支出",
    "merchant_discount": "商户优惠",
    "subsidy": "补贴",
    "marketing_cost": "营销成本",
    "inventory_loss": "损耗",
    "transaction_direction": "资金方向",
    "counterparty": "交易对方",
    "transaction_reference": "流水号/凭证号",
    "balance": "交易后余额",
    "bad_reviews": "差评数",
    "repeat_orders": "复购单",
    "new_members": "新会员",
    "notes": "备注",
    "amount": "金额",
    "cash_amount": "现金",
    "wechat_amount": "微信",
    "alipay_amount": "支付宝",
    "meituan_amount": "美团",
    "taobao_flash_amount": "淘宝闪购",
    "douyin_coupon_amount": "抖音团购券",
    "customer_count": "来客数",
    "avg_ticket": "客单价",
}

FIELD_PATTERNS: list[tuple[str, str]] = [
    ("revenue", r"(?:营收|营业额|流水|收入|实收|销售额|销售收入|总金额|合计)\s*(?:是|为|:|：|¥|￥)?\s*([0-9]+(?:\.[0-9]+)?)"),
    ("orders", r"(?:订单数|订单|总单量|单量|总订单|全部订单)\s*(?:是|为|:|：)?\s*([0-9]+)"),
    ("delivery_revenue", r"(?:外卖营收|外卖收入|外卖实收|美团实收|闪购实收|平台营收|外卖流水)\s*(?:是|为|:|：|¥|￥)?\s*([0-9]+(?:\.[0-9]+)?)"),
    ("delivery_orders", r"(?:外卖订单数|外卖单数|有效订单|平台订单|美团订单|闪购订单)\s*(?:是|为|:|：)?\s*([0-9]+)"),
    ("takeout_orders", r"(?:外卖订单|外卖单|外卖)\s*(?:是|为|:|：)?\s*([0-9]+)"),
    ("dine_in_revenue", r"(?:堂食营收|堂食收入|堂食实收|线下实收)\s*(?:是|为|:|：|¥|￥)?\s*([0-9]+(?:\.[0-9]+)?)"),
    ("dine_in_orders", r"(?:堂食订单|堂食单|线下订单)\s*(?:是|为|:|：)?\s*([0-9]+)"),
    ("food_cost", r"(?:食材成本|物料成本|原料成本|食材|物料|原料)\s*(?:成本|花费|是|为|:|：)?\s*([0-9]+(?:\.[0-9]+)?)"),
    ("packaging_cost", r"(?:包装成本|包装费|餐盒费|打包费|打包成本)\s*(?:是|为|:|：)?\s*([0-9]+(?:\.[0-9]+)?)"),
    ("labor", r"(?:人工成本|人工|工资)\s*(?:成本|花费|是|为|:|：)?\s*([0-9]+(?:\.[0-9]+)?)"),
    ("rent_allocated", r"(?:房租|租金)\s*(?:摊销|成本|是|为|:|：)?\s*([0-9]+(?:\.[0-9]+)?)"),
    ("utility", r"(?:水电费|水电|能耗)\s*(?:是|为|:|：)?\s*([0-9]+(?:\.[0-9]+)?)"),
    ("platform_fee", r"(?:平台费|平台佣金|佣金|服务费|扣点|抽成|平台抽成)\s*(?:是|为|:|：)?\s*([0-9]+(?:\.[0-9]+)?)"),
    ("marketing_cost", r"(?:营销成本|营销|满减|活动|推广|推广费|推广通|美团券|满减补贴)\s*(?:成本|花费|费用|是|为|:|：)?\s*([0-9]+(?:\.[0-9]+)?)"),
    ("inventory_loss", r"(?:库存损耗|损耗|报损)\s*(?:是|为|:|：)?\s*([0-9]+(?:\.[0-9]+)?)"),
    ("bad_reviews", r"(?:差评数|差评|坏评)\s*(?:是|为|:|：)?\s*([0-9]+)"),
]

SHELF_LIFE_ITEMS = [
    {"category": "常用酱料", "name": "原味酱", "storage": "酱瓶", "shelf_life": "瓶内 3 天；开封常温 7 天", "confidence": "high"},
    {"category": "常用酱料", "name": "沙拉酱", "storage": "酱瓶", "shelf_life": "瓶内 3 天；开封常温 7 天", "confidence": "medium"},
    {"category": "常用酱料", "name": "青芥末酱", "storage": "酱瓶", "shelf_life": "瓶内 7 天；开封常温 7 天", "confidence": "medium"},
    {"category": "常用酱料", "name": "美式芥末酱", "storage": "酱瓶", "shelf_life": "瓶内 7 天；开封常温 7 天", "confidence": "medium"},
    {"category": "常用酱料", "name": "藤椒酱", "storage": "酱瓶", "shelf_life": "瓶内 7 天；开封常温 7 天", "confidence": "medium"},
    {"category": "常用酱料", "name": "番茄酱", "storage": "酱瓶", "shelf_life": "瓶内 7 天；开封常温 7 天", "confidence": "medium"},
    {"category": "常用配料", "name": "肉松", "storage": "常温", "shelf_life": "开封后常温 7 天", "confidence": "medium"},
    {"category": "常用配料", "name": "切丝海苔", "storage": "常温", "shelf_life": "开封后常温 7 天", "confidence": "medium"},
    {"category": "常用配料", "name": "木鱼花", "storage": "常温", "shelf_life": "开封后常温 7 天", "confidence": "medium"},
    {"category": "常用配料", "name": "海苔粉", "storage": "罐装", "shelf_life": "罐内 30 天；开封后常温 30 天", "confidence": "medium"},
    {"category": "产品辅料", "name": "咸蛋黄酱", "storage": "冷藏", "shelf_life": "开封后常温 7 天；调制后冷藏 3 天", "confidence": "medium"},
    {"category": "产品辅料", "name": "奶酪酱", "storage": "冷藏", "shelf_life": "开封后冷藏 3 天", "confidence": "medium"},
    {"category": "产品辅料", "name": "芝士碎", "storage": "冷冻/冷藏", "shelf_life": "分装冷冻保存 1 个月；冷藏 7 天", "confidence": "medium"},
    {"category": "产品辅料", "name": "培根丁", "storage": "冷藏", "shelf_life": "冷藏保存 3 天", "confidence": "medium"},
    {"category": "产品辅料", "name": "大虾", "storage": "冷冻/冷藏", "shelf_life": "开封冷冻 1 个月；解冻剥壳后冷藏 3 天", "confidence": "medium"},
    {"category": "调制配料", "name": "面浆", "storage": "冷藏", "shelf_life": "6-9 月 12h；12-2 月 36h；其余时间 24h", "confidence": "medium"},
    {"category": "调制配料", "name": "玉米", "storage": "冷藏", "shelf_life": "拆封未解冻保存 7 天；已解冻冷藏 24h", "confidence": "medium"},
    {"category": "鸡蛋汉堡", "name": "五花肉", "storage": "熟制后", "shelf_life": "炒熟后常温 12h；冷藏 24h；开封后冷藏 7 天", "confidence": "medium"},
    {"category": "鸡蛋汉堡", "name": "鸡蛋", "storage": "常温/冷藏", "shelf_life": "煎熟好鸡蛋常温保存 12h", "confidence": "medium"},
    {"category": "鸡蛋汉堡", "name": "鸡蛋汉堡面浆", "storage": "冷藏", "shelf_life": "6-9 月 12h；12-2 月 36h；其余时间 24h", "confidence": "medium"},
    {"category": "鸡蛋汉堡", "name": "黄瓜丝", "storage": "常温/冷藏", "shelf_life": "常温保存 6h；冷藏保存 12h", "confidence": "medium"},
]

TRAINING_RECIPES = [
    {"flavor": "原味", "key_steps": ["原味酱 13g", "香甜酱 8-10g", "中火加热木鱼花", "表面放切丝海苔"], "confidence": "medium"},
    {"flavor": "肉松", "key_steps": ["原味酱约 13g", "香甜酱 8-10g", "中心放肉松", "表面放切丝海苔"], "confidence": "medium"},
    {"flavor": "芥末", "key_steps": ["原味酱 13g", "芥末酱 8-10g", "中火处理木鱼花", "表面放切丝海苔"], "confidence": "medium"},
    {"flavor": "藤椒蛤蜊", "key_steps": ["藤椒酱 8-10g", "中心放木鱼花", "中火处理", "表面放蛤蜊"], "confidence": "low"},
    {"flavor": "咸蛋黄", "key_steps": ["底部垫木鱼花", "丸子中心放咸蛋黄酱", "上放咸蛋黄粉", "出餐前装袋"], "confidence": "medium"},
    {"flavor": "超级双拼", "key_steps": ["原味酱 10g", "香甜酱 8-10g", "放木鱼花", "另放肉松"], "confidence": "medium"},
    {"flavor": "全家福", "key_steps": ["原味/香甜/藤椒酱组合", "放肉松、章鱼花等配料", "保持台面清洁"], "confidence": "low"},
]

DOCUMENT_HINTS = [
    "协议",
    "合同",
    "转让方",
    "受让方",
    "甲方",
    "乙方",
    "店铺转让",
    "转让费",
    "设施归属",
    "租金及费用结算",
    "大口效期管理",
    "效期管理",
    "开封常温",
    "开封冷藏",
    "出餐岗前培训",
    "注意事项",
    "营业执照",
    "食品经营许可证",
    "健康证",
    "排班",
    "工资",
    "差评",
    "投诉",
    "退款",
    "整改",
    "收据",
    "小票",
    "付款",
    "转账汇款",
    "交易成功",
    "销售订单",
    "取餐号",
    "内用POS",
    "实付金额",
]


def _normalize_result_shape(result: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize model output so frontend contracts remain stable."""
    normalized = dict(result)
    raw_fields = normalized.get("fields")
    if isinstance(raw_fields, dict):
        normalized["fields"] = [
            {
                "key": str(key),
                "label": FIELD_LABELS.get(str(key), "金额" if key == "amount" else str(key)),
                "value": value,
                "confidence": "low",
            }
            for key, value in raw_fields.items()
        ]
    elif isinstance(raw_fields, list):
        normalized["fields"] = [field for field in raw_fields if isinstance(field, dict)]
    else:
        normalized["fields"] = []

    raw_facts = normalized.get("document_facts")
    if isinstance(raw_facts, dict):
        normalized["document_facts"] = [
            {"label": str(label), "value": value, "confidence": "low", "evidence": "视觉模型识别，需人工复核"}
            for label, value in raw_facts.items()
        ]
    elif isinstance(raw_facts, list):
        normalized["document_facts"] = [fact for fact in raw_facts if isinstance(fact, dict)]
    else:
        normalized["document_facts"] = []

    raw_items = normalized.get("line_items")
    normalized["line_items"] = [item for item in raw_items if isinstance(item, dict)] if isinstance(raw_items, list) else []
    return normalized


def _select_vision_provider() -> tuple[str, str, str]:
    """Return api_key, base_url, model for a vision-capable provider."""
    import os

    route = paid_vision_route()
    if route.configured and route.provider == "openai":
        return os.environ["OPENAI_API_KEY"], route.base_url or "https://api.openai.com/v1", route.model
    if route.configured and route.provider == "deepseek":
        return DEEPSEEK_API_KEY, route.base_url or "", route.model

    raise HTTPException(
        status_code=503,
        detail=(
            "图片识别需要配置支持视觉的模型。当前 deepseek-chat 是文本模型，不能识别图片。"
            "请配置 OPENAI_API_KEY（默认使用 gpt-4o-mini），或配置 DEEPSEEK_VISION_MODEL 为支持图片的 VL 模型。"
        ),
    )


def _detect_source_type(text: str) -> str:
    lowered = text.lower()
    compact = re.sub(r"\s+", "", text)

    BUSINESS_KEYWORDS = [
        "营收", "营业额", "流水", "订单数", "订单", "收款", "支付",
        "微信", "支付宝", "现金", "外卖", "堂食", "营业收入",
        "当日", "今日", "日报", "报表", "成交", "销售", "实收",
        "订单金额", "来客人数", "客单价", "营业时长", "销售额",
    ]
    business_count = sum(1 for kw in BUSINESS_KEYWORDS if kw in text)

    RISK_KEYWORDS = ["差评", "投诉", "罚款", "整改", "纠纷"]
    risk_count = sum(1 for kw in RISK_KEYWORDS if kw in text)

    PLATFORM_KEYWORDS = {
        "客如云": "客如云日报",
        "美团团购": "美团团购后台",
        "美团外卖": "美团外卖后台",
        "京东外卖": "京东外卖后台",
        "京东秒送": "京东外卖后台",
        "抖音团购": "抖音团购后台",
        "淘宝闪购": "淘宝闪购后台",
        "闪购": "淘宝闪购后台",
        "美团": "美团外卖后台",
        "京东": "京东外卖后台",
        "抖音": "抖音团购后台",
    }

    if (
        "境内汇款电子回单" in compact
        or (
            "回单编号" in compact
            and any(token in compact for token in ["收款卡号", "付款卡号", "收款金额"])
        )
    ):
        return "银行转账凭证"

    for platform, source_type in PLATFORM_KEYWORDS.items():
        if platform in text or (platform.lower() in lowered):
            if business_count >= 1:
                return source_type
            if risk_count >= 2:
                return "投诉异常截图"
            return source_type

    if "交易成功" in compact and any(token in compact for token in ["卡(账)号", "卡(帐)号", "付款人", "收款人", "交易时间", "转账汇款"]):
        return "银行转账凭证"

    if "销售订单" in compact or ("单据编号" in compact and any(token in compact for token in ["供应链", "商品名称", "规格型号"])):
        return "进货单"

    if "取餐号" in compact or "内用POS" in compact or (
        re.search(r"\bT\d{4,}\b", compact, re.IGNORECASE) and any(token in compact for token in ["1/1", "购物中心", "商品"])
    ):
        if len(compact) > 350 or any(token in compact for token in ["实付金额", "订单号", "扫码团购券", "应付金额", "商户收银终"]):
            return "POS销售小票"
        return "出餐标签"

    if any(token in text for token in ["实付金额", "应付金额"]) and any(token in text for token in ["商品", "订单号", "合计"]):
        return "POS销售小票"

    if "物料盘点表" in compact or ("盘点表" in compact and all(token in compact for token in ["品名", "数量", "总数量"])):
        return "库存盘点表"

    if "大口效期管理" in text or "效期管理" in text or ("开封" in text and ("常温" in text or "冷藏" in text)):
        return "效期管理表"

    if "出餐岗前培训" in text or ("口味" in text and "步骤" in text and "注意事项" in text):
        return "总部/SOP资料"

    if any(token in text for token in ["营业执照", "食品经营许可证", "食品经营许可", "健康证", "许可证"]):
        return "证照资料"

    if "店铺转让协议" in text or ("店铺转让" in text and "协议" in text):
        return "店铺转让协议"

    if any(token in text for token in ["转让协议", "转让合同", "租赁合同", "合同"]):
        return "合同/协议资料"

    if any(token in text for token in ["挂账", "赊账", "应付"]) and any(token in compact for token in ["商品名", "下单数", "实际出货", "销售单价", "小计"]):
        return "菜场挂账小票"

    if business_count >= 3:
        return "客如云日报"

    if risk_count >= 2:
        return "投诉异常截图"

    if any(token in text for token in ["进货", "采购", "供货", "货单"]):
        return "进货单"

    if any(token in text for token in ["库存", "冰柜", "货架"]):
        return "库存照片"

    if any(token in text for token in ["水电", "电费", "水费"]):
        return "水电单"

    if any(token in text for token in ["排班", "班次", "工时", "工资表", "薪资", "提成"]):
        return "排班工资表"

    if any(token in text for token in ["小票", "收据", "发票"]):
        return "票据单据"

    if business_count >= 2:
        return "客如云日报"

    if risk_count == 1 and business_count >= 2:
        return "客如云日报"

    return "本地 OCR"


def _capture_kind(source_type: str, text: str, fields: list[dict[str, Any]]) -> str:
    if source_type == "客如云日报":
        return "operation"
    if source_type in {
        "店铺转让协议", "合同/协议资料", "效期管理表", "总部/SOP资料",
        "证照资料", "进货单", "库存照片", "库存盘点表", "水电单", "排班工资表",
        "投诉异常截图", "票据单据", "银行转账凭证", "POS销售小票", "出餐标签",
        "菜场挂账小票",
    }:
        return "document"
    if any(hint in text for hint in DOCUMENT_HINTS):
        return "document"
    if fields:
        return "operation"
    return "unknown"


def _normalize_ocr_number(value: str) -> str:
    return value.translate(str.maketrans({"O": "0", "o": "0", "I": "1", "l": "1"})).replace("_", "")


def _parse_amount(value: str) -> float:
    normalized = (
        value.replace(",", "")
        .replace("，", "")
        .replace("￥", "")
        .replace("¥", "")
        .replace("元", "")
        .strip()
    )
    return round(float(normalized), 2)


def _find_money_after_labels(text: str, labels: list[str]) -> float | None:
    for label in labels:
        patterns = [
            rf"{re.escape(label)}[^0-9\-￥¥]{{0,24}}[￥¥]?\s*(-?[0-9]+(?:\.[0-9]{{1,2}})?)",
            rf"{re.escape(label)}\s*[：:]\s*[￥¥]?\s*(-?[0-9]+(?:\.[0-9]{{1,2}})?)",
            rf"{re.escape(label)}\s+(-?[0-9]+(?:\.[0-9]{{1,2}})?)\s*[元块]",
            rf"(-?[0-9]+(?:\.[0-9]{{1,2}})?)\s*[元块]\s*{re.escape(label)}",
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                try:
                    return _parse_amount(match.group(1))
                except ValueError:
                    continue
    return None


def _find_int_after_labels(text: str, labels: list[str]) -> int | None:
    for label in labels:
        patterns = [
            rf"{re.escape(label)}[^0-9]{{0,24}}([0-9]+)\s*(?:笔|单|人|个)?",
            rf"{re.escape(label)}\s*[：:]\s*([0-9]+)\s*(?:笔|单|人|个)?",
            rf"([0-9]+)\s*(?:笔|单|人|个)?\s*{re.escape(label)}",
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return int(match.group(1))
    return None


def _field(key: str, value: float | int | str, confidence: str = "medium") -> dict[str, Any]:
    return {"key": key, "label": FIELD_LABELS.get(key, key), "value": value, "confidence": confidence}


def _parse_keruyun_fields_from_text(text: str, existing: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Extract the stable business fields visible in Keruyun daily screenshots."""
    fields = list(existing)
    seen = {str(field.get("key")) for field in fields}

    def add_money(key: str, labels: list[str], confidence: str = "medium") -> None:
        if key in seen:
            return
        value = _find_money_after_labels(text, labels)
        if value is not None:
            fields.append(_field(key, value, confidence))
            seen.add(key)

    def add_int(key: str, labels: list[str], confidence: str = "medium") -> None:
        if key in seen:
            return
        value = _find_int_after_labels(text, labels)
        if value is not None:
            fields.append(_field(key, value, confidence))
            seen.add(key)

    add_money("order_amount", ["订单金额", "订单总金额"])
    add_money("operating_income", ["营业收入", "当日已收到款"])
    add_money("revenue", ["营业收入", "当日已收到款"])
    add_int("orders", ["订单数", "销售 退货", "总订单数"])
    add_int("customer_count", ["来客人数", "今日来客数", "就餐人数"])
    add_money("avg_ticket", ["折后客单价", "今日客单价"])
    add_money("dine_in_revenue", ["店内营业收入", "堂食收入"])
    add_money("delivery_revenue", ["第三方营业收入", "外卖收入"])
    add_int("dine_in_orders", ["店内订单数"])
    add_int("delivery_orders", ["第三方订单数", "外卖订单"])
    add_money("merchant_discount", ["商户优惠"])
    add_money("delivery_fee", ["订单配送支出"])
    add_money("service_fee", ["服务费"])
    add_money("subsidy", ["补贴"])
    add_money("cash_amount", ["现金"])
    add_money("wechat_amount", ["微信"])
    add_money("alipay_amount", ["支付宝"])
    add_money("meituan_amount", ["美团外卖", "美团"])
    add_money("taobao_flash_amount", ["淘宝闪购餐饮", "淘宝闪购"])
    add_money("douyin_coupon_amount", ["抖音团购券"])

    if len(fields) < 2:
        money_matches = re.findall(r"[￥¥]?\s*([0-9]{2,}(?:\.[0-9]{1,2})?)\s*[元块]?", text)
        int_matches = re.findall(r"([0-9]{2,})\s*(?:笔|单|人|个|份)", text)

        if money_matches:
            large_amounts = sorted([float(m) for m in money_matches], reverse=True)
            if "revenue" not in seen and large_amounts:
                fields.append(_field("revenue", large_amounts[0], "medium"))
                seen.add("revenue")
            if "order_amount" not in seen and len(large_amounts) > 1:
                fields.append(_field("order_amount", large_amounts[1], "medium"))
                seen.add("order_amount")

        if int_matches and "orders" not in seen:
            order_counts = sorted([int(m) for m in int_matches], reverse=True)
            if order_counts:
                fields.append(_field("orders", order_counts[0], "medium"))
                seen.add("orders")

    return fields


def _parse_supplier_credit_receipt(text: str, line_items: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], float | None]:
    """Parse local market credit receipts. These create payables, not cash spend."""
    compact = re.sub(r"\s+", "", text)
    facts: list[dict[str, Any]] = [
        {"label": "资料类型", "value": "供应商挂账小票", "confidence": "high", "evidence": "识别到挂账/赊账与商品明细结构。"},
        {"label": "账务口径", "value": "采购入库 + 应付账款；未结账前不减少现金", "confidence": "high", "evidence": "用户说明菜场叫菜通常最后一起结账。"},
    ]
    supplier_match = re.search(r"(?:客户名称|供应商|商户名称)[：:\s]*([^\n\s]{2,20})", text)
    if supplier_match:
        facts.append({"label": "供应商/客户", "value": supplier_match.group(1), "confidence": "medium", "evidence": "OCR 识别"})
    date_match = re.search(r"(20\d{2})[-年/.](\d{1,2})[-月/.](\d{1,2})", text)
    if date_match:
        facts.append({"label": "单据日期", "value": f"{date_match.group(1)}-{int(date_match.group(2)):02d}-{int(date_match.group(3)):02d}", "confidence": "medium", "evidence": "OCR 识别"})

    items = list(line_items)
    row_pattern = re.compile(r"([\u4e00-\u9fff]{1,8})\s+([0-9]+(?:\.[0-9]+)?)\s*(?:个|斤|kg|袋|份)?\s+([0-9]+(?:\.[0-9]+)?)\s+([0-9]+(?:\.[0-9]+)?)")
    for name, qty, price, total in row_pattern.findall(text):
        if not any(item.get("name") == name for item in items):
            items.append({"name": name, "quantity": float(qty), "unit_cost": float(price), "total": float(total)})
    total = _find_money_after_labels(text, ["合计", "总计", "小计"])
    if total is None:
        totals = [float(item.get("total") or 0) for item in items]
        if totals:
            total = round(sum(totals), 2)
    if total is not None:
        facts.append({"label": "挂账金额", "value": total, "confidence": "medium", "evidence": "按小票合计或明细合计"})
    if items:
        facts.append({"label": "采购品项", "value": f"{len(items)} 项", "confidence": "medium", "evidence": "识别到商品明细"})
    return facts, items, total


def _redact_sensitive_text(text: str) -> str:
    """Mask personal identifiers before returning OCR text to the client."""
    redacted = re.sub(
        r"(身份证号?\s*[:：]?\s*)[0-9A-Za-zxX_\-\s]{8,24}",
        r"\1[已隐藏]",
        text,
    )
    redacted = re.sub(r"\b\d{15,18}[0-9Xx]?\b", "[已隐藏]", redacted)
    return redacted


def _parse_document_facts(text: str, source_type: str) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    compact = re.sub(r"\s+", "", text)

    if source_type == "银行转账凭证":
        facts.append({"label": "资料类型", "value": "银行转账凭证", "confidence": "high", "evidence": "识别到转账汇款/交易成功"})
        amount_match = re.search(r"(?:金额|合计)[^0-9]{0,8}([0-9][0-9,，]*\.[0-9]{2})", text)
        if amount_match:
            facts.append({"label": "转账金额", "value": amount_match.group(1).replace("，", ","), "confidence": "medium", "evidence": "OCR 金额需核对原图"})
        if "转让费" in text:
            facts.append({"label": "用途", "value": "转让费", "confidence": "high", "evidence": "识别到附言“转让费”"})

    if source_type in {"POS销售小票", "出餐标签"}:
        facts.append({"label": "资料类型", "value": source_type, "confidence": "high", "evidence": "识别到 POS/取餐号/订单结构"})
        pickup_match = re.search(r"\b(T\d{4,})\b", text, re.IGNORECASE)
        if pickup_match:
            facts.append({"label": "取餐号", "value": pickup_match.group(1).upper(), "confidence": "medium", "evidence": "OCR 识别"})
        paid_match = re.search(r"(?:实付金额|应付金额|合计)[^0-9]{0,8}([0-9]+(?:\.[0-9]{1,2})?)", text)
        if paid_match:
            facts.append({"label": "金额", "value": paid_match.group(1), "confidence": "medium", "evidence": "单笔金额，不计入当日总营收"})

    if source_type == "进货单":
        facts.append({"label": "资料类型", "value": "供应商进货单", "confidence": "high", "evidence": "识别到销售订单/供应链"})
        total_matches = re.findall(r"(?:合计|总计)[^0-9]{0,12}([0-9]+(?:\.[0-9]{1,3})?)", text)
        if total_matches:
            facts.append({"label": "单据总额", "value": total_matches[-1], "confidence": "low", "evidence": "OCR 识别，必须与原图和明细合计核对"})

    if source_type == "菜场挂账小票":
        supplier_facts, _, _ = _parse_supplier_credit_receipt(text, [])
        facts.extend(supplier_facts)

    if source_type == "店铺转让协议" or "店铺转让协议" in text:
        facts.append({
            "label": "资料类型",
            "value": "店铺转让协议",
            "confidence": "high",
            "evidence": "识别到标题“店铺转让协议”。",
        })

    area_match = re.search(r"(?:建筑面积|筑面积|面积为)[^0-9OolIl]{0,8}([0-9OolIl_]{1,4})\s*平方", text)
    if area_match:
        area = _normalize_ocr_number(area_match.group(1))
        if area.isdigit():
            facts.append({
                "label": "建筑面积",
                "value": f"{int(area)} 平方米",
                "confidence": "medium",
                "evidence": "OCR 识别到“建筑面积/面积为 ... 平方米”。",
            })

    date_match = re.search(r"(20[0-9OolIl]{2})\s*年\s*([0-9OolIl]{1,2})\s*月\s*([0-9OolIl]{1,2})\s*日", text)
    if date_match:
        year, month, day = (_normalize_ocr_number(part) for part in date_match.groups())
        if year.isdigit() and month.isdigit() and day.isdigit():
            facts.append({
                "label": "付款/生效日期",
                "value": f"{int(year):04d}-{int(month):02d}-{int(day):02d}",
                "confidence": "low",
                "evidence": "日期来自 OCR，照片中有手写内容，需复核。",
            })

    amount_match = re.search(r"(?:人民币|转让费|共计)[^0-9OolIl]{0,8}([0-9OolIl_,，]{4,})\s*元", text)
    if amount_match:
        amount = _normalize_ocr_number(amount_match.group(1).replace(",", "").replace("，", ""))
        if amount.isdigit():
            facts.append({
                "label": "转让费",
                "value": f"{int(amount):,} 元",
                "confidence": "low",
                "evidence": "金额来自 OCR，手写金额必须人工核对原图。",
            })

    if "租金及费用结算" in text or ("租金" in text and "水电费" in text):
        facts.append({
            "label": "租金及费用",
            "value": "乙方承接租金、水电费等合同约定费用",
            "confidence": "medium",
            "evidence": "识别到“租金及费用结算”“水电费”等条款。",
        })

    if "供应商货款" in text or "员工工资" in text or "不得隐瞒" in text:
        facts.append({
            "label": "转让前债务",
            "value": "甲方需结清租金、水电费、员工工资、供应商货款等债务",
            "confidence": "medium",
            "evidence": "识别到债务结清和不得隐瞒条款。",
        })

    if "营业设备" in text or "设备全部归乙" in compact or "设施归属" in text:
        facts.append({
            "label": "设施归属",
            "value": "转让后现有装修、装饰及营业设备归乙方",
            "confidence": "medium",
            "evidence": "识别到“设施归属”“营业设备全部归乙方”等条款。",
        })

    if source_type == "效期管理表" or "效期管理" in text or ("开封" in text and ("常温" in text or "冷藏" in text)):
        facts.append({
            "label": "资料类型",
            "value": "大口物料效期管理表",
            "confidence": "high" if "效期管理" in text else "medium",
            "evidence": "识别到效期、开封、常温、冷藏等关键词。",
        })
        if "开封常温7天" in text or ("开封" in text and "常温7天" in text):
            facts.append({
                "label": "常温开封规则",
                "value": "多项酱料/配料开封后常温 7 天",
                "confidence": "medium",
                "evidence": "识别到“开封常温7天”。",
            })
        if "冷藏" in text:
            facts.append({
                "label": "冷藏效期规则",
                "value": "部分物料需冷藏保存，效期按表格条目复核后录入",
                "confidence": "medium",
                "evidence": "识别到冷藏保存和效期条款。",
            })

    if source_type == "总部/SOP资料" or "出餐岗前培训" in text:
        facts.append({
            "label": "资料类型",
            "value": "出餐岗前培训 SOP",
            "confidence": "high" if "出餐岗前培训" in text else "medium",
            "evidence": "识别到“出餐岗前培训”或口味/步骤/注意事项结构。",
        })
        if "口味" in text or "原味" in text:
            facts.append({
                "label": "覆盖内容",
                "value": "口味配方、出餐步骤、注意事项",
                "confidence": "medium",
                "evidence": "识别到口味、步骤、注意事项等表格栏目。",
            })

    return facts


def _build_structured_artifact(
    source_type: str,
    facts: list[dict[str, Any]],
    risks: list[dict[str, str]],
    raw_text: str,
    fields: Optional[list[dict[str, Any]]] = None,
    line_items: Optional[list[dict[str, Any]]] = None,
) -> dict[str, Any]:
    fields = fields or []
    line_items = line_items or []
    if source_type == "客如云日报":
        fields = _parse_keruyun_fields_from_text(raw_text, fields)
    if source_type in {"客如云日报", "美团后台", "美团外卖后台", "美团团购后台", "淘宝闪购后台", "京东外卖后台", "抖音后台", "抖音团购后台"} or (
        fields and source_type not in {
            "店铺转让协议", "合同/协议资料", "效期管理表", "总部/SOP资料",
            "证照资料", "进货单", "库存照片", "水电单", "排班工资表",
            "投诉异常截图", "票据单据", "银行转账凭证", "POS销售小票", "出餐标签",
        }
    ):
        return _with_universal_template({
            "type": "operation_record",
            "title": f"{source_type}经营数据草稿",
            "confidence": "high" if source_type == "客如云日报" and len(fields) >= 4 else "medium" if fields else "low",
            "summary": "识别为经营数据截图。客如云订单金额、营业收入、优惠、扣费、支付方式和商品销量必须分口径确认，避免把订单金额误当实收利润。",
            "fields": fields,
            "write_payloads": {
                "business_fact_source": "keruyun_daily_report" if source_type == "客如云日报" else "operation_record",
                "fields": fields,
            },
            "required_manual_fields": [
                {"key": "date", "label": "日期", "reason": "经营数据必须确认归属日期。"},
                {"key": "source_platform", "label": "来源平台", "reason": "同一订单可能同时出现在收银和平台后台，需避免重复入账。"},
                {"key": "revenue_basis", "label": "收入口径", "reason": "订单金额、营业收入、收款金额必须分开。"},
            ],
            "ai_next_actions": [
                "生成待确认经营事实",
                "检查订单金额、营业收入、扣费、现金和平台结算是否缺字段",
                "确认后写入财务经营台、资金对账和商品销量",
            ],
            "risks": risks,
        }, source_type)

    if source_type == "银行转账凭证":
        return _with_universal_template({
            "type": "payment_voucher",
            "title": "转账付款凭证草稿",
            "confidence": "medium" if facts else "low",
            "summary": "识别为银行转账凭证。金额、付款人、收款人和用途需要核对后归入成本与现金流证据。",
            "facts": facts,
            "required_manual_fields": [
                {"key": "date", "label": "交易日期", "reason": "用于归入正确月份。"},
                {"key": "amount", "label": "转账金额", "reason": "财务金额必须按原图确认。"},
                {"key": "cost_type", "label": "费用类型", "reason": "本图应确认是否为转让费。"},
                {"key": "counterparty", "label": "交易对方", "reason": "账户信息仅保存脱敏结果。"},
            ],
            "ai_next_actions": ["归档付款凭证", "关联转让费成本", "进入现金流证据"],
            "risks": risks,
        }, source_type)

    if source_type == "POS销售小票":
        return _with_universal_template({
            "type": "sale_receipt",
            "title": "单笔销售小票草稿",
            "confidence": "medium" if facts or line_items else "low",
            "summary": "识别为单笔销售小票。可作为订单和商品销量证据，但不能直接写成当日总营收。",
            "facts": facts,
            "items": line_items,
            "required_manual_fields": [
                {"key": "date", "label": "交易时间", "reason": "用于订单追踪。"},
                {"key": "amount", "label": "实付金额", "reason": "核对优惠前后金额。"},
                {"key": "product", "label": "商品", "reason": "用于商品销量与菜单分析。"},
            ],
            "ai_next_actions": ["归档交易凭证", "累计商品销量", "与当日 POS 汇总对账"],
            "risks": risks,
        }, source_type)

    if source_type == "出餐标签":
        return _with_universal_template({
            "type": "kitchen_ticket",
            "title": "出餐标签草稿",
            "confidence": "medium" if facts or line_items else "low",
            "summary": "识别为出餐标签。用于核对商品、取餐号和出餐时间，不直接计入当日总营收。",
            "facts": facts,
            "items": line_items,
            "required_manual_fields": [
                {"key": "date", "label": "出餐时间", "reason": "用于履约追踪。"},
                {"key": "product", "label": "商品", "reason": "用于商品销量和新品识别。"},
                {"key": "amount", "label": "金额", "reason": "只能作为单笔订单金额。"},
            ],
            "ai_next_actions": ["归档出餐证据", "关联商品销量", "检查菜单中是否存在该商品"],
            "risks": risks,
        }, source_type)

    if source_type in {"店铺转让协议", "合同/协议资料"}:
        return _with_universal_template({
            "type": "contract_review",
            "title": "店铺转让协议审查草稿",
            "confidence": "medium" if facts else "low",
            "summary": "识别为店铺转让相关协议。已提取可见条款，金额、日期、签章和出租方/商场同意仍需人工复核。",
            "facts": facts,
            "required_manual_fields": [
                {"key": "transfer_fee", "label": "转让费金额", "reason": "手写金额 OCR 不稳定，必须人工核对大小写一致。"},
                {"key": "landlord_or_mall_consent", "label": "出租方/商场同意转让证明", "reason": "当前图片未稳定识别到授权或盖章。"},
                {"key": "debt_clearance_receipts", "label": "债务结清凭证", "reason": "协议要求甲方结清租金、水电、员工工资和供应商货款。"},
                {"key": "equipment_list", "label": "设备清单与照片", "reason": "设施归属条款需要附件支撑。"},
            ],
            "ai_next_actions": [
                "生成转让协议风险清单",
                "提醒补充商场/出租方同意材料",
                "创建设备交接清单",
            ],
            "risks": risks,
        }, source_type)

    if source_type == "菜场挂账小票":
        supplier_facts, supplier_items, payable_total = _parse_supplier_credit_receipt(raw_text, line_items)
        facts = supplier_facts
        return _with_universal_template({
            "type": "supplier_credit_receipt",
            "title": "菜场挂账采购草稿",
            "confidence": "medium",
            "summary": "识别为菜场/供应商挂账小票。它表示采购入库和应付账款增加，未结账前不能写成现金支出。",
            "facts": facts,
            "items": supplier_items,
            "write_payloads": {
                "supplier_credit": {
                    "amount": payable_total,
                    "items": supplier_items,
                    "payment_status": "unpaid",
                    "cash_impact": 0,
                },
            },
            "required_manual_fields": [
                {"key": "date", "label": "采购日期", "reason": "用于归入库存和应付账款。"},
                {"key": "amount", "label": "挂账金额", "reason": "需要核对小票合计。"},
                {"key": "supplier_or_payee", "label": "菜场/供应商", "reason": "用于月底统一结账。"},
                {"key": "payment_status", "label": "是否已结账", "reason": "未结账只记应付，不减少现金。"},
            ],
            "ai_next_actions": [
                "生成供应商应付账款",
                "生成采购入库草稿",
                "等实际结账时再冲减应付并记录现金/银行卡付款",
            ],
            "risks": risks or [{
                "level": "medium",
                "title": "挂账采购不能当现金支出",
                "detail": "菜场票据先进入应付账款；实际付款日再影响现金流。",
            }],
        }, source_type)

    if source_type in {"进货单", "水电单", "票据单据"}:
        # 进货单专项提取
        purchase_date = ""
        purchase_supplier = ""
        purchase_items: list[dict[str, Any]] = [
            item for item in line_items
            if len(re.findall(r"[\u4e00-\u9fff]", str(item.get("name") or ""))) >= 2
            and 0 < float(item.get("quantity") or 0) <= 1000
            and 0 <= float(item.get("unit_cost") or 0) <= 10000
        ]
        if source_type == "进货单":
            date_match = re.search(r"(20\d{2})[年/\-.](\d{1,2})[月/\-.](\d{1,2})", raw_text)
            if date_match:
                purchase_date = f"{date_match.group(1)}-{int(date_match.group(2)):02d}-{int(date_match.group(3)):02d}"
            supplier_match = re.search(r"(?:供应商|from|供货方)[：:\s]*([^\s\d\n]{2,20})", raw_text)
            purchase_supplier = supplier_match.group(1).strip() if supplier_match else "待确认"
            for line in raw_text.split("\n"):
                name_m = re.search(r"^([^\d\s]{2,15})", line)
                qty_m = re.search(r"(\d+(?:\.\d+)?)\s*(?:个|份|袋|箱|瓶|kg|KG|克|g|升|ml)?", line)
                price_m = re.search(r"[¥￥]?\s*(\d+(?:\.\d+)?)\s*(?:元|块)?$", line)
                if name_m and qty_m:
                    candidate = {
                        "name": name_m.group(1).strip(),
                        "quantity": float(qty_m.group(1)),
                        "unit_cost": float(price_m.group(1)) if price_m else 0.0,
                    }
                    if (
                        len(re.findall(r"[\u4e00-\u9fff]", candidate["name"])) >= 2
                        and 0 < candidate["quantity"] <= 1000
                        and 0 <= candidate["unit_cost"] <= 10000
                        and not any(item.get("name") == candidate["name"] for item in purchase_items)
                    ):
                        purchase_items.append(candidate)
            new_facts = [
                {"label": "进货日期", "value": purchase_date, "confidence": "medium", "evidence": "OCR 识别"} if purchase_date else None,
                {"label": "供应商", "value": purchase_supplier, "confidence": "medium", "evidence": "OCR 识别"} if purchase_supplier != "待确认" else None,
                {"label": "进货品项", "value": f"{len(purchase_items)} 项", "confidence": "medium", "evidence": f"识别到 {len(purchase_items)} 个品名"} if purchase_items else None,
            ]
            facts = [f for f in new_facts if f]

        return _with_universal_template({
            "type": "purchase_order" if source_type == "进货单" else "cost_receipt",
            "title": f"{source_type}成本归档草稿",
            "confidence": "medium",
            "summary": "识别为成本或付款凭证。金额、日期、供应商/用途确认后，可写入成本、库存或现金流。",
            "facts": facts,
            "write_payloads": {
                "purchase_order": {
                    "date": purchase_date,
                    "supplier": purchase_supplier,
                    "items": purchase_items,
                },
            } if purchase_items else {},
            "required_manual_fields": [
                {"key": "date", "label": "发生日期", "reason": "用于归入正确日报或月份。"},
                {"key": "amount", "label": "金额", "reason": "票据金额需人工核对。"},
                {"key": "cost_type", "label": "费用类型", "reason": "需要区分食材、耗材、水电、营销、其他成本。"},
                {"key": "supplier_or_payee", "label": "供应商/收款方", "reason": "用于供应商和现金流追踪。"},
            ],
            "ai_next_actions": [
                "生成成本录入草稿",
                "若是进货单，生成库存入库草稿",
                "若是水电单，归入固定/能耗成本",
            ],
            "risks": risks,
        }, source_type)

    if source_type == "证照资料":
        return _with_universal_template({
            "type": "compliance_document",
            "title": "证照合规资料草稿",
            "confidence": "medium",
            "summary": "识别为营业执照、食品经营许可或健康证等合规资料。需提取证号、主体、有效期和到期提醒。",
            "facts": facts,
            "required_manual_fields": [
                {"key": "holder", "label": "证照主体/持有人", "reason": "确认属于本店或员工本人。"},
                {"key": "certificate_no", "label": "证照编号", "reason": "OCR 可能误读，需人工复核。"},
                {"key": "expiry_date", "label": "有效期/到期日", "reason": "用于到期提醒。"},
            ],
            "ai_next_actions": [
                "写入资料箱",
                "生成证照到期提醒",
                "检查是否缺少食品安全必备证照",
            ],
            "risks": risks or [{
                "level": "medium",
                "title": "证照有效期需人工复核",
                "detail": "证照编号和有效期属于高风险字段，不能仅凭 OCR 自动确认。",
            }],
        }, source_type)

    if source_type == "排班工资表":
        # 专项提取：从 OCR 文本中解析工时记录
        attendance_records: list[dict[str, Any]] = []
        for line in raw_text.split("\n"):
            name_m = re.search(r"^([\u4e00-\u9fa5]{2,4})", line.strip())
            date_m = re.search(r"(20\d{2})[/\-.](\d{1,2})[/\-.](\d{1,2})", line)
            hours_m = re.search(r"(?:工时|小时)[：:\s]*(\d+(?:\.\d+)?)", line)
            shift_m = re.search(r"(早班|中班|晚班|休息|加班|夜班|午班|全天|半天)", line)
            if name_m:
                record: dict[str, Any] = {"staff_name": name_m.group(1)}
                if date_m:
                    record["date"] = f"20{date_m.group(1)}-{int(date_m.group(2)):02d}"
                if hours_m:
                    record["hours"] = float(hours_m.group(1))
                if shift_m:
                    record["shift"] = shift_m.group(1)
                if len(record) > 1:
                    attendance_records.append(record)
        new_facts = [
            {"label": "考勤记录", "value": f"{len(attendance_records)} 条", "confidence": "medium", "evidence": f"识别到 {len(attendance_records)} 条工时记录"} if attendance_records else {"label": "考勤记录", "value": "未识别", "confidence": "low", "evidence": "未找到工时记录"},
        ]
        return _with_universal_template({
            "type": "labor_record",
            "title": "排班工资结构化草稿",
            "confidence": "medium",
            "summary": "识别为排班、工时或工资资料。确认人员、班次、工时后可进入工资核算。",
            "facts": new_facts,
            "write_payloads": [
                {"type": "work_records", "records": attendance_records},
            ] if attendance_records else [],
            "required_manual_fields": [
                {"key": "staff_name", "label": "员工", "reason": "员工姓名需与员工档案匹配。"},
                {"key": "work_date", "label": "工作日期", "reason": "用于按月工资核算。"},
                {"key": "hours", "label": "工时", "reason": "工时直接影响工资。"},
            ],
            "ai_next_actions": [
                "生成工时工资草稿",
                "检查缺勤、加班和临时班次",
                "同步到工资核算",
            ],
            "risks": risks,
        }, source_type)

    if source_type == "投诉异常截图":
        return _with_universal_template({
            "type": "incident_report",
            "title": "投诉/异常事件草稿",
            "confidence": "medium",
            "summary": "识别为差评、投诉、退款、罚款或整改类异常。需进入风险事件和 SOP 复盘。",
            "facts": facts,
            "required_manual_fields": [
                {"key": "event_date", "label": "发生日期", "reason": "用于追踪处理时限。"},
                {"key": "channel", "label": "来源渠道", "reason": "区分顾客、平台、商场或监管。"},
                {"key": "owner", "label": "负责人", "reason": "异常必须有人跟进。"},
                {"key": "resolution", "label": "处理结果", "reason": "用于闭环复盘。"},
            ],
            "ai_next_actions": [
                "生成风险事件",
                "关联到差评/退款/食品安全/SOP",
                "生成复盘和整改任务",
            ],
            "risks": risks or [{
                "level": "high",
                "title": "异常事件需闭环",
                "detail": "投诉、退款、罚款、整改如果不闭环，会影响评分、食品安全或商场关系。",
            }],
        }, source_type)

    if source_type in {"库存照片", "库存盘点表"}:
        is_count_sheet = source_type == "库存盘点表"
        return _with_universal_template({
            "type": "inventory_observation",
            "title": "库存盘点复核草稿" if is_count_sheet else "库存现场观察草稿",
            "confidence": "medium" if is_count_sheet else "low",
            "summary": (
                "识别为员工物料盘点表。品名、期初、使用和结余需逐行复核后写入库存。"
                if is_count_sheet
                else "识别为库存或现场照片。照片只能作为观察证据，数量、批次和效期需人工确认。"
            ),
            "facts": facts,
            "required_manual_fields": [
                {"key": "sku_name", "label": "物料/SKU", "reason": "照片中物料名称需人工确认。"},
                {"key": "quantity", "label": "数量", "reason": "图片难以稳定估算真实数量。"},
                {"key": "expiry_or_open_date", "label": "效期/开封日期", "reason": "食品安全字段必须复核。"},
            ],
            "ai_next_actions": [
                "生成库存盘点草稿",
                "检查是否缺货、临期或摆放异常",
                "必要时生成补货或报损任务",
            ],
            "risks": risks or [{
                "level": "medium",
                "title": "库存照片不能直接当账",
                "detail": "照片可作为证据，但库存数量和效期必须人工确认后写入。",
            }],
        }, source_type)

    if source_type == "效期管理表":
        return _with_universal_template({
            "type": "shelf_life_policy",
            "title": "大口物料效期管理结构化草稿",
            "confidence": "medium",
            "summary": "识别为物料效期管理表，可进入库存效期和食品安全检查。具体物料仍需按原图逐项复核。",
            "items": SHELF_LIFE_ITEMS,
            "checklist": [
                "所有开封物料必须贴开封日期。",
                "按常温、冷藏、冷冻分区检查保存方式。",
                "每日打烊检查临期和过期物料。",
                "过期物料禁止继续使用，报损写入经营日报。",
            ],
            "suggested_sop": {
                "category": "检查",
                "title": "物料效期检查 SOP",
                "source": "总部资料",
                "review_cycle_days": 30,
                "steps": [
                    {"order": 1, "title": "核对开封日期", "description": "所有开封酱料和配料贴上开封日期。", "is_critical": True},
                    {"order": 2, "title": "按保存方式检查", "description": "区分常温、冷藏、冷冻保存，超过效期禁止使用。", "is_critical": True},
                    {"order": 3, "title": "每日打烊复核", "description": "打烊前检查临期和过期物料，记录报损。", "is_critical": False},
                ],
            },
            "ai_next_actions": [
                "把高频物料拆成库存批次字段",
                "生成每日打烊效期检查任务",
                "把过期/临期物料接入报损记录",
            ],
            "risks": risks,
        }, source_type)

    if source_type == "总部/SOP资料":
        return _with_universal_template({
            "type": "training_sop",
            "title": "出餐岗前培训结构化草稿",
            "confidence": "medium",
            "summary": "识别为出餐岗位培训表，可进入 SOP 作业库和员工训练。克重和步骤需要店主按原图复核。",
            "recipes": TRAINING_RECIPES,
            "quality_checks": [
                "出餐前核对口味和配料。",
                "酱料克重需按总部表复核。",
                "出餐区保持干净，酱瓶及时补充。",
                "新人按口味逐项考核，通过后再独立出餐。",
            ],
            "suggested_sop": {
                "category": "培训",
                "title": "出餐岗前培训 SOP",
                "source": "总部资料",
                "review_cycle_days": 30,
                "steps": [
                    {"order": 1, "title": "按口味准备配料", "description": "按不同口味核对酱料、木鱼花、海苔等配料。", "is_critical": True},
                    {"order": 2, "title": "按表格步骤出餐", "description": "按培训表顺序完成装盒、撒料和交付。", "is_critical": True},
                    {"order": 3, "title": "复核出餐区卫生", "description": "保持台面、酱瓶和工具清洁，缺料及时补充。", "is_critical": True},
                ],
            },
            "ai_next_actions": [
                "生成新人出餐训练清单",
                "把口味步骤拆成考核项",
                "把差评原因关联到对应 SOP 步骤",
            ],
            "risks": risks,
        }, source_type)

    return _with_universal_template({
        "type": "document",
        "title": "资料识别草稿",
        "confidence": "low",
        "summary": "已读取图片文本，但尚未匹配到专门的业务模板。",
        "facts": facts,
        "risks": risks,
        "ai_next_actions": ["人工确认资料类型", "补充关键字段后再写入业务模块"],
    }, source_type)


def _with_universal_template(artifact: dict[str, Any], source_type: str) -> dict[str, Any]:
    """Attach a stable cross-document envelope for all image recognition results."""
    facts = list(artifact.get("facts") or [])
    risks = list(artifact.get("risks") or [])
    items = list(artifact.get("items") or [])
    recipes = list(artifact.get("recipes") or [])
    manual_fields = list(artifact.get("required_manual_fields") or [])
    checklist = list(artifact.get("checklist") or artifact.get("quality_checks") or [])
    next_actions = list(artifact.get("ai_next_actions") or [])
    suggested_sop = dict(artifact.get("suggested_sop") or {})

    document_class = {
        "operation_record": "经营数据",
        "contract_review": "合同/协议",
        "cost_receipt": "票据/成本",
        "compliance_document": "证照/合规",
        "labor_record": "排班/工资",
        "incident_report": "投诉/异常",
        "inventory_observation": "库存/现场",
        "shelf_life_policy": "库存/食品安全",
        "training_sop": "SOP/员工训练",
        "payment_voucher": "财务/付款",
        "sale_receipt": "销售/订单",
        "purchase_order": "进货/库存",
        "supplier_credit_receipt": "采购/应付",
        "kitchen_ticket": "出餐/订单",
    }.get(str(artifact.get("type")), "通用资料")

    if artifact.get("type") == "operation_record":
        write_targets = ["经营日报", "渠道分析", "利润看板"]
    elif artifact.get("type") == "contract_review":
        write_targets = ["资料箱", "合同风险清单", "待补资料任务"]
    elif artifact.get("type") == "cost_receipt":
        write_targets = ["资料箱", "成本记录", "库存入库", "现金流"]
    elif artifact.get("type") == "compliance_document":
        write_targets = ["资料箱", "证照到期提醒", "合规风险"]
    elif artifact.get("type") == "labor_record":
        write_targets = ["工资核算", "排班记录", "员工档案"]
    elif artifact.get("type") == "incident_report":
        write_targets = ["风险事件", "SOP复盘", "待办任务"]
    elif artifact.get("type") == "inventory_observation":
        write_targets = ["库存盘点", "补货任务", "食品安全检查"]
    elif artifact.get("type") == "shelf_life_policy":
        write_targets = ["资料箱", "SOP作业库", "库存效期检查", "食品安全任务"]
    elif artifact.get("type") == "training_sop":
        write_targets = ["资料箱", "SOP作业库", "员工训练"]
    elif artifact.get("type") == "payment_voucher":
        write_targets = ["资料箱", "成本记录", "现金流"]
    elif artifact.get("type") == "sale_receipt":
        write_targets = ["资料箱", "交易凭证", "商品销量", "POS对账"]
    elif artifact.get("type") == "purchase_order":
        write_targets = ["资料箱", "采购记录", "库存入库", "成本记录"]
    elif artifact.get("type") == "supplier_credit_receipt":
        write_targets = ["资料箱", "采购记录", "库存入库", "应付账款"]
    elif artifact.get("type") == "kitchen_ticket":
        write_targets = ["资料箱", "出餐记录", "商品销量"]
    else:
        write_targets = ["资料箱", "人工确认"]

    universal = {
        "schema_version": "capture_artifact_v1",
        "source_type": source_type,
        "document_class": document_class,
        "review_status": "needs_human_review",
        "write_targets": write_targets,
        "confidence_summary": {
            "overall": artifact.get("confidence", "low"),
            "ocr": "medium",
            "business_mapping": artifact.get("confidence", "low"),
        },
        "canonical_sections": {
            "facts": facts,
            "line_items": items or recipes,
            "checks": checklist,
            "risks": risks,
            "manual_review": manual_fields,
            "ai_next_actions": next_actions,
        },
    }

    if suggested_sop:
        universal["write_payloads"] = {"sop_draft": suggested_sop}
    else:
        universal["write_payloads"] = {}

    return {**universal, **artifact}


def _document_risk_flags(text: str, facts: list[dict[str, Any]]) -> list[dict[str, str]]:
    fact_labels = {str(fact.get("label")) for fact in facts}
    risks: list[dict[str, str]] = []

    if any(fact.get("value") == "大口物料效期管理表" for fact in facts):
        risks.append({
            "level": "medium",
            "title": "效期表需要拆成可执行检查项",
            "detail": "当前只能识别为效期资料。要用于库存预警，需要把关键物料、保存方式和开封后天数拆成结构化 SOP。",
        })
        return risks

    if any(fact.get("value") == "出餐岗前培训 SOP" for fact in facts):
        risks.append({
            "level": "medium",
            "title": "培训表需要转成岗位 SOP",
            "detail": "当前识别为培训资料。要用于员工训练，需要拆出口味、克重、步骤、关键注意事项和复核周期。",
        })
        return risks

    if not any(token in text for token in ["店铺转让协议", "转让方", "受让方", "设施归属", "租金及费用结算"]):
        return risks

    if "转让费" not in fact_labels:
        risks.append({
            "level": "high",
            "title": "转让费未可靠提取",
            "detail": "照片里有手写金额，但 OCR 未稳定读出。写入前必须人工核对金额和大写金额是否一致。",
        })

    if not any(token in text for token in ["房东", "出租方", "商场", "同意转让", "盖章"]):
        risks.append({
            "level": "high",
            "title": "出租方或商场同意证据不足",
            "detail": "当前页未稳定识别到出租方、商场或总部同意转让的签章/授权信息。",
        })

    if "转让前债务" in fact_labels:
        risks.append({
            "level": "medium",
            "title": "转让前债务需要清单化",
            "detail": "条款要求甲方结清租金、水电、工资、供应商货款。需要补充结清清单或收据。",
        })

    if "设施归属" in fact_labels:
        risks.append({
            "level": "medium",
            "title": "设备归属需要附件",
            "detail": "协议写到设备归属，但应补设备清单、数量、状态和照片，避免交接争议。",
        })

    return risks


def _source_type_to_platform(source_type: str) -> str:
    """将来源类型映射为标准渠道标识。"""
    mapping = {
        "美团后台": "meituan_delivery",
        "美团外卖后台": "meituan_delivery",
        "美团团购后台": "meituan_group",
        "淘宝闪购后台": "taobao_flash",
        "京东外卖后台": "jd_delivery",
        "抖音后台": "douyin_group",
        "抖音团购后台": "douyin_group",
        "客如云日报": "keyun",
        "客如云": "keyun",
        "进货单": "supply",
        "库存照片": "supply",
        "库存盘点表": "supply",
        "水电单": "utility",
        "排班工资表": "labor",
    }
    for key, value in mapping.items():
        if key in source_type:
            return value
    return "unknown"


def _enrich_capture_result(result: Dict[str, Any]) -> Dict[str, Any]:
    result = _normalize_result_shape(result)
    llm_source_type = str(result.get("source_type") or "未知")
    fields = list(result.get("fields") or [])
    raw_text = str(result.get("raw_text") or "")

    detected_source_type = _detect_source_type(raw_text) if raw_text else "本地 OCR"

    if llm_source_type not in {"", "未知", "本地 OCR", "Ollama 本地视觉"}:
        if detected_source_type in {"客如云日报", "美团后台", "美团外卖后台", "美团团购后台", "淘宝闪购后台", "京东外卖后台", "抖音后台", "抖音团购后台"}:
            source_type = detected_source_type
        elif llm_source_type in {"客如云日报", "美团后台", "美团外卖后台", "美团团购后台", "淘宝闪购后台", "京东外卖后台", "抖音后台", "抖音团购后台"}:
            source_type = llm_source_type
        elif detected_source_type != "本地 OCR":
            source_type = detected_source_type
        else:
            source_type = llm_source_type
    else:
        source_type = detected_source_type if detected_source_type != "本地 OCR" else llm_source_type

    result["source_type"] = source_type
    kind = _capture_kind(source_type, raw_text, fields)
    inferred_facts = _parse_document_facts(raw_text, source_type) if kind in {"document", "unknown"} else []
    supplied_facts = list(result.get("document_facts") or [])
    facts = supplied_facts + [
        fact for fact in inferred_facts
        if not any(existing.get("label") == fact.get("label") for existing in supplied_facts)
    ]
    risks = _document_risk_flags(raw_text, facts) if kind == "document" else []
    structured_artifact = _build_structured_artifact(
        source_type,
        facts,
        risks,
        raw_text,
        fields,
        list(result.get("line_items") or []),
    )
    if structured_artifact.get("type") == "operation_record" and structured_artifact.get("fields"):
        fields = list(structured_artifact.get("fields") or [])
        result["fields"] = fields

    result["capture_kind"] = kind
    result["document_facts"] = facts
    result["risk_flags"] = risks
    result["structured_artifact"] = structured_artifact
    if source_type == "效期管理表":
        destination = "SOP作业库/库存效期"
    elif source_type == "总部/SOP资料":
        destination = "SOP作业库/员工训练"
    elif source_type == "库存盘点表":
        destination = "库存盘点/补货任务"
    elif kind == "document":
        destination = "采购/应付账款" if source_type == "菜场挂账小票" else "合同/风险档案"
    else:
        destination = "经营日报" if kind == "operation" else "待人工确认"
    result["recommended_destination"] = destination
    result["can_write_operation"] = kind == "operation" and bool(fields)
    if kind == "document":
        result["parse_error"] = None
    return result


def _parse_fields_from_text(text: str) -> list[dict[str, Any]]:
    compact = re.sub(r"[ \t]+", " ", text)
    fields: list[dict[str, Any]] = []
    seen: set[str] = set()

    date_match = re.search(r"(20[0-9]{2})[./年-]\s*([0-9]{1,2})[./月-]\s*([0-9]{1,2})", compact)
    if date_match:
        year, month, day = date_match.groups()
        fields.append({
            "key": "date",
            "label": FIELD_LABELS["date"],
            "value": f"{int(year):04d}-{int(month):02d}-{int(day):02d}",
            "confidence": "medium",
        })
        seen.add("date")

    if _detect_source_type(text) == "银行转账凭证":
        amount_match = re.search(
            r"(?:收款金额|转账金额|交易金额|金额)\s*(?:是|为|:|：|¥|￥)?\s*"
            r"([0-9][0-9,]*\.[0-9]{2})",
            compact,
        )
        if not amount_match:
            # Bank OCR often reads the amount while garbling the small label.
            # Requiring the RMB suffix avoids accepting an arbitrary number.
            amount_match = re.search(
                r"([0-9][0-9,]*\.[0-9]{2})\s*元\s*[（(]?人民币",
                compact,
            )
        if amount_match:
            fields.append({
                "key": "amount",
                "label": FIELD_LABELS["amount"],
                "value": float(amount_match.group(1).replace(",", "")),
                "confidence": "medium",
            })
            seen.add("amount")
        reference_match = re.search(
            r"(?:回单编号|交易流水号|凭证号)\s*(?:是|为|:|：)?\s*"
            r"([A-Z0-9][A-Z0-9-]{8,})",
            compact,
            re.IGNORECASE,
        )
        if reference_match:
            fields.append({
                "key": "transaction_reference",
                "label": FIELD_LABELS["transaction_reference"],
                "value": reference_match.group(1),
                "confidence": "medium",
            })
            seen.add("transaction_reference")
        payee_match = re.search(r"收款户名\s*([^\s]{2,20})", text)
        if payee_match:
            fields.append({
                "key": "counterparty",
                "label": FIELD_LABELS["counterparty"],
                "value": payee_match.group(1),
                "confidence": "medium",
            })
            seen.add("counterparty")
        fields.append({
            "key": "transaction_direction",
            "label": FIELD_LABELS["transaction_direction"],
            "value": "inflow",
            "confidence": "medium",
        })
        seen.add("transaction_direction")

    for key, pattern in FIELD_PATTERNS:
        match = re.search(pattern, compact, re.IGNORECASE)
        if not match or key in seen:
            continue
        raw_value = match.group(1).replace(",", "")
        value: int | float
        if key in {"orders", "takeout_orders", "bad_reviews"}:
            value = int(float(raw_value))
        else:
            value = float(raw_value)
            if value.is_integer():
                value = int(value)
        fields.append({
            "key": key,
            "label": FIELD_LABELS.get(key, key),
            "value": value,
            "confidence": "medium",
        })
        seen.add(key)

    return fields


def _filter_fields_by_evidence(fields: list[dict[str, Any]], evidence_text: str) -> list[dict[str, Any]]:
    if not evidence_text.strip():
        return fields

    normalized_evidence = re.sub(r"[\s,，￥¥元]+", "", evidence_text)
    filtered: list[dict[str, Any]] = []
    for field in fields:
        value = field.get("value")
        if field.get("key") == "notes":
            filtered.append(field)
            continue
        if value is None:
            continue
        normalized_value = re.sub(r"[\s,，￥¥元]+", "", str(value))
        if normalized_value and normalized_value in normalized_evidence:
            filtered.append(field)
    return filtered


def _make_local_ocr_call(contents: bytes, suffix: str) -> Optional[Dict[str, Any]]:
    """Use free local Tesseract OCR and conservative regex extraction."""
    tesseract_cmd = shutil.which("tesseract")
    if not tesseract_cmd and Path("/opt/homebrew/bin/tesseract").exists():
        tesseract_cmd = "/opt/homebrew/bin/tesseract"
    if not tesseract_cmd:
        return None

    candidates: list[tuple[int, str]] = []
    image_paths: list[Path] = []

    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(contents)
            image_paths.append(Path(tmp.name))

        try:
            from io import BytesIO
            from PIL import Image as PILImage, ImageOps

            original = ImageOps.exif_transpose(PILImage.open(BytesIO(contents))).convert("RGB")
            grayscale = ImageOps.autocontrast(original.convert("L"))
            if grayscale.width < 1600:
                scale = min(2.0, 1600 / max(grayscale.width, 1))
                grayscale = grayscale.resize(
                    (int(grayscale.width * scale), int(grayscale.height * scale)),
                    PILImage.Resampling.LANCZOS,
                )
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                grayscale.save(tmp.name)
                image_paths.append(Path(tmp.name))
        except Exception as exc:
            logger.debug("跳过 OCR 增强预处理: %s", exc)

        for image_path in image_paths:
            for page_mode in ("6", "11"):
                try:
                    completed = subprocess.run(
                        [tesseract_cmd, str(image_path), "stdout", "-l", "chi_sim+eng", "--psm", page_mode],
                        check=False,
                        capture_output=True,
                        text=True,
                        timeout=25,
                    )
                except Exception as exc:
                    logger.warning("本地 OCR 失败: %s", exc)
                    continue
                text = completed.stdout.strip()
                if text:
                    candidates.append((_score_ocr_text(text), text))
    finally:
        for image_path in image_paths:
            image_path.unlink(missing_ok=True)

    if not candidates:
        return None

    ranked_candidates = sorted(candidates, key=lambda item: item[0], reverse=True)
    raw_text = "\n\n".join(text for _, text in ranked_candidates[:3])
    if not raw_text:
        return None

    fields = _parse_fields_from_text(raw_text)
    source_type = _detect_source_type(raw_text)
    if source_type in {"POS销售小票", "进货单", "出餐标签"}:
        # These are individual documents, not daily summaries. Never promote a
        # single receipt amount or quantity into daily revenue/orders.
        fields = [
            {**field, "confidence": "low"}
            for field in fields
            if field.get("key") == "date"
        ]
    elif source_type == "银行转账凭证":
        fields = [
            {**field, "confidence": "medium"}
            for field in fields
            if field.get("key") in {"date", "amount", "transaction_reference", "counterparty", "transaction_direction"}
        ]
    return _enrich_capture_result({
        "source_type": source_type,
        "fields": fields,
        "raw_text": raw_text,
        "parse_error": None if fields else "本地 OCR 已读取图片文字，但未匹配到经营字段，请手动确认。",
    })


def _score_ocr_text(text: str) -> int:
    keywords = [
        "店铺转让协议", "转让方", "受让方", "租金及费用", "设施归属",
        "效期管理", "开封", "冷藏", "常温", "保质", "原味酱",
        "出餐岗前培训", "口味", "步骤", "注意事项", "原味", "肉松",
        "转账汇款", "交易成功", "转让费", "销售订单", "供应链",
        "实付金额", "取餐号", "内用POS", "商品名称", "金额", "合计",
    ]
    keyword_score = sum(text.count(keyword) * 20 for keyword in keywords)
    chinese_chars = len(re.findall(r"[\u4e00-\u9fff]", text))
    numeric_groups = len(re.findall(r"\d+(?:[,.]\d+)*", text))
    return keyword_score + chinese_chars + numeric_groups * 3


def _make_ollama_vision_call(image_base64: str) -> Optional[Dict[str, Any]]:
    """Try free local Ollama vision model if one is available."""
    import os

    route = local_vision_route()
    if not route.configured:
        return None
    model = route.model
    base_url = (route.base_url or "http://127.0.0.1:11434").rstrip("/")
    payload = {
        "model": model,
        "prompt": LOCAL_VISION_PROMPT,
        "images": [image_base64],
        "format": "json",
        "stream": False,
        "think": False,
        "keep_alive": "10m",
        "options": {"temperature": 0, "num_predict": 600},
    }
    request = urllib.request.Request(
        f"{base_url}/api/generate",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            body = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        logger.info("Ollama vision unavailable: %s", exc)
        return None

    content = str(body.get("response") or "").strip()
    if not content:
        return None
    parsed = _parse_llm_json(content)
    if parsed is None:
        return _enrich_capture_result({
            "source_type": "Ollama 本地视觉",
            "fields": _parse_fields_from_text(content),
            "raw_text": content,
            "parse_error": "Ollama 本地视觉未返回标准 JSON，已尽量提取文本字段。",
        })
    parsed.setdefault("raw_text", content)
    return _enrich_capture_result(parsed)


def _make_vision_llm_call(image_base64: str, mime_type: str) -> Dict[str, Any]:
    """调用 LLM 视觉能力提取图片中的经营数据。"""
    from openai import OpenAI

    data_url = f"data:{mime_type};base64,{image_base64}"
    api_key, base_url, model = _select_vision_provider()

    client = OpenAI(
        api_key=api_key,
        base_url=base_url,
    )

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": CAPTURE_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "请从这张图片中提取经营数据字段。"},
                        {"type": "image_url", "image_url": {"url": data_url, "detail": "auto"}},
                    ],
                },
            ],
            temperature=0.1,
            max_tokens=1000,
        )
    except Exception as exc:
        error_msg = str(exc).lower()
        if any(kw in error_msg for kw in ["vision", "image", "multimodal", "not support", "invalid"]):
            raise HTTPException(
                status_code=400,
                detail={
                    "code": "model_no_vision",
                    "message": f"当前模型 {model} 不支持图片识别。请使用支持视觉的模型（如 gpt-4o、gpt-4o-mini、deepseek-vl2）。",
                },
            )
        raise HTTPException(status_code=502, detail=f"LLM 调用失败: {exc}")

    content = response.choices[0].message.content or ""
    logger.info("Vision response: %s", content[:500])

    # 尝试解析 JSON 响应
    parsed = _parse_llm_json(content)
    if parsed is None:
        # 返回 raw_text 让前端手动处理
        return _enrich_capture_result({
            "source_type": "未知",
            "fields": [],
            "raw_text": content.strip(),
            "parse_error": "LLM 未返回有效 JSON，请手动录入",
        })
    return _enrich_capture_result(parsed)


def _parse_llm_json(content: str) -> Optional[Dict[str, Any]]:
    """从 LLM 响应中提取 JSON 对象。"""
    text = content.strip()
    # 去掉可能的 markdown 代码块
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # 尝试用正则提取 JSON 对象
        import re
        match = re.search(r'\{[^{}]*"fields"\s*:\s*\[.*?\][^{}]*\}', text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
    return None


@router.post("/recognize")
async def recognize_capture(project_id: str = "xinyu-hengtai-dakou", image: UploadFile = File(...)):
    """上传经营截图，调用 LLM 视觉提取结构化字段。

    返回字段列表，前端可填入 DraftModal 供用户确认后写入。
    """
    if not image.content_type or not image.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="只支持图片文件（image/*）")

    contents = await image.read()
    if len(contents) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=400, detail=f"图片不能超过 {MAX_IMAGE_BYTES // (1024*1024)}MB")

    # 持久化原图，供待确认页对照
    capture_dir = PROJECT_DATA_DIR / project_id / "captures"
    capture_dir.mkdir(parents=True, exist_ok=True)
    file_ext = Path(image.filename or "capture.png").suffix or ".png"
    capture_filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}{file_ext}"
    capture_path = capture_dir / capture_filename
    capture_path.write_bytes(contents)
    image_url = f"/api/capture/captures/{project_id}/{capture_filename}"

    original_suffix = Path(image.filename or "capture.png").suffix or ".png"
    local_result = _make_local_ocr_call(contents, original_suffix)
    local_source_type = str(local_result.get("source_type") or "") if local_result else ""
    fast_document_sources = {
        "银行转账凭证",
        "POS销售小票",
        "进货单",
        "出餐标签",
        "水电单",
        "合同/协议资料",
        "总部/SOP资料",
        "证照资料",
        "库存照片",
    }
    if local_result and local_source_type in fast_document_sources:
        _enrich_capture_result(local_result)
        return {
            "success": True,
            "image_url": image_url,
            "source_type": local_result.get("source_type", "本地 OCR"),
            "source_platform": _source_type_to_platform(local_result.get("source_type", "")),
            "capture_kind": local_result.get("capture_kind", "unknown"),
            "fields": local_result.get("fields", []),
            "document_facts": local_result.get("document_facts", []),
            "risk_flags": local_result.get("risk_flags", []),
            "structured_artifact": local_result.get("structured_artifact", {}),
            "recommended_destination": local_result.get("recommended_destination", "待人工确认"),
            "can_write_operation": local_result.get("can_write_operation", False),
            "raw_text": _redact_sensitive_text(str(local_result.get("raw_text", ""))),
            "parse_error": local_result.get("parse_error"),
        }

    mime_type = image.content_type or "image/png"
    vision_contents = contents
    # 保留票据和表格小字，再交给本地视觉模型。
    try:
        from io import BytesIO
        from PIL import Image as PILImage

        img = PILImage.open(BytesIO(contents)).convert("RGB")
        # 长票据和表格缩到 768 会丢失小字；保留足够分辨率给本地视觉模型。
        if max(img.size) > 2048:
            img.thumbnail((2048, 2048), PILImage.LANCZOS)
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=88)
        vision_contents = buf.getvalue()
        mime_type = "image/jpeg"
    except Exception as exc:
        logger.warning("图片预处理失败，使用原图: %s", exc)
    image_base64 = base64.b64encode(vision_contents).decode("utf-8")

    result = _make_ollama_vision_call(image_base64)
    if result is not None:
        result = _normalize_result_shape(result)
    if result is not None and local_result and local_result.get("raw_text"):
        # OCR is corroborating evidence, not a veto. Complex tables often use
        # spacing or punctuation that differs from the vision model output.
        result["ocr_raw_text"] = local_result.get("raw_text", "")
        result["ocr_fields"] = local_result.get("fields", [])
        local_source = str(local_result.get("source_type") or "")
        model_source = str(result.get("source_type") or "")
        if model_source in {"", "未知", "本地 OCR", "Ollama 本地视觉"} and local_source not in {"", "未知", "本地 OCR"}:
            result["source_type"] = local_source
        if not result.get("raw_text"):
            result["raw_text"] = local_result.get("raw_text", "")
        result = _enrich_capture_result(result)
    if result is None and paid_vision_route().configured:
        try:
            result = _make_vision_llm_call(image_base64, mime_type)
        except HTTPException:
            if local_result and local_result.get("raw_text"):
                result = local_result
            else:
                result = None
    if result is None:
        result = local_result or _enrich_capture_result({
            "source_type": "未知",
            "fields": [],
            "raw_text": "",
            "parse_error": "本地图片识别未产出可靠字段，请选择资料类型并人工确认。",
        })

    return {
        "success": True,
        "image_url": image_url,
        "source_type": result.get("source_type", "未知"),
        "source_platform": _source_type_to_platform(result.get("source_type", "")),
        "capture_kind": result.get("capture_kind", "unknown"),
        "fields": result.get("fields", []),
        "document_facts": result.get("document_facts", []),
        "risk_flags": result.get("risk_flags", []),
        "structured_artifact": result.get("structured_artifact", {}),
        "recommended_destination": result.get("recommended_destination", "待人工确认"),
        "can_write_operation": result.get("can_write_operation", False),
        "raw_text": _redact_sensitive_text(str(result.get("raw_text", ""))),
        "parse_error": result.get("parse_error"),
        "analysis_summary": result.get("analysis_summary", ""),
        "questions": result.get("questions", []),
    }


@router.get("/captures/{project_id}/{filename}")
async def serve_capture(project_id: str, filename: str):
    """提供已持久化的经营截图，供待确认页对照原图。"""
    if "/" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="非法文件名")
    capture_path = PROJECT_DATA_DIR / project_id / "captures" / filename
    if not capture_path.exists():
        raise HTTPException(status_code=404, detail="图片不存在")
    return FileResponse(capture_path)


@router.post("/confirm/{project_id}")
async def confirm_capture(project_id: str, req: CaptureConfirmRequest):
    """Archive a confirmed capture and post reviewed costs through business facts."""
    from models.project import ProjectMemory
    from models.operating_ledger import OperatingLedger

    memory = ProjectMemory.load(project_id) or ProjectMemory.create(project_id)
    operating = OperatingLedger.load(project_id)
    posted_business_facts: list[dict[str, Any]] = []
    pending_business_facts: list[dict[str, Any]] = []
    if req.source_type in {"进货单", "菜场挂账小票", "库存照片", "库存盘点表"}:
        capture_fields = list(req.recognized_fields)
        if req.date and not any(field.get("key") == "date" for field in capture_fields):
            capture_fields.append({"key": "date", "value": req.date})
        imported = operating.ingest_capture_artifact(
            source_type=req.source_type,
            fields=capture_fields,
            structured_artifact=req.structured_artifact,
            file_name=req.file_name,
        )
        for candidate in imported["facts"]:
            if candidate.get("missing_fields"):
                pending_business_facts.append(candidate)
                continue
            result = operating.confirm_fact(candidate["id"])
            posted_business_facts.append(result["fact"])
    expense_lines = _confirmed_capture_expenses(req)
    posted_expenses: list[dict[str, Any]] = []
    if expense_lines:
        field_date = next(
            (str(field.get("value")) for field in req.recognized_fields if field.get("key") == "date"),
            "",
        )
        entry_date = req.date or field_date or datetime.now().date().isoformat()
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", entry_date):
            raise HTTPException(status_code=400, detail="确认入账需要有效日期")
        document_key = hashlib.sha256(
            json.dumps(
                {
                    "project_id": project_id,
                    "file_name": req.file_name,
                    "source_type": req.source_type,
                    "date": entry_date,
                },
                ensure_ascii=False,
                sort_keys=True,
            ).encode()
        ).hexdigest()[:20]
        candidates = operating.ingest_expense_candidates(
            document_key=document_key,
            source_type=req.source_type,
            file_name=req.file_name,
            date=entry_date,
            expenses=[{
                "field": field_key,
                "account": account,
                "amount_minor": amount_minor,
                "title": f"{req.source_type}确认入账：{FIELD_LABELS.get(field_key, field_key)}",
            } for account, amount_minor, field_key in expense_lines],
        )
        for candidate in candidates:
            result = operating.confirm_fact(candidate["id"])
            finance_entries = result.get("finance_entries") or []
            metadata = result["fact"].get("metadata") or {}
            posted_expenses.append({
                "field": metadata.get("source_field"),
                "account": metadata.get("finance_account_code"),
                "amount_minor": money_to_minor(result["fact"].get("amount")),
                "business_fact_id": result["fact"]["id"],
                "journal_entry_id": finance_entries[0] if finance_entries else None,
            })
    voucher_id: str | None = None
    pending_bookkeeping_records: list[str] = []
    capture_filename = req.image_url.rstrip("/").split("/")[-1] if req.image_url else ""
    capture_path = PROJECT_DATA_DIR / project_id / "captures" / capture_filename if capture_filename else None
    if capture_path and capture_path.exists() and capture_path.is_file():
        contents = capture_path.read_bytes()
        digest = hashlib.sha256(contents).hexdigest()
        field_map = {str(field.get("key") or ""): field.get("value") for field in req.recognized_fields}
        business_date = req.date or str(field_map.get("date") or "")
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", business_date):
            business_date = None
        amount_minor = 0
        for key in ("amount", "utility", "food_cost", "packaging_cost", "platform_fee", "marketing_cost"):
            try:
                amount_minor = money_to_minor(field_map.get(key))
            except Exception:
                amount_minor = 0
            if amount_minor > 0:
                break
        ledger = FinanceLedger.for_project(project_id)
        profile = memory.profile or {}
        ledger.ensure_store(
            project_id,
            str(profile.get("store_name") or profile.get("name") or project_id),
            str(profile.get("transfer_date") or business_date or datetime.now().date().isoformat()),
        )
        voucher_id = ledger.register_evidence_voucher(
            project_id,
            voucher_key=f"capture:{digest}",
            business_date=business_date,
            evidence_type=req.source_type or "经营图片",
            channel=req.source_type,
            amount_minor=amount_minor or None,
            original_filename=req.file_name or capture_filename,
            original_path=str(Path("captures") / capture_filename),
            sha256=digest,
            status="confirmed",
            notes=f"图片识别确认；人工修改字段：{','.join(req.human_modified_fields) or '无'}",
        )
        direction = str(field_map.get("transaction_direction") or "").lower()
        financial_tokens = ("转账", "付款凭证", "收款凭证", "支付凭证", "账单", "结算", "支付宝", "微信支付", "银行流水")
        if (
            not posted_expenses
            and amount_minor > 0
            and direction in {"inflow", "outflow"}
            and any(token in req.source_type for token in financial_tokens)
        ):
            counterparty = str(field_map.get("counterparty") or "").strip()
            summary = str(field_map.get("notes") or req.source_type).strip()
            classification = classify_finance_transaction(
                direction=direction,
                counterparty=counterparty,
                summary=summary,
                account_owner_kind="unknown",
            )
            record_id = ledger.create_bookkeeping_record(
                project_id,
                transaction_date=business_date or datetime.now().date().isoformat(),
                direction=direction,
                amount_minor=amount_minor,
                transaction_kind=classification["transaction_kind"],
                business_scope=classification["business_scope"],
                category_code=classification["category_code"],
                category_name=classification["category_name"],
                account_key=None,
                counterparty=counterparty or None,
                summary=summary,
                source_type="image_capture",
                source_reference=f"voucher:{voucher_id}",
                voucher_id=voucher_id,
                confidence=classification["confidence"],
                classification_reason=classification["classification_reason"],
                raw_data={"recognized_fields": req.recognized_fields, "structured_artifact": req.structured_artifact},
                status="needs_review",
            )
            pending_bookkeeping_records.append(record_id)
    memory.add_capture_audit_log({
        "source_type": req.source_type,
        "file_name": req.file_name,
        "capture_kind": req.capture_kind,
        "recognized_fields": req.recognized_fields,
        "human_modified_fields": req.human_modified_fields,
        "review_status": "written",
        "write_target": req.write_target,
        "date": req.date,
        "finance_postings": posted_expenses,
        "voucher_id": voucher_id,
        "pending_bookkeeping_record_ids": pending_bookkeeping_records,
        "business_fact_ids": [item["id"] for item in posted_business_facts + pending_business_facts],
    })
    return {
        "success": True,
        "posted_expenses": posted_expenses,
        "posted_business_facts": posted_business_facts,
        "pending_business_facts": pending_business_facts,
        "voucher_id": voucher_id,
        "pending_bookkeeping_record_ids": pending_bookkeeping_records,
    }
