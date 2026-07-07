#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""本地语音转写路由。语音只转成待确认文本，不直接写经营数据。"""

from __future__ import annotations

import asyncio
import os
import shutil
import tempfile
import threading
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, HTTPException, UploadFile

from server.model_routing import speech_route


router = APIRouter(prefix="/speech", tags=["speech"])
MAX_AUDIO_BYTES = 20 * 1024 * 1024
_whisper_model: Any = None
_model_lock = threading.Lock()


def _parse_spoken_number(raw: str) -> float:
    """解析语音转写中的阿拉伯数字或常见中文数词。"""
    import re

    text = re.sub(r"[元块,\s]+", "", raw).replace("两", "二")
    if not text:
        return 0.0
    try:
        return float(text)
    except ValueError:
        pass

    integer_text, _, decimal_text = text.partition("点")
    digits = {"零": 0, "一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
    small_units = {"十": 10, "百": 100, "千": 1000}
    total = 0
    section = 0
    number = 0
    for char in integer_text:
        if char.isdigit():
            number = number * 10 + int(char)
        elif char in digits:
            number = digits[char]
        elif char in small_units:
            unit = small_units[char]
            section += (number or 1) * unit
            number = 0
        elif char == "万":
            total += (section + number or 1) * 10000
            section = 0
            number = 0
        else:
            return 0.0
    value = float(total + section + number)

    if decimal_text:
        decimal_digits = []
        for char in decimal_text:
            if char.isdigit():
                decimal_digits.append(char)
            elif char in digits:
                decimal_digits.append(str(digits[char]))
            else:
                return 0.0
        if decimal_digits:
            value += int("".join(decimal_digits)) / (10 ** len(decimal_digits))
    return value


def _ensure_ffmpeg() -> None:
    if shutil.which("ffmpeg"):
        return
    homebrew_ffmpeg = Path("/opt/homebrew/bin/ffmpeg")
    if homebrew_ffmpeg.exists():
        os.environ["PATH"] = f"{homebrew_ffmpeg.parent}:{os.environ.get('PATH', '')}"
    if not shutil.which("ffmpeg"):
        raise RuntimeError("本机未安装 ffmpeg，无法读取录音")


def _get_whisper_model():
    global _whisper_model
    if _whisper_model is not None:
        return _whisper_model
    with _model_lock:
        if _whisper_model is None:
            import whisper

            route = speech_route()
            if not route.configured:
                raise RuntimeError("本地 Whisper 模型未准备好")
            _whisper_model = whisper.load_model(route.model)
    return _whisper_model


def _transcribe(path: str) -> dict[str, Any]:
    _ensure_ffmpeg()
    model = _get_whisper_model()
    result = model.transcribe(
        path,
        language="zh",
        task="transcribe",
        fp16=False,
        temperature=0,
        condition_on_previous_text=False,
        initial_prompt=(
            "以下是简体中文餐饮门店经营录入，常见词包括营业额、订单、食材、人工、"
            "租金、水电、库存、利润、写入、确认。请忠实转写数字和否定词。"
        ),
    )
    text = str(result.get("text") or "").strip()
    segments = list(result.get("segments") or [])
    duration = max((float(segment.get("end", 0)) for segment in segments), default=0)
    return {"text": text, "duration_seconds": round(duration, 2)}


@router.post("/transcribe")
async def transcribe_speech(audio: UploadFile = File(...)):
    if not audio.content_type or not (
        audio.content_type.startswith("audio/") or audio.content_type in {"video/webm", "application/octet-stream"}
    ):
        raise HTTPException(status_code=400, detail="只支持音频录音")
    contents = await audio.read()
    if not contents:
        raise HTTPException(status_code=400, detail="录音为空")
    if len(contents) > MAX_AUDIO_BYTES:
        raise HTTPException(status_code=400, detail="录音不能超过 20MB")

    suffix = Path(audio.filename or "recording.webm").suffix or ".webm"
    temp_path = ""
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as temp:
            temp.write(contents)
            temp_path = temp.name
        result = await asyncio.wait_for(asyncio.to_thread(_transcribe, temp_path), timeout=120)
    except asyncio.TimeoutError as exc:
        raise HTTPException(status_code=504, detail="语音转写超时，请缩短录音后重试") from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"本地语音转写不可用：{exc}") from exc
    finally:
        if temp_path:
            Path(temp_path).unlink(missing_ok=True)

    if not result["text"]:
        raise HTTPException(status_code=422, detail="没有识别到清晰语音，请靠近麦克风重试")

    # 从转写文本中提取结构化字段
    structured = _parse_voice_text(result["text"])

    return {
        "success": True,
        "text": result["text"],
        "duration_seconds": result["duration_seconds"],
        "review_status": "needs_human_review",
        "model": speech_route().model,
        "extracted_fields": structured,
    }


def _parse_voice_text(text: str) -> dict[str, Any]:
    """从语音转写文本中提取结构化经营数据字段。"""
    import re

    extracted: dict[str, Any] = {}
    confidence_fields: list[str] = []

    # 营收（支持"三千五"、"3500"、"三万"等）
    revenue_patterns = [
        r"(?:营业额|营收|收入|流水|实收)[^0-9千万]*?([零一二三四五六七八九千百千万0-9]+(?:点[零一二三四五六七八九0-9]+)?)",
        r"(?:今天|今日|本日)[^0-9千万]*?([零一二三四五六七八九千百千万0-9]+(?:点[零一二七八九0-9]+)?)",
        r"([零一二三四五六七八九千百千万0-9]+(?:点[零一二三四五六七八九0-9]+)?)[^0-9千万]*?(?:营业额|营收|收入|流水)",
    ]
    for pattern in revenue_patterns:
        m = re.search(pattern, text)
        if m:
            raw = m.group(1).strip()
            value = _parse_spoken_number(raw)
            if value > 0:
                extracted["revenue"] = round(value, 2)
                confidence_fields.append("revenue")
                break

    # 外卖营收
    delivery_patterns = [
        r"(?:外卖|美团|闪购|抖音)[^0-9千万]*?([零一二三四五六七八九千百千万0-9]+)",
        r"外卖[^0-9千万]*?([零一二三四五六七八九千百千万0-9]+)",
    ]
    for pattern in delivery_patterns:
        m = re.search(pattern, text)
        if m:
            raw = m.group(1).strip()
            value = _parse_spoken_number(raw)
            if value > 0:
                extracted["delivery_revenue"] = round(value, 2)
                confidence_fields.append("delivery_revenue")
                break

    # 订单数
    orders_patterns = [
        r"(?:订单|单量|单)[^0-9]*?(\d+)",
        r"(\d+)[^0-9]*?(?:单|订单)",
    ]
    for pattern in orders_patterns:
        m = re.search(pattern, text)
        if m:
            value = int(m.group(1))
            if 0 < value < 10000:
                extracted["orders"] = value
                confidence_fields.append("orders")
                break

    # 食材成本
    cost_patterns = [
        r"(?:食材|物料|成本|进货)[^0-9千万]*?([零一二三四五六七八九千百千万0-9]+)",
    ]
    for pattern in cost_patterns:
        m = re.search(pattern, text)
        if m:
            raw = m.group(1).strip()
            value = _parse_spoken_number(raw)
            if value > 0:
                extracted["food_cost"] = round(value, 2)
                confidence_fields.append("food_cost")
                break

    # 日期（今天/昨日/具体日期）
    if "今天" in text or "今日" in text:
        from datetime import date
        extracted["date"] = date.today().isoformat()
        confidence_fields.append("date")
    elif "昨天" in text or "昨日" in text:
        from datetime import date, timedelta
        extracted["date"] = (date.today() - timedelta(days=1)).isoformat()
        confidence_fields.append("date")

    return {
        "fields": extracted,
        "confidence_fields": confidence_fields,
        "has_structured_data": bool(extracted),
        "message": f"提取到 {len(confidence_fields)} 个结构化字段" if confidence_fields else "未识别到结构化数据，请在下方手动输入",
    }
