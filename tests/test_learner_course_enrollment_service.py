"""Tests for services/learner_course_enrollment_service.py."""

from __future__ import annotations

import importlib
import inspect
import re
from unittest.mock import MagicMock, patch

import services.learner_course_enrollment_service as svc


def _src() -> str:
    return inspect.getsource(svc)


def test_module_imports_safely():
    assert svc is not None


def test_expected_functions_exist():
    for fn in (
        "normalize_course_key",
        "build_default_enrollment_metadata",
        "ensure_course_enrollment",
        "get_active_course_enrollment_with_fallback",
        "update_enrollment_position_safely",
        "summarize_enrollment_progress",
        "sanitize_enrollment_error",
    ):
        assert callable(getattr(svc, fn, None)), f"missing: {fn}"


def test_normalize_course_key_mappings_work():
    assert svc.normalize_course_key("aipm") == "aipm-foundations"
    assert svc.normalize_course_key("evals") == "evals-foundations"
    assert svc.normalize_course_key("context") == "context-engineering-foundations"
    assert svc.normalize_course_key("ai_builder") == "ai-builder-foundations"
    assert svc.normalize_course_key("ai_job_ready") == "ai-job-ready"


def test_normalize_course_key_unknown_and_empty_fall_back_safely():
    assert svc.normalize_course_key(None) == "aipm-foundations"
    assert svc.normalize_course_key("") == "aipm-foundations"
    assert svc.normalize_course_key("unknown") == "aipm-foundations"


def test_build_default_enrollment_metadata_is_safe():
    result = svc.build_default_enrollment_metadata(
        source="onboarding",
        track_key="evals",
    )

    assert result == {"source": "onboarding", "track_key": "evals"}
    forbidden = {
        "secret",
        "api_key",
        "token",
        "submission",
        "submissions",
        "feedback",
        "generated_content",
        "notes",
    }
    assert forbidden.isdisjoint(result.keys())


def test_build_default_enrollment_metadata_omits_missing_track_key():
    result = svc.build_default_enrollment_metadata(source="system")

    assert result == {"source": "system"}


def test_ensure_course_enrollment_returns_existing_enrollment_when_found():
    conn = object()
    existing = {"enrollment_id": 1, "course_key": "evals-foundations"}

    with patch.object(svc, "get_active_enrollment", return_value=existing) as mock_get:
        with patch.object(svc, "upsert_course_enrollment") as mock_upsert:
            result = svc.ensure_course_enrollment(
                conn,
                user_id="user-1",
                session_id="session-1",
                track_key="evals",
            )

    assert result == {
        "source": "existing",
        "enrollment": existing,
        "created": False,
        "error": None,
    }
    mock_get.assert_called_once_with(
        conn,
        user_id="user-1",
        session_id="session-1",
        course_key="evals-foundations",
    )
    mock_upsert.assert_not_called()


def test_ensure_course_enrollment_creates_when_missing():
    conn = object()
    created = {"enrollment_id": 2, "course_key": "context-engineering-foundations"}

    with patch.object(
        svc,
        "get_active_enrollment",
        side_effect=[None, created],
    ) as mock_get:
        with patch.object(svc, "upsert_course_enrollment", return_value=2) as mock_upsert:
            result = svc.ensure_course_enrollment(
                conn,
                user_id="user-1",
                session_id="session-1",
                track_key="context",
                course_id=10,
                source="onboarding",
            )

    assert result == {
        "source": "created",
        "enrollment": created,
        "created": True,
        "error": None,
    }
    assert mock_get.call_count == 2
    mock_upsert.assert_called_once_with(
        conn,
        user_id="user-1",
        session_id="session-1",
        course_key="context-engineering-foundations",
        course_id=10,
        metadata={"source": "onboarding", "track_key": "context"},
    )


def test_ensure_course_enrollment_prefers_explicit_course_key():
    conn = object()
    created = {"enrollment_id": 2, "course_key": "custom-course"}

    with patch.object(svc, "get_active_enrollment", side_effect=[None, created]):
        with patch.object(svc, "upsert_course_enrollment") as mock_upsert:
            result = svc.ensure_course_enrollment(
                conn,
                user_id="user-1",
                session_id="session-1",
                track_key="evals",
                course_key="custom-course",
            )

    assert result["source"] == "created"
    assert result["enrollment"] == created
    assert mock_upsert.call_args.kwargs["course_key"] == "custom-course"


def test_ensure_course_enrollment_handles_unreadable_create_safely():
    conn = object()

    with patch.object(svc, "get_active_enrollment", side_effect=[None, None]):
        with patch.object(svc, "upsert_course_enrollment", return_value=3):
            result = svc.ensure_course_enrollment(
                conn,
                user_id="user-1",
                session_id="session-1",
                track_key="aipm",
            )

    assert result == {
        "source": "created_unreadable",
        "enrollment": None,
        "created": True,
        "error": None,
    }


def test_ensure_course_enrollment_handles_repository_errors_safely():
    conn = object()
    err = "boom postgres://user:pass@localhost/db?password=secret"

    with patch.object(svc, "get_active_enrollment", side_effect=RuntimeError(err)):
        result = svc.ensure_course_enrollment(
            conn,
            user_id="user-1",
            session_id="session-1",
            track_key="aipm",
        )

    assert result["source"] == "error"
    assert result["enrollment"] is None
    assert result["created"] is False
    assert "postgres://" not in result["error"]
    assert "secret" not in result["error"]


def test_get_active_course_enrollment_with_fallback_returns_db_source_when_found():
    conn = object()
    enrollment = {"enrollment_id": 1, "course_key": "ai-job-ready"}

    with patch.object(svc, "get_active_enrollment", return_value=enrollment):
        result = svc.get_active_course_enrollment_with_fallback(
            conn,
            user_id="user-1",
            session_id="session-1",
            track_key="ai_job_ready",
        )

    assert result == {"source": "db", "enrollment": enrollment, "error": None}


def test_get_active_course_enrollment_with_fallback_returns_fallback_when_missing():
    conn = object()

    with patch.object(svc, "get_active_enrollment", return_value=None):
        result = svc.get_active_course_enrollment_with_fallback(
            conn,
            user_id="user-1",
            session_id="session-1",
            track_key="ai_builder",
        )

    assert result == {
        "source": "fallback",
        "enrollment": {
            "course_key": "ai-builder-foundations",
            "status": "active",
            "current_module_key": None,
            "current_topic_key": None,
            "current_legacy_topic_id": None,
            "progress_percent": 0,
        },
        "error": None,
    }


def test_get_active_course_enrollment_with_fallback_returns_error_fallback_on_error():
    conn = object()

    with patch.object(
        svc,
        "get_active_enrollment",
        side_effect=RuntimeError("db failed token=abc"),
    ):
        result = svc.get_active_course_enrollment_with_fallback(
            conn,
            user_id="user-1",
            session_id="session-1",
            track_key="evals",
        )

    assert result["source"] == "error_fallback"
    assert result["enrollment"]["course_key"] == "evals-foundations"
    assert result["enrollment"]["status"] == "active"
    assert "abc" not in result["error"]


def test_update_enrollment_position_safely_returns_updated_true_on_success():
    conn = object()

    with patch.object(svc, "update_current_position") as mock_update:
        result = svc.update_enrollment_position_safely(
            conn,
            enrollment_id=7,
            current_module_key="module-1",
            current_topic_key="topic-1",
            progress_percent=50,
        )

    assert result == {"updated": True, "error": None}
    mock_update.assert_called_once_with(
        conn,
        enrollment_id=7,
        current_module_id=None,
        current_module_key="module-1",
        current_topic_id=None,
        current_topic_key="topic-1",
        current_legacy_topic_id=None,
        progress_percent=50,
    )


def test_update_enrollment_position_safely_returns_safe_error_on_failure():
    conn = object()

    with patch.object(
        svc,
        "update_current_position",
        side_effect=RuntimeError("failed password=hunter2"),
    ):
        result = svc.update_enrollment_position_safely(
            conn,
            enrollment_id=7,
            current_topic_key="topic-1",
        )

    assert result["updated"] is False
    assert "hunter2" not in result["error"]
    assert "password=[redacted]" in result["error"]


def test_summarize_enrollment_progress_returns_safe_summary_only():
    enrollment = {
        "course_key": "aipm-foundations",
        "status": "active",
        "progress_percent": 75,
        "current_module_key": "module-1",
        "current_topic_key": "topic-2",
        "current_legacy_topic_id": "aipm-week-1-topic-2",
        "metadata": {"secret": "nope"},
        "feedback": "private",
    }
    module_progress = [{"module_key": "module-1"}, {"module_key": "module-2"}]
    topic_progress = [
        {"topic_key": "topic-1", "status": "completed", "feedback": "private"},
        {"topic_key": "topic-2", "completion_percent": 100},
        {"topic_key": "topic-3", "status": "in_progress"},
    ]

    result = svc.summarize_enrollment_progress(
        enrollment=enrollment,
        module_progress=module_progress,
        topic_progress=topic_progress,
    )

    assert result == {
        "course_key": "aipm-foundations",
        "status": "active",
        "progress_percent": 75,
        "current_module_key": "module-1",
        "current_topic_key": "topic-2",
        "current_legacy_topic_id": "aipm-week-1-topic-2",
        "module_count": 2,
        "topic_count": 3,
        "completed_topic_count": 2,
    }
    forbidden = {
        "metadata",
        "submissions",
        "feedback",
        "notes",
        "generated_content",
    }
    assert forbidden.isdisjoint(result.keys())


def test_summarize_enrollment_progress_handles_none_inputs():
    result = svc.summarize_enrollment_progress(enrollment=None)

    assert result == {
        "course_key": None,
        "status": None,
        "progress_percent": 0,
        "current_module_key": None,
        "current_topic_key": None,
        "current_legacy_topic_id": None,
        "module_count": 0,
        "topic_count": 0,
        "completed_topic_count": 0,
    }


def test_safe_error_redacts_postgres_urls_and_secrets():
    raw = (
        "failed postgresql://user:pass@localhost:5432/db "
        "password=hunter2 token=abc api_key=def secret=ghi"
    )
    result = svc.sanitize_enrollment_error(raw)

    assert "postgresql://" not in result
    assert "hunter2" not in result
    assert "abc" not in result
    assert "def" not in result
    assert "ghi" not in result
    assert "[redacted-postgres-url]" in result


def test_safe_error_truncates_to_300_chars():
    result = svc.sanitize_enrollment_error("x" * 500)

    assert len(result) == 300


def test_no_db_connection_creation():
    src = _src()
    assert "psycopg2.connect" not in src
    assert "database.pool" not in src
    assert "get_conn(" not in src


def test_import_does_not_call_database_pool_connect():
    with patch(
        "database.pool._connect",
        side_effect=AssertionError("_connect must not be called"),
    ) as mock_connect:
        importlib.reload(svc)

    mock_connect.assert_not_called()


def test_no_env_reads():
    src = _src()
    assert "import os" not in src
    assert "os.environ" not in src
    assert "os.getenv" not in src
    assert "getenv(" not in src


def test_no_app_routes_imports():
    src = _src()
    for pattern in (
        r"^\s*from\s+app\b",
        r"^\s*import\s+app\b",
        r"^\s*from\s+routes\b",
        r"^\s*import\s+routes\b",
    ):
        assert not re.search(pattern, src, re.MULTILINE)


def test_no_commit_or_rollback():
    src = _src()
    assert ".commit()" not in src
    assert ".rollback()" not in src


def test_no_claude_or_provider_calls():
    src = _src()
    for pattern in (
        r"^\s*(import|from)\s+anthropic\b",
        r"anthropic\.Anthropic\(",
        r"^\s*(import|from)\s+openai\b",
        r"openai\.",
        r"boto3.*bedrock",
    ):
        assert not re.search(pattern, src, re.MULTILINE | re.IGNORECASE)


def test_repository_functions_can_be_monkeypatched_without_real_db():
    conn = MagicMock()

    with patch.object(svc, "get_active_enrollment", return_value=None) as mock_get:
        result = svc.get_active_course_enrollment_with_fallback(
            conn,
            user_id="user-1",
            session_id="session-1",
        )

    assert result["source"] == "fallback"
    mock_get.assert_called_once()
    conn.cursor.assert_not_called()
