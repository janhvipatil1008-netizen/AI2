"""Split tests for generated-learning and usage-events debug routes."""

from __future__ import annotations

import os
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

os.environ["AI2_TEST_MODE"] = "1"
os.environ["ANTHROPIC_API_KEY"] = "test-key"

from fastapi.testclient import TestClient

import routes.debug as _debug_module
from app import app


client = TestClient(app)

TOKEN = "generated-usage-split-token"
URL_GENERATED_DB = "/debug/generated-learning-db-check"
URL_USAGE_DB = "/debug/usage-events-db-check"
URL_USAGE_MISMATCH = "/debug/usage-events-mismatch-check"
URL_GENERATED_MISMATCH = "/debug/generated-learning-mismatch-check"
MOVED_URLS = (
    URL_GENERATED_DB,
    URL_USAGE_DB,
    URL_USAGE_MISMATCH,
    URL_GENERATED_MISMATCH,
)


def _source(path: str) -> str:
    with open(path, encoding="utf-8") as f:
        return f.read()


def _app_source() -> str:
    return _source(os.path.join(os.path.dirname(__file__), "..", "app.py"))


def _debug_source() -> str:
    return _source(os.path.join(os.path.dirname(__file__), "..", "routes", "debug.py"))


def _make_conn():
    conn = MagicMock()
    conn.close = MagicMock()
    return conn


def _fake_get_conn(conn):
    @contextmanager
    def _ctx():
        try:
            yield conn
        finally:
            conn.close()

    return _ctx


def _fake_get_conn_raises(exc):
    @contextmanager
    def _ctx():
        raise exc
        yield  # pragma: no cover

    return _ctx


def _empty_generated_state():
    return {
        "generated_topic_content": None,
        "generated_topic_practice": {
            "quiz": None,
            "portfolio_task": None,
            "interview_practice": None,
        },
        "quiz_submission": None,
        "portfolio_submission": None,
        "interview_submission": None,
        "topic_notes": None,
    }


def _private_generated_state():
    return {
        "generated_topic_content": {"content": "PRIVATE GENERATED CONTENT", "metadata": {"secret": "x"}},
        "generated_topic_practice": {
            "quiz": {"content": "PRIVATE QUIZ", "metadata": {"secret": "x"}},
            "portfolio_task": None,
            "interview_practice": None,
        },
        "quiz_submission": {"answers": "PRIVATE ANSWERS", "evaluation": "PRIVATE EVAL"},
        "portfolio_submission": {"submission": "PRIVATE SUBMISSION", "feedback": "PRIVATE FEEDBACK"},
        "interview_submission": {"answer": "PRIVATE INTERVIEW", "feedback": "PRIVATE REVIEW"},
        "topic_notes": {"reflection": "PRIVATE NOTES", "application_idea": "PRIVATE IDEA"},
    }


def _summary():
    return {
        "total_events": 0,
        "claude_events": 0,
        "cache_events": 0,
        "test_mode_events": 0,
        "error_events": 0,
        "by_event_type": {},
    }


def _session_data():
    return {"session": object(), "orch": None, "client": None, "profile": None}


def _comparison(matches=True):
    return {"matches": matches, "comparisons": []}


def _params_for(url: str) -> dict:
    if url in (URL_GENERATED_DB, URL_GENERATED_MISMATCH):
        return {"session_id": "sess-1", "legacy_topic_id": "topic-1"}
    return {"session_id": "sess-1"}


def test_routes_debug_contains_moved_routes():
    assert callable(getattr(_debug_module, "debug_generated_learning_db_check", None))
    assert callable(getattr(_debug_module, "debug_usage_events_db_check", None))
    assert callable(getattr(_debug_module, "debug_usage_events_mismatch_check", None))
    assert callable(getattr(_debug_module, "debug_generated_learning_mismatch_check", None))

    debug_source = _debug_source()
    for url in MOVED_URLS:
        assert f'@router.get("{url}")' in debug_source


def test_app_includes_debug_router_and_route_urls_are_unchanged():
    assert "app.include_router(debug_router)" in _app_source()
    paths = {route.path for route in app.routes}
    for url in MOVED_URLS:
        assert url in paths


def test_app_no_longer_directly_defines_moved_route_handlers():
    app_source = _app_source()
    for url in MOVED_URLS:
        assert f'@app.get("{url}")' not in app_source

    for name in (
        "debug_generated_learning_db_check",
        "debug_usage_events_db_check",
        "debug_usage_events_mismatch_check",
        "debug_generated_learning_mismatch_check",
    ):
        assert f"async def {name}" not in app_source


def test_production_missing_or_wrong_token_returns_404(monkeypatch):
    monkeypatch.setenv("AI2_ENV", "production")
    monkeypatch.setenv("AI2_DEBUG_TOKEN", TOKEN)

    for url in MOVED_URLS:
        assert client.get(url, params=_params_for(url)).status_code == 404
        assert client.get(
            url,
            params=_params_for(url),
            headers={"X-AI2-Debug-Token": "wrong"},
        ).status_code == 404


def test_correct_token_allows_moved_routes(monkeypatch):
    monkeypatch.setenv("AI2_ENV", "production")
    monkeypatch.setenv("AI2_DEBUG_TOKEN", TOKEN)
    headers = {"X-AI2-Debug-Token": TOKEN}
    conn = _make_conn()

    with patch("routes.debug.get_conn", _fake_get_conn(conn)), patch(
        "services.generated_learning_read_service.get_generated_learning_state_from_db",
        return_value=_empty_generated_state(),
    ):
        assert client.get(URL_GENERATED_DB, params=_params_for(URL_GENERATED_DB), headers=headers).status_code == 200

    with patch("routes.debug.get_conn", _fake_get_conn(conn)), patch(
        "repositories.usage_events_repository.list_usage_events_for_session",
        return_value=[],
    ), patch(
        "repositories.usage_events_repository.usage_event_summary_for_session",
        return_value=_summary(),
    ):
        assert client.get(URL_USAGE_DB, params=_params_for(URL_USAGE_DB), headers=headers).status_code == 200

    with patch("routes.deps.get_session_data", return_value=_session_data()), patch(
        "routes.debug.get_conn", _fake_get_conn(conn)
    ), patch(
        "repositories.usage_events_repository.list_usage_events_for_session",
        return_value=[],
    ), patch(
        "repositories.usage_events_repository.usage_event_summary_for_session",
        return_value=_summary(),
    ), patch(
        "services.usage_events_mismatch_service.compare_usage_events_state",
        return_value=_comparison(True),
    ):
        assert client.get(URL_USAGE_MISMATCH, params=_params_for(URL_USAGE_MISMATCH), headers=headers).status_code == 200

    with patch("routes.deps.get_session_data", return_value=_session_data()), patch(
        "routes.debug.get_conn", _fake_get_conn(conn)
    ), patch(
        "services.generated_learning_read_service.get_generated_learning_state_from_db",
        return_value=_empty_generated_state(),
    ), patch(
        "services.generated_learning_mismatch_service.compare_generated_learning_state",
        return_value=_comparison(True),
    ):
        assert client.get(
            URL_GENERATED_MISMATCH,
            params=_params_for(URL_GENERATED_MISMATCH),
            headers=headers,
        ).status_code == 200


def test_unauthorized_requests_do_not_open_db_connection(monkeypatch):
    monkeypatch.setenv("AI2_ENV", "production")
    monkeypatch.delenv("AI2_DEBUG_TOKEN", raising=False)

    with patch("routes.debug.get_conn", side_effect=AssertionError("DB must not open")) as get_conn:
        for url in MOVED_URLS:
            assert client.get(url, params=_params_for(url)).status_code == 404

    get_conn.assert_not_called()


def test_response_shapes_are_unchanged(monkeypatch):
    monkeypatch.delenv("AI2_ENV", raising=False)
    conn = _make_conn()

    with patch("routes.debug.get_conn", _fake_get_conn(conn)), patch(
        "services.generated_learning_read_service.get_generated_learning_state_from_db",
        return_value=_empty_generated_state(),
    ):
        data = client.get(URL_GENERATED_DB, params=_params_for(URL_GENERATED_DB)).json()
    assert set(data) == {
        "session_id", "legacy_topic_id", "attempted_db_connection",
        "source", "state_found", "state", "error", "notes",
    }

    with patch("routes.debug.get_conn", _fake_get_conn(conn)), patch(
        "repositories.usage_events_repository.list_usage_events_for_session",
        return_value=[],
    ), patch(
        "repositories.usage_events_repository.usage_event_summary_for_session",
        return_value=_summary(),
    ):
        data = client.get(URL_USAGE_DB, params=_params_for(URL_USAGE_DB)).json()
    assert set(data) == {
        "session_id", "attempted_db_connection", "source", "events_count",
        "summary", "events", "error", "notes",
    }

    with patch("routes.deps.get_session_data", return_value=_session_data()), patch(
        "routes.debug.get_conn", _fake_get_conn(conn)
    ), patch(
        "repositories.usage_events_repository.list_usage_events_for_session",
        return_value=[],
    ), patch(
        "repositories.usage_events_repository.usage_event_summary_for_session",
        return_value=_summary(),
    ), patch(
        "services.usage_events_mismatch_service.compare_usage_events_state",
        return_value=_comparison(True),
    ):
        data = client.get(URL_USAGE_MISMATCH, params=_params_for(URL_USAGE_MISMATCH)).json()
    assert set(data) == {
        "session_id", "attempted_db_connection", "source", "matches",
        "comparison", "error", "notes",
    }

    with patch("routes.deps.get_session_data", return_value=_session_data()), patch(
        "routes.debug.get_conn", _fake_get_conn(conn)
    ), patch(
        "services.generated_learning_read_service.get_generated_learning_state_from_db",
        return_value=_empty_generated_state(),
    ), patch(
        "services.generated_learning_mismatch_service.compare_generated_learning_state",
        return_value=_comparison(True),
    ):
        data = client.get(URL_GENERATED_MISMATCH, params=_params_for(URL_GENERATED_MISMATCH)).json()
    assert set(data) == {
        "session_id", "legacy_topic_id", "attempted_db_connection",
        "source", "matches", "comparison", "error", "notes",
    }


def test_safe_error_response_does_not_expose_secrets(monkeypatch):
    monkeypatch.delenv("AI2_ENV", raising=False)
    secret_url = "postgresql://user:secret@host/db"
    monkeypatch.setenv("SUPABASE_DATABASE_URL", secret_url)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-live-secret")

    exc = RuntimeError(f"failed {secret_url} ANTHROPIC_API_KEY=sk-live-secret Traceback line")
    with patch("routes.debug.get_conn", _fake_get_conn_raises(exc)):
        response = client.get(URL_USAGE_DB, params=_params_for(URL_USAGE_DB))

    assert response.status_code == 200
    for forbidden in (
        "postgresql://",
        "user:secret",
        "sk-live-secret",
        "SUPABASE_DATABASE_URL",
        "ANTHROPIC_API_KEY",
        "Traceback",
    ):
        assert forbidden not in response.text


def test_generated_db_response_does_not_expose_private_content(monkeypatch):
    monkeypatch.delenv("AI2_ENV", raising=False)
    conn = _make_conn()

    with patch("routes.debug.get_conn", _fake_get_conn(conn)), patch(
        "services.generated_learning_read_service.get_generated_learning_state_from_db",
        return_value=_private_generated_state(),
    ):
        response = client.get(URL_GENERATED_DB, params=_params_for(URL_GENERATED_DB))

    assert response.status_code == 200
    for forbidden in (
        "PRIVATE GENERATED CONTENT",
        "PRIVATE QUIZ",
        "PRIVATE ANSWERS",
        "PRIVATE SUBMISSION",
        "PRIVATE INTERVIEW",
        "PRIVATE NOTES",
        '"secret"',
    ):
        assert forbidden not in response.text


def test_existing_debug_routes_still_work(monkeypatch):
    monkeypatch.delenv("AI2_ENV", raising=False)
    assert client.get("/debug/storage-status").status_code == 200
    assert client.get("/debug/storage-health").status_code == 200

    with patch("services.storage_flags.is_curriculum_db_reads_enabled", return_value=False):
        assert client.get("/debug/curriculum-db-check").status_code == 200

    with patch("services.storage_flags.is_progress_db_reads_enabled", return_value=False), patch(
        "services.storage_flags.is_todos_db_reads_enabled",
        return_value=False,
    ):
        assert client.get("/debug/learner-state-db-check").status_code == 200


def test_admin_beta_metrics_and_modular_curriculum_remain_in_app_py():
    app_source = _app_source()
    assert '@app.get("/admin/beta-metrics"' in app_source
    assert "async def admin_beta_metrics" in app_source
    assert "async def debug_modular_curriculum" not in app_source
