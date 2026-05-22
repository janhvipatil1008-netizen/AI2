"""Text-based tests verifying the content_cache table exists in schema.sql.

These tests do not connect to a database. They read the SQL file directly and
confirm the additive content-cache schema exists without changing runtime state.
"""

from pathlib import Path

SCHEMA_PATH = Path(__file__).parent.parent / "database" / "schema.sql"


def _sql() -> str:
    return SCHEMA_PATH.read_text(encoding="utf-8")


def _compact(sql: str) -> str:
    return " ".join(sql.split())


def _cache_block() -> str:
    """Return the text from the CREATE TABLE content_cache statement to the end."""
    sql = _sql()
    start = sql.index("CREATE TABLE IF NOT EXISTS content_cache")
    return sql[start:]


# ── Table exists ──────────────────────────────────────────────────────────────

def test_content_cache_table_present():
    assert "content_cache" in _sql()


def test_content_cache_uses_create_table_if_not_exists():
    assert "CREATE TABLE IF NOT EXISTS content_cache" in _sql()


# ── Section comments ──────────────────────────────────────────────────────────

def test_content_cache_comments_mention_reusable_canonical_content():
    sql = _sql()
    assert "reusable canonical AI-generated learning content" in sql


def test_content_cache_comments_mention_repeated_claude_calls():
    sql = _sql()
    assert "repeated Claude calls" in sql


def test_content_cache_comments_note_personalised_feedback_excluded():
    sql = _sql()
    assert "Personalised feedback" in sql or "personalised feedback" in sql or "Personalized" in sql


def test_content_cache_comments_note_schema_only():
    sql = _sql()
    assert "schema-only" in sql


# ── Required columns ──────────────────────────────────────────────────────────

def test_content_cache_has_cache_key():
    block = _cache_block()
    assert "cache_key" in block


def test_content_cache_has_track_key():
    block = _cache_block()
    assert "track_key" in block


def test_content_cache_has_legacy_topic_id():
    block = _cache_block()
    assert "legacy_topic_id" in block


def test_content_cache_has_topic_id_reference():
    block = _compact(_cache_block())
    assert "topic_id INTEGER REFERENCES learning_topics(id) ON DELETE SET NULL" in block


def test_content_cache_has_content_type():
    block = _cache_block()
    assert "content_type" in block


def test_content_cache_has_difficulty_level():
    block = _cache_block()
    assert "difficulty_level" in block


def test_content_cache_has_language():
    block = _cache_block()
    assert "language" in block


def test_content_cache_has_version():
    block = _cache_block()
    assert "version" in block


def test_content_cache_has_provider():
    block = _cache_block()
    assert "provider" in block


def test_content_cache_has_model():
    block = _cache_block()
    assert "model" in block


def test_content_cache_has_content():
    block = _cache_block()
    assert "content" in block


def test_content_cache_has_metadata_jsonb():
    block = _compact(_cache_block())
    assert "metadata JSONB NOT NULL DEFAULT '{}'::jsonb" in block


def test_content_cache_has_status():
    block = _cache_block()
    assert "status" in block


def test_content_cache_has_created_at():
    block = _cache_block()
    assert "created_at" in block


def test_content_cache_has_updated_at():
    block = _cache_block()
    assert "updated_at" in block


# ── NOT NULL constraints and defaults ─────────────────────────────────────────

def test_content_cache_cache_key_is_not_null():
    block = _compact(_cache_block())
    assert "cache_key TEXT NOT NULL" in block


def test_content_cache_content_type_is_not_null():
    block = _compact(_cache_block())
    assert "content_type TEXT NOT NULL" in block


def test_content_cache_content_is_not_null():
    block = _compact(_cache_block())
    assert "content TEXT NOT NULL" in block


def test_content_cache_difficulty_level_has_default():
    block = _compact(_cache_block())
    assert "difficulty_level TEXT NOT NULL DEFAULT 'beginner'" in block


def test_content_cache_language_has_default():
    block = _compact(_cache_block())
    assert "language TEXT NOT NULL DEFAULT 'en'" in block


def test_content_cache_version_has_default():
    block = _compact(_cache_block())
    assert "version TEXT NOT NULL DEFAULT 'v1'" in block


def test_content_cache_status_has_default():
    block = _compact(_cache_block())
    assert "status TEXT NOT NULL DEFAULT 'active'" in block


def test_content_cache_timestamps_have_defaults():
    block = _compact(_cache_block())
    assert "created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()" in block
    assert "updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()" in block


# ── Uniqueness ────────────────────────────────────────────────────────────────

def test_content_cache_has_unique_cache_key():
    sql = _compact(_sql())
    assert (
        "UNIQUE(cache_key)" in sql
        or "CREATE UNIQUE INDEX IF NOT EXISTS idx_content_cache_cache_key ON content_cache(cache_key)" in sql
    )


# ── Indexes ───────────────────────────────────────────────────────────────────

def test_content_cache_indexes_present():
    sql = _sql()
    for idx in (
        "idx_content_cache_cache_key",
        "idx_content_cache_track_key",
        "idx_content_cache_legacy_topic_id",
        "idx_content_cache_topic_id",
        "idx_content_cache_content_type",
        "idx_content_cache_difficulty_level",
        "idx_content_cache_language",
        "idx_content_cache_version",
        "idx_content_cache_status",
        "idx_content_cache_created_at",
        "idx_content_cache_updated_at",
        "idx_content_cache_lookup",
    ):
        assert idx in sql, f"missing index: {idx}"


def test_content_cache_composite_lookup_index_covers_expected_columns():
    sql = _compact(_sql())
    assert (
        "idx_content_cache_lookup ON content_cache(track_key, legacy_topic_id, "
        "content_type, difficulty_level, language, version, status)"
    ) in sql


# ── Existing tables remain intact ─────────────────────────────────────────────

def test_existing_usage_events_table_remains_intact():
    sql = _sql()
    assert "CREATE TABLE IF NOT EXISTS usage_events" in sql
    assert "idx_usage_events_event_id" in sql
    assert "idx_usage_events_session_event_type" in sql


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
