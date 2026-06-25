#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""拍照录入路由 — 图片上传 + LLM 字段提取。"""

from __future__ import annotations

import base64
import json
import logging
import re
import shutil
import subprocess
import tempfile
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, File, HTTPException, UploadFile

from config import DEEPSEEK_API_KEY
from server.model_routing import local_vision_route, paid_vision_route

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/capture", tags=["capture"])

MAX_IMAGE_BYTES = 5 * 1024 * 1024  # 5MB

CAPTURE_SYSTEM_PROMPT = """你是一个经营数据提取助手。用户会上传一张餐饮经营相关的截图或照片（客如云日报、美团后台、进货单、库存照片、水电单等）。

请从图片中提取所有可见的经营数据字段，以 JSON 格式返回。

返回格式：
{
  "source_type": "识别到的来源类型（如：客如云日报/美团后台/进货单/库存照片/水电单/未知）",
  "fields": [
    {"key": "date", "label": "日期", "value": "2026-01-15", "confidence": "high"},
    {"key": "revenue", "label": "营收", "value": 1234, "confidence": "high"}
  ]
}

可提取的字段（只返回图片中实际存在的字段）：
- date: 报表日期
- revenue: 营业额/流水/收入（数字）
- orders: 订单数（整数）
- takeout_orders: 外卖订单数（整数）
- food_cost: 食材成本/物料成本（数字）
- labor: 人工成本/工资（数字）
- rent_allocated: 房租（数字）
- utility: 水电费（数字）
- platform_fee: 平台扣点/佣金/服务费（数字）
- marketing_cost: 营销/满减/活动成本（数字）
- inventory_loss: 损耗/报损（数字）
- bad_reviews: 差评数（整数）
- notes: 图片中值得记录的备注文字

confidence 标注：
- high: 数字清晰可读，确定正确
- medium: 可分辨但不够清晰，或需结合上下文推断
- low: 模糊猜测，需要人工确认

只返回 JSON 对象，不要额外文字或 markdown 代码块。"""

LOCAL_VISION_PROMPT = """请识别这张餐饮经营截图或照片中的经营数据，只返回 JSON。

要求：
- 只返回图片里真实可见的字段，不要猜测，不要使用示例值。
- 如果没有看到经营数据，返回 {"source_type":"未知","fields":[],"raw_text":"","parse_error":"未识别到经营数据"}。
- fields 中只允许这些 key：date, revenue, orders, takeout_orders, food_cost, labor, rent_allocated, utility, platform_fee, marketing_cost, inventory_loss, bad_reviews, notes。
- confidence 只能是 high、medium、low。
"""

FIELD_LABELS = {
    "date": "日期",
    "revenue": "营收",
    "orders": "订单数",
    "takeout_orders": "外卖订单",
    "food_cost": "食材成本",
    "labor": "人工成本",
    "rent_allocated": "房租",
    "utility": "水电费",
    "platform_fee": "平台费",
    "marketing_cost": "营销成本",
    "inventory_loss": "损耗",
    "bad_reviews": "差评数",
    "notes": "备注",
}

FIELD_PATTERNS: list[tuple[str, str]] = [
    ("revenue", r"(?:营收|营业额|流水|收入|实收|销售额|销售收入)\s*(?:是|为|:|：|¥|￥)?\s*([0-9]+(?:\.[0-9]+)?)"),
    ("orders", r"(?:订单数|订单|总单量|单量)\s*(?:是|为|:|：)?\s*([0-9]+)"),
    ("takeout_orders", r"(?:外卖订单|外卖单|外卖)\s*(?:是|为|:|：)?\s*([0-9]+)"),
    ("food_cost", r"(?:食材成本|物料成本|原料成本|食材|物料|原料)\s*(?:成本|花费|是|为|:|：)?\s*([0-9]+(?:\.[0-9]+)?)"),
    ("labor", r"(?:人工成本|人工|工资)\s*(?:成本|花费|是|为|:|：)?\s*([0-9]+(?:\.[0-9]+)?)"),
    ("rent_allocated", r"(?:房租|租金)\s*(?:摊销|成本|是|为|:|：)?\s*([0-9]+(?:\.[0-9]+)?)"),
    ("utility", r"(?:水电费|水电|能耗)\s*(?:是|为|:|：)?\s*([0-9]+(?:\.[0-9]+)?)"),
    ("platform_fee", r"(?:平台费|平台佣金|佣金|服务费|扣点)\s*(?:是|为|:|：)?\s*([0-9]+(?:\.[0-9]+)?)"),
    ("marketing_cost", r"(?:营销成本|营销|满减|活动|推广)\s*(?:成本|花费|是|为|:|：)?\s*([0-9]+(?:\.[0-9]+)?)"),
    ("inventory_loss", r"(?:库存损耗|损耗|报损)\s*(?:是|为|:|：)?\s*([0-9]+(?:\.[0-9]+)?)"),
    ("bad_reviews", r"(?:差评数|差评|坏评)\s*(?:是|为|:|：)?\s*([0-9]+)"),
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
]


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
    if "店铺转让协议" in text or ("店铺转让" in text and "协议" in text):
        return "店铺转让协议"
    if any(token in text for token in ["转让协议", "转让合同", "租赁合同", "合同"]):
        return "合同/协议资料"
    if any(token in text for token in ["客如云", "客如雲"]) or "keruyun" in lowered:
        return "客如云日报"
    if "美团" in text or "meituan" in lowered:
        return "美团后台"
    if "抖音" in text or "douyin" in lowered:
        return "抖音后台"
    if "淘宝闪购" in text or "闪购" in text:
        return "淘宝闪购后台"
    if any(token in text for token in ["进货", "采购", "供货", "货单"]):
        return "进货单"
    if any(token in text for token in ["库存", "冰柜", "货架"]):
        return "库存照片"
    if any(token in text for token in ["水电", "电费", "水费"]):
        return "水电单"
    return "本地 OCR"


def _capture_kind(source_type: str, text: str, fields: list[dict[str, Any]]) -> str:
    if source_type in {"店铺转让协议", "合同/协议资料"}:
        return "document"
    if any(hint in text for hint in DOCUMENT_HINTS):
        return "document"
    if fields:
        return "operation"
    return "unknown"


def _normalize_ocr_number(value: str) -> str:
    return value.translate(str.maketrans({"O": "0", "o": "0", "I": "1", "l": "1"})).replace("_", "")


def _parse_document_facts(text: str, source_type: str) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    compact = re.sub(r"\s+", "", text)

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

    return facts


def _document_risk_flags(text: str, facts: list[dict[str, Any]]) -> list[dict[str, str]]:
    fact_labels = {str(fact.get("label")) for fact in facts}
    risks: list[dict[str, str]] = []

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


def _enrich_capture_result(result: Dict[str, Any]) -> Dict[str, Any]:
    source_type = str(result.get("source_type") or "未知")
    fields = list(result.get("fields") or [])
    raw_text = str(result.get("raw_text") or "")
    kind = _capture_kind(source_type, raw_text, fields)
    facts = _parse_document_facts(raw_text, source_type) if kind == "document" else []
    risks = _document_risk_flags(raw_text, facts) if kind == "document" else []

    result["capture_kind"] = kind
    result["document_facts"] = facts
    result["risk_flags"] = risks
    result["recommended_destination"] = "合同/风险档案" if kind == "document" else ("经营日报" if kind == "operation" else "待人工确认")
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
    if not shutil.which("tesseract"):
        return None

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(contents)
        image_path = Path(tmp.name)

    try:
        completed = subprocess.run(
            ["tesseract", str(image_path), "stdout", "-l", "chi_sim+eng", "--psm", "6"],
            check=False,
            capture_output=True,
            text=True,
            timeout=20,
        )
    except Exception as exc:
        logger.warning("本地 OCR 失败: %s", exc)
        return None
    finally:
        image_path.unlink(missing_ok=True)

    raw_text = completed.stdout.strip()
    if not raw_text:
        return None

    fields = _parse_fields_from_text(raw_text)
    return _enrich_capture_result({
        "source_type": _detect_source_type(raw_text),
        "fields": fields,
        "raw_text": raw_text,
        "parse_error": None if fields else "本地 OCR 已读取图片文字，但未匹配到经营字段，请手动确认。",
    })


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
        "options": {"temperature": 0},
    }
    request = urllib.request.Request(
        f"{base_url}/api/generate",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=35) as response:
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
async def recognize_capture(image: UploadFile = File(...)):
    """上传经营截图，调用 LLM 视觉提取结构化字段。

    返回字段列表，前端可填入 DraftModal 供用户确认后写入。
    """
    if not image.content_type or not image.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="只支持图片文件（image/*）")

    contents = await image.read()
    if len(contents) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=400, detail=f"图片不能超过 {MAX_IMAGE_BYTES // (1024*1024)}MB")

    original_suffix = Path(image.filename or "capture.png").suffix or ".png"
    local_result = _make_local_ocr_call(contents, original_suffix)
    if local_result and local_result.get("fields"):
        return {
            "success": True,
            "source_type": local_result.get("source_type", "本地 OCR"),
            "capture_kind": local_result.get("capture_kind", "unknown"),
            "fields": local_result.get("fields", []),
            "document_facts": local_result.get("document_facts", []),
            "risk_flags": local_result.get("risk_flags", []),
            "recommended_destination": local_result.get("recommended_destination", "待人工确认"),
            "can_write_operation": local_result.get("can_write_operation", False),
            "raw_text": local_result.get("raw_text", ""),
            "parse_error": local_result.get("parse_error"),
        }

    image_base64 = base64.b64encode(contents).decode("utf-8")
    mime_type = image.content_type or "image/png"

    # 图片太大时做简单压缩：若 base64 超过 3MB，降采样
    if len(image_base64) > 3 * 1024 * 1024:
        try:
            from io import BytesIO
            from PIL import Image as PILImage
            img = PILImage.open(BytesIO(contents))
            w, h = img.size
            if max(w, h) > 1024:
                ratio = 1024 / max(w, h)
                img = img.resize((int(w * ratio), int(h * ratio)), PILImage.LANCZOS)
            buf = BytesIO()
            img.save(buf, format="JPEG", quality=75)
            image_base64 = base64.b64encode(buf.getvalue()).decode("utf-8")
            mime_type = "image/jpeg"
            logger.info("图片已压缩至 %d chars base64", len(image_base64))
        except ImportError:
            logger.warning("Pillow 未安装，跳过图片压缩")
        except Exception as exc:
            logger.warning("图片压缩失败: %s", exc)

    result = _make_ollama_vision_call(image_base64)
    if result is not None and local_result and local_result.get("raw_text"):
        result["fields"] = _filter_fields_by_evidence(
            list(result.get("fields") or []),
            str(local_result.get("raw_text") or ""),
        )
        if not result["fields"]:
            result = local_result
    if result is None:
        try:
            result = _make_vision_llm_call(image_base64, mime_type)
        except HTTPException:
            if local_result and local_result.get("raw_text"):
                result = local_result
            else:
                raise

    return {
        "success": True,
        "source_type": result.get("source_type", "未知"),
        "capture_kind": result.get("capture_kind", "unknown"),
        "fields": result.get("fields", []),
        "document_facts": result.get("document_facts", []),
        "risk_flags": result.get("risk_flags", []),
        "recommended_destination": result.get("recommended_destination", "待人工确认"),
        "can_write_operation": result.get("can_write_operation", False),
        "raw_text": result.get("raw_text", ""),
        "parse_error": result.get("parse_error"),
    }
