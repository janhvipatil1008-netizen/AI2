"""Fake-cursor tests for content_cache_repository.

These tests do not require a live database. They verify:
- function existence and import safety
- build_content_cache_key determinism and normalisation
- SQL correctness via source inspection and fake-cursor execution
- repository safety constraints (no env, no DB connections, no services, no Claude)
"""

from __future__ import annotations

from pathlib import Path

REPO_FILE = Path(__file__).parent.parent / "repositories" / "content_cache_repository.py"


def _src() -> str:
    return REPO_FILE.read_text(encoding="utf-8")


# ── Fake DB helpers ───────────────────────────────────────────────────────────

class FakeCursor:
    def __init__(self, *, fetchone_row=None, rowcount: int = 0):
        self.executed: list[tuple[str, tuple]] = []
        self._fetchone_row = fetchone_row
        self.rowcount = rowcount

    def execute(self, sql: str, params=None) -> None:
        self.executed.append((sql.strip(), params))

    def fetchone(self):
        return self._fetchone_row

    def fetchall(self):
        return []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


class FakeConn:
    def __init__(self, *, fetchone_row=None, rowcount: int = 0):
        self.cursor_obj = FakeCursor(fetchone_row=fetchone_row, rowcount=rowcount)
        self.commit_count = 0
        self.rollback_count = 0

    def cursor(self, **kwargs):
        return self.cursor_obj

    def commit(self):
        self.commit_count += 1

    def rollback(self):
        self.rollback_count += 1

    @property
    def executed(self):
        return self.cursor_obj.executed


def _all_sql(conn: FakeConn) -> str:
    return " ".join(sql for sql, _ in conn.executed)


def _all_params(conn: FakeConn) -> list:
    return [p for _, params in conn.executed for p in (params or [])]


# ── Import and function existence ─────────────────────────────────────────────

def test_module_imports_safely():
    import repositories.content_cache_repository  # noqa: F401


def test_expected_functions_exist():
    from repositories import content_cache_repository as r
    for fn in (
        "build_content_cache_key",
        "get_cached_content",
        "upsert_cached_content",
        "mark_cached_content_stale",
    ):
        assert callable(getattr(r, fn, None)), f"missing: {fn}"


# ── build_content_cache_key ───────────────────────────────────────────────────

def test_build_key_is_deterministic():
    from repositories.content_cache_repository import build_content_cache_key
    k1 = build_content_cache_key(
        track_key="aipm", legacy_topic_id="rag-basics", content_type="base_lesson"
    )
    k2 = build_content_cache_key(
        track_key="aipm", legacy_topic_id="rag-basics", content_type="base_lesson"
    )
    assert k1 == k2


def test_build_key_includes_all_dimensions():
    from repositories.content_cache_repository import build_content_cache_key
    key = build_content_cache_key(
        track_key="aipm",
        legacy_topic_id="rag-basics",
        content_type="base_lesson",
        difficulty_level="advanced",
        language="fr",
        version="v2",
    )
    assert "track:aipm" in key
    assert "topic:rag-basics" in key
    assert "type:base_lesson" in key
    assert "level:advanced" in key
    assert "lang:fr" in key
    assert "version:v2" in key


def test_build_key_uses_defaults_for_optional_dimensions():
    from repositories.content_cache_repository import build_content_cache_key
    key = build_content_cache_key(
        track_key="aipm", legacy_topic_id="embeddings", content_type="quiz"
    )
    assert "level:beginner" in key
    assert "lang:en" in key
    assert "version:v1" in key


def test_build_key_normalizes_to_lowercase():
    from repositories.content_cache_repository import build_content_cache_key
    key = build_content_cache_key(
        track_key="AIPM", legacy_topic_id="RAG-Basics", content_type="Base_Lesson"
    )
    assert "track:aipm" in key
    assert "topic:rag-basics" in key
    assert "type:base_lesson" in key


def test_build_key_strips_leading_trailing_whitespace():
    from repositories.content_cache_repository import build_content_cache_key
    k1 = build_content_cache_key(
        track_key="aipm", legacy_topic_id="rag-basics", content_type="quiz"
    )
    k2 = build_content_cache_key(
        track_key="  aipm  ", legacy_topic_id="  rag-basics  ", content_type="  quiz  "
    )
    assert k1 == k2


def test_build_key_normalizes_internal_whitespace():
    from repositories.content_cache_repository import build_content_cache_key
    key = build_content_cache_key(
        track_key="ai  pm",
        legacy_topic_id="rag  basics",
        content_type="base  lesson",
    )
    assert " " not in key


def test_build_key_missing_track_key_none_becomes_unknown():
    from repositories.content_cache_repository import build_content_cache_key
    key = build_content_cache_key(
        track_key=None, legacy_topic_id="topic-x", content_type="quiz"
    )
    assert "track:unknown" in key


def test_build_key_empty_track_key_becomes_unknown():
    from repositories.content_cache_repository import build_content_cache_key
    for track in ("", "   "):
        key = build_content_cache_key(
            track_key=track, legacy_topic_id="topic-x", content_type="quiz"
        )
        assert "track:unknown" in key, f"expected 'unknown' for track_key={track!r}"


def test_build_key_different_dimensions_produce_different_keys():
    from repositories.content_cache_repository import build_content_cache_key
    k_beginner = build_content_cache_key(
        track_key="aipm", legacy_topic_id="t1", content_type="quiz",
        difficulty_level="beginner",
    )
    k_advanced = build_content_cache_key(
        track_key="aipm", legacy_topic_id="t1", content_type="quiz",
        difficulty_level="advanced",
    )
    assert k_beginner != k_advanced


def test_build_key_example_format():
    from repositories.content_cache_repository import build_content_cache_key
    key = build_content_cache_key(
        track_key="aipm",
        legacy_topic_id="rag-basics",
        content_type="base_lesson",
        difficulty_level="beginner",
        language="en",
        version="v1",
    )
    assert key == "track:aipm|topic:rag-basics|type:base_lesson|level:beginner|lang:en|version:v1"


# ── get_cached_content ────────────────────────────────────────────────────────

def test_get_cached_content_queries_content_cache_table():
    from repositories.content_cache_repository import get_cached_content
    conn = FakeConn()
    get_cached_content(conn, cache_key="some-key")
    assert "content_cache" in _all_sql(conn)


def test_get_cached_content_filters_by_status_active():
    from repositories.content_cache_repository import get_cached_content
    conn = FakeConn()
    get_cached_content(conn, cache_key="some-key")
    sql = _all_sql(conn)
    assert "status" in sql
    assert "active" in sql


def test_get_cached_content_uses_parameterized_cache_key():
    from repositories.content_cache_repository import get_cached_content
    conn = FakeConn()
    get_cached_content(conn, cache_key="my-cache-key")
    assert "%s" in _all_sql(conn)
    assert "my-cache-key" in _all_params(conn)


def test_get_cached_content_returns_dict_when_row_exists():
    from repositories.content_cache_repository import get_cached_content
    row = {"cache_key": "k1", "content": "Lesson text.", "status": "active"}
    conn = FakeConn(fetchone_row=row)
    result = get_cached_content(conn, cache_key="k1")
    assert result == row


def test_get_cached_content_returns_none_when_no_row():
    from repositories.content_cache_repository import get_cached_content
    conn = FakeConn()
    result = get_cached_content(conn, cache_key="missing-key")
    assert result is None


def test_get_cached_content_does_not_commit():
    from repositories.content_cache_repository import get_cached_content
    conn = FakeConn()
    get_cached_content(conn, cache_key="k")
    assert conn.commit_count == 0


def test_get_cached_content_does_not_rollback():
    from repositories.content_cache_repository import get_cached_content
    conn = FakeConn()
    get_cached_content(conn, cache_key="k")
    assert conn.rollback_count == 0


# ── upsert_cached_content ─────────────────────────────────────────────────────

def test_upsert_cached_content_targets_content_cache_table():
    from repositories.content_cache_repository import upsert_cached_content
    conn = FakeConn()
    upsert_cached_content(
        conn,
        cache_key="k1",
        track_key="aipm",
        legacy_topic_id="rag-basics",
        content_type="base_lesson",
        content="Lesson text.",
    )
    assert "content_cache" in _all_sql(conn)


def test_upsert_cached_content_uses_on_conflict_cache_key_do_update():
    from repositories.content_cache_repository import upsert_cached_content
    conn = FakeConn()
    upsert_cached_content(
        conn,
        cache_key="k1",
        track_key="aipm",
        legacy_topic_id="t1",
        content_type="quiz",
        content="Q text.",
    )
    sql = _all_sql(conn)
    assert "ON CONFLICT" in sql
    assert "cache_key" in sql
    assert "DO UPDATE" in sql


def test_upsert_cached_content_writes_content_in_params():
    from repositories.content_cache_repository import upsert_cached_content
    conn = FakeConn()
    upsert_cached_content(
        conn,
        cache_key="k1",
        track_key="aipm",
        legacy_topic_id="t1",
        content_type="base_lesson",
        content="My lesson content",
    )
    assert "My lesson content" in _all_params(conn)


def test_upsert_cached_content_writes_provider_and_model():
    from repositories.content_cache_repository import upsert_cached_content
    conn = FakeConn()
    upsert_cached_content(
        conn,
        cache_key="k2",
        track_key="aipm",
        legacy_topic_id="t1",
        content_type="quiz",
        content="Q text.",
        provider="anthropic",
        model="claude-sonnet-4-6",
    )
    params = _all_params(conn)
    assert "anthropic" in params
    assert "claude-sonnet-4-6" in params


def test_upsert_cached_content_serialises_metadata_as_json():
    from repositories.content_cache_repository import upsert_cached_content
    import json
    conn = FakeConn()
    upsert_cached_content(
        conn,
        cache_key="k3",
        track_key="aipm",
        legacy_topic_id="t1",
        content_type="base_lesson",
        content="text",
        metadata={"tokens": 512, "source": "claude"},
    )
    params = _all_params(conn)
    json_param = next((p for p in params if isinstance(p, str) and "tokens" in p), None)
    assert json_param is not None, "metadata was not serialised to JSON in params"
    parsed = json.loads(json_param)
    assert parsed["tokens"] == 512
    assert parsed["source"] == "claude"


def test_upsert_cached_content_writes_status_param():
    from repositories.content_cache_repository import upsert_cached_content
    conn = FakeConn()
    upsert_cached_content(
        conn,
        cache_key="k4",
        track_key=None,
        legacy_topic_id="t1",
        content_type="base_lesson",
        content="text",
        status="active",
    )
    assert "active" in _all_params(conn)


def test_upsert_cached_content_excludes_created_at_from_update_clause():
    from repositories.content_cache_repository import upsert_cached_content
    conn = FakeConn()
    upsert_cached_content(
        conn,
        cache_key="k5",
        track_key="aipm",
        legacy_topic_id="t1",
        content_type="quiz",
        content="text",
    )
    sql = _all_sql(conn)
    assert "DO UPDATE SET" in sql
    update_part = sql[sql.find("DO UPDATE SET"):]
    assert "created_at" not in update_part


def test_upsert_cached_content_does_not_commit():
    from repositories.content_cache_repository import upsert_cached_content
    conn = FakeConn()
    upsert_cached_content(
        conn, cache_key="k", track_key=None,
        legacy_topic_id="t", content_type="c", content="x",
    )
    assert conn.commit_count == 0


def test_upsert_cached_content_does_not_rollback():
    from repositories.content_cache_repository import upsert_cached_content
    conn = FakeConn()
    upsert_cached_content(
        conn, cache_key="k", track_key=None,
        legacy_topic_id="t", content_type="c", content="x",
    )
    assert conn.rollback_count == 0


# ── mark_cached_content_stale ─────────────────────────────────────────────────

def test_mark_cached_content_stale_updates_content_cache():
    from repositories.content_cache_repository import mark_cached_content_stale
    conn = FakeConn(rowcount=1)
    mark_cached_content_stale(conn, cache_key="k1")
    sql = _all_sql(conn)
    assert "content_cache" in sql
    assert "stale" in sql


def test_mark_cached_content_stale_uses_parameterized_cache_key():
    from repositories.content_cache_repository import mark_cached_content_stale
    conn = FakeConn(rowcount=1)
    mark_cached_content_stale(conn, cache_key="target-key")
    assert "%s" in _all_sql(conn)
    assert "target-key" in _all_params(conn)


def test_mark_cached_content_stale_returns_true_when_row_updated():
    from repositories.content_cache_repository import mark_cached_content_stale
    conn = FakeConn(rowcount=1)
    result = mark_cached_content_stale(conn, cache_key="exists")
    assert result is True


def test_mark_cached_content_stale_returns_false_when_no_row():
    from repositories.content_cache_repository import mark_cached_content_stale
    conn = FakeConn(rowcount=0)
    result = mark_cached_content_stale(conn, cache_key="missing")
    assert result is False


def test_mark_cached_content_stale_does_not_commit():
    from repositories.content_cache_repository import mark_cached_content_stale
    conn = FakeConn(rowcount=0)
    mark_cached_content_stale(conn, cache_key="k")
    assert conn.commit_count == 0


def test_mark_cached_content_stale_does_not_rollback():
    from repositories.content_cache_repository import mark_cached_content_stale
    conn = FakeConn(rowcount=0)
    mark_cached_content_stale(conn, cache_key="k")
    assert conn.rollback_count == 0


# ── No commit/rollback across all operations ──────────────────────────────────

def test_no_commit_or_rollback_in_any_operation():
    from repositories.content_cache_repository import (
        get_cached_content,
        mark_cached_content_stale,
        upsert_cached_content,
    )
    conn = FakeConn(rowcount=1)
    get_cached_content(conn, cache_key="k")
    upsert_cached_content(
        conn, cache_key="k", track_key=None,
        legacy_topic_id="t", content_type="c", content="x",
    )
    mark_cached_content_stale(conn, cache_key="k")
    assert conn.commit_count == 0
    assert conn.rollback_count == 0


# ── Source-code safety checks ─────────────────────────────────────────────────

def test_no_os_environ_reads():
    src = _src()
    assert "os.environ" not in src
    assert "os.getenv" not in src


def test_no_psycopg2_connect():
    src = _src()
    assert "psycopg2.connect(" not in src


def test_no_database_pool_import():
    src = _src()
    assert "database.pool" not in src
    assert "from database" not in src


def test_no_routes_or_app_imports():
    src = _src()
    assert "from routes" not in src
    assert "import routes" not in src
    assert "from app" not in src
    assert "import app" not in src


def test_no_services_imports():
    src = _src()
    assert "from services" not in src
    assert "import services" not in src


def test_no_claude_api_calls():
    src = _src()
    assert "client.messages" not in src
    assert "make_client" not in src
    assert "anthropic.Anthropic(" not in src


def test_uses_parameterized_queries():
    src = _src()
    assert "%s" in src


def test_references_content_cache_table():
    src = _src()
    assert "content_cache" in src
