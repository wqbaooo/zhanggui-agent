"""Optional reasoning runtimes behind the trusted store Agent contract."""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RuntimeAnswer:
    text: str
    provider: str
    model: str


class HermesGatewayRuntime:
    """Use a separately managed Hermes Gateway as the reasoning engine.

    The store application owns business facts, permissions and product history.
    Hermes owns model orchestration and its private execution context. Keeping a
    gateway boundary makes upgrades reversible and avoids importing Hermes'
    large dependency graph into the FastAPI process.
    """

    provider = "hermes"

    def __init__(self, project_id: str, session_id: str):
        self.project_id = project_id
        self.session_id = session_id
        self.base_url = os.getenv("HERMES_API_BASE", "http://127.0.0.1:8652").rstrip("/")
        self.api_key = os.getenv("HERMES_API_KEY", "").strip()
        key_file = os.getenv("HERMES_API_KEY_FILE", "").strip()
        if not self.api_key and key_file:
            try:
                self.api_key = open(key_file, encoding="utf-8").read().strip()
            except OSError as exc:
                logger.warning("Unable to read HERMES_API_KEY_FILE: %s", exc)
        self.model = os.getenv("HERMES_MODEL", "hermes-agent").strip() or "hermes-agent"
        self.timeout = float(os.getenv("HERMES_TIMEOUT_SECONDS", "75"))

    def get_response(self, user_input: str, context: dict[str, Any]) -> RuntimeAnswer:
        system_message = (
            "你是掌柜，新余恒太城五楼大口章鱼烧唯一对外的经营 Agent。"
            "用户是老板。你必须以门店已确认事实为准；不知道就明确说不知道。"
            "你是最高层协调者；财务、库存、经营和店务 Agent 是平级的独立专业责任主体。"
            "你可以拆解、分派、汇总和追踪任务，但不能冒充专业 Agent 完成其正式写入。"
            "专业 Agent 只能写自己负责的模块；跨模块任务必须由你协调，并在收到执行结果后才可宣称完成。"
            "禁止把销售收入、平台结算、银行卡到账、老板投入和个人消费混为一谈。"
            "任何写账、改库存或外部动作必须在当前轮次得到明确确认。"
            f"\n本轮可信上下文：{json.dumps(context, ensure_ascii=False, default=str)}"
        )
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_input},
            ],
            "stream": False,
        }
        headers = {
            "Content-Type": "application/json",
            "X-Hermes-Session-Id": self.session_id,
            "X-Hermes-Session-Key": f"store:{self.project_id}:master",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        request = urllib.request.Request(
            f"{self.base_url}/v1/chat/completions",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                body = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            raise RuntimeError(f"Hermes Gateway 不可用: {exc}") from exc
        choices = body.get("choices") or []
        text = str(((choices[0] if choices else {}).get("message") or {}).get("content") or "").strip()
        if not text:
            raise RuntimeError("Hermes Gateway 没有返回有效内容")
        return RuntimeAnswer(text=text, provider=self.provider, model=self.model)


class PiAgentRuntime:
    """Use the isolated Pi Agent Core sidecar with product-owned permissions."""

    provider = "pi"

    def __init__(self, project_id: str, session_id: str):
        self.project_id = project_id
        self.session_id = session_id
        self.base_url = os.getenv("PI_AGENT_API_BASE", "http://127.0.0.1:8653").rstrip("/")
        self.api_key = os.getenv("PI_AGENT_API_KEY", "").strip()
        key_file = os.getenv("PI_AGENT_API_KEY_FILE", "").strip()
        if not self.api_key and key_file:
            try:
                self.api_key = open(key_file, encoding="utf-8").read().strip()
            except OSError as exc:
                logger.warning("Unable to read PI_AGENT_API_KEY_FILE: %s", exc)
        self.model = os.getenv("PI_AGENT_MODEL", "deepseek-v4-pro").strip() or "deepseek-v4-pro"
        self.timeout = float(os.getenv("PI_AGENT_TIMEOUT_SECONDS", "75"))

    def get_response(self, user_input: str, context: dict[str, Any]) -> RuntimeAnswer:
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": user_input}],
            "stream": False,
            "zhanggui_context": context,
        }
        headers = {
            "Content-Type": "application/json",
            "X-Agent-Session-Id": self.session_id,
            "X-Agent-Project-Id": self.project_id,
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        request = urllib.request.Request(
            f"{self.base_url}/v1/chat/completions",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                body = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            raise RuntimeError(f"Pi Agent 运行时不可用: {exc}") from exc
        choices = body.get("choices") or []
        text = str(((choices[0] if choices else {}).get("message") or {}).get("content") or "").strip()
        if not text:
            raise RuntimeError("Pi Agent 没有返回有效内容")
        return RuntimeAnswer(text=text, provider=self.provider, model=self.model)


def build_reasoning_runtime(project_id: str, session_id: str) -> HermesGatewayRuntime | PiAgentRuntime | None:
    runtime = os.getenv("AGENT_RUNTIME", "trusted").strip().lower()
    if runtime == "hermes":
        return HermesGatewayRuntime(project_id, session_id)
    if runtime == "pi":
        return PiAgentRuntime(project_id, session_id)
    return None


def runtime_status() -> dict[str, Any]:
    selected = os.getenv("AGENT_RUNTIME", "trusted").strip().lower()
    if selected not in {"hermes", "pi"}:
        return {
            "selected": "trusted",
            "available": True,
            "active": True,
            "label": "掌柜可信运行时",
            "fallback": None,
        }
    runtime = (
        HermesGatewayRuntime("xinyu-hengtai-dakou", "runtime-health")
        if selected == "hermes"
        else PiAgentRuntime("xinyu-hengtai-dakou", "runtime-health")
    )
    request = urllib.request.Request(f"{runtime.base_url}/health", method="GET")
    try:
        with urllib.request.urlopen(request, timeout=1.5) as response:
            available = 200 <= response.status < 500
    except Exception:
        available = False
    return {
        "selected": selected,
        "available": available,
        "active": available,
        "label": (
            "Hermes Agent" if selected == "hermes" else "Pi Agent Core"
        ) if available else (
            "Hermes 未连接" if selected == "hermes" else "Pi Agent 未连接"
        ),
        "model": runtime.model,
        "base_url": runtime.base_url,
        "fallback": None if available else "掌柜可信运行时",
    }
