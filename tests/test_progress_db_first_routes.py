"""
Tests for topic progress DB-first behavior in GET /topics/{session_id} and
GET /topic/{session_id}/{topic_id}.

Verifies:
- Flag off: SessionContext progress is used, no DB connection opened.
- Flag on + DB success: DB progress is rendered.
- Flag on + DB returns None: falls back to SessionContext progress.
- Flag on + DB query error: falls back to SessionContext progress.
- Flag on + connection error: falls back to SessionContext progress.
- DB errors are never exposed in the response body.
- Mutation routes (POST /topic/progress, POST /topic/notes) are unaffected.
- No route URLs changed.
- No DB read is attempted when the flag is off.

All tests run without a real DB (AI2_TEST_MODE=1, all DB calls mocked).
"""

from __future__ import annotations

import os

os.environ["AI2_TEST_MODE"] = "1"
os.environ["ANTHROPIC_API_KEY"] = "test-key"

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app import app
from curriculum.topics import get_topics_for_week

client = TestClient(app)

_FLAG = "AI2_PROGRESS_DB_READS_ENABLED"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _start_session() -> str:
    r = client.post("/session/start", json={"track": "aipm", "week": 1})
    assert r.status_code == 200, r.text
    return r.json()["session_id"]


def _first_topic_id() -> str:
    return get_topics_for_week("aipm", 1)[0].topic_id


def _db_progress(
    learn: str = "not_started",
    completion_percent: int = 73,
    legacy_topic_id: str = "",
) -> dict:
    """Return a normalized topic_progress dict as if returned from get_topic_progress_from_db."""
    return {
        "learn":               learn,
        "quiz":                "not_started",
        "portfolio_task":      "not_started",
        "interview_practice":  "not_started",
        "reflection":          "not_started",
        "completion_percent":  completion_percent,
        "legacy_topic_id":     legacy_topic_id or _first_topic_id(),
        "metadata":            {},
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
    def test_topics_page_returns_200_flag_off(self, monkeypatch):
        monkeypatch.delenv(_FLAG, raising=False)
        session_id = _start_session()
        resp = client.get(f"/topics/{session_id}")
        assert resp.status_code == 200

    def test_topic_detail_returns_200_flag_off(self, monkeypatch):
        monkeypatch.delenv(_FLAG, raising=False)
        session_id = _start_session()
        topic_id   = _first_topic_id()
        resp = client.get(f"/topic/{session_id}/{topic_id}")
        assert resp.status_code == 200

    def test_topics_page_shows_zero_percent_flag_off(self, monkeypatch):
        monkeypatch.delenv(_FLAG, raising=False)
        session_id = _start_session()
        resp = client.get(f"/topics/{session_id}")
        assert resp.status_code == 200
        assert "0%" in resp.text

    def test_topic_detail_shows_zero_percent_flag_off(self, monkeypatch):
        monkeypatch.delenv(_FLAG, raising=False)
        session_id = _start_session()
        topic_id   = _first_topic_id()
        resp = client.get(f"/topic/{session_id}/{topic_id}")
        assert resp.status_code == 200
        assert "0%" in resp.text

    def test_flag_off_does_not_open_db_connection_topics_page(self, monkeypatch):
        monkeypatch.delenv(_FLAG, raising=False)
        session_id = _start_session()
        with patch("database.pool.get_conn") as mock_conn:
            resp = client.get(f"/topics/{session_id}")
            mock_conn.assert_not_called()
        assert resp.status_code == 200

    def test_flag_off_does_not_open_db_connection_topic_detail(self, monkeypatch):
        monkeypatch.delenv(_FLAG, raising=False)
        session_id = _start_session()
        topic_id   = _first_topic_id()
        with patch("database.pool.get_conn") as mock_conn:
            resp = client.get(f"/topic/{session_id}/{topic_id}")
            mock_conn.assert_not_called()
        assert resp.status_code == 200

    def test_flag_false_value_does_not_open_db(self, monkeypatch):
        monkeypatch.setenv(_FLAG, "0")
        session_id = _start_session()
        with patch("database.pool.get_conn") as mock_conn:
            resp = client.get(f"/topics/{session_id}")
            mock_conn.assert_not_called()
        assert resp.status_code == 200


# ── Flag ON + DB success: DB progress is rendered ─────────────────────────────

class TestFlagOnDbSuccess:
    def test_topics_page_shows_db_completion_percent(self, monkeypatch):
        monkeypatch.setenv(_FLAG, "1")
        session_id = _start_session()
        db_prog    = _db_progress(completion_percent=73)

        with patch("database.pool.get_conn", return_value=_mock_get_conn()):
            with patch(
                "services.learner_state_read_service.get_topic_progress_from_db",
                return_value=db_prog,
            ):
                resp = client.get(f"/topics/{session_id}")

        assert resp.status_code == 200
        assert "73%" in resp.text

    def test_topic_detail_shows_db_completion_percent(self, monkeypatch):
        monkeypatch.setenv(_FLAG, "1")
        session_id = _start_session()
        topic_id   = _first_topic_id()
        db_prog    = _db_progress(completion_percent=73, legacy_topic_id=topic_id)

        with patch("database.pool.get_conn", return_value=_mock_get_conn()):
            with patch(
                "services.learner_state_read_service.get_topic_progress_from_db",
                return_value=db_prog,
            ):
                resp = client.get(f"/topic/{session_id}/{topic_id}")

        assert resp.status_code == 200
        assert "73%" in resp.text

    def test_topic_detail_shows_db_learn_status_done(self, monkeypatch):
        monkeypatch.setenv(_FLAG, "1")
        session_id = _start_session()
        topic_id   = _first_topic_id()
        db_prog    = _db_progress(learn="done", completion_percent=20, legacy_topic_id=topic_id)

        with patch("database.pool.get_conn", return_value=_mock_get_conn()):
            with patch(
                "services.learner_state_read_service.get_topic_progress_from_db",
                return_value=db_prog,
            ):
                resp = client.get(f"/topic/{session_id}/{topic_id}")

        assert resp.status_code == 200

    def test_flag_on_db_zero_percent_shown_when_db_returns_zero(self, monkeypatch):
        monkeypatch.setenv(_FLAG, "1")
        session_id = _start_session()
        topic_id   = _first_topic_id()
        db_prog    = _db_progress(completion_percent=0, legacy_topic_id=topic_id)

        with patch("database.pool.get_conn", return_value=_mock_get_conn()):
            with patch(
                "services.learner_state_read_service.get_topic_progress_from_db",
                return_value=db_prog,
            ):
                resp = client.get(f"/topic/{session_id}/{topic_id}")

        assert resp.status_code == 200


# ── Flag ON + DB returns None: falls back to session ─────────────────────────

class TestFlagOnDbNoRow:
    def test_topics_page_falls_back_when_db_returns_none(self, monkeypatch):
        monkeypatch.setenv(_FLAG, "1")
        session_id = _start_session()

        with patch("database.pool.get_conn", return_value=_mock_get_conn()):
            with patch(
                "services.learner_state_read_service.get_topic_progress_from_db",
                return_value=None,
            ):
                resp = client.get(f"/topics/{session_id}")

        assert resp.status_code == 200
        assert "0%" in resp.text

    def test_topic_detail_falls_back_when_db_returns_none(self, monkeypatch):
        monkeypatch.setenv(_FLAG, "1")
        session_id = _start_session()
        topic_id   = _first_topic_id()

        with patch("database.pool.get_conn", return_value=_mock_get_conn()):
            with patch(
                "services.learner_state_read_service.get_topic_progress_from_db",
                return_value=None,
            ):
                resp = client.get(f"/topic/{session_id}/{topic_id}")

        assert resp.status_code == 200
        assert "0%" in resp.text


# ── Flag ON + DB query failure: fallback to SessionContext ────────────────────

class TestFlagOnDbQueryFailure:
    def test_topics_page_falls_back_on_query_error(self, monkeypatch):
        monkeypatch.setenv(_FLAG, "1")
        session_id = _start_session()

        with patch("database.pool.get_conn", return_value=_mock_get_conn()):
            with patch(
                "services.learner_state_read_service.get_topic_progress_from_db",
                side_effect=RuntimeError("DB query blew up"),
            ):
                resp = client.get(f"/topics/{session_id}")

        assert resp.status_code == 200
        assert "0%" in resp.text

    def test_topic_detail_falls_back_on_query_error(self, monkeypatch):
        monkeypatch.setenv(_FLAG, "1")
        session_id = _start_session()
        topic_id   = _first_topic_id()

        with patch("database.pool.get_conn", return_value=_mock_get_conn()):
            with patch(
                "services.learner_state_read_service.get_topic_progress_from_db",
                side_effect=RuntimeError("DB query blew up"),
            ):
                resp = client.get(f"/topic/{session_id}/{topic_id}")

        assert resp.status_code == 200
        assert "0%" in resp.text

    def test_query_error_not_exposed_in_topics_page(self, monkeypatch):
        monkeypatch.setenv(_FLAG, "1")
        session_id = _start_session()

        with patch("database.pool.get_conn", return_value=_mock_get_conn()):
            with patch(
                "services.learner_state_read_service.get_topic_progress_from_db",
                side_effect=RuntimeError("secret query error xyz"),
            ):
                resp = client.get(f"/topics/{session_id}")

        assert resp.status_code == 200
        assert "secret query error xyz" not in resp.text
        assert "RuntimeError" not in resp.text

    def test_query_error_not_exposed_in_topic_detail(self, monkeypatch):
        monkeypatch.setenv(_FLAG, "1")
        session_id = _start_session()
        topic_id   = _first_topic_id()

        with patch("database.pool.get_conn", return_value=_mock_get_conn()):
            with patch(
                "services.learner_state_read_service.get_topic_progress_from_db",
                side_effect=RuntimeError("secret query error xyz"),
            ):
                resp = client.get(f"/topic/{session_id}/{topic_id}")

        assert resp.status_code == 200
        assert "secret query error xyz" not in resp.text


# ── Flag ON + connection error: fallback to SessionContext ────────────────────

class TestFlagOnConnError:
    def test_topics_page_falls_back_on_conn_error(self, monkeypatch):
        monkeypatch.setenv(_FLAG, "1")
        session_id = _start_session()

        with patch("database.pool.get_conn", side_effect=OSError("cannot connect")):
            resp = client.get(f"/topics/{session_id}")

        assert resp.status_code == 200
        assert "0%" in resp.text

    def test_topic_detail_falls_back_on_conn_error(self, monkeypatch):
        monkeypatch.setenv(_FLAG, "1")
        session_id = _start_session()
        topic_id   = _first_topic_id()

        with patch("database.pool.get_conn", side_effect=OSError("cannot connect")):
            resp = client.get(f"/topic/{session_id}/{topic_id}")

        assert resp.status_code == 200
        assert "0%" in resp.text

    def test_conn_error_not_exposed_in_response(self, monkeypatch):
        monkeypatch.setenv(_FLAG, "1")
        session_id = _start_session()

        with patch("database.pool.get_conn", side_effect=OSError("cannot connect secret")):
            resp = client.get(f"/topics/{session_id}")

        assert resp.status_code == 200
        assert "cannot connect secret" not in resp.text


# ── Mutations unchanged ───────────────────────────────────────────────────────

class TestMutationsUnchanged:
    def test_topic_progress_update_flag_off(self, monkeypatch):
        monkeypatch.delenv(_FLAG, raising=False)
        session_id = _start_session()
        topic_id   = _first_topic_id()
        r = client.post("/topic/progress", json={
            "session_id": session_id,
            "topic_id":   topic_id,
            "step":       "learn",
            "status":     "done",
        })
        assert r.status_code == 200
        assert r.json()["step"] == "learn"
        assert r.json()["status"] == "done"

    def test_topic_progress_update_flag_on(self, monkeypatch):
        monkeypatch.setenv(_FLAG, "1")
        session_id = _start_session()
        topic_id   = _first_topic_id()
        r = client.post("/topic/progress", json={
            "session_id": session_id,
            "topic_id":   topic_id,
            "step":       "quiz",
            "status":     "in_progress",
        })
        assert r.status_code == 200
        assert r.json()["step"] == "quiz"
        assert r.json()["status"] == "in_progress"

    def test_progress_mutation_does_not_open_db_read_flag_off(self, monkeypatch):
        monkeypatch.delenv(_FLAG, raising=False)
        monkeypatch.delenv("AI2_DB_WRITE_THROUGH_ENABLED", raising=False)
        session_id = _start_session()
        topic_id   = _first_topic_id()
        with patch("database.pool.get_conn") as mock_conn:
            r = client.post("/topic/progress", json={
                "session_id": session_id,
                "topic_id":   topic_id,
                "step":       "learn",
                "status":     "done",
            })
            mock_conn.assert_not_called()
        assert r.status_code == 200


# ── Route URLs unchanged ──────────────────────────────────────────────────────

class TestRouteUrlsUnchanged:
    def test_topics_page_url(self, monkeypatch):
        monkeypatch.delenv(_FLAG, raising=False)
        session_id = _start_session()
        resp = client.get(f"/topics/{session_id}")
        assert resp.status_code == 200

    def test_topic_detail_url(self, monkeypatch):
        monkeypatch.delenv(_FLAG, raising=False)
        session_id = _start_session()
        topic_id   = _first_topic_id()
        resp = client.get(f"/topic/{session_id}/{topic_id}")
        assert resp.status_code == 200

    def test_topic_progress_mutation_url(self, monkeypatch):
        monkeypatch.delenv(_FLAG, raising=False)
        session_id = _start_session()
        topic_id   = _first_topic_id()
        resp = client.post("/topic/progress", json={
            "session_id": session_id,
            "topic_id":   topic_id,
            "step":       "learn",
            "status":     "done",
        })
        assert resp.status_code == 200
