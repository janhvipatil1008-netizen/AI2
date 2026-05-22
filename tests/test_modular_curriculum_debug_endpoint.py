"""Tests for GET /debug/modular-curriculum.

Verifies that the endpoint:
- exists and is accessible in non-production without a token
- is protected in production by the debug token gate
- returns course_structure in course mode
- returns topic in topic mode
- uses source="db" when DB succeeds
- falls back safely when DB connection fails
- uses at most one DB connection
- never exposes DB URLs or secrets in error responses
- never calls session helpers (_get_session_data, _save_session)
- never invokes Claude / Anthropic API
- does not mutate WEEKS or ROLE_TRACKS
- does not change any existing runtime route URLs
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

os.environ["AI2_TEST_MODE"]     = "1"
os.environ["ANTHROPIC_API_KEY"] = "test-key"

from fastapi.testclient import TestClient

from app import app

client = TestClient(app)

URL   = "/debug/modular-curriculum"
_TOKEN = "test-debug-token-xyz"

_FALLBACK_SVC = "services.modular_curriculum_fallback_service"

# ── Fake helpers ──────────────────────────────────────────────────────────────


def _make_conn():
    conn = MagicMock()
    conn.close = MagicMock()
    return conn


def _fake_get_conn(conn):
    """Context manager that yields conn and calls conn.close() on exit."""
    @contextmanager
    def _ctx():
        try:
            yield conn
        finally:
            conn.close()
    return _ctx


def _fake_get_conn_raises(exc):
    """Context manager that raises exc immediately on entry."""
    @contextmanager
    def _ctx():
        raise exc
        yield  # pragma: no cover
    return _ctx


def _fake_course_result(source="db"):
    return {
        "source": source,
        "course_structure": {
            "course": {
                "course_id":   1,
                "course_key":  "aipm-foundations",
                "title":       "AI PM Foundations",
                "description": "",
                "status":      "active",
            },
            "modules":           [],
            "unassigned_topics": [],
        },
        "error": None,
    }


def _fake_topic_result(source="db"):
    return {
        "source": source,
        "topic": {
            "topic_id":        42,
            "legacy_topic_id": "aipm-week-1-ai-vs-ml-vs-dl",
            "topic_key":       "ai-vs-ml-vs-dl",
            "title":           "AI vs ML vs DL",
            "skills":          [],
            "activities":      [],
        },
        "error": None,
    }


def _fake_fallback_course_result():
    return {
        "source": "fallback",
        "course_structure": {
            "course":            {"course_key": "aipm-foundations", "course_id": None},
            "modules":           [],
            "unassigned_topics": [],
        },
        "error": None,
    }


def _fake_error_fallback_course_result():
    return {
        "source": "error_fallback",
        "course_structure": {
            "course":            {"course_key": "aipm-foundations", "course_id": None},
            "modules":           [],
            "unassigned_topics": [],
        },
        "error": "RuntimeError: query failed",
    }


# ── Endpoint exists ───────────────────────────────────────────────────────────

class TestEndpointExists:
    def test_endpoint_accessible_in_dev(self, monkeypatch):
        monkeypatch.delenv("AI2_ENV", raising=False)
        conn = _make_conn()
        with patch("app.get_conn", _fake_get_conn(conn)), \
             patch(f"{_FALLBACK_SVC}.get_course_structure_with_fallback",
                   return_value=_fake_course_result()):
            resp = client.get(URL)
        assert resp.status_code == 200

    def test_endpoint_returns_json(self, monkeypatch):
        monkeypatch.delenv("AI2_ENV", raising=False)
        conn = _make_conn()
        with patch("app.get_conn", _fake_get_conn(conn)), \
             patch(f"{_FALLBACK_SVC}.get_course_structure_with_fallback",
                   return_value=_fake_course_result()):
            resp = client.get(URL)
        assert resp.headers["content-type"].startswith("application/json")

    def test_endpoint_default_course_key(self, monkeypatch):
        monkeypatch.delenv("AI2_ENV", raising=False)
        conn = _make_conn()
        with patch("app.get_conn", _fake_get_conn(conn)), \
             patch(f"{_FALLBACK_SVC}.get_course_structure_with_fallback",
                   return_value=_fake_course_result()) as mock_fn:
            client.get(URL)
        mock_fn.assert_called_once()
        _, kwargs = mock_fn.call_args
        assert kwargs.get("course_key") == "aipm-foundations"


# ── Production protection ─────────────────────────────────────────────────────

class TestProductionProtection:
    def test_blocked_in_production_no_token_configured(self, monkeypatch):
        monkeypatch.setenv("AI2_ENV", "production")
        monkeypatch.delenv("AI2_DEBUG_TOKEN", raising=False)
        resp = client.get(URL)
        assert resp.status_code == 404

    def test_blocked_in_production_no_header(self, monkeypatch):
        monkeypatch.setenv("AI2_ENV", "production")
        monkeypatch.setenv("AI2_DEBUG_TOKEN", _TOKEN)
        resp = client.get(URL)
        assert resp.status_code == 404

    def test_blocked_in_production_wrong_token(self, monkeypatch):
        monkeypatch.setenv("AI2_ENV", "production")
        monkeypatch.setenv("AI2_DEBUG_TOKEN", _TOKEN)
        resp = client.get(URL, headers={"X-AI2-Debug-Token": "wrong-token"})
        assert resp.status_code == 404

    def test_allowed_in_production_correct_token(self, monkeypatch):
        monkeypatch.setenv("AI2_ENV", "production")
        monkeypatch.setenv("AI2_DEBUG_TOKEN", _TOKEN)
        conn = _make_conn()
        with patch("app.get_conn", _fake_get_conn(conn)), \
             patch(f"{_FALLBACK_SVC}.get_course_structure_with_fallback",
                   return_value=_fake_course_result()):
            resp = client.get(URL, headers={"X-AI2-Debug-Token": _TOKEN})
        assert resp.status_code == 200

    def test_allowed_in_dev_without_token(self, monkeypatch):
        monkeypatch.delenv("AI2_ENV", raising=False)
        conn = _make_conn()
        with patch("app.get_conn", _fake_get_conn(conn)), \
             patch(f"{_FALLBACK_SVC}.get_course_structure_with_fallback",
                   return_value=_fake_course_result()):
            resp = client.get(URL)
        assert resp.status_code == 200


# ── Course mode ───────────────────────────────────────────────────────────────

class TestCourseModeDB:
    def test_course_mode_returns_course_mode_field(self):
        conn = _make_conn()
        with patch("app.get_conn", _fake_get_conn(conn)), \
             patch(f"{_FALLBACK_SVC}.get_course_structure_with_fallback",
                   return_value=_fake_course_result("db")):
            body = client.get(URL).json()
        assert body["mode"] == "course"

    def test_course_mode_db_success_source_is_db(self):
        conn = _make_conn()
        with patch("app.get_conn", _fake_get_conn(conn)), \
             patch(f"{_FALLBACK_SVC}.get_course_structure_with_fallback",
                   return_value=_fake_course_result("db")):
            body = client.get(URL).json()
        assert body["source"] == "db"

    def test_course_mode_returns_course_structure(self):
        conn = _make_conn()
        with patch("app.get_conn", _fake_get_conn(conn)), \
             patch(f"{_FALLBACK_SVC}.get_course_structure_with_fallback",
                   return_value=_fake_course_result("db")):
            body = client.get(URL).json()
        assert "course_structure" in body
        assert body["course_structure"]["course"]["course_key"] == "aipm-foundations"

    def test_course_mode_returns_course_key_field(self):
        conn = _make_conn()
        with patch("app.get_conn", _fake_get_conn(conn)), \
             patch(f"{_FALLBACK_SVC}.get_course_structure_with_fallback",
                   return_value=_fake_course_result("db")):
            body = client.get(URL).json()
        assert "course_key" in body

    def test_course_mode_error_is_none_on_success(self):
        conn = _make_conn()
        with patch("app.get_conn", _fake_get_conn(conn)), \
             patch(f"{_FALLBACK_SVC}.get_course_structure_with_fallback",
                   return_value=_fake_course_result("db")):
            body = client.get(URL).json()
        assert body["error"] is None

    def test_course_mode_passes_course_key_to_service(self):
        conn = _make_conn()
        with patch("app.get_conn", _fake_get_conn(conn)), \
             patch(f"{_FALLBACK_SVC}.get_course_structure_with_fallback",
                   return_value=_fake_course_result("db")) as mock_fn:
            client.get(f"{URL}?course_key=evals-foundations")
        _, kwargs = mock_fn.call_args
        assert kwargs.get("course_key") == "evals-foundations"

    def test_course_mode_has_notes_list(self):
        conn = _make_conn()
        with patch("app.get_conn", _fake_get_conn(conn)), \
             patch(f"{_FALLBACK_SVC}.get_course_structure_with_fallback",
                   return_value=_fake_course_result("db")):
            body = client.get(URL).json()
        assert "notes" in body
        assert isinstance(body["notes"], list)


# ── Topic mode ────────────────────────────────────────────────────────────────

class TestTopicMode:
    _LEGACY_ID = "aipm-week-1-ai-vs-ml-vs-dl"

    def test_topic_mode_returns_topic_mode_field(self):
        conn = _make_conn()
        with patch("app.get_conn", _fake_get_conn(conn)), \
             patch(f"{_FALLBACK_SVC}.get_topic_structure_by_legacy_id_with_fallback",
                   return_value=_fake_topic_result("db")):
            body = client.get(f"{URL}?legacy_topic_id={self._LEGACY_ID}").json()
        assert body["mode"] == "topic"

    def test_topic_mode_db_success_source_is_db(self):
        conn = _make_conn()
        with patch("app.get_conn", _fake_get_conn(conn)), \
             patch(f"{_FALLBACK_SVC}.get_topic_structure_by_legacy_id_with_fallback",
                   return_value=_fake_topic_result("db")):
            body = client.get(f"{URL}?legacy_topic_id={self._LEGACY_ID}").json()
        assert body["source"] == "db"

    def test_topic_mode_returns_topic_dict(self):
        conn = _make_conn()
        with patch("app.get_conn", _fake_get_conn(conn)), \
             patch(f"{_FALLBACK_SVC}.get_topic_structure_by_legacy_id_with_fallback",
                   return_value=_fake_topic_result("db")):
            body = client.get(f"{URL}?legacy_topic_id={self._LEGACY_ID}").json()
        assert "topic" in body
        assert body["topic"]["legacy_topic_id"] == self._LEGACY_ID

    def test_topic_mode_returns_legacy_topic_id_field(self):
        conn = _make_conn()
        with patch("app.get_conn", _fake_get_conn(conn)), \
             patch(f"{_FALLBACK_SVC}.get_topic_structure_by_legacy_id_with_fallback",
                   return_value=_fake_topic_result("db")):
            body = client.get(f"{URL}?legacy_topic_id={self._LEGACY_ID}").json()
        assert body["legacy_topic_id"] == self._LEGACY_ID

    def test_topic_mode_passes_legacy_topic_id_to_service(self):
        conn = _make_conn()
        with patch("app.get_conn", _fake_get_conn(conn)), \
             patch(f"{_FALLBACK_SVC}.get_topic_structure_by_legacy_id_with_fallback",
                   return_value=_fake_topic_result("db")) as mock_fn:
            client.get(f"{URL}?legacy_topic_id={self._LEGACY_ID}")
        _, kwargs = mock_fn.call_args
        assert kwargs.get("legacy_topic_id") == self._LEGACY_ID

    def test_topic_mode_does_not_return_course_structure(self):
        conn = _make_conn()
        with patch("app.get_conn", _fake_get_conn(conn)), \
             patch(f"{_FALLBACK_SVC}.get_topic_structure_by_legacy_id_with_fallback",
                   return_value=_fake_topic_result("db")):
            body = client.get(f"{URL}?legacy_topic_id={self._LEGACY_ID}").json()
        assert "course_structure" not in body


# ── Fallback behaviour ────────────────────────────────────────────────────────

class TestFallback:
    def test_db_conn_failure_returns_200(self):
        with patch("app.get_conn", _fake_get_conn_raises(RuntimeError("timeout"))):
            resp = client.get(URL)
        assert resp.status_code == 200

    def test_db_conn_failure_source_is_fallback(self):
        with patch("app.get_conn", _fake_get_conn_raises(RuntimeError("timeout"))):
            body = client.get(URL).json()
        assert body["source"] in ("fallback", "error_fallback")

    def test_db_conn_failure_still_returns_course_structure(self):
        with patch("app.get_conn", _fake_get_conn_raises(RuntimeError("timeout"))):
            body = client.get(URL).json()
        assert body["course_structure"] is not None

    def test_db_conn_failure_fallback_calls_service_with_none_conn(self):
        """When get_conn raises, fallback service must be called with conn=None."""
        with patch("app.get_conn", _fake_get_conn_raises(RuntimeError("db down"))), \
             patch(f"{_FALLBACK_SVC}.get_course_structure_with_fallback",
                   return_value=_fake_fallback_course_result()) as mock_fn:
            client.get(URL)
        # Verify it was called with conn=None for the fallback path
        calls = mock_fn.call_args_list
        # Should have been called once with conn=None (after get_conn raised)
        none_conn_calls = [c for c in calls if c.args and c.args[0] is None]
        assert len(none_conn_calls) == 1

    def test_fallback_source_shown_in_response(self):
        conn = _make_conn()
        with patch("app.get_conn", _fake_get_conn(conn)), \
             patch(f"{_FALLBACK_SVC}.get_course_structure_with_fallback",
                   return_value=_fake_fallback_course_result()):
            body = client.get(URL).json()
        assert body["source"] == "fallback"

    def test_fallback_uses_static_curriculum_when_db_unavailable(self):
        """With no DB, endpoint still returns course structure from static data."""
        with patch("app.get_conn", _fake_get_conn_raises(RuntimeError("no db"))):
            body = client.get(URL).json()
        cs = body["course_structure"]
        assert cs is not None
        assert "modules" in cs


# ── One DB connection max ─────────────────────────────────────────────────────

class TestOneConnectionMax:
    def test_get_conn_called_at_most_once_on_success(self):
        conn = _make_conn()
        mock_gc = MagicMock(side_effect=_fake_get_conn(conn))
        with patch("app.get_conn", mock_gc), \
             patch(f"{_FALLBACK_SVC}.get_course_structure_with_fallback",
                   return_value=_fake_course_result("db")):
            client.get(URL)
        assert mock_gc.call_count <= 1

    def test_get_conn_called_at_most_once_on_failure(self):
        call_count = 0
        @contextmanager
        def _counting_ctx():
            nonlocal call_count
            call_count += 1
            raise RuntimeError("fail")
            yield  # pragma: no cover

        with patch("app.get_conn", _counting_ctx):
            client.get(URL)
        assert call_count <= 1

    def test_conn_closed_on_success(self):
        conn = _make_conn()
        with patch("app.get_conn", _fake_get_conn(conn)), \
             patch(f"{_FALLBACK_SVC}.get_course_structure_with_fallback",
                   return_value=_fake_course_result("db")):
            client.get(URL)
        conn.close.assert_called_once()


# ── Safety: no secrets or private data ───────────────────────────────────────

class TestSafety:
    def test_db_url_not_in_error_response(self):
        db_url = "postgresql://user:secret_pw@db.host:5432/mydb"
        with patch("app.get_conn",
                   _fake_get_conn_raises(RuntimeError(f"connect failed: {db_url}"))):
            resp = client.get(URL)
        body = resp.text
        assert "postgresql://" not in body
        assert "secret_pw" not in body

    def test_supabase_database_url_env_name_not_in_response(self, monkeypatch):
        monkeypatch.setenv("SUPABASE_DATABASE_URL", "postgresql://u:p@h/d")
        with patch("app.get_conn",
                   _fake_get_conn_raises(RuntimeError("SUPABASE_DATABASE_URL=postgresql://u:p@h/d"))):
            resp = client.get(URL)
        assert "SUPABASE_DATABASE_URL" not in resp.text or "[redacted]" in resp.text

    def test_anthropic_key_not_in_response(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-super-secret")
        with patch("app.get_conn",
                   _fake_get_conn_raises(RuntimeError("ANTHROPIC_API_KEY=sk-ant-super-secret"))):
            resp = client.get(URL)
        assert "sk-ant-super-secret" not in resp.text

    def test_no_session_data_in_course_response(self):
        conn = _make_conn()
        with patch("app.get_conn", _fake_get_conn(conn)), \
             patch(f"{_FALLBACK_SVC}.get_course_structure_with_fallback",
                   return_value=_fake_course_result("db")):
            body = client.get(URL).json()
        # Debug endpoint must not return session-related fields
        for forbidden in ("session_id", "user_id", "topic_progress",
                          "todos", "submissions", "notes_content"):
            assert forbidden not in body, f"Session field {forbidden!r} found in response"

    def test_no_get_session_data_called(self):
        conn = _make_conn()
        with patch("app.get_conn", _fake_get_conn(conn)), \
             patch(f"{_FALLBACK_SVC}.get_course_structure_with_fallback",
                   return_value=_fake_course_result("db")), \
             patch("app._get_session_data") as mock_session:
            client.get(URL)
        mock_session.assert_not_called()

    def test_no_save_session_called(self):
        conn = _make_conn()
        with patch("app.get_conn", _fake_get_conn(conn)), \
             patch(f"{_FALLBACK_SVC}.get_course_structure_with_fallback",
                   return_value=_fake_course_result("db")), \
             patch("app._save_session") as mock_save:
            client.get(URL)
        mock_save.assert_not_called()

    def test_no_claude_call_on_course_mode(self):
        conn = _make_conn()
        with patch("app.get_conn", _fake_get_conn(conn)), \
             patch(f"{_FALLBACK_SVC}.get_course_structure_with_fallback",
                   return_value=_fake_course_result("db")), \
             patch("app.Orchestrator") as mock_orch:
            client.get(URL)
        mock_orch.assert_not_called()

    def test_response_has_notes_field(self):
        conn = _make_conn()
        with patch("app.get_conn", _fake_get_conn(conn)), \
             patch(f"{_FALLBACK_SVC}.get_course_structure_with_fallback",
                   return_value=_fake_course_result("db")):
            body = client.get(URL).json()
        assert "notes" in body
        assert any("static" in n.lower() or "runtime" in n.lower() for n in body["notes"])


# ── WEEKS / ROLE_TRACKS not mutated ──────────────────────────────────────────

class TestNoMutation:
    def test_role_tracks_not_mutated_after_course_request(self):
        from curriculum.syllabus import ROLE_TRACKS
        keys_before = list(ROLE_TRACKS.keys())
        with patch("app.get_conn", _fake_get_conn_raises(RuntimeError("no db"))):
            client.get(URL)
        assert list(ROLE_TRACKS.keys()) == keys_before

    def test_weeks_not_mutated_after_course_request(self):
        from curriculum.syllabus import WEEKS
        len_before = len(WEEKS)
        with patch("app.get_conn", _fake_get_conn_raises(RuntimeError("no db"))):
            client.get(URL)
        assert len(WEEKS) == len_before


# ── Existing routes unchanged ─────────────────────────────────────────────────

class TestRuntimeRoutesUnchanged:
    def test_health_still_accessible(self):
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_existing_curriculum_debug_still_works(self, monkeypatch):
        monkeypatch.delenv("AI2_ENV", raising=False)
        with patch("services.storage_flags.is_curriculum_db_reads_enabled",
                   return_value=False):
            resp = client.get("/debug/curriculum-db-check")
        assert resp.status_code == 200

    def test_storage_status_still_accessible(self, monkeypatch):
        monkeypatch.delenv("AI2_ENV", raising=False)
        resp = client.get("/debug/storage-status")
        assert resp.status_code == 200

    def test_new_endpoint_does_not_change_existing_urls(self):
        """Hitting the new endpoint URL returns 200, not a redirect or error at /debug."""
        with patch("app.get_conn", _fake_get_conn_raises(RuntimeError("no db"))):
            resp = client.get(URL)
        assert resp.status_code == 200
        assert resp.json()["mode"] == "course"
