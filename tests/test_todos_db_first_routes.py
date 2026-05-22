"""
Tests for todos DB-first behavior in GET /todos/{session_id}.

Verifies:
- Flag off: SessionContext todos are used, no DB connection opened.
- Flag on + DB success: DB todos are rendered.
- Flag on + DB failure (query error): falls back to SessionContext todos.
- Flag on + connection error: falls back to SessionContext todos.
- DB errors are never exposed in the response body.
- Mutation routes (create, status) are unaffected — still use SessionContext
  and existing write-through.
- No route URLs changed.
- No DB read is attempted when the flag is off.

All tests run without a real DB (AI2_TEST_MODE=1, all DB calls mocked).
"""

from __future__ import annotations

import os

os.environ["AI2_TEST_MODE"] = "1"
os.environ["ANTHROPIC_API_KEY"] = "test-key"

from contextlib import contextmanager
from unittest.mock import MagicMock, call, patch

import pytest
from fastapi.testclient import TestClient

from app import app

client = TestClient(app)

_FLAG = "AI2_TODOS_DB_READS_ENABLED"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _start_session() -> str:
    r = client.post("/session/start", json={"track": "aipm", "week": 1})
    assert r.status_code == 200, r.text
    return r.json()["session_id"]


def _create_todo(session_id: str, title: str, todo_type: str = "daily") -> dict:
    r = client.post("/todos/create", json={
        "session_id": session_id,
        "title":      title,
        "todo_type":  todo_type,
    })
    assert r.status_code == 200, r.text
    return r.json()


def _db_todo(title: str = "DB Todo", todo_type: str = "daily") -> dict:
    """Return a normalized todo dict as if returned from normalize_todo_row."""
    return {
        "todo_id":         "db-todo-abc",
        "title":           title,
        "todo_type":       todo_type,
        "status":          "todo",
        "linked_topic_id": "",
        "created_by":      "learner",
        "due_label":       "",
        "created_at":      "2024-01-01T00:00:00",
        "updated_at":      "2024-01-01T00:00:00",
    }


def _mock_get_conn(mock_conn: MagicMock | None = None):
    """Return a context-manager mock for database.pool.get_conn."""
    inner = mock_conn or MagicMock()
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=inner)
    ctx.__exit__  = MagicMock(return_value=False)
    return ctx


# ── Flag OFF: SessionContext is used, no DB opened ────────────────────────────

class TestFlagOff:
    def test_todos_page_returns_200_flag_off(self, monkeypatch):
        monkeypatch.delenv(_FLAG, raising=False)
        session_id = _start_session()
        resp = client.get(f"/todos/{session_id}")
        assert resp.status_code == 200

    def test_flag_off_uses_session_context_todos(self, monkeypatch):
        monkeypatch.delenv(_FLAG, raising=False)
        session_id = _start_session()
        _create_todo(session_id, "Session Todo Flag Off")
        resp = client.get(f"/todos/{session_id}")
        assert resp.status_code == 200
        assert "Session Todo Flag Off" in resp.text

    def test_flag_off_does_not_open_db_connection(self, monkeypatch):
        monkeypatch.delenv(_FLAG, raising=False)
        session_id = _start_session()
        with patch("database.pool.get_conn") as mock_conn:
            resp = client.get(f"/todos/{session_id}")
            mock_conn.assert_not_called()
        assert resp.status_code == 200

    def test_flag_off_false_value_does_not_open_db(self, monkeypatch):
        monkeypatch.setenv(_FLAG, "0")
        session_id = _start_session()
        with patch("database.pool.get_conn") as mock_conn:
            resp = client.get(f"/todos/{session_id}")
            mock_conn.assert_not_called()
        assert resp.status_code == 200


# ── Flag ON + DB success: DB todos are rendered ───────────────────────────────

class TestFlagOnDbSuccess:
    def test_flag_on_db_daily_todo_appears(self, monkeypatch):
        monkeypatch.setenv(_FLAG, "1")
        session_id = _start_session()
        db_todo = _db_todo("From The Database Daily", todo_type="daily")

        with patch("database.pool.get_conn", return_value=_mock_get_conn()):
            with patch(
                "services.learner_state_read_service.list_todos_from_db",
                return_value=[db_todo],
            ):
                resp = client.get(f"/todos/{session_id}")

        assert resp.status_code == 200
        assert "From The Database Daily" in resp.text

    def test_flag_on_db_weekly_todo_appears(self, monkeypatch):
        monkeypatch.setenv(_FLAG, "1")
        session_id = _start_session()
        db_todo = _db_todo("From The Database Weekly", todo_type="weekly")

        with patch("database.pool.get_conn", return_value=_mock_get_conn()):
            with patch(
                "services.learner_state_read_service.list_todos_from_db",
                return_value=[db_todo],
            ):
                resp = client.get(f"/todos/{session_id}")

        assert resp.status_code == 200
        assert "From The Database Weekly" in resp.text

    def test_flag_on_db_empty_list_is_valid(self, monkeypatch):
        monkeypatch.setenv(_FLAG, "1")
        session_id = _start_session()

        with patch("database.pool.get_conn", return_value=_mock_get_conn()):
            with patch(
                "services.learner_state_read_service.list_todos_from_db",
                return_value=[],
            ):
                resp = client.get(f"/todos/{session_id}")

        assert resp.status_code == 200

    def test_flag_on_db_session_todo_not_shown_when_db_returns_empty(self, monkeypatch):
        """When DB returns [] and flag is on, session todos are NOT shown (DB wins)."""
        monkeypatch.setenv(_FLAG, "1")
        session_id = _start_session()
        _create_todo(session_id, "Session Only Todo")

        with patch("database.pool.get_conn", return_value=_mock_get_conn()):
            with patch(
                "services.learner_state_read_service.list_todos_from_db",
                return_value=[],
            ):
                resp = client.get(f"/todos/{session_id}")

        assert resp.status_code == 200
        assert "Session Only Todo" not in resp.text


# ── Flag ON + DB query failure: fallback to SessionContext ────────────────────

class TestFlagOnDbFailure:
    def test_flag_on_db_failure_falls_back_to_session(self, monkeypatch):
        monkeypatch.setenv(_FLAG, "1")
        session_id = _start_session()
        _create_todo(session_id, "Session Fallback Todo")

        with patch("database.pool.get_conn", return_value=_mock_get_conn()):
            with patch(
                "services.learner_state_read_service.list_todos_from_db",
                side_effect=RuntimeError("DB query blew up"),
            ):
                resp = client.get(f"/todos/{session_id}")

        assert resp.status_code == 200
        assert "Session Fallback Todo" in resp.text

    def test_flag_on_db_failure_does_not_expose_error(self, monkeypatch):
        monkeypatch.setenv(_FLAG, "1")
        session_id = _start_session()

        with patch("database.pool.get_conn", return_value=_mock_get_conn()):
            with patch(
                "services.learner_state_read_service.list_todos_from_db",
                side_effect=RuntimeError("secret DB error message xyz"),
            ):
                resp = client.get(f"/todos/{session_id}")

        assert resp.status_code == 200
        assert "secret DB error message xyz" not in resp.text
        assert "RuntimeError" not in resp.text

    def test_flag_on_conn_error_falls_back_to_session(self, monkeypatch):
        """If get_conn() itself raises, the route still returns session todos."""
        monkeypatch.setenv(_FLAG, "1")
        session_id = _start_session()
        _create_todo(session_id, "Connection Error Fallback Todo")

        with patch("database.pool.get_conn", side_effect=OSError("cannot connect")):
            resp = client.get(f"/todos/{session_id}")

        assert resp.status_code == 200
        assert "Connection Error Fallback Todo" in resp.text

    def test_flag_on_conn_error_not_exposed_in_response(self, monkeypatch):
        monkeypatch.setenv(_FLAG, "1")
        session_id = _start_session()

        with patch("database.pool.get_conn", side_effect=OSError("cannot connect secret")):
            resp = client.get(f"/todos/{session_id}")

        assert resp.status_code == 200
        assert "cannot connect secret" not in resp.text


# ── Mutations unchanged ───────────────────────────────────────────────────────

class TestMutationsUnchanged:
    def test_create_todo_returns_200_flag_off(self, monkeypatch):
        monkeypatch.delenv(_FLAG, raising=False)
        session_id = _start_session()
        r = client.post("/todos/create", json={
            "session_id": session_id,
            "title":      "New Task",
            "todo_type":  "daily",
        })
        assert r.status_code == 200
        assert r.json()["todo"]["title"] == "New Task"

    def test_create_todo_returns_200_flag_on(self, monkeypatch):
        monkeypatch.setenv(_FLAG, "1")
        session_id = _start_session()
        r = client.post("/todos/create", json={
            "session_id": session_id,
            "title":      "New Task Flag On",
            "todo_type":  "daily",
        })
        assert r.status_code == 200
        assert r.json()["todo"]["title"] == "New Task Flag On"

    def test_status_update_returns_200_flag_off(self, monkeypatch):
        monkeypatch.delenv(_FLAG, raising=False)
        session_id = _start_session()
        todo_id = _create_todo(session_id, "Status Task")["todo"]["todo_id"]
        r = client.post("/todos/status", json={
            "session_id": session_id,
            "todo_id":    todo_id,
            "status":     "done",
        })
        assert r.status_code == 200
        assert r.json()["todo"]["status"] == "done"

    def test_status_update_returns_200_flag_on(self, monkeypatch):
        monkeypatch.setenv(_FLAG, "1")
        session_id = _start_session()
        todo_id = _create_todo(session_id, "Status Task Flag On")["todo"]["todo_id"]
        r = client.post("/todos/status", json={
            "session_id": session_id,
            "todo_id":    todo_id,
            "status":     "in_progress",
        })
        assert r.status_code == 200
        assert r.json()["todo"]["status"] == "in_progress"

    def test_create_does_not_open_db_read_connection_flag_off(self, monkeypatch):
        """Creating a todo never opens a DB read even when flag is on (writes use write-through)."""
        monkeypatch.delenv(_FLAG, raising=False)
        monkeypatch.delenv("AI2_DB_WRITE_THROUGH_ENABLED", raising=False)
        session_id = _start_session()
        with patch("database.pool.get_conn") as mock_conn:
            r = client.post("/todos/create", json={
                "session_id": session_id,
                "title":      "No DB Read Task",
                "todo_type":  "daily",
            })
            mock_conn.assert_not_called()
        assert r.status_code == 200


# ── Route URLs unchanged ──────────────────────────────────────────────────────

class TestRouteUrlsUnchanged:
    def test_todos_page_url(self, monkeypatch):
        monkeypatch.delenv(_FLAG, raising=False)
        session_id = _start_session()
        resp = client.get(f"/todos/{session_id}")
        assert resp.status_code == 200

    def test_create_url(self, monkeypatch):
        monkeypatch.delenv(_FLAG, raising=False)
        session_id = _start_session()
        resp = client.post("/todos/create", json={
            "session_id": session_id,
            "title":      "URL Check",
            "todo_type":  "daily",
        })
        assert resp.status_code == 200

    def test_status_url(self, monkeypatch):
        monkeypatch.delenv(_FLAG, raising=False)
        session_id = _start_session()
        todo_id = _create_todo(session_id, "URL Status Check")["todo"]["todo_id"]
        resp = client.post("/todos/status", json={
            "session_id": session_id,
            "todo_id":    todo_id,
            "status":     "done",
        })
        assert resp.status_code == 200


# ── Debug endpoints unaffected ────────────────────────────────────────────────

class TestDebugEndpointsUnaffected:
    def test_storage_health_still_works(self, monkeypatch):
        monkeypatch.setenv(_FLAG, "1")
        monkeypatch.delenv("AI2_ENV", raising=False)
        resp = client.get("/debug/storage-health")
        assert resp.status_code == 200
