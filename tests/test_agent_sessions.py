from pathlib import Path

from models.agent_sessions import AgentSessionStore


def test_agent_session_store_persists_and_archives_history(tmp_path: Path):
    store = AgentSessionStore(tmp_path / "agent_sessions.sqlite3")
    session_id = store.ensure_session(
        "xinyu-hengtai-dakou",
        "sess-history",
        runtime="hermes",
    )
    store.append_message(
        session_id,
        "user",
        "昨天哪些平台收入还没有录入？",
        message_id="user-1",
    )
    store.append_message(
        session_id,
        "assistant",
        "我会按每日固定渠道逐项核对。",
        metadata={"model_provider": "hermes", "domains": ["finance"]},
        message_id="assistant-1",
    )

    sessions = store.list_sessions("xinyu-hengtai-dakou")

    assert len(sessions) == 1
    assert sessions[0]["title"].startswith("昨天哪些平台收入")
    assert sessions[0]["runtime"] == "hermes"
    assert [message["role"] for message in sessions[0]["messages"]] == ["user", "assistant"]
    assert sessions[0]["messages"][1]["run"]["domains"] == ["finance"]

    assert store.archive_session("xinyu-hengtai-dakou", session_id) is True
    assert store.list_sessions("xinyu-hengtai-dakou") == []


def test_agent_session_import_is_idempotent(tmp_path: Path):
    store = AgentSessionStore(tmp_path / "agent_sessions.sqlite3")
    messages = [
        {"id": "user-local", "role": "user", "content": "旧问题", "timestamp": "2026-07-01T10:00:00+08:00"},
        {"id": "assistant-local", "role": "assistant", "content": "旧回答", "timestamp": "2026-07-01T10:00:01+08:00"},
    ]

    store.import_session("xinyu-hengtai-dakou", "sess-local", "旧对话", messages)
    store.import_session("xinyu-hengtai-dakou", "sess-local", "旧对话", messages)

    session = store.get_session("xinyu-hengtai-dakou", "sess-local")
    assert session is not None
    assert len(session["messages"]) == 2


def test_agent_preference_signals_are_scoped_and_ranked(tmp_path: Path):
    store = AgentSessionStore(tmp_path / "agent_sessions.sqlite3")
    store.record_preference_signal("xinyu-hengtai-dakou", "finance", "funds_settlement")
    store.record_preference_signal("xinyu-hengtai-dakou", "finance", "funds_settlement")
    store.record_preference_signal("xinyu-hengtai-dakou", "finance", "profit_cost")
    store.record_preference_signal("xinyu-hengtai-dakou", "inventory", "stockout")

    profile = store.get_preference_profile("xinyu-hengtai-dakou", scope="finance")

    assert [item["topic"] for item in profile] == ["funds_settlement", "profit_cost"]
    assert profile[0]["count"] == 2


def test_cross_domain_handoff_is_durable_and_coordinated_by_master(tmp_path: Path):
    store = AgentSessionStore(tmp_path / "agent_sessions.sqlite3")
    session_id = store.ensure_session(
        "xinyu-hengtai-dakou", "sess-handoff", scope="finance",
    )

    created = store.create_handoff(
        "xinyu-hengtai-dakou",
        session_id=session_id,
        source_agent="finance",
        target_agent="inventory",
        coordinator_agent="master",
        summary="核对食材采购与库存事实",
        reason="财务 Agent 不得越权修改库存事实",
    )
    queued = store.list_handoffs(
        "xinyu-hengtai-dakou", status="queued_for_master",
    )

    assert created["status"] == "queued_for_master"
    assert len(queued) == 1
    assert queued[0]["source_agent"] == "finance"
    assert queued[0]["target_agent"] == "inventory"
    assert queued[0]["coordinator_agent"] == "master"
