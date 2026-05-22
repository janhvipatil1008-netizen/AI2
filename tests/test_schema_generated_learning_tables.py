"""Lightweight text-based tests verifying the 6 generated-content/submission tables
exist in database/schema.sql.

No database connection required — reads the SQL file directly and checks structure.
"""

from pathlib import Path

SCHEMA_PATH = Path(__file__).parent.parent / "database" / "schema.sql"


def _sql() -> str:
    return SCHEMA_PATH.read_text(encoding="utf-8")


def _block(sql: str, table: str, next_table: str | None = None) -> str:
    start = sql.index(f"CREATE TABLE IF NOT EXISTS {table}")
    if next_table:
        end = sql.index(f"CREATE TABLE IF NOT EXISTS {next_table}")
        return sql[start:end]
    return sql[start:]


# ── Table presence ────────────────────────────────────────────────────────────

def test_generated_topic_content_table_present():
    assert "generated_topic_content" in _sql()


def test_generated_topic_practice_table_present():
    assert "generated_topic_practice" in _sql()


def test_quiz_submissions_table_present():
    assert "quiz_submissions" in _sql()


def test_portfolio_submissions_table_present():
    assert "portfolio_submissions" in _sql()


def test_interview_submissions_table_present():
    assert "interview_submissions" in _sql()


def test_topic_notes_table_present():
    assert "topic_notes" in _sql()


# ── CREATE TABLE IF NOT EXISTS safety ─────────────────────────────────────────

def test_all_new_tables_use_if_not_exists():
    sql = _sql()
    for table in (
        "generated_topic_content",
        "generated_topic_practice",
        "quiz_submissions",
        "portfolio_submissions",
        "interview_submissions",
        "topic_notes",
    ):
        assert f"CREATE TABLE IF NOT EXISTS {table}" in sql, (
            f"{table} does not use CREATE TABLE IF NOT EXISTS"
        )


# ── session_id and legacy_topic_id present in all new tables ─────────────────

def test_all_new_tables_have_session_id_and_legacy_topic_id():
    sql = _sql()
    tables = [
        ("generated_topic_content",  "generated_topic_practice"),
        ("generated_topic_practice", "quiz_submissions"),
        ("quiz_submissions",         "portfolio_submissions"),
        ("portfolio_submissions",    "interview_submissions"),
        ("interview_submissions",    "topic_notes"),
        ("topic_notes",              None),
    ]
    for table, next_t in tables:
        block = _block(sql, table, next_t)
        assert "session_id" in block,       f"{table} missing session_id"
        assert "legacy_topic_id" in block,  f"{table} missing legacy_topic_id"


# ── generated_topic_content columns ──────────────────────────────────────────

def test_generated_topic_content_has_required_columns():
    sql  = _sql()
    block = _block(sql, "generated_topic_content", "generated_topic_practice")
    for col in ("content", "model", "freshness_label", "source", "generated_at", "version"):
        assert col in block, f"generated_topic_content missing column: {col}"


# ── generated_topic_practice columns ─────────────────────────────────────────

def test_generated_topic_practice_has_practice_type():
    sql   = _sql()
    block = _block(sql, "generated_topic_practice", "quiz_submissions")
    assert "practice_type" in block


def test_generated_topic_practice_has_content_and_model():
    sql   = _sql()
    block = _block(sql, "generated_topic_practice", "quiz_submissions")
    for col in ("content", "model", "freshness_label", "source"):
        assert col in block, f"generated_topic_practice missing column: {col}"


# ── quiz_submissions columns ──────────────────────────────────────────────────

def test_quiz_submissions_has_required_columns():
    sql   = _sql()
    block = _block(sql, "quiz_submissions", "portfolio_submissions")
    for col in ("answers", "evaluation", "score", "evaluated_at"):
        assert col in block, f"quiz_submissions missing column: {col}"


# ── portfolio_submissions columns ─────────────────────────────────────────────

def test_portfolio_submissions_has_required_columns():
    sql   = _sql()
    block = _block(sql, "portfolio_submissions", "interview_submissions")
    for col in ("submission", "feedback", "score", "reviewed_at"):
        assert col in block, f"portfolio_submissions missing column: {col}"


# ── interview_submissions columns ─────────────────────────────────────────────

def test_interview_submissions_has_required_columns():
    sql   = _sql()
    block = _block(sql, "interview_submissions", "topic_notes")
    for col in ("answer", "feedback", "score", "reviewed_at"):
        assert col in block, f"interview_submissions missing column: {col}"


# ── topic_notes columns ───────────────────────────────────────────────────────

def test_topic_notes_has_required_columns():
    sql   = _sql()
    block = _block(sql, "topic_notes", None)
    for col in ("reflection", "confusions", "application_idea"):
        assert col in block, f"topic_notes missing column: {col}"


# ── FK references to learning_topics ─────────────────────────────────────────

def test_all_new_tables_reference_learning_topics():
    sql = _sql()
    tables = [
        ("generated_topic_content",  "generated_topic_practice"),
        ("generated_topic_practice", "quiz_submissions"),
        ("quiz_submissions",         "portfolio_submissions"),
        ("portfolio_submissions",    "interview_submissions"),
        ("interview_submissions",    "topic_notes"),
        ("topic_notes",              None),
    ]
    for table, next_t in tables:
        block = _block(sql, table, next_t)
        assert "learning_topics(id)" in block, f"{table} missing FK to learning_topics(id)"


# ── Indexes present ───────────────────────────────────────────────────────────

def test_generated_topic_content_indexes_present():
    sql = _sql()
    for idx in (
        "idx_generated_topic_content_session_id",
        "idx_generated_topic_content_legacy_topic",
        "idx_generated_topic_content_topic_id",
        "idx_generated_topic_content_generated_at",
        "idx_generated_topic_content_session_legacy",
    ):
        assert idx in sql, f"missing index: {idx}"


def test_generated_topic_practice_indexes_present():
    sql = _sql()
    for idx in (
        "idx_generated_topic_practice_session_id",
        "idx_generated_topic_practice_legacy_topic",
        "idx_generated_topic_practice_practice_type",
        "idx_generated_topic_practice_topic_id",
        "idx_generated_topic_practice_session_legacy_type",
    ):
        assert idx in sql, f"missing index: {idx}"


def test_quiz_submissions_indexes_present():
    sql = _sql()
    for idx in (
        "idx_quiz_submissions_session_id",
        "idx_quiz_submissions_legacy_topic",
        "idx_quiz_submissions_score",
        "idx_quiz_submissions_submitted_at",
        "idx_quiz_submissions_session_legacy",
    ):
        assert idx in sql, f"missing index: {idx}"


def test_portfolio_submissions_indexes_present():
    sql = _sql()
    for idx in (
        "idx_portfolio_submissions_session_id",
        "idx_portfolio_submissions_legacy_topic",
        "idx_portfolio_submissions_score",
        "idx_portfolio_submissions_submitted_at",
        "idx_portfolio_submissions_session_legacy",
    ):
        assert idx in sql, f"missing index: {idx}"


def test_interview_submissions_indexes_present():
    sql = _sql()
    for idx in (
        "idx_interview_submissions_session_id",
        "idx_interview_submissions_legacy_topic",
        "idx_interview_submissions_score",
        "idx_interview_submissions_submitted_at",
        "idx_interview_submissions_session_legacy",
    ):
        assert idx in sql, f"missing index: {idx}"


def test_topic_notes_indexes_present():
    sql = _sql()
    for idx in (
        "idx_topic_notes_session_id",
        "idx_topic_notes_legacy_topic",
        "idx_topic_notes_topic_id",
        "idx_topic_notes_updated_at",
        "idx_topic_notes_session_legacy",
    ):
        assert idx in sql, f"missing index: {idx}"


# ── Existing tables untouched ─────────────────────────────────────────────────

def test_existing_curriculum_tables_still_present():
    sql = _sql()
    for table in (
        "users", "sessions", "conversation_history", "learner_profiles",
        "jobs", "job_enrichments",
        "learning_tracks", "learning_modules", "learning_topics",
        "topic_progress", "todos",
    ):
        assert table in sql, f"existing table missing: {table}"


def test_existing_indexes_still_present():
    sql = _sql()
    for idx in (
        "idx_topic_progress_session_id",
        "idx_topic_progress_legacy_topic",
        "idx_todos_session_id",
        "idx_todos_due_date",
        "idx_learning_tracks_status",
    ):
        assert idx in sql, f"existing index missing: {idx}"
