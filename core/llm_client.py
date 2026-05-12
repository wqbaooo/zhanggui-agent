#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""LLM统一调用层：DeepSeek API + 三级降级机制。"""

from __future__ import annotations

import json
import logging
from typing import Any, Callable, Dict, Optional

from config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL

logger = logging.getLogger(__name__)

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None  # type: ignore


class LLMClient:
    """统一的 LLM 调用接口，支持降级到本地规则。"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        self.api_key = api_key or DEEPSEEK_API_KEY
        self.model = model or DEEPSEEK_MODEL
        self.base_url = base_url or DEEPSEEK_BASE_URL
        self._client: Optional[Any] = None

        if self.api_key and OpenAI:
            self._client = OpenAI(api_key=self.api_key, base_url=self.base_url)

    def available(self) -> bool:
        """LLM是否可用。"""
        return self._client is not None

    def call(
        self,
        prompt: str,
        system_msg: str = "你是一个餐饮开店规划专家。",
        temperature: float = 0.3,
        max_tokens: int = 500,
    ) -> Optional[str]:
        """调用LLM，失败返回 None。

        内部含重试逻辑（最多2次）。
        """
        if not self._client:
            return None

        for attempt in range(2):
            try:
                response = self._client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_msg},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=temperature if attempt == 0 else 0.1,
                    max_tokens=max_tokens,
                )
                content = response.choices[0].message.content
                if content:
                    return content.strip()
            except Exception as exc:
                logger.warning("LLM调用失败(attempt=%d): %s", attempt + 1, exc)
                continue

        return None

    def call_json(
        self,
        prompt: str,
        system_msg: str = "你是一个餐饮开店规划专家。请严格按JSON格式输出。",
        temperature: float = 0.2,
        max_tokens: int = 300,
    ) -> Optional[Dict[str, Any]]:
        """调用LLM并解析JSON响应。失败返回 None。"""
        raw = self.call(prompt, system_msg, temperature, max_tokens)
        if not raw:
            return None

        # 尝试从响应中提取JSON
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass

        # 尝试提取 ```json ... ``` 块
        import re
        match = re.search(r"```json\s*(.*?)\s*```", raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass

        # 尝试提取 { ... } 块
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass

        logger.warning("无法从LLM响应中解析JSON: %s...", raw[:100])
        return None

    def call_with_fallback(
        self,
        prompt: str,
        fallback_fn: Callable[[], str],
        system_msg: str = "你是一个餐饮开店规划专家。",
        temperature: float = 0.3,
        max_tokens: int = 500,
    ) -> tuple[str, bool]:
        """调用LLM，失败时执行 fallback_fn。

        返回: (result, used_llm)
        """
        result = self.call(prompt, system_msg, temperature, max_tokens)
        if result:
            return result, True
        return fallback_fn(), False

    def call_json_with_fallback(
        self,
        prompt: str,
        fallback_fn: Callable[[], Dict[str, Any]],
        system_msg: str = "你是一个餐饮开店规划专家。请严格按JSON格式输出。",
        temperature: float = 0.2,
        max_tokens: int = 300,
    ) -> tuple[Dict[str, Any], bool]:
        """调用LLM解析JSON，失败时执行 fallback_fn。

        返回: (result_dict, used_llm)
        """
        result = self.call_json(prompt, system_msg, temperature, max_tokens)
        if result:
            return result, True
        return fallback_fn(), False
