import asyncio
import json

from fastapi.testclient import TestClient

from server.main import app
import server.routes.chat as chat_route
from server.stream import stream_agent_response


class FakeAgent:
    def __init__(self):
        self.messages = []

    def get_response(self, message):
        self.messages.append(message)
        return "这是结合本店数据后的回答。"

    def get_run_metadata(self):
        return {
            "status": "needs_input",
            "domains": ["procurement"],
            "consulted_modules": ["总部物料、采购与门店库存"],
            "gaps": ["订书机是否受总部采购规则限制尚未确认"],
            "conflict_count": 1,
        }


def test_sync_chat_returns_answer_and_structured_run_metadata(monkeypatch):
    agent = FakeAgent()
    monkeypatch.setattr(chat_route, "get_agent", lambda project_id, session_id: agent)

    response = TestClient(app).post(
        "/api/chat/sync",
        json={
            "message": "准备外卖物料，给我一份建议",
            "project_id": "xinyu-hengtai-dakou",
            "session_id": "test-session",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["response"] == "这是结合本店数据后的回答。"
    assert payload["meta"]["status"] == "needs_input"
    assert payload["meta"]["domains"] == ["procurement"]
    assert payload["meta"]["conflict_count"] == 1
    assert agent.messages == ["准备外卖物料，给我一份建议"]


def test_sync_chat_is_restored_from_backend_history(monkeypatch):
    agent = FakeAgent()
    project_id = "chat-history-test"
    monkeypatch.setattr(chat_route, "get_agent", lambda project_id, session_id: agent)

    client = TestClient(app)
    response = client.post(
        "/api/chat/sync",
        json={
            "message": "我还有哪些天没有录入？",
            "project_id": project_id,
            "session_id": "sess-persisted",
            "client_message_id": "user-persisted",
        },
    )
    history = client.get(f"/api/projects/{project_id}/agent/sessions?scope=master")

    assert response.status_code == 200
    assert history.status_code == 200
    sessions = history.json()["sessions"]
    selected = next(item for item in sessions if item["id"] == "sess-persisted")
    assert [message["role"] for message in selected["messages"]] == ["user", "assistant"]
    assert selected["messages"][0]["content"] == "我还有哪些天没有录入？"
    assert selected["messages"][1]["content"] == "这是结合本店数据后的回答。"


def test_stream_chat_uses_same_trusted_agent_path_as_sync(monkeypatch):
    agent = FakeAgent()

    class LegacyGraph:
        async def astream_events(self, *args, **kwargs):
            yield {
                "event": "on_chat_model_stream",
                "data": {"chunk": type("Chunk", (), {"content": "旧流式链", "tool_call_chunks": []})()},
            }

    monkeypatch.setattr("server.deps.get_agent", lambda project_id, session_id: agent)
    monkeypatch.setattr("graph.agent.build_agent", lambda: LegacyGraph())

    async def collect():
        return [
            event
            async for event in stream_agent_response(
                "库存还缺哪些信息？",
                "stream-session",
                "xinyu-hengtai-dakou",
            )
        ]

    events = asyncio.run(collect())
    body = "".join(events)
    rendered_text = "".join(
        json.loads(line[2:])
        for line in body.splitlines()
        if line.startswith("0:")
    )

    assert "这是结合本店数据后的回答" in rendered_text
    assert "旧流式链" not in rendered_text
    assert "新手加盟最低闭环" not in rendered_text
    assert agent.messages == ["库存还缺哪些信息？"]
