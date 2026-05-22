"""Lightweight text-based tests verifying new learning tables exist in schema.sql.

These tests do not connect to a database — they read the SQL file directly.
They confirm that the additive curriculum schema was written correctly and that
transition-compatibility columns are present before any runtime migration starts.
"""

from pathlib import Path

SCHEMA_PATH = Path(__file__).parent.parent / "database" / "schema.sql"


def _sql() -> str:
    return SCHEMA_PATH.read_text(encoding="utf-8")


# ── Table presence ────────────────────────────────────────────────────────────

def test_schema_file_exists():
    assert SCHEMA_PATH.exists(), f"schema.sql not found at {SCHEMA_PATH}"


def test_learning_tracks_table_present():
    assert "learning_tracks" in _sql()


def test_learning_modules_table_present():
    assert "learning_modules" in _sql()


def test_learning_topics_table_present():
    assert "learning_topics" in _sql()


def test_topic_progress_table_present():
    assert "topic_progress" in _sql()


def test_todos_table_present():
    assert "todos" in _sql()


# ── CREATE TABLE IF NOT EXISTS safety ─────────────────────────────────────────

def test_all_new_tables_use_if_not_exists():
    sql = _sql()
    for table in ("learning_tracks", "learning_modules", "learning_topics", "topic_progress", "todos"):
        assert f"CREATE TABLE IF NOT EXISTS {table}" in sql, (
            f"{table} does not use CREATE TABLE IF NOT EXISTS"
        )


# ── Transition compatibility columns ─────────────────────────────────────────

def test_legacy_topic_id_column_present():
    assert "legacy_topic_id" in _sql()


def test_legacy_linked_topic_id_column_present():
    assert "legacy_linked_topic_id" in _sql()


# ── Key structural columns ────────────────────────────────────────────────────

def test_learning_tracks_has_track_key():
    assert "track_key" in _sql()


def test_learning_tracks_has_status():
    sql = _sql()
    tracks_block = sql[sql.index("learning_tracks"):sql.index("learning_modules")]
    assert "status" in tracks_block


def test_learning_modules_has_sequence_order():
    assert "sequence_order" in _sql()


def test_learning_topics_has_freshness_label():
    assert "freshness_label" in _sql()


def test_topic_progress_has_step_columns():
    sql = _sql()
    for col in (
        "learn_status",
        "quiz_status",
        "portfolio_task_status",
        "interview_practice_status",
        "reflection_status",
        "completion_percent",
    ):
        assert col in sql, f"topic_progress missing column: {col}"


def test_todos_has_required_columns():
    sql = _sql()
    for col in ("todo_type", "status", "due_label", "due_date", "completed_at"):
        assert col in sql, f"todos missing column: {col}"


# ── Foreign key references to existing tables ─────────────────────────────────

def test_topic_progress_references_users():
    sql = _sql()
    progress_block = sql[sql.index("topic_progress"):]
    assert "users(user_id)" in progress_block


def test_topic_progress_references_sessions():
    sql = _sql()
    progress_block = sql[sql.index("topic_progress"):]
    assert "sessions(session_id)" in progress_block


def test_todos_references_learning_topics():
    sql = _sql()
    todos_block = sql[sql.index("CREATE TABLE IF NOT EXISTS todos"):]
    assert "learning_topics(id)" in todos_block


# ── Indexes present ───────────────────────────────────────────────────────────

def test_indexes_created_for_new_tables():
    sql = _sql()
    for idx in (
        "idx_learning_tracks_status",
        "idx_learning_modules_track_id",
        "idx_learning_topics_module_id",
        "idx_topic_progress_user_id",
        "idx_topic_progress_legacy_topic",
        "idx_todos_user_id",
        "idx_todos_due_date",
    ):
        assert idx in sql, f"missing index: {idx}"


# ── Existing tables untouched ─────────────────────────────────────────────────

def test_existing_tables_still_present():
    sql = _sql()
    for table in ("users", "sessions", "conversation_history", "learner_profiles", "jobs", "job_enrichments"):
        assert table in sql, f"existing table missing: {table}"


def test_sessions_session_data_column_untouched():
    sql = _sql()
    sessions_block = sql[sql.index("CREATE TABLE IF NOT EXISTS sessions"):sql.index("CREATE TABLE IF NOT EXISTS conversation_history")]
    assert "session_data" in sessions_block
