#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Capability-specific model routing for agents."""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
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


def local_ocr_route() -> ModelRoute:
    return ModelRoute(
        agent="capture_agent",
        capability="image_ocr",
        provider="tesseract",
        model="chi_sim+eng",
        configured=bool(shutil.which("tesseract")),
        free=True,
        notes="Free local OCR for screenshots and receipts.",
    )


def local_vision_route() -> ModelRoute:
    return ModelRoute(
        agent="capture_agent",
        capability="image_vision_free",
        provider="ollama",
        model=os.environ.get("OLLAMA_VISION_MODEL", "moondream:1.8b"),
        base_url=os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434"),
        configured=bool(shutil.which("ollama")),
        free=True,
        notes="Free local vision fallback after OCR.",
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
    routes = [chat_route(), local_ocr_route(), local_vision_route(), paid_vision_route()]
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
        ]
    }
