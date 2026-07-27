from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from core.agent_runtime import HermesGatewayRuntime, PiAgentRuntime, build_reasoning_runtime


ROOT = Path(__file__).resolve().parents[1]


def test_hermes_runtime_reads_api_key_from_private_file(tmp_path, monkeypatch):
    key_file = tmp_path / "hermes.key"
    key_file.write_text("private-test-key\n", encoding="utf-8")
    monkeypatch.delenv("HERMES_API_KEY", raising=False)
    monkeypatch.delenv("HERMES_API_BASE", raising=False)
    monkeypatch.setenv("HERMES_API_KEY_FILE", str(key_file))

    runtime = HermesGatewayRuntime("xinyu-hengtai-dakou", "test-session")

    assert runtime.api_key == "private-test-key"
    assert runtime.base_url == "http://127.0.0.1:8652"


def test_inventory_tool_uses_project_scoped_read_only_route(monkeypatch):
    tools_path = ROOT / ".hermes/plugins/zhanggui-store/tools.py"
    spec = importlib.util.spec_from_file_location("zhanggui_store_tools", tools_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    captured = {}

    def fake_get(path, params=None):
        captured["path"] = path
        captured["params"] = params
        return "{}"

    monkeypatch.setattr(module, "_get", fake_get)
    monkeypatch.setenv("ZHANGGUI_PROJECT_ID", "xinyu-hengtai-dakou")

    assert module.inventory_summary({}) == "{}"
    assert captured == {
        "path": "/api/projects/xinyu-hengtai-dakou/skus/inventory-summary",
        "params": None,
    }


def test_pi_runtime_forwards_turn_policy_and_session_without_write_tools(monkeypatch):
    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return json.dumps({
                "choices": [{"message": {"content": "按库存事实回答"}}]
            }).encode()

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["headers"] = dict(request.header_items())
        captured["payload"] = json.loads(request.data.decode())
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr("core.agent_runtime.urllib.request.urlopen", fake_urlopen)
    runtime = PiAgentRuntime("xinyu-hengtai-dakou", "pi-session")
    answer = runtime.get_response(
        "库存还缺哪些信息？",
        {"intent": "business_question", "allowed_tools": ["inventory"]},
    )

    assert answer.provider == "pi"
    assert answer.text == "按库存事实回答"
    assert captured["url"] == "http://127.0.0.1:8653/v1/chat/completions"
    assert captured["headers"]["X-agent-session-id"] == "pi-session"
    assert captured["payload"]["zhanggui_context"]["allowed_tools"] == ["inventory"]


def test_runtime_factory_can_select_pi_without_replacing_trusted_default(monkeypatch):
    monkeypatch.setenv("AGENT_RUNTIME", "pi")
    assert isinstance(build_reasoning_runtime("xinyu-hengtai-dakou", "session"), PiAgentRuntime)

    monkeypatch.setenv("AGENT_RUNTIME", "trusted")
    assert build_reasoning_runtime("xinyu-hengtai-dakou", "session") is None
