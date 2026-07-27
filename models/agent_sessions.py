"""Durable, project-scoped conversation history for the store Agent."""

from __future__ import annotations

import json
import os
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="milliseconds")


class AgentSessionStore:
    """Persist the product's conversations independently from any LLM runtime.

    Hermes may keep its own execution trace and compressed context, but this
    database remains the product-facing source of truth for conversation lists,
    message rendering and runtime migration.
    """

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._migrate()

    @classmethod
    def for_project(cls, project_id: str) -> "AgentSessionStore":
        import config

        safe_project_id = "".join(
            character for character in (project_id or "anonymous")
            if character.isalnum() or character in {"-", "_"}
        ) or "anonymous"
        if os.environ.get("PYTEST_CURRENT_TEST"):
            root = Path("/tmp") / f"zhanggui-agent-tests-{os.getpid()}" / safe_project_id
        else:
            root = Path(config.PROJECT_DATA_DIR) / safe_project_id
        return cls(root / "agent_sessions.sqlite3")

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        return connection

    def _migrate(self) -> None:
        with self.connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS agent_sessions (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    scope TEXT NOT NULL DEFAULT 'master',
                    title TEXT NOT NULL,
                    runtime TEXT NOT NULL DEFAULT 'trusted',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    archived_at TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_agent_sessions_project
                    ON agent_sessions(project_id, scope, updated_at DESC);

                CREATE TABLE IF NOT EXISTS agent_messages (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL REFERENCES agent_sessions(id) ON DELETE CASCADE,
                    role TEXT NOT NULL CHECK(role IN ('user', 'assistant', 'system')),
                    content TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'complete',
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_agent_messages_session
                    ON agent_messages(session_id, created_at);
                """
            )

    @staticmethod
    def _title(text: str) -> str:
        compact = " ".join(text.strip().split())
        if not compact:
            return "新对话"
        return compact if len(compact) <= 24 else f"{compact[:24]}…"

    def ensure_session(
        self,
        project_id: str,
        session_id: str | None = None,
        *,
        scope: str = "master",
        title: str = "新对话",
        runtime: str = "trusted",
    ) -> str:
        session_id = session_id or f"sess_{uuid.uuid4().hex}"
        now = _now()
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO agent_sessions(id, project_id, scope, title, runtime, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    runtime = excluded.runtime,
                    updated_at = excluded.updated_at
                """,
                (session_id, project_id, scope, title or "新对话", runtime, now, now),
            )
        return session_id

    def append_message(
        self,
        session_id: str,
        role: str,
        content: str,
        *,
        status: str = "complete",
        metadata: dict[str, Any] | None = None,
        message_id: str | None = None,
        created_at: str | None = None,
    ) -> str:
        message_id = message_id or f"msg_{uuid.uuid4().hex}"
        timestamp = created_at or _now()
        with self.connect() as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO agent_messages(
                    id, session_id, role, content, status, metadata_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    message_id,
                    session_id,
                    role,
                    content,
                    status,
                    json.dumps(metadata or {}, ensure_ascii=False, default=str),
                    timestamp,
                ),
            )
            if role == "user":
                row = connection.execute(
                    "SELECT title FROM agent_sessions WHERE id = ?", (session_id,)
                ).fetchone()
                title = self._title(content) if row and row["title"] == "新对话" else None
                if title:
                    connection.execute(
                        "UPDATE agent_sessions SET title = ?, updated_at = ? WHERE id = ?",
                        (title, timestamp, session_id),
                    )
                else:
                    connection.execute(
                        "UPDATE agent_sessions SET updated_at = ? WHERE id = ?",
                        (timestamp, session_id),
                    )
            else:
                connection.execute(
                    "UPDATE agent_sessions SET updated_at = ? WHERE id = ?",
                    (timestamp, session_id),
                )
        return message_id

    def import_session(
        self,
        project_id: str,
        session_id: str,
        title: str,
        messages: Iterable[dict[str, Any]],
        *,
        scope: str = "master",
    ) -> str:
        self.ensure_session(project_id, session_id, scope=scope, title=title)
        for message in messages:
            role = str(message.get("role") or "")
            content = str(message.get("content") or "")
            if role not in {"user", "assistant", "system"} or not content:
                continue
            self.append_message(
                session_id,
                role,
                content,
                metadata=message.get("run") or message.get("metadata") or {},
                message_id=str(message.get("id") or f"msg_{uuid.uuid4().hex}"),
                created_at=str(message.get("timestamp") or message.get("created_at") or _now()),
            )
        return session_id

    def list_sessions(
        self,
        project_id: str,
        *,
        scope: str = "master",
        limit: int = 50,
        include_messages: bool = True,
    ) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM agent_sessions
                WHERE project_id = ? AND scope = ? AND archived_at IS NULL
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (project_id, scope, max(1, min(limit, 200))),
            ).fetchall()
            return [
                self._session_dict(connection, row, include_messages=include_messages)
                for row in rows
            ]

    def get_session(self, project_id: str, session_id: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM agent_sessions WHERE project_id = ? AND id = ? AND archived_at IS NULL",
                (project_id, session_id),
            ).fetchone()
            return self._session_dict(connection, row, include_messages=True) if row else None

    def archive_session(self, project_id: str, session_id: str) -> bool:
        with self.connect() as connection:
            result = connection.execute(
                "UPDATE agent_sessions SET archived_at = ?, updated_at = ? WHERE project_id = ? AND id = ?",
                (_now(), _now(), project_id, session_id),
            )
            return result.rowcount > 0

    @staticmethod
    def _session_dict(
        connection: sqlite3.Connection,
        row: sqlite3.Row,
        *,
        include_messages: bool,
    ) -> dict[str, Any]:
        messages: list[dict[str, Any]] = []
        if include_messages:
            message_rows = connection.execute(
                "SELECT * FROM agent_messages WHERE session_id = ? ORDER BY created_at, rowid",
                (row["id"],),
            ).fetchall()
            for message in message_rows:
                try:
                    metadata = json.loads(message["metadata_json"] or "{}")
                except json.JSONDecodeError:
                    metadata = {}
                messages.append(
                    {
                        "id": message["id"],
                        "role": message["role"],
                        "content": message["content"],
                        "status": message["status"],
                        "timestamp": message["created_at"],
                        "run": metadata or None,
                    }
                )
        return {
            "id": row["id"],
            "projectId": row["project_id"],
            "scope": row["scope"],
            "title": row["title"],
            "runtime": row["runtime"],
            "createdAt": row["created_at"],
            "updatedAt": row["updated_at"],
            "messages": messages,
        }
