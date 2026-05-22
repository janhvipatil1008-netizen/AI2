"""Text-based schema tests for the modular curriculum tables.

Verifies that database/schema.sql contains the expected CREATE TABLE statements,
indexes, constraints, and section comments for the modular curriculum model.
No DB connection is required; all assertions operate on the raw SQL text.
"""

import pathlib

SCHEMA_PATH = pathlib.Path(__file__).parent.parent / "database" / "schema.sql"


def _sql() -> str:
    return SCHEMA_PATH.read_text(encoding="utf-8")


# ── Presence of new tables ────────────────────────────────────────────────────

def test_courses_table_exists():
    assert "CREATE TABLE IF NOT EXISTS courses" in _sql()


def test_course_modules_table_exists():
    assert "CREATE TABLE IF NOT EXISTS course_modules" in _sql()


def test_skills_table_exists():
    assert "CREATE TABLE IF NOT EXISTS skills" in _sql()


def test_course_topics_table_exists():
    assert "CREATE TABLE IF NOT EXISTS course_topics" in _sql()


def test_topic_skills_table_exists():
    assert "CREATE TABLE IF NOT EXISTS topic_skills" in _sql()


def test_topic_activities_table_exists():
    assert "CREATE TABLE IF NOT EXISTS topic_activities" in _sql()


# ── CREATE TABLE IF NOT EXISTS used for all new tables ───────────────────────

def test_all_new_tables_use_if_not_exists():
    sql = _sql()
    for table in ("courses", "course_modules", "skills", "course_topics",
                  "topic_skills", "topic_activities"):
        assert f"CREATE TABLE IF NOT EXISTS {table}" in sql, (
            f"Expected 'CREATE TABLE IF NOT EXISTS {table}'"
        )


# ── sequence_order replaces week_number ──────────────────────────────────────

def test_new_tables_use_sequence_order_not_week_number():
    sql = _sql()
    # sequence_order must appear for every new table
    assert sql.count("sequence_order") >= 5
    # week_number must not be introduced as a column definition in any table
    # (it may appear in comments describing the migration rationale)
    import re
    column_defs = re.findall(r"^\s+week_number\s+\w", sql, re.MULTILINE)
    assert column_defs == [], (
        f"week_number found as a column definition: {column_defs}"
    )


# ── courses table columns ─────────────────────────────────────────────────────

def test_courses_has_course_key():
    assert "course_key" in _sql()


def test_courses_has_title():
    sql = _sql()
    # title appears in courses block
    courses_block = sql[sql.index("CREATE TABLE IF NOT EXISTS courses"):]
    assert "title" in courses_block[:500]


def test_courses_has_status():
    sql = _sql()
    courses_block = sql[sql.index("CREATE TABLE IF NOT EXISTS courses"):]
    assert "status" in courses_block[:500]


def test_courses_has_version():
    sql = _sql()
    courses_block = sql[sql.index("CREATE TABLE IF NOT EXISTS courses"):]
    assert "version" in courses_block[:500]


def test_courses_has_level():
    sql = _sql()
    courses_block = sql[sql.index("CREATE TABLE IF NOT EXISTS courses"):]
    assert "level" in courses_block[:500]


def test_courses_course_key_is_unique():
    sql = _sql()
    courses_block = sql[sql.index("CREATE TABLE IF NOT EXISTS courses"):]
    assert "UNIQUE" in courses_block[:600]


# ── course_modules references courses ────────────────────────────────────────

def test_course_modules_references_courses():
    sql = _sql()
    block = sql[sql.index("CREATE TABLE IF NOT EXISTS course_modules"):]
    assert "REFERENCES courses" in block[:600]


def test_course_modules_has_on_delete_cascade():
    sql = _sql()
    block = sql[sql.index("CREATE TABLE IF NOT EXISTS course_modules"):]
    assert "ON DELETE CASCADE" in block[:600]


def test_course_modules_has_unique_course_module_key():
    sql = _sql()
    block = sql[sql.index("CREATE TABLE IF NOT EXISTS course_modules"):]
    assert "UNIQUE(course_id, module_key)" in block[:700]


# ── course_topics references courses and modules ──────────────────────────────

def test_course_topics_references_courses():
    sql = _sql()
    block = sql[sql.index("CREATE TABLE IF NOT EXISTS course_topics"):]
    assert "REFERENCES courses" in block[:800]


def test_course_topics_references_course_modules():
    sql = _sql()
    block = sql[sql.index("CREATE TABLE IF NOT EXISTS course_topics"):]
    assert "REFERENCES course_modules" in block[:800]


def test_course_topics_has_legacy_topic_id_bridge():
    sql = _sql()
    block = sql[sql.index("CREATE TABLE IF NOT EXISTS course_topics"):]
    assert "legacy_topic_id" in block[:800]


def test_course_topics_has_unique_course_topic_key():
    sql = _sql()
    block = sql[sql.index("CREATE TABLE IF NOT EXISTS course_topics"):]
    assert "UNIQUE(course_id, topic_key)" in block[:900]


def test_course_topics_has_difficulty_level():
    sql = _sql()
    block = sql[sql.index("CREATE TABLE IF NOT EXISTS course_topics"):]
    assert "difficulty_level" in block[:800]


# ── topic_skills links topics and skills ─────────────────────────────────────

def test_topic_skills_references_course_topics():
    sql = _sql()
    block = sql[sql.index("CREATE TABLE IF NOT EXISTS topic_skills"):]
    assert "REFERENCES course_topics" in block[:400]


def test_topic_skills_references_skills():
    sql = _sql()
    block = sql[sql.index("CREATE TABLE IF NOT EXISTS topic_skills"):]
    assert "REFERENCES skills" in block[:400]


def test_topic_skills_has_composite_primary_key():
    sql = _sql()
    block = sql[sql.index("CREATE TABLE IF NOT EXISTS topic_skills"):]
    assert "PRIMARY KEY (topic_id, skill_id)" in block[:400]


def test_topic_skills_has_importance_column():
    sql = _sql()
    block = sql[sql.index("CREATE TABLE IF NOT EXISTS topic_skills"):]
    assert "importance" in block[:400]


# ── topic_activities columns ──────────────────────────────────────────────────

def test_topic_activities_references_course_topics():
    sql = _sql()
    block = sql[sql.index("CREATE TABLE IF NOT EXISTS topic_activities"):]
    assert "REFERENCES course_topics" in block[:600]


def test_topic_activities_has_activity_type():
    sql = _sql()
    block = sql[sql.index("CREATE TABLE IF NOT EXISTS topic_activities"):]
    assert "activity_type" in block[:600]


def test_topic_activities_has_rubric_key():
    sql = _sql()
    block = sql[sql.index("CREATE TABLE IF NOT EXISTS topic_activities"):]
    assert "rubric_key" in block[:600]


def test_topic_activities_has_is_required():
    sql = _sql()
    block = sql[sql.index("CREATE TABLE IF NOT EXISTS topic_activities"):]
    assert "is_required" in block[:600]


def test_topic_activities_has_unique_topic_activity_key():
    sql = _sql()
    block = sql[sql.index("CREATE TABLE IF NOT EXISTS topic_activities"):]
    assert "UNIQUE(topic_id, activity_key)" in block[:700]


# ── Important indexes ─────────────────────────────────────────────────────────

def test_index_on_courses_course_key():
    assert "idx_courses_course_key" in _sql()


def test_index_on_courses_status():
    assert "idx_courses_status" in _sql()


def test_index_on_courses_sequence_order():
    assert "idx_courses_sequence_order" in _sql()


def test_index_on_course_modules_course_id():
    assert "idx_course_modules_course_id" in _sql()


def test_composite_index_course_modules_course_sequence():
    assert "idx_course_modules_course_sequence" in _sql()


def test_index_on_course_topics_legacy_topic_id():
    assert "idx_course_topics_legacy_topic_id" in _sql()


def test_index_on_course_topics_course_id():
    assert "idx_course_topics_course_id" in _sql()


def test_composite_index_course_topics_course_sequence():
    assert "idx_course_topics_course_sequence" in _sql()


def test_composite_index_course_topics_module_sequence():
    assert "idx_course_topics_module_sequence" in _sql()


def test_index_on_topic_skills_skill_id():
    assert "idx_topic_skills_skill_id" in _sql()


def test_index_on_topic_activities_activity_type():
    assert "idx_topic_activities_activity_type" in _sql()


def test_composite_index_topic_activities_topic_sequence():
    assert "idx_topic_activities_topic_sequence" in _sql()


def test_index_on_skills_category():
    assert "idx_skills_category" in _sql()


# ── Section comment mentions modular curriculum and WEEKS/ROLE_TRACKS ─────────

def test_comment_mentions_modular_curriculum():
    sql = _sql()
    assert "Modular curriculum schema" in sql or "modular curriculum" in sql.lower()


def test_comment_mentions_weeks_remain_temporary():
    sql = _sql()
    assert "WEEKS" in sql


def test_comment_mentions_role_tracks_remain():
    sql = _sql()
    assert "ROLE_TRACKS" in sql


def test_comment_mentions_runtime_migration_later():
    sql = _sql()
    assert "feature flag" in sql.lower() or "AI2_MODULAR_CURRICULUM_ENABLED" in sql


# ── Old tables remain intact ──────────────────────────────────────────────────

def test_old_learning_tracks_table_intact():
    assert "CREATE TABLE IF NOT EXISTS learning_tracks" in _sql()


def test_old_learning_modules_table_intact():
    assert "CREATE TABLE IF NOT EXISTS learning_modules" in _sql()


def test_old_learning_topics_table_intact():
    assert "CREATE TABLE IF NOT EXISTS learning_topics" in _sql()


def test_learning_tracks_still_has_track_key():
    sql = _sql()
    block = sql[sql.index("CREATE TABLE IF NOT EXISTS learning_tracks"):]
    assert "track_key" in block[:400]


def test_learning_modules_still_references_learning_tracks():
    sql = _sql()
    block = sql[sql.index("CREATE TABLE IF NOT EXISTS learning_modules"):]
    assert "REFERENCES learning_tracks" in block[:400]


def test_learning_topics_still_references_learning_modules():
    sql = _sql()
    block = sql[sql.index("CREATE TABLE IF NOT EXISTS learning_topics"):]
    assert "REFERENCES learning_modules" in block[:400]
