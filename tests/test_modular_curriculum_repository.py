"""Tests for repositories/modular_curriculum_repository.py.

No real DB connection required. All tests use a fake conn/cursor to verify
SQL correctness, parameter passing, and isolation properties.
"""

from __future__ import annotations

import importlib
import inspect
import types
from unittest.mock import MagicMock, call, patch

import repositories.modular_curriculum_repository as repo


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_conn(fetchone_return=None, fetchall_return=None):
    """Return a fake conn whose cursor() context manager works correctly."""
    cur = MagicMock()
    cur.fetchone.return_value = fetchone_return
    cur.fetchall.return_value = fetchall_return or []
    # description used by dict-building read helpers
    cur.description = []

    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=cur)
    ctx.__exit__ = MagicMock(return_value=False)

    conn = MagicMock()
    conn.cursor.return_value = ctx
    return conn, cur


def _sql_for(cur) -> str:
    """Extract the SQL string passed to cursor.execute."""
    return cur.execute.call_args[0][0]


def _params_for(cur) -> tuple:
    """Extract the params tuple passed to cursor.execute."""
    return cur.execute.call_args[0][1]


# ── Import sanity ─────────────────────────────────────────────────────────────

def test_module_imports_safely():
    assert repo is not None


def test_all_write_functions_exist():
    for fn in (
        "upsert_course",
        "upsert_course_module",
        "upsert_skill",
        "upsert_course_topic",
        "link_topic_skill",
        "upsert_topic_activity",
    ):
        assert hasattr(repo, fn), f"Missing function: {fn}"


def test_all_read_functions_exist():
    for fn in (
        "get_course_by_key",
        "list_courses",
        "list_modules_for_course",
        "list_topics_for_course",
        "list_topics_for_module",
        "get_topic_by_legacy_id",
        "list_activities_for_topic",
        "list_skills_for_topic",
    ):
        assert hasattr(repo, fn), f"Missing function: {fn}"


# ── Isolation: forbidden imports ──────────────────────────────────────────────

def _source() -> str:
    return inspect.getsource(repo)


def test_no_os_environ_usage():
    src = _source()
    assert "os.environ" not in src
    assert "os.getenv" not in src


def test_no_database_pool_import():
    import re
    src = _source()
    # Must not import database.pool (comment mentions are fine)
    assert not re.search(r"^\s*(import|from)\s+database\.pool", src, re.MULTILINE), (
        "database.pool must not be imported"
    )
    assert "psycopg2.connect" not in src


def test_no_app_routes_services_import():
    src = _source()
    assert "from app" not in src
    assert "from routes" not in src
    assert "from services" not in src
    assert "import app" not in src


def test_no_commit_or_rollback_called():
    src = _source()
    assert ".commit()" not in src
    assert ".rollback()" not in src


# ── SQL quality: parameterized placeholders ───────────────────────────────────

def test_all_sqls_use_percent_s_placeholders():
    src = _source()
    # Every VALUES clause should use %s, not string formatting
    assert "VALUES (%s" in src
    assert "f'" not in src  # no f-strings in SQL
    assert '%" %' not in src  # no %-format in SQL


# ── upsert_course ─────────────────────────────────────────────────────────────

def test_upsert_course_inserts_into_courses():
    conn, cur = _make_conn(fetchone_return=(42,))
    result = repo.upsert_course(conn, course_key="aipm-v1", title="AI PM Course")
    assert "INSERT INTO courses" in _sql_for(cur)
    assert result == 42


def test_upsert_course_conflicts_on_course_key():
    conn, cur = _make_conn(fetchone_return=(1,))
    repo.upsert_course(conn, course_key="aipm-v1", title="T")
    assert "ON CONFLICT (course_key)" in _sql_for(cur)


def test_upsert_course_uses_do_update():
    conn, cur = _make_conn(fetchone_return=(1,))
    repo.upsert_course(conn, course_key="aipm-v1", title="T")
    assert "DO UPDATE SET" in _sql_for(cur)


def test_upsert_course_returns_none_when_no_row():
    conn, cur = _make_conn(fetchone_return=None)
    result = repo.upsert_course(conn, course_key="x", title="T")
    assert result is None


def test_upsert_course_passes_defaults():
    conn, cur = _make_conn(fetchone_return=(5,))
    repo.upsert_course(conn, course_key="k", title="T")
    params = _params_for(cur)
    # level, status, version, sequence_order defaults
    assert "beginner" in params
    assert "draft" in params
    assert "v1" in params
    assert 0 in params


# ── upsert_course_module ──────────────────────────────────────────────────────

def test_upsert_course_module_inserts_into_course_modules():
    conn, cur = _make_conn(fetchone_return=(7,))
    result = repo.upsert_course_module(conn, course_id=1, module_key="m1", title="Module 1")
    assert "INSERT INTO course_modules" in _sql_for(cur)
    assert result == 7


def test_upsert_course_module_conflicts_on_course_id_and_module_key():
    conn, cur = _make_conn(fetchone_return=(1,))
    repo.upsert_course_module(conn, course_id=1, module_key="m1", title="T")
    assert "ON CONFLICT (course_id, module_key)" in _sql_for(cur)


def test_upsert_course_module_passes_course_id():
    conn, cur = _make_conn(fetchone_return=(1,))
    repo.upsert_course_module(conn, course_id=99, module_key="m", title="T")
    assert 99 in _params_for(cur)


# ── upsert_skill ──────────────────────────────────────────────────────────────

def test_upsert_skill_inserts_into_skills():
    conn, cur = _make_conn(fetchone_return=(3,))
    result = repo.upsert_skill(conn, skill_key="prompt-engineering", title="Prompt Engineering")
    assert "INSERT INTO skills" in _sql_for(cur)
    assert result == 3


def test_upsert_skill_conflicts_on_skill_key():
    conn, cur = _make_conn(fetchone_return=(1,))
    repo.upsert_skill(conn, skill_key="sk", title="T")
    assert "ON CONFLICT (skill_key)" in _sql_for(cur)


def test_upsert_skill_passes_skill_key():
    conn, cur = _make_conn(fetchone_return=(1,))
    repo.upsert_skill(conn, skill_key="my-skill", title="T")
    assert "my-skill" in _params_for(cur)


# ── upsert_course_topic ───────────────────────────────────────────────────────

def test_upsert_course_topic_inserts_into_course_topics():
    conn, cur = _make_conn(fetchone_return=(10,))
    result = repo.upsert_course_topic(
        conn, course_id=1, module_id=2, topic_key="t1", title="Topic 1"
    )
    assert "INSERT INTO course_topics" in _sql_for(cur)
    assert result == 10


def test_upsert_course_topic_conflicts_on_course_id_and_topic_key():
    conn, cur = _make_conn(fetchone_return=(1,))
    repo.upsert_course_topic(conn, course_id=1, module_id=None, topic_key="t", title="T")
    assert "ON CONFLICT (course_id, topic_key)" in _sql_for(cur)


def test_upsert_course_topic_stores_legacy_topic_id():
    conn, cur = _make_conn(fetchone_return=(1,))
    repo.upsert_course_topic(
        conn,
        course_id=1,
        module_id=2,
        topic_key="t",
        title="T",
        legacy_topic_id="aipm-week-1-transformers",
    )
    assert "aipm-week-1-transformers" in _params_for(cur)


def test_upsert_course_topic_accepts_none_module_id():
    conn, cur = _make_conn(fetchone_return=(1,))
    repo.upsert_course_topic(conn, course_id=1, module_id=None, topic_key="t", title="T")
    assert None in _params_for(cur)


# ── link_topic_skill ──────────────────────────────────────────────────────────

def test_link_topic_skill_inserts_into_topic_skills():
    conn, cur = _make_conn()
    repo.link_topic_skill(conn, topic_id=1, skill_id=2)
    assert "INSERT INTO topic_skills" in _sql_for(cur)


def test_link_topic_skill_conflicts_on_topic_id_skill_id():
    conn, cur = _make_conn()
    repo.link_topic_skill(conn, topic_id=1, skill_id=2)
    assert "ON CONFLICT (topic_id, skill_id)" in _sql_for(cur)


def test_link_topic_skill_updates_importance_on_conflict():
    conn, cur = _make_conn()
    repo.link_topic_skill(conn, topic_id=1, skill_id=2, importance="supplementary")
    sql = _sql_for(cur)
    assert "importance = EXCLUDED.importance" in sql


def test_link_topic_skill_passes_importance():
    conn, cur = _make_conn()
    repo.link_topic_skill(conn, topic_id=5, skill_id=9, importance="core")
    assert "core" in _params_for(cur)


def test_link_topic_skill_returns_none():
    conn, cur = _make_conn()
    result = repo.link_topic_skill(conn, topic_id=1, skill_id=2)
    assert result is None


# ── upsert_topic_activity ─────────────────────────────────────────────────────

def test_upsert_topic_activity_inserts_into_topic_activities():
    conn, cur = _make_conn(fetchone_return=(20,))
    result = repo.upsert_topic_activity(
        conn, topic_id=1, activity_key="learn", activity_type="learn"
    )
    assert "INSERT INTO topic_activities" in _sql_for(cur)
    assert result == 20


def test_upsert_topic_activity_conflicts_on_topic_id_activity_key():
    conn, cur = _make_conn(fetchone_return=(1,))
    repo.upsert_topic_activity(conn, topic_id=1, activity_key="quiz", activity_type="quiz")
    assert "ON CONFLICT (topic_id, activity_key)" in _sql_for(cur)


def test_upsert_topic_activity_stores_rubric_key():
    conn, cur = _make_conn(fetchone_return=(1,))
    repo.upsert_topic_activity(
        conn,
        topic_id=1,
        activity_key="quiz",
        activity_type="quiz",
        rubric_key="quiz_rubric_v1",
    )
    assert "quiz_rubric_v1" in _params_for(cur)


def test_upsert_topic_activity_stores_is_required():
    conn, cur = _make_conn(fetchone_return=(1,))
    repo.upsert_topic_activity(
        conn, topic_id=1, activity_key="reflection", activity_type="reflection",
        is_required=False,
    )
    assert False in _params_for(cur)


# ── get_course_by_key ─────────────────────────────────────────────────────────

def test_get_course_by_key_selects_from_courses():
    conn, cur = _make_conn(fetchone_return=None)
    cur.description = []
    repo.get_course_by_key(conn, course_key="aipm-v1")
    assert "FROM courses" in _sql_for(cur)


def test_get_course_by_key_returns_none_when_not_found():
    conn, cur = _make_conn(fetchone_return=None)
    cur.description = []
    result = repo.get_course_by_key(conn, course_key="missing")
    assert result is None


def test_get_course_by_key_returns_dict_when_found():
    conn, cur = _make_conn(fetchone_return=(1, "aipm-v1", "AI PM", None, None,
                                            "beginner", "active", "v1", 0, {},
                                            "2026-01-01", "2026-01-01"))
    cur.description = [
        (col,) for col in (
            "course_id", "course_key", "title", "description", "target_audience",
            "level", "status", "version", "sequence_order", "metadata",
            "created_at", "updated_at",
        )
    ]
    result = repo.get_course_by_key(conn, course_key="aipm-v1")
    assert isinstance(result, dict)
    assert result["course_key"] == "aipm-v1"


def test_get_course_by_key_passes_course_key_param():
    conn, cur = _make_conn(fetchone_return=None)
    cur.description = []
    repo.get_course_by_key(conn, course_key="my-course")
    assert "my-course" in _params_for(cur)


# ── list_courses ──────────────────────────────────────────────────────────────

def test_list_courses_returns_list():
    conn, cur = _make_conn(fetchall_return=[])
    cur.description = []
    result = repo.list_courses(conn)
    assert isinstance(result, list)


def test_list_courses_filters_by_status_when_provided():
    conn, cur = _make_conn(fetchall_return=[])
    cur.description = []
    repo.list_courses(conn, status="active")
    sql = _sql_for(cur)
    assert "WHERE status = %s" in sql
    assert "active" in _params_for(cur)


def test_list_courses_no_where_when_status_is_none():
    conn, cur = _make_conn(fetchall_return=[])
    cur.description = []
    repo.list_courses(conn, status=None)
    assert "WHERE" not in _sql_for(cur)


def test_list_courses_orders_by_sequence_order():
    conn, cur = _make_conn(fetchall_return=[])
    cur.description = []
    repo.list_courses(conn)
    assert "ORDER BY sequence_order" in _sql_for(cur)


# ── list_modules_for_course ───────────────────────────────────────────────────

def test_list_modules_for_course_returns_list():
    conn, cur = _make_conn(fetchall_return=[])
    cur.description = []
    result = repo.list_modules_for_course(conn, course_id=1)
    assert isinstance(result, list)


def test_list_modules_for_course_filters_by_course_id():
    conn, cur = _make_conn(fetchall_return=[])
    cur.description = []
    repo.list_modules_for_course(conn, course_id=5)
    assert "WHERE course_id = %s" in _sql_for(cur)
    assert 5 in _params_for(cur)


def test_list_modules_for_course_orders_by_sequence_order():
    conn, cur = _make_conn(fetchall_return=[])
    cur.description = []
    repo.list_modules_for_course(conn, course_id=1)
    assert "ORDER BY sequence_order" in _sql_for(cur)


# ── list_topics_for_course ────────────────────────────────────────────────────

def test_list_topics_for_course_returns_list():
    conn, cur = _make_conn(fetchall_return=[])
    cur.description = []
    result = repo.list_topics_for_course(conn, course_id=1)
    assert isinstance(result, list)


def test_list_topics_for_course_filters_by_course_id():
    conn, cur = _make_conn(fetchall_return=[])
    cur.description = []
    repo.list_topics_for_course(conn, course_id=3)
    assert 3 in _params_for(cur)


def test_list_topics_for_course_orders_by_sequence_order():
    conn, cur = _make_conn(fetchall_return=[])
    cur.description = []
    repo.list_topics_for_course(conn, course_id=1)
    assert "ORDER BY sequence_order" in _sql_for(cur)


# ── list_topics_for_module ────────────────────────────────────────────────────

def test_list_topics_for_module_returns_list():
    conn, cur = _make_conn(fetchall_return=[])
    cur.description = []
    result = repo.list_topics_for_module(conn, module_id=2)
    assert isinstance(result, list)


def test_list_topics_for_module_filters_by_module_id():
    conn, cur = _make_conn(fetchall_return=[])
    cur.description = []
    repo.list_topics_for_module(conn, module_id=7)
    assert 7 in _params_for(cur)


def test_list_topics_for_module_orders_by_sequence_order():
    conn, cur = _make_conn(fetchall_return=[])
    cur.description = []
    repo.list_topics_for_module(conn, module_id=1)
    assert "ORDER BY sequence_order" in _sql_for(cur)


# ── get_topic_by_legacy_id ────────────────────────────────────────────────────

def test_get_topic_by_legacy_id_selects_from_course_topics():
    conn, cur = _make_conn(fetchone_return=None)
    cur.description = []
    repo.get_topic_by_legacy_id(conn, legacy_topic_id="aipm-week-1-transformers")
    assert "FROM course_topics" in _sql_for(cur)


def test_get_topic_by_legacy_id_filters_on_legacy_topic_id():
    conn, cur = _make_conn(fetchone_return=None)
    cur.description = []
    repo.get_topic_by_legacy_id(conn, legacy_topic_id="aipm-week-1-transformers")
    sql = _sql_for(cur)
    assert "legacy_topic_id = %s" in sql
    assert "aipm-week-1-transformers" in _params_for(cur)


def test_get_topic_by_legacy_id_returns_none_when_not_found():
    conn, cur = _make_conn(fetchone_return=None)
    cur.description = []
    result = repo.get_topic_by_legacy_id(conn, legacy_topic_id="missing")
    assert result is None


def test_get_topic_by_legacy_id_returns_dict_when_found():
    conn, cur = _make_conn(
        fetchone_return=(10, 1, 2, "aipm-week-1-transformers", "t-key",
                         "Transformers", None, "beginner", 0, None,
                         "active", {}, "2026-01-01", "2026-01-01")
    )
    cur.description = [
        (col,) for col in (
            "topic_id", "course_id", "module_id", "legacy_topic_id", "topic_key",
            "title", "description", "difficulty_level", "sequence_order",
            "estimated_minutes", "status", "metadata", "created_at", "updated_at",
        )
    ]
    result = repo.get_topic_by_legacy_id(conn, legacy_topic_id="aipm-week-1-transformers")
    assert isinstance(result, dict)
    assert result["legacy_topic_id"] == "aipm-week-1-transformers"


# ── list_activities_for_topic ─────────────────────────────────────────────────

def test_list_activities_for_topic_returns_list():
    conn, cur = _make_conn(fetchall_return=[])
    cur.description = []
    result = repo.list_activities_for_topic(conn, topic_id=1)
    assert isinstance(result, list)


def test_list_activities_for_topic_filters_by_topic_id():
    conn, cur = _make_conn(fetchall_return=[])
    cur.description = []
    repo.list_activities_for_topic(conn, topic_id=4)
    assert 4 in _params_for(cur)


def test_list_activities_for_topic_orders_by_sequence_order():
    conn, cur = _make_conn(fetchall_return=[])
    cur.description = []
    repo.list_activities_for_topic(conn, topic_id=1)
    assert "ORDER BY sequence_order" in _sql_for(cur)


# ── list_skills_for_topic ─────────────────────────────────────────────────────

def test_list_skills_for_topic_returns_list():
    conn, cur = _make_conn(fetchall_return=[])
    cur.description = []
    result = repo.list_skills_for_topic(conn, topic_id=1)
    assert isinstance(result, list)


def test_list_skills_for_topic_joins_skills_table():
    conn, cur = _make_conn(fetchall_return=[])
    cur.description = []
    repo.list_skills_for_topic(conn, topic_id=1)
    assert "JOIN skills" in _sql_for(cur)


def test_list_skills_for_topic_filters_by_topic_id():
    conn, cur = _make_conn(fetchall_return=[])
    cur.description = []
    repo.list_skills_for_topic(conn, topic_id=8)
    assert 8 in _params_for(cur)
