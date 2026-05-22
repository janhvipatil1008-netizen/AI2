"""Tests for services/modular_curriculum_fallback_service.py.

No real DB connection required.  Read-service functions are patched at source.
Static curriculum (WEEKS / ROLE_TRACKS) is used as-is — no mocking needed
for pure static helpers.
"""

from __future__ import annotations

import inspect
import re
from unittest.mock import MagicMock, patch

import pytest

import services.modular_curriculum_fallback_service as svc


# ── Patch targets ─────────────────────────────────────────────────────────────

_READ_SVC = "services.modular_curriculum_read_service"
_TOPICS   = "curriculum.topics"

# A real legacy topic ID from the aipm track — used in static-lookup tests
_REAL_LEGACY_ID = "aipm-week-1-ai-vs-ml-vs-dl"


# ── Import / API surface ──────────────────────────────────────────────────────

def test_module_imports_safely():
    assert svc is not None


def test_expected_helpers_exist():
    for fn in ("static_topic_to_modular_topic", "static_track_to_modular_course"):
        assert hasattr(svc, fn), f"Missing helper: {fn}"


def test_expected_fallback_functions_exist():
    for fn in (
        "get_course_structure_with_fallback",
        "list_courses_with_fallback",
        "get_topic_structure_by_legacy_id_with_fallback",
    ):
        assert hasattr(svc, fn), f"Missing function: {fn}"


# ── Isolation guards ──────────────────────────────────────────────────────────

def _src() -> str:
    return inspect.getsource(svc)


def test_no_db_connection_creation():
    src = _src()
    assert "psycopg2.connect" not in src
    assert not re.search(r"^\s*(import|from)\s+database\.pool", src, re.MULTILINE)


def test_no_env_reads():
    src = _src()
    assert "os.environ" not in src
    assert "os.getenv" not in src


def test_no_app_routes_imports():
    src = _src()
    for bad in ("from app", "import app", "from routes", "import routes"):
        assert bad not in src, f"Forbidden import found: {bad!r}"


def test_no_commit_or_rollback():
    src = _src()
    assert ".commit()" not in src
    assert ".rollback()" not in src


def test_no_claude_or_anthropic_calls():
    src = _src()
    for pattern in (
        r"^\s*(import|from)\s+anthropic",
        r"anthropic\.Anthropic\(",
        r"boto3.*bedrock",
        r"openai\.",
    ):
        assert not re.search(pattern, src, re.MULTILINE | re.IGNORECASE), (
            f"Unexpected provider reference: {pattern}"
        )


# ── static_topic_to_modular_topic ─────────────────────────────────────────────

def _real_topic():
    from curriculum.topics import get_topics_for_track
    return get_topics_for_track("aipm")[0]


def test_static_topic_to_modular_topic_returns_dict():
    result = svc.static_topic_to_modular_topic(_real_topic())
    assert isinstance(result, dict)


def test_static_topic_to_modular_topic_has_legacy_topic_id():
    topic = _real_topic()
    result = svc.static_topic_to_modular_topic(topic)
    assert result["legacy_topic_id"] == topic.topic_id


def test_static_topic_to_modular_topic_has_topic_key():
    result = svc.static_topic_to_modular_topic(_real_topic())
    assert result["topic_key"]
    assert isinstance(result["topic_key"], str)


def test_static_topic_to_modular_topic_has_title():
    topic = _real_topic()
    result = svc.static_topic_to_modular_topic(topic)
    assert result["title"] == topic.topic_title


def test_static_topic_to_modular_topic_has_skills_list():
    result = svc.static_topic_to_modular_topic(_real_topic())
    assert "skills" in result
    assert isinstance(result["skills"], list)


def test_static_topic_to_modular_topic_has_activities_list():
    result = svc.static_topic_to_modular_topic(_real_topic())
    assert "activities" in result
    assert isinstance(result["activities"], list)
    assert len(result["activities"]) > 0


def test_static_topic_to_modular_topic_activities_have_type():
    result = svc.static_topic_to_modular_topic(_real_topic())
    for act in result["activities"]:
        assert "activity_type" in act
        assert act["activity_type"]


def test_static_topic_to_modular_topic_sequence_order_default():
    result = svc.static_topic_to_modular_topic(_real_topic())
    assert result["sequence_order"] == 0


def test_static_topic_to_modular_topic_sequence_order_custom():
    result = svc.static_topic_to_modular_topic(_real_topic(), sequence_order=7)
    assert result["sequence_order"] == 7


def test_static_topic_to_modular_topic_does_not_mutate_input():
    topic  = _real_topic()
    before = topic.topic_id
    svc.static_topic_to_modular_topic(topic)
    assert topic.topic_id == before


def test_static_topic_to_modular_topic_all_expected_keys():
    result = svc.static_topic_to_modular_topic(_real_topic())
    for key in ("legacy_topic_id", "topic_key", "title", "description",
                "sequence_order", "skills", "activities", "status", "metadata"):
        assert key in result, f"Missing key: {key}"


# ── static_track_to_modular_course ────────────────────────────────────────────

def test_static_track_to_modular_course_returns_none_for_unknown():
    assert svc.static_track_to_modular_course("nonexistent") is None


def test_static_track_to_modular_course_returns_expected_top_level_keys():
    result = svc.static_track_to_modular_course("aipm")
    assert result is not None
    assert "course"            in result
    assert "modules"           in result
    assert "unassigned_topics" in result


def test_static_track_to_modular_course_course_has_course_key():
    result = svc.static_track_to_modular_course("aipm")
    assert result["course"]["course_key"] == "aipm-foundations"


def test_static_track_to_modular_course_has_modules():
    result = svc.static_track_to_modular_course("aipm")
    assert len(result["modules"]) >= 1


def test_static_track_to_modular_course_module_keys_use_module_prefix():
    result = svc.static_track_to_modular_course("aipm")
    for mod in result["modules"]:
        assert mod["module_key"].startswith("module-"), (
            f"module_key {mod['module_key']!r} does not start with 'module-'"
        )


def test_static_track_to_modular_course_no_week_number_public_field():
    """week_number must not appear as a direct dict key in modules or topics."""
    result = svc.static_track_to_modular_course("aipm")
    for mod in result["modules"]:
        assert "week_number" not in mod, f"week_number found in module: {mod}"
        for topic in mod.get("topics", []):
            assert "week_number" not in topic, f"week_number found in topic: {topic}"


def test_static_track_to_modular_course_no_week_number_in_course():
    result = svc.static_track_to_modular_course("aipm")
    assert "week_number" not in result["course"]


def test_static_track_to_modular_course_preserves_legacy_topic_id():
    result = svc.static_track_to_modular_course("aipm")
    topic_ids = [
        t["legacy_topic_id"]
        for mod in result["modules"]
        for t in mod["topics"]
    ]
    assert len(topic_ids) > 0
    assert all(tid for tid in topic_ids), "Some legacy_topic_ids are empty"


def test_static_track_to_modular_course_topics_have_skills_and_activities():
    result = svc.static_track_to_modular_course("aipm")
    for mod in result["modules"]:
        for topic in mod["topics"]:
            assert "skills"     in topic
            assert "activities" in topic


def test_static_track_to_modular_course_unassigned_topics_is_empty():
    result = svc.static_track_to_modular_course("aipm")
    assert result["unassigned_topics"] == []


def test_static_track_to_modular_course_does_not_mutate_role_tracks():
    from curriculum.syllabus import ROLE_TRACKS
    keys_before = list(ROLE_TRACKS.keys())
    svc.static_track_to_modular_course("aipm")
    assert list(ROLE_TRACKS.keys()) == keys_before


def test_static_track_to_modular_course_does_not_mutate_weeks():
    from curriculum.syllabus import WEEKS
    len_before = len(WEEKS)
    svc.static_track_to_modular_course("aipm")
    assert len(WEEKS) == len_before


def test_static_track_to_modular_course_works_for_all_tracks():
    from curriculum.syllabus import ROLE_TRACKS
    for track_key in ROLE_TRACKS:
        result = svc.static_track_to_modular_course(track_key)
        assert result is not None, f"Expected result for track {track_key!r}"
        assert len(result["modules"]) >= 1


# ── get_course_structure_with_fallback ────────────────────────────────────────

def _fake_conn():
    return MagicMock()


def _fake_course_structure():
    return {
        "course":            {"course_id": 1, "course_key": "aipm-foundations"},
        "modules":           [],
        "unassigned_topics": [],
    }


def test_get_course_structure_with_fallback_db_success_returns_db_source():
    conn = _fake_conn()
    with patch(f"{_READ_SVC}.get_course_structure", return_value=_fake_course_structure()):
        result = svc.get_course_structure_with_fallback(conn, course_key="aipm-foundations")
    assert result["source"] == "db"


def test_get_course_structure_with_fallback_db_success_returns_course_structure():
    conn = _fake_conn()
    with patch(f"{_READ_SVC}.get_course_structure", return_value=_fake_course_structure()):
        result = svc.get_course_structure_with_fallback(conn, course_key="aipm-foundations")
    assert result["course_structure"] == _fake_course_structure()


def test_get_course_structure_with_fallback_db_success_error_is_none():
    conn = _fake_conn()
    with patch(f"{_READ_SVC}.get_course_structure", return_value=_fake_course_structure()):
        result = svc.get_course_structure_with_fallback(conn, course_key="aipm-foundations")
    assert result["error"] is None


def test_get_course_structure_with_fallback_db_none_returns_fallback():
    conn = _fake_conn()
    with patch(f"{_READ_SVC}.get_course_structure", return_value=None):
        result = svc.get_course_structure_with_fallback(conn, course_key="aipm-foundations")
    assert result["source"] == "fallback"


def test_get_course_structure_with_fallback_db_none_provides_static_structure():
    conn = _fake_conn()
    with patch(f"{_READ_SVC}.get_course_structure", return_value=None):
        result = svc.get_course_structure_with_fallback(conn, course_key="aipm-foundations")
    assert result["course_structure"] is not None
    assert "modules" in result["course_structure"]


def test_get_course_structure_with_fallback_db_error_returns_error_fallback():
    conn = _fake_conn()
    with patch(f"{_READ_SVC}.get_course_structure", side_effect=RuntimeError("DB down")):
        result = svc.get_course_structure_with_fallback(conn, course_key="aipm-foundations")
    assert result["source"] == "error_fallback"


def test_get_course_structure_with_fallback_db_error_sets_error_field():
    conn = _fake_conn()
    with patch(f"{_READ_SVC}.get_course_structure", side_effect=RuntimeError("DB down")):
        result = svc.get_course_structure_with_fallback(conn, course_key="aipm-foundations")
    assert result["error"] is not None
    assert "DB down" in result["error"]


def test_get_course_structure_with_fallback_conn_none_returns_fallback():
    result = svc.get_course_structure_with_fallback(None, course_key="aipm-foundations")
    assert result["source"] == "fallback"
    assert result["course_structure"] is not None


def test_get_course_structure_with_fallback_uses_fallback_track_key():
    result = svc.get_course_structure_with_fallback(
        None,
        course_key="some-other-key",
        fallback_track_key="aipm",
    )
    assert result["course_structure"] is not None
    assert result["course_structure"]["course"]["course_key"] == "aipm-foundations"


def test_get_course_structure_with_fallback_unknown_key_returns_none_structure():
    result = svc.get_course_structure_with_fallback(None, course_key="unknown-course")
    assert result["source"] == "fallback"
    assert result["course_structure"] is None


def test_get_course_structure_with_fallback_result_has_all_keys():
    result = svc.get_course_structure_with_fallback(None, course_key="aipm-foundations")
    for key in ("source", "course_structure", "error"):
        assert key in result, f"Missing key: {key}"


def test_get_course_structure_with_fallback_safe_error_no_db_url():
    conn = _fake_conn()
    exc = RuntimeError("connection failed: postgresql://user:secret@host:5432/db")
    with patch(f"{_READ_SVC}.get_course_structure", side_effect=exc):
        result = svc.get_course_structure_with_fallback(conn, course_key="aipm-foundations")
    assert "postgresql://" not in result["error"]
    assert "secret" not in result["error"]
    assert "[DB_URL_REDACTED]" in result["error"]


def test_get_course_structure_with_fallback_error_is_truncated():
    conn = _fake_conn()
    long_error = "x" * 1000
    with patch(f"{_READ_SVC}.get_course_structure", side_effect=RuntimeError(long_error)):
        result = svc.get_course_structure_with_fallback(conn, course_key="aipm-foundations")
    assert len(result["error"]) <= 300


# ── list_courses_with_fallback ────────────────────────────────────────────────

def _fake_db_courses():
    return [
        {"course_id": 1, "course_key": "aipm-foundations", "title": "AI PM"},
        {"course_id": 2, "course_key": "evals-foundations", "title": "Evals"},
    ]


def test_list_courses_with_fallback_result_has_all_keys():
    result = svc.list_courses_with_fallback(None)
    for key in ("source", "courses", "error"):
        assert key in result, f"Missing key: {key}"


def test_list_courses_with_fallback_db_success_returns_db_source():
    conn = _fake_conn()
    with patch(f"{_READ_SVC}.list_available_courses", return_value=_fake_db_courses()):
        result = svc.list_courses_with_fallback(conn)
    assert result["source"] == "db"


def test_list_courses_with_fallback_db_success_returns_courses():
    conn = _fake_conn()
    with patch(f"{_READ_SVC}.list_available_courses", return_value=_fake_db_courses()):
        result = svc.list_courses_with_fallback(conn)
    assert len(result["courses"]) == 2


def test_list_courses_with_fallback_db_empty_returns_fallback():
    conn = _fake_conn()
    with patch(f"{_READ_SVC}.list_available_courses", return_value=[]):
        result = svc.list_courses_with_fallback(conn)
    assert result["source"] == "fallback"


def test_list_courses_with_fallback_db_empty_returns_static_courses():
    conn = _fake_conn()
    with patch(f"{_READ_SVC}.list_available_courses", return_value=[]):
        result = svc.list_courses_with_fallback(conn)
    assert len(result["courses"]) >= 1


def test_list_courses_with_fallback_db_error_returns_error_fallback():
    conn = _fake_conn()
    with patch(f"{_READ_SVC}.list_available_courses", side_effect=RuntimeError("timeout")):
        result = svc.list_courses_with_fallback(conn)
    assert result["source"] == "error_fallback"


def test_list_courses_with_fallback_db_error_still_returns_static_courses():
    conn = _fake_conn()
    with patch(f"{_READ_SVC}.list_available_courses", side_effect=RuntimeError("timeout")):
        result = svc.list_courses_with_fallback(conn)
    assert len(result["courses"]) >= 1


def test_list_courses_with_fallback_conn_none_returns_fallback():
    result = svc.list_courses_with_fallback(None)
    assert result["source"] == "fallback"


def test_list_courses_with_fallback_conn_none_returns_static_courses():
    result = svc.list_courses_with_fallback(None)
    assert len(result["courses"]) >= 1


def test_list_courses_with_fallback_static_courses_have_course_key():
    result = svc.list_courses_with_fallback(None)
    for course in result["courses"]:
        assert "course_key" in course
        assert course["course_key"]


def test_list_courses_with_fallback_includes_all_tracks():
    from curriculum.syllabus import ROLE_TRACKS
    result = svc.list_courses_with_fallback(None)
    course_keys = {c["course_key"] for c in result["courses"]}
    assert "aipm-foundations" in course_keys
    assert len(result["courses"]) == len(ROLE_TRACKS)


def test_list_courses_with_fallback_passes_status_none_to_db():
    conn = _fake_conn()
    with patch(f"{_READ_SVC}.list_available_courses", return_value=[]) as mock_lc:
        svc.list_courses_with_fallback(conn)
    mock_lc.assert_called_once_with(conn, status=None)


# ── get_topic_structure_by_legacy_id_with_fallback ────────────────────────────

def _fake_db_topic():
    return {
        "topic_id": 42, "legacy_topic_id": _REAL_LEGACY_ID,
        "topic_key": "ai-vs-ml-vs-dl", "title": "AI vs ML vs DL",
        "skills": [], "activities": [],
    }


def test_get_topic_by_legacy_id_fallback_result_has_all_keys():
    conn = _fake_conn()
    with patch(f"{_READ_SVC}.get_topic_structure_by_legacy_id", return_value=_fake_db_topic()):
        result = svc.get_topic_structure_by_legacy_id_with_fallback(
            conn, legacy_topic_id=_REAL_LEGACY_ID
        )
    for key in ("source", "topic", "error"):
        assert key in result, f"Missing key: {key}"


def test_get_topic_by_legacy_id_fallback_db_success_returns_db_source():
    conn = _fake_conn()
    with patch(f"{_READ_SVC}.get_topic_structure_by_legacy_id", return_value=_fake_db_topic()):
        result = svc.get_topic_structure_by_legacy_id_with_fallback(
            conn, legacy_topic_id=_REAL_LEGACY_ID
        )
    assert result["source"] == "db"


def test_get_topic_by_legacy_id_fallback_db_success_returns_topic():
    conn = _fake_conn()
    with patch(f"{_READ_SVC}.get_topic_structure_by_legacy_id", return_value=_fake_db_topic()):
        result = svc.get_topic_structure_by_legacy_id_with_fallback(
            conn, legacy_topic_id=_REAL_LEGACY_ID
        )
    assert result["topic"]["topic_id"] == 42


def test_get_topic_by_legacy_id_fallback_db_none_returns_fallback():
    conn = _fake_conn()
    with patch(f"{_READ_SVC}.get_topic_structure_by_legacy_id", return_value=None):
        result = svc.get_topic_structure_by_legacy_id_with_fallback(
            conn, legacy_topic_id=_REAL_LEGACY_ID
        )
    assert result["source"] == "fallback"


def test_get_topic_by_legacy_id_fallback_db_none_finds_static_topic():
    conn = _fake_conn()
    with patch(f"{_READ_SVC}.get_topic_structure_by_legacy_id", return_value=None):
        result = svc.get_topic_structure_by_legacy_id_with_fallback(
            conn, legacy_topic_id=_REAL_LEGACY_ID
        )
    assert result["topic"] is not None
    assert result["topic"]["legacy_topic_id"] == _REAL_LEGACY_ID


def test_get_topic_by_legacy_id_fallback_db_error_returns_error_fallback():
    conn = _fake_conn()
    with patch(
        f"{_READ_SVC}.get_topic_structure_by_legacy_id",
        side_effect=RuntimeError("connection refused"),
    ):
        result = svc.get_topic_structure_by_legacy_id_with_fallback(
            conn, legacy_topic_id=_REAL_LEGACY_ID
        )
    assert result["source"] == "error_fallback"
    assert result["error"] is not None


def test_get_topic_by_legacy_id_fallback_db_error_still_finds_static_topic():
    conn = _fake_conn()
    with patch(
        f"{_READ_SVC}.get_topic_structure_by_legacy_id",
        side_effect=RuntimeError("timeout"),
    ):
        result = svc.get_topic_structure_by_legacy_id_with_fallback(
            conn, legacy_topic_id=_REAL_LEGACY_ID
        )
    assert result["topic"] is not None
    assert result["topic"]["legacy_topic_id"] == _REAL_LEGACY_ID


def test_get_topic_by_legacy_id_fallback_conn_none_uses_static():
    result = svc.get_topic_structure_by_legacy_id_with_fallback(
        None, legacy_topic_id=_REAL_LEGACY_ID
    )
    assert result["source"] == "fallback"
    assert result["topic"] is not None
    assert result["topic"]["legacy_topic_id"] == _REAL_LEGACY_ID


def test_get_topic_by_legacy_id_fallback_unknown_id_returns_none_topic():
    result = svc.get_topic_structure_by_legacy_id_with_fallback(
        None, legacy_topic_id="aipm-week-99-nonexistent-topic"
    )
    assert result["topic"] is None


def test_get_topic_by_legacy_id_fallback_static_topic_has_activities():
    result = svc.get_topic_structure_by_legacy_id_with_fallback(
        None, legacy_topic_id=_REAL_LEGACY_ID
    )
    assert result["topic"] is not None
    assert isinstance(result["topic"]["activities"], list)
    assert len(result["topic"]["activities"]) > 0


def test_get_topic_by_legacy_id_fallback_safe_error_no_db_url():
    conn = _fake_conn()
    exc  = RuntimeError("failed: postgresql://admin:pw@db.host:5432/mydb")
    with patch(f"{_READ_SVC}.get_topic_structure_by_legacy_id", side_effect=exc):
        result = svc.get_topic_structure_by_legacy_id_with_fallback(
            conn, legacy_topic_id=_REAL_LEGACY_ID
        )
    assert "postgresql://" not in result["error"]
    assert "[DB_URL_REDACTED]" in result["error"]


# ── WEEKS / ROLE_TRACKS mutation guards ───────────────────────────────────────

def test_role_tracks_not_mutated_after_get_course_structure_with_fallback():
    from curriculum.syllabus import ROLE_TRACKS
    keys_before = list(ROLE_TRACKS.keys())
    svc.get_course_structure_with_fallback(None, course_key="aipm-foundations")
    assert list(ROLE_TRACKS.keys()) == keys_before


def test_weeks_not_mutated_after_get_course_structure_with_fallback():
    from curriculum.syllabus import WEEKS
    len_before = len(WEEKS)
    svc.get_course_structure_with_fallback(None, course_key="aipm-foundations")
    assert len(WEEKS) == len_before


def test_role_tracks_not_mutated_after_list_courses_with_fallback():
    from curriculum.syllabus import ROLE_TRACKS
    keys_before = list(ROLE_TRACKS.keys())
    svc.list_courses_with_fallback(None)
    assert list(ROLE_TRACKS.keys()) == keys_before


def test_role_tracks_not_mutated_after_topic_fallback():
    from curriculum.syllabus import ROLE_TRACKS
    keys_before = list(ROLE_TRACKS.keys())
    svc.get_topic_structure_by_legacy_id_with_fallback(None, legacy_topic_id=_REAL_LEGACY_ID)
    assert list(ROLE_TRACKS.keys()) == keys_before
