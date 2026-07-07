#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Capability-specific model routing for agents."""

from __future__ import annotations

import os
import importlib.util
import json
import shutil
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL


@dataclass(frozen=True)
class ModelRoute:
    agent: str
    capability: str
    provider: str
    model: str
    base_url: str | None = None
    configured: bool = False
    free: bool = False
    notes: str = ""


def is_configured_key(value: str) -> bool:
    stripped = value.strip()
    return bool(stripped) and "placeholder" not in stripped.lower() and not stripped.startswith("sk-your-")


def is_vision_model(model: str) -> bool:
    lowered = model.lower()
    return any(token in lowered for token in ["vision", "vl", "gpt-4o", "gemini", "qwen-vl"])


def _ollama_model_available(base_url: str, model: str) -> bool:
    """以真实 HTTP 服务和模型清单判断 Ollama 能力，不依赖 shell PATH。"""
    try:
        with urllib.request.urlopen(f"{base_url.rstrip('/')}/api/tags", timeout=2) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return False
    names = {str(item.get("name") or "") for item in payload.get("models", [])}
    return model in names or any(name.split(":")[0] == model.split(":")[0] for name in names)


def chat_route() -> ModelRoute:
    deepseek_key = DEEPSEEK_API_KEY if is_configured_key(DEEPSEEK_API_KEY) else ""
    if deepseek_key:
        return ModelRoute(
            agent="chat_agent",
            capability="reasoning_text",
            provider="deepseek",
            model=DEEPSEEK_MODEL,
            base_url=DEEPSEEK_BASE_URL,
            configured=True,
            notes="Default text reasoning model.",
        )

    openai_key = os.environ.get("OPENAI_API_KEY", "")
    return ModelRoute(
        agent="chat_agent",
        capability="reasoning_text",
        provider="openai",
        model=os.environ.get("OPENAI_TEXT_MODEL", "gpt-4o-mini"),
        base_url="https://api.openai.com/v1",
        configured=is_configured_key(openai_key),
        notes="Fallback text model when DeepSeek is not configured.",
    )


def local_text_route() -> ModelRoute:
    base_url = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    model = os.environ.get("OLLAMA_TEXT_MODEL", "qwen3.5:4b-q4_K_M")
    return ModelRoute(
        agent="chat_agent",
        capability="reasoning_text_fallback",
        provider="ollama",
        model=model,
        base_url=base_url,
        configured=_ollama_model_available(base_url, model),
        free=True,
        notes="Local text fallback when the primary reasoning provider is unavailable.",
    )


def local_ocr_route() -> ModelRoute:
    tesseract_available = bool(shutil.which("tesseract") or Path("/opt/homebrew/bin/tesseract").exists())
    return ModelRoute(
        agent="capture_agent",
        capability="image_ocr",
        provider="tesseract",
        model="chi_sim+eng",
        configured=tesseract_available,
        free=True,
        notes="Free local OCR for screenshots and receipts.",
    )


def local_vision_route() -> ModelRoute:
    base_url = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    model = os.environ.get("OLLAMA_VISION_MODEL", "qwen3.5:4b-q4_K_M")
    return ModelRoute(
        agent="capture_agent",
        capability="image_vision_free",
        provider="ollama",
        model=model,
        base_url=base_url,
        configured=_ollama_model_available(base_url, model),
        free=True,
        notes="Primary free local vision model after OCR; supports Chinese and structured output.",
    )


def speech_route() -> ModelRoute:
    model = os.environ.get("WHISPER_MODEL", "small")
    cached_model = Path.home() / ".cache" / "whisper" / f"{model}.pt"
    return ModelRoute(
        agent="intake_agent",
        capability="speech_to_text",
        provider="whisper",
        model=model,
        configured=bool(importlib.util.find_spec("whisper") and cached_model.exists()),
        free=True,
        notes="Local speech transcription; transcript always requires user confirmation.",
    )


def paid_vision_route() -> ModelRoute:
    openai_key = os.environ.get("OPENAI_API_KEY", "")
    if is_configured_key(openai_key):
        return ModelRoute(
            agent="capture_agent",
            capability="image_vision_paid",
            provider="openai",
            model=os.environ.get("OPENAI_VISION_MODEL", "gpt-4o-mini"),
            base_url="https://api.openai.com/v1",
            configured=True,
            notes="Paid vision fallback for difficult images.",
        )

    deepseek_key = DEEPSEEK_API_KEY if is_configured_key(DEEPSEEK_API_KEY) else ""
    deepseek_vision_model = os.environ.get("DEEPSEEK_VISION_MODEL") or DEEPSEEK_MODEL
    return ModelRoute(
        agent="capture_agent",
        capability="image_vision_paid",
        provider="deepseek",
        model=deepseek_vision_model,
        base_url=DEEPSEEK_BASE_URL,
        configured=bool(deepseek_key and is_vision_model(deepseek_vision_model)),
        notes="Only enabled when a real VL/vision model is configured.",
    )


def model_routing_state() -> dict[str, Any]:
    routes = [
        chat_route(),
        local_text_route(),
        local_ocr_route(),
        local_vision_route(),
        speech_route(),
        paid_vision_route(),
    ]
    return {
        "routes": [
            {
                "agent": route.agent,
                "capability": route.capability,
                "provider": route.provider,
                "model": route.model,
                "base_url": route.base_url,
                "configured": route.configured,
                "free": route.free,
                "notes": route.notes,
            }
            for route in routes
        ],
        "intake_pipelines": {
            "text": ["reasoning_text", "reasoning_text_fallback", "human_confirmation"],
            "image": ["image_ocr", "image_vision_free", "human_confirmation"],
            "speech": ["speech_to_text", "human_confirmation", "reasoning_text"],
        },
    }
