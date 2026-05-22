"""Text-based tests for learner course enrollment schema.

These tests read database/schema.sql directly. No database connection is
required; they verify additive schema for future current_week removal.
"""

from __future__ import annotations

import re
from pathlib import Path


SCHEMA_PATH = Path(__file__).parent.parent / "database" / "schema.sql"


def _sql() -> str:
    return SCHEMA_PATH.read_text(encoding="utf-8")


def _compact(sql: str) -> str:
    return " ".join(sql.split())


def _table_block(table: str) -> str:
    sql = _sql()
    start = sql.index(f"CREATE TABLE IF NOT EXISTS {table}")
    match = re.search(r"\nCREATE (?:TABLE|INDEX|UNIQUE INDEX)", sql[start + 1:])
    if not match:
        return sql[start:]
    return sql[start:start + 1 + match.start()]


def _enrollments_block() -> str:
    return _table_block("learner_course_enrollments")


def _module_progress_block() -> str:
    return _table_block("learner_module_progress")


def _topic_progress_block() -> str:
    return _table_block("learner_topic_progress")


def test_learner_course_enrollments_table_exists():
    assert "CREATE TABLE IF NOT EXISTS learner_course_enrollments" in _sql()


def test_learner_module_progress_table_exists():
    assert "CREATE TABLE IF NOT EXISTS learner_module_progress" in _sql()


def test_learner_topic_progress_table_exists():
    assert "CREATE TABLE IF NOT EXISTS learner_topic_progress" in _sql()


def test_new_tables_use_create_table_if_not_exists():
    sql = _sql()
    for table in (
        "learner_course_enrollments",
        "learner_module_progress",
        "learner_topic_progress",
    ):
        assert f"CREATE TABLE IF NOT EXISTS {table}" in sql


def test_learner_course_enrollments_core_columns_exist():
    block = _enrollments_block()
    for col in ("user_id", "session_id", "course_id", "course_key", "status"):
        assert col in block, f"missing enrollment column: {col}"


def test_learner_course_enrollments_current_position_columns_exist():
    block = _enrollments_block()
    for col in ("current_module_key", "current_topic_key", "current_legacy_topic_id"):
        assert col in block, f"missing current-position column: {col}"


def test_learner_course_enrollments_progress_percent_exists():
    assert "progress_percent" in _enrollments_block()


def test_learner_course_enrollments_unique_constraint_exists():
    compact = _compact(_enrollments_block())
    assert "UNIQUE(user_id, session_id, course_key)" in compact


def test_learner_course_enrollments_references_expected_tables():
    compact = _compact(_enrollments_block())
    assert "user_id TEXT REFERENCES users(user_id) ON DELETE CASCADE" in compact
    assert "course_id INTEGER REFERENCES courses(course_id) ON DELETE SET NULL" in compact
    assert "current_module_id INTEGER REFERENCES course_modules(module_id) ON DELETE SET NULL" in compact
    assert "current_topic_id INTEGER REFERENCES course_topics(topic_id) ON DELETE SET NULL" in compact


def test_learner_module_progress_columns_exist():
    block = _module_progress_block()
    for col in ("enrollment_id", "module_key", "status", "progress_percent"):
        assert col in block, f"missing module progress column: {col}"


def test_learner_module_progress_unique_constraint_exists():
    compact = _compact(_module_progress_block())
    assert "UNIQUE(enrollment_id, module_key)" in compact


def test_learner_module_progress_references_enrollment_and_module():
    compact = _compact(_module_progress_block())
    assert (
        "enrollment_id INTEGER REFERENCES learner_course_enrollments(enrollment_id) "
        "ON DELETE CASCADE"
    ) in compact
    assert "module_id INTEGER REFERENCES course_modules(module_id) ON DELETE SET NULL" in compact


def test_learner_topic_progress_columns_exist():
    block = _topic_progress_block()
    for col in ("enrollment_id", "topic_key", "legacy_topic_id", "status", "completion_percent"):
        assert col in block, f"missing topic progress column: {col}"


def test_learner_topic_progress_unique_constraint_exists():
    compact = _compact(_topic_progress_block())
    assert "UNIQUE(enrollment_id, topic_key)" in compact


def test_learner_topic_progress_references_enrollment_and_topic():
    compact = _compact(_topic_progress_block())
    assert (
        "enrollment_id INTEGER REFERENCES learner_course_enrollments(enrollment_id) "
        "ON DELETE CASCADE"
    ) in compact
    assert "topic_id INTEGER REFERENCES course_topics(topic_id) ON DELETE SET NULL" in compact


def test_relevant_indexes_exist():
    sql = _sql()
    for idx in (
        "idx_learner_course_enrollments_user_id",
        "idx_learner_course_enrollments_session_id",
        "idx_learner_course_enrollments_course_key",
        "idx_learner_course_enrollments_status",
        "idx_learner_course_enrollments_current_module_key",
        "idx_learner_course_enrollments_current_topic_key",
        "idx_learner_course_enrollments_current_legacy_topic",
        "idx_learner_course_enrollments_user_session",
        "idx_learner_course_enrollments_user_course",
        "idx_learner_module_progress_enrollment_id",
        "idx_learner_module_progress_module_key",
        "idx_learner_module_progress_status",
        "idx_learner_module_progress_progress_percent",
        "idx_learner_topic_progress_enrollment_id",
        "idx_learner_topic_progress_module_key",
        "idx_learner_topic_progress_topic_key",
        "idx_learner_topic_progress_legacy_topic_id",
        "idx_learner_topic_progress_status",
        "idx_learner_topic_progress_completion_percent",
    ):
        assert idx in sql, f"missing index: {idx}"


def test_comments_mention_current_week_replacement_and_compatibility():
    sql = _sql()
    assert "will eventually replace" in sql
    assert "current_week" in sql
    assert "compatibility" in sql
    assert "legacy_topic_id/current_legacy_topic_id are preserved" in sql


def test_old_learner_progress_tables_remain_intact():
    sql = _sql()
    for table in ("topic_progress", "todos", "learning_outcomes"):
        assert f"CREATE TABLE IF NOT EXISTS {table}" in sql


def test_modular_curriculum_tables_remain_intact():
    sql = _sql()
    for table in ("courses", "course_modules", "skills", "course_topics", "topic_skills", "topic_activities"):
        assert f"CREATE TABLE IF NOT EXISTS {table}" in sql


def test_no_week_number_column_introduced_in_new_tables():
    combined = "\n".join((
        _enrollments_block(),
        _module_progress_block(),
        _topic_progress_block(),
    ))
    column_defs = re.findall(r"^\s+week_number\s+\w", combined, re.MULTILINE)
    assert column_defs == []
