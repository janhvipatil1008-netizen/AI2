"""Text-based tests verifying the usage_events table exists in schema.sql.

These tests do not connect to a database. They read the SQL file directly and
confirm the additive usage-event schema exists without changing runtime state.
"""

from pathlib import Path

SCHEMA_PATH = Path(__file__).parent.parent / "database" / "schema.sql"


def _sql() -> str:
    return SCHEMA_PATH.read_text(encoding="utf-8")


def _compact(sql: str) -> str:
    return " ".join(sql.split())


def _usage_events_block() -> str:
    sql = _sql()
    start = sql.index("CREATE TABLE IF NOT EXISTS usage_events")
    end_marker = "CREATE UNIQUE INDEX IF NOT EXISTS idx_usage_events_event_id"
    end = sql.index(end_marker)
    return sql[start:end]


def test_usage_events_table_present():
    assert "usage_events" in _sql()


def test_usage_events_uses_create_table_if_not_exists():
    assert "CREATE TABLE IF NOT EXISTS usage_events" in _sql()


def test_usage_events_comments_document_schema_only_transition():
    sql = _sql()
    assert "usage_events stores AI/harness usage events" in sql
    assert "SessionContext remains the runtime source of truth for now" in sql
    assert "DB write-through will be added later" in sql


def test_usage_events_has_required_columns():
    block = _usage_events_block()
    for col in (
        "event_id",
        "user_id",
        "session_id",
        "legacy_topic_id",
        "event_type",
        "model",
        "source",
        "status",
        "metadata",
        "created_at",
    ):
        assert col in block, f"usage_events missing column: {col}"


def test_usage_events_event_id_is_not_null():
    block = _compact(_usage_events_block())
    assert "event_id TEXT NOT NULL" in block


def test_usage_events_references_users_and_sessions():
    block = _compact(_usage_events_block())
    assert "user_id TEXT REFERENCES users(user_id) ON DELETE CASCADE" in block
    assert "session_id TEXT REFERENCES sessions(session_id) ON DELETE CASCADE" in block


def test_usage_events_has_metadata_jsonb_default():
    block = _compact(_usage_events_block())
    assert "metadata JSONB NOT NULL DEFAULT '{}'::jsonb" in block


def test_usage_events_has_created_at_default():
    block = _compact(_usage_events_block())
    assert "created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()" in block


def test_usage_events_has_unique_event_id():
    sql = _compact(_sql())
    assert (
        "UNIQUE(event_id)" in sql
        or "CREATE UNIQUE INDEX IF NOT EXISTS idx_usage_events_event_id ON usage_events(event_id)" in sql
    )


def test_usage_events_indexes_present():
    sql = _sql()
    for idx in (
        "idx_usage_events_event_id",
        "idx_usage_events_user_id",
        "idx_usage_events_session_id",
        "idx_usage_events_legacy_topic",
        "idx_usage_events_event_type",
        "idx_usage_events_source",
        "idx_usage_events_status",
        "idx_usage_events_created_at",
        "idx_usage_events_session_legacy_topic",
        "idx_usage_events_session_event_type",
    ):
        assert idx in sql, f"missing index: {idx}"


def test_existing_generated_learning_tables_remain_intact():
    sql = _sql()
    for table in (
        "generated_topic_content",
        "generated_topic_practice",
        "quiz_submissions",
        "portfolio_submissions",
        "interview_submissions",
        "topic_notes",
    ):
        assert table in sql, f"existing generated-learning table missing: {table}"


def test_existing_learning_tables_remain_intact():
    sql = _sql()
    for table in (
        "learning_tracks",
        "learning_modules",
        "learning_topics",
        "topic_progress",
        "todos",
    ):
        assert table in sql, f"existing learning table missing: {table}"


def test_sessions_session_data_column_remains_intact():
    sql = _sql()
    sessions_block = sql[
        sql.index("CREATE TABLE IF NOT EXISTS sessions") :
        sql.index("CREATE TABLE IF NOT EXISTS conversation_history")
    ]
    assert "session_data" in sessions_block
