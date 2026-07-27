from fastapi.testclient import TestClient

from server.main import app


def test_chat_answers_channel_order_target_from_real_store_data():
    client = TestClient(app)

    response = client.post("/api/chat/sync", json={
        "project_id": "xinyu-hengtai-dakou",
        "session_id": "channel-goal-regression",
        "message": "实收目标1000元需要多少堂食单和外卖单？",
    })

    assert response.status_code == 200
    answer = response.json()["response"]
    assert "最近一份渠道拆分完整的日报" in answer
    assert "堂食" in answer and "外卖" in answer
    assert "不等于线上曝光或线下进店客流" in answer
