from fastapi.testclient import TestClient

from server.main import app
import server.routes.chat as chat_route


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
