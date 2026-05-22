"""Text-based tests for the learning_outcomes schema.

These tests do not connect to a database. They read schema.sql and verify the
additive learning outcome validation table exists.
"""

from pathlib import Path


SCHEMA_PATH = Path(__file__).parent.parent / "database" / "schema.sql"


def _sql() -> str:
    return SCHEMA_PATH.read_text(encoding="utf-8")


def _compact(sql: str) -> str:
    return " ".join(sql.split())


def _learning_outcomes_block() -> str:
    sql = _sql()
    start = sql.index("CREATE TABLE IF NOT EXISTS learning_outcomes")
    end = sql.index("CREATE INDEX IF NOT EXISTS idx_learning_outcomes_user_id")
    return sql[start:end]


def test_learning_outcomes_table_exists():
    assert "learning_outcomes" in _sql()


def test_learning_outcomes_uses_create_table_if_not_exists():
    assert "CREATE TABLE IF NOT EXISTS learning_outcomes" in _sql()


def test_learning_outcomes_comments_mention_learning_improvement():
    sql = _sql()
    assert "tracks baseline and post-topic learning improvement" in sql
    assert "validate whether learners are improving" in sql
    assert "not a full automated model-eval suite yet" in sql


def test_learning_outcomes_important_columns_exist():
    block = _learning_outcomes_block()
    for col in (
        "id",
        "user_id",
        "session_id",
        "legacy_topic_id",
        "topic_id",
        "baseline_prompt",
        "baseline_answer",
        "baseline_score",
        "post_prompt",
        "post_answer",
        "post_score",
        "improvement_delta",
        "status",
        "metadata",
        "created_at",
        "updated_at",
    ):
        assert col in block, f"learning_outcomes missing column: {col}"


def test_learning_outcomes_references_expected_tables():
    block = _compact(_learning_outcomes_block())
    assert "user_id TEXT REFERENCES users(user_id) ON DELETE CASCADE" in block
    assert "session_id TEXT REFERENCES sessions(session_id) ON DELETE CASCADE" in block
    assert "topic_id INTEGER REFERENCES learning_topics(id) ON DELETE SET NULL" in block


def test_learning_outcomes_defaults_exist():
    block = _compact(_learning_outcomes_block())
    assert "status TEXT NOT NULL DEFAULT 'started'" in block
    assert "metadata JSONB NOT NULL DEFAULT '{}'::jsonb" in block
    assert "created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()" in block
    assert "updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()" in block


def test_learning_outcomes_unique_session_legacy_exists():
    block = _compact(_learning_outcomes_block())
    assert "UNIQUE(session_id, legacy_topic_id)" in block


def test_learning_outcomes_indexes_exist():
    sql = _sql()
    for idx in (
        "idx_learning_outcomes_user_id",
        "idx_learning_outcomes_session_id",
        "idx_learning_outcomes_legacy_topic",
        "idx_learning_outcomes_topic_id",
        "idx_learning_outcomes_status",
        "idx_learning_outcomes_created_at",
        "idx_learning_outcomes_updated_at",
        "idx_learning_outcomes_session_legacy",
    ):
        assert idx in sql, f"missing index: {idx}"


def test_learning_outcomes_composite_index_exists():
    compact = _compact(_sql())
    assert (
        "CREATE INDEX IF NOT EXISTS idx_learning_outcomes_session_legacy "
        "ON learning_outcomes(session_id, legacy_topic_id)"
    ) in compact
