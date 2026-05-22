"""Tests for services/modular_progress_write_through_service.py."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import services.modular_progress_write_through_service as svc


SERVICE_PATH = Path("services/modular_progress_write_through_service.py")


def _src() -> str:
    return SERVICE_PATH.read_text(encoding="utf-8")


def _course_progress() -> dict:
    return {
        "course_key": "aipm-foundations",
        "progress_percent": 45,
        "status": "in_progress",
        "modules": [
            {
                "module_key": "module-01",
                "progress_percent": 80,
                "status": "in_progress",
                "completed_topics": 1,
                "total_topics": 2,
                "topics": [],
            },
            {
                "module_key": "module-02",
                "progress_percent": 0,
                "status": "not_started",
                "completed_topics": 0,
                "total_topics": 1,
                "topics": [],
            },
        ],
        "unassigned_topics": [],
        "topic_progress": [
            {
                "module_key": "module-01",
                "topic_key": "topic-1",
                "legacy_topic_id": "legacy-1",
                "status": "completed",
                "completion_percent": 100,
                "required_activities_completed": 5,
                "required_activities_total": 5,
                "feedback": "private",
            },
            {
                "module_key": "module-01",
                "topic_key": "topic-2",
                "legacy_topic_id": "legacy-2",
                "status": "in_progress",
                "completion_percent": 40,
                "required_activities_completed": 2,
                "required_activities_total": 5,
                "generated_content": "private",
            },
            {
                "module_key": None,
                "topic_key": "topic-3",
                "legacy_topic_id": "legacy-3",
                "status": "not_started",
                "completion_percent": 0,
                "required_activities_completed": 0,
                "required_activities_total": 5,
            },
        ],
    }


def test_module_imports_safely():
    assert svc is not None


def test_expected_functions_exist():
    assert callable(getattr(svc, "write_modular_progress_snapshot", None))
    assert callable(getattr(svc, "sanitize_progress_write_error", None))


def test_writes_module_progress_using_repository_helper(monkeypatch):
    calls = []

    def fake_upsert_module_progress(conn, **kwargs):
        calls.append((conn, kwargs))
        return 1

    monkeypatch.setattr(svc, "upsert_module_progress", fake_upsert_module_progress)
    monkeypatch.setattr(svc, "upsert_topic_progress", lambda conn, **kwargs: 1)
    monkeypatch.setattr(svc, "update_current_position", lambda conn, **kwargs: None)

    conn = object()
    result = svc.write_modular_progress_snapshot(
        conn,
        enrollment_id=7,
        course_progress=_course_progress(),
    )

    assert result["updated"] is True
    assert result["modules"] == 2
    assert len(calls) == 2
    assert calls[0][0] is conn
    assert calls[0][1] == {
        "enrollment_id": 7,
        "module_key": "module-01",
        "status": "in_progress",
        "completed_topics": 1,
        "total_topics": 2,
        "progress_percent": 80,
    }


def test_writes_topic_progress_using_repository_helper(monkeypatch):
    calls = []

    monkeypatch.setattr(svc, "upsert_module_progress", lambda conn, **kwargs: 1)

    def fake_upsert_topic_progress(conn, **kwargs):
        calls.append((conn, kwargs))
        return 1

    monkeypatch.setattr(svc, "upsert_topic_progress", fake_upsert_topic_progress)
    monkeypatch.setattr(svc, "update_current_position", lambda conn, **kwargs: None)

    conn = object()
    result = svc.write_modular_progress_snapshot(
        conn,
        enrollment_id=7,
        course_progress=_course_progress(),
    )

    assert result["topics"] == 3
    assert len(calls) == 3
    assert calls[1][0] is conn
    assert calls[1][1] == {
        "enrollment_id": 7,
        "topic_key": "topic-2",
        "module_key": "module-01",
        "legacy_topic_id": "legacy-2",
        "status": "in_progress",
        "completion_percent": 40,
        "required_activities_completed": 2,
        "required_activities_total": 5,
    }


def test_preserves_legacy_topic_id(monkeypatch):
    legacy_ids = []

    monkeypatch.setattr(svc, "upsert_module_progress", lambda conn, **kwargs: 1)

    def fake_upsert_topic_progress(conn, **kwargs):
        legacy_ids.append(kwargs["legacy_topic_id"])
        return 1

    monkeypatch.setattr(svc, "upsert_topic_progress", fake_upsert_topic_progress)
    monkeypatch.setattr(svc, "update_current_position", lambda conn, **kwargs: None)

    svc.write_modular_progress_snapshot(
        object(),
        enrollment_id=7,
        course_progress=_course_progress(),
    )

    assert legacy_ids == ["legacy-1", "legacy-2", "legacy-3"]


def test_skips_malformed_modules_and_topics_safely(monkeypatch):
    course_progress = _course_progress()
    course_progress["modules"].append({"status": "completed"})
    course_progress["topic_progress"].append({"status": "completed"})
    module_calls = []
    topic_calls = []

    monkeypatch.setattr(
        svc,
        "upsert_module_progress",
        lambda conn, **kwargs: module_calls.append(kwargs),
    )
    monkeypatch.setattr(
        svc,
        "upsert_topic_progress",
        lambda conn, **kwargs: topic_calls.append(kwargs),
    )
    monkeypatch.setattr(svc, "update_current_position", lambda conn, **kwargs: None)

    result = svc.write_modular_progress_snapshot(
        object(),
        enrollment_id=7,
        course_progress=course_progress,
    )

    assert result["modules"] == 2
    assert result["topics"] == 3
    assert len(module_calls) == 2
    assert len(topic_calls) == 3


def test_updates_current_enrollment_position(monkeypatch):
    calls = []
    course_progress = _course_progress()
    course_progress["current_position"] = {
        "current_module_key": "module-explicit",
        "current_topic_key": "topic-explicit",
        "current_legacy_topic_id": "legacy-explicit",
    }

    monkeypatch.setattr(svc, "upsert_module_progress", lambda conn, **kwargs: 1)
    monkeypatch.setattr(svc, "upsert_topic_progress", lambda conn, **kwargs: 1)

    def fake_update_current_position(conn, **kwargs):
        calls.append((conn, kwargs))

    monkeypatch.setattr(svc, "update_current_position", fake_update_current_position)

    conn = object()
    result = svc.write_modular_progress_snapshot(
        conn,
        enrollment_id=7,
        course_progress=course_progress,
    )

    assert result["position_updated"] is True
    assert calls == [
        (
            conn,
            {
                "enrollment_id": 7,
                "current_module_key": "module-explicit",
                "current_topic_key": "topic-explicit",
                "current_legacy_topic_id": "legacy-explicit",
                "progress_percent": 45,
            },
        )
    ]


def test_updates_current_position_from_progress_when_missing(monkeypatch):
    calls = []
    monkeypatch.setattr(svc, "upsert_module_progress", lambda conn, **kwargs: 1)
    monkeypatch.setattr(svc, "upsert_topic_progress", lambda conn, **kwargs: 1)
    monkeypatch.setattr(
        svc,
        "update_current_position",
        lambda conn, **kwargs: calls.append(kwargs),
    )

    result = svc.write_modular_progress_snapshot(
        object(),
        enrollment_id=7,
        course_progress=_course_progress(),
    )

    assert result["position_updated"] is True
    assert calls[0]["current_module_key"] == "module-01"
    assert calls[0]["current_topic_key"] == "topic-2"
    assert calls[0]["current_legacy_topic_id"] == "legacy-2"


def test_returns_safe_counts(monkeypatch):
    monkeypatch.setattr(svc, "upsert_module_progress", lambda conn, **kwargs: 1)
    monkeypatch.setattr(svc, "upsert_topic_progress", lambda conn, **kwargs: 1)
    monkeypatch.setattr(svc, "update_current_position", lambda conn, **kwargs: None)

    result = svc.write_modular_progress_snapshot(
        object(),
        enrollment_id=7,
        course_progress=_course_progress(),
    )

    assert result == {
        "updated": True,
        "modules": 2,
        "topics": 3,
        "position_updated": True,
        "error": None,
    }


def test_handles_repository_errors_safely(monkeypatch):
    def boom(conn, **kwargs):
        raise RuntimeError("failed postgres://user:pass@localhost/db password=secret")

    monkeypatch.setattr(svc, "upsert_module_progress", boom)
    monkeypatch.setattr(svc, "upsert_topic_progress", lambda conn, **kwargs: 1)
    monkeypatch.setattr(svc, "update_current_position", lambda conn, **kwargs: None)

    result = svc.write_modular_progress_snapshot(
        object(),
        enrollment_id=7,
        course_progress=_course_progress(),
    )

    assert result["updated"] is False
    assert result["modules"] == 0
    assert result["topics"] == 0
    assert result["position_updated"] is False
    assert "postgres://" not in result["error"]
    assert "secret" not in result["error"]


def test_safe_error_redacts_postgres_urls_and_secrets():
    result = svc.sanitize_progress_write_error(
        "boom postgresql://user:pass@host/db token=abc api_key=def secret=ghi"
    )

    assert "postgresql://" not in result
    assert "abc" not in result
    assert "def" not in result
    assert "ghi" not in result
    assert "[redacted-postgres-url]" in result


def test_safe_error_truncates_to_300_chars():
    assert len(svc.sanitize_progress_write_error("x" * 500)) == 300


def test_does_not_mutate_input_course_progress(monkeypatch):
    course_progress = _course_progress()
    original = deepcopy(course_progress)

    monkeypatch.setattr(svc, "upsert_module_progress", lambda conn, **kwargs: 1)
    monkeypatch.setattr(svc, "upsert_topic_progress", lambda conn, **kwargs: 1)
    monkeypatch.setattr(svc, "update_current_position", lambda conn, **kwargs: None)

    svc.write_modular_progress_snapshot(
        object(),
        enrollment_id=7,
        course_progress=course_progress,
    )

    assert course_progress == original


def test_no_db_connection_creation():
    src = _src()
    assert "psycopg2.connect" not in src
    assert "database.pool" not in src
    assert "get_conn(" not in src
    assert "_connect(" not in src


def test_no_env_reads():
    src = _src()
    assert "import os" not in src
    assert "os.environ" not in src
    assert "os.getenv" not in src
    assert "getenv(" not in src


def test_no_app_or_routes_imports():
    src = _src()
    assert "from app" not in src
    assert "import app" not in src
    assert "from routes" not in src
    assert "import routes" not in src


def test_no_commit_or_rollback():
    src = _src()
    assert ".commit()" not in src
    assert ".rollback()" not in src


def test_no_claude_or_provider_calls():
    src = _src().lower()
    assert "anthropic" not in src
    assert "claude" not in src
    assert "openai" not in src
    assert "boto3" not in src
