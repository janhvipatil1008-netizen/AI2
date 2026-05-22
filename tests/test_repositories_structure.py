"""Tests for the repositories/ package.

All tests run without a real database connection.
Source-code structural tests verify safe patterns at the file level.
FakeCursor tests verify SQL is executed with parameters.
"""

from __future__ import annotations

import inspect
from pathlib import Path

# ── Helpers ───────────────────────────────────────────────────────────────────

REPO_ROOT = Path(__file__).parent.parent / "repositories"


def _src(filename: str) -> str:
    return (REPO_ROOT / filename).read_text(encoding="utf-8")


class FakeCursor:
    """Records every (sql, params) pair passed to execute()."""

    def __init__(self):
        self.executed: list[tuple[str, tuple]] = []

    def execute(self, sql: str, params: tuple = ()) -> None:
        self.executed.append((sql.strip(), params))

    def fetchone(self):
        return None

    def fetchall(self):
        return []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


class FakeConn:
    """Returns the same FakeCursor for every cursor() call."""

    def __init__(self):
        self.cursor_obj = FakeCursor()

    def cursor(self, **kwargs):
        return self.cursor_obj

    @property
    def executed(self):
        return self.cursor_obj.executed


# ── Import tests ──────────────────────────────────────────────────────────────

def test_repositories_package_imports():
    import repositories  # noqa: F401


def test_curriculum_repository_imports():
    import repositories.curriculum_repository  # noqa: F401


def test_progress_repository_imports():
    import repositories.progress_repository  # noqa: F401


def test_todos_repository_imports():
    import repositories.todos_repository  # noqa: F401


# ── Function existence ────────────────────────────────────────────────────────

def test_curriculum_repository_has_expected_functions():
    from repositories import curriculum_repository as cr
    for fn in (
        "upsert_learning_track",
        "upsert_learning_module",
        "upsert_learning_topic",
        "seed_curriculum_export",
        "get_learning_track_by_key",
        "get_learning_topic_by_legacy_id",
    ):
        assert callable(getattr(cr, fn, None)), f"missing: curriculum_repository.{fn}"


def test_progress_repository_has_expected_functions():
    from repositories import progress_repository as pr
    for fn in ("upsert_topic_progress", "get_topic_progress_by_legacy_id"):
        assert callable(getattr(pr, fn, None)), f"missing: progress_repository.{fn}"


def test_todos_repository_has_expected_functions():
    from repositories import todos_repository as tr
    for fn in ("upsert_todo", "list_todos_for_session"):
        assert callable(getattr(tr, fn, None)), f"missing: todos_repository.{fn}"


# ── Source-code safety checks ─────────────────────────────────────────────────

def test_curriculum_repository_does_not_call_os_environ():
    src = _src("curriculum_repository.py")
    assert "os.environ" not in src
    assert "os.getenv" not in src


def test_progress_repository_does_not_call_os_environ():
    src = _src("progress_repository.py")
    assert "os.environ" not in src
    assert "os.getenv" not in src


def test_todos_repository_does_not_call_os_environ():
    src = _src("todos_repository.py")
    assert "os.environ" not in src
    assert "os.getenv" not in src


def test_curriculum_repository_does_not_open_connection():
    src = _src("curriculum_repository.py")
    assert "psycopg2.connect(" not in src
    assert "get_conn(" not in src


def test_progress_repository_does_not_open_connection():
    src = _src("progress_repository.py")
    assert "psycopg2.connect(" not in src
    assert "get_conn(" not in src


def test_todos_repository_does_not_open_connection():
    src = _src("todos_repository.py")
    assert "psycopg2.connect(" not in src
    assert "get_conn(" not in src


def test_curriculum_repository_uses_parameterized_queries():
    src = _src("curriculum_repository.py")
    assert "%s" in src, "curriculum_repository.py must use %s placeholders"


def test_progress_repository_uses_parameterized_queries():
    src = _src("progress_repository.py")
    assert "%s" in src, "progress_repository.py must use %s placeholders"


def test_todos_repository_uses_parameterized_queries():
    src = _src("todos_repository.py")
    assert "%s" in src, "todos_repository.py must use %s placeholders"


# ── Table/column name presence in source ─────────────────────────────────────

def test_curriculum_repository_references_learning_tracks():
    assert "learning_tracks" in _src("curriculum_repository.py")


def test_curriculum_repository_references_learning_modules():
    assert "learning_modules" in _src("curriculum_repository.py")


def test_curriculum_repository_references_learning_topics():
    assert "learning_topics" in _src("curriculum_repository.py")


def test_progress_repository_references_topic_progress():
    assert "topic_progress" in _src("progress_repository.py")


def test_progress_repository_references_legacy_topic_id():
    assert "legacy_topic_id" in _src("progress_repository.py")


def test_todos_repository_references_todos_table():
    assert "todos" in _src("todos_repository.py")


def test_todos_repository_references_legacy_linked_topic_id():
    assert "legacy_linked_topic_id" in _src("todos_repository.py")


# ── FakeCursor: upsert_topic_progress executes SQL with params ────────────────

def test_upsert_topic_progress_insert_executes_sql():
    from repositories.progress_repository import upsert_topic_progress

    conn = FakeConn()
    upsert_topic_progress(
        conn,
        user_id="user-1",
        session_id="sess-1",
        legacy_topic_id="aipm-week-1-topic",
        progress={"learn": "done", "quiz": "in_progress"},
        completion_percent=40,
    )

    all_sql = " ".join(sql for sql, _ in conn.executed)
    assert "topic_progress" in all_sql
    assert "legacy_topic_id" in all_sql


def test_upsert_topic_progress_passes_legacy_topic_id_as_param():
    from repositories.progress_repository import upsert_topic_progress

    conn = FakeConn()
    upsert_topic_progress(
        conn,
        user_id=None,
        session_id="sess-2",
        legacy_topic_id="aipm-week-2-embeddings",
        progress={},
        completion_percent=0,
    )

    all_params = [p for _, params in conn.executed for p in (params or [])]
    assert "aipm-week-2-embeddings" in all_params


def test_upsert_topic_progress_uses_not_started_defaults():
    from repositories.progress_repository import upsert_topic_progress

    conn = FakeConn()
    upsert_topic_progress(
        conn,
        user_id=None,
        session_id="sess-3",
        legacy_topic_id="topic-x",
        progress={},
        completion_percent=0,
    )

    all_params = [p for _, params in conn.executed for p in (params or [])]
    assert "not_started" in all_params


# ── FakeCursor: upsert_todo executes SQL with params ─────────────────────────

def test_upsert_todo_insert_executes_sql():
    from repositories.todos_repository import upsert_todo

    conn = FakeConn()
    todo = {
        "todo_id": "todo-abc",
        "title": "Read chapter 3",
        "todo_type": "daily",
        "status": "todo",
        "linked_topic_id": "",
        "created_by": "learner",
    }
    upsert_todo(conn, user_id=None, session_id="sess-1", todo=todo)

    all_sql = " ".join(sql for sql, _ in conn.executed)
    assert "todos" in all_sql


def test_upsert_todo_passes_title_as_param():
    from repositories.todos_repository import upsert_todo

    conn = FakeConn()
    todo = {
        "todo_id": "todo-xyz",
        "title": "Review prompt engineering",
        "todo_type": "weekly",
        "status": "in_progress",
        "linked_topic_id": "aipm-week-1-prompting",
        "created_by": "learner",
    }
    upsert_todo(conn, user_id="user-1", session_id="sess-4", todo=todo)

    all_params = [p for _, params in conn.executed for p in (params or [])]
    assert "Review prompt engineering" in all_params


def test_upsert_todo_stores_legacy_linked_topic_id():
    from repositories.todos_repository import upsert_todo

    conn = FakeConn()
    todo = {
        "todo_id": "todo-zzz",
        "title": "Practice quiz",
        "todo_type": "daily",
        "status": "todo",
        "linked_topic_id": "aipm-week-3-rag",
        "created_by": "learner",
    }
    upsert_todo(conn, user_id=None, session_id="sess-5", todo=todo)

    all_params = [p for _, params in conn.executed for p in (params or [])]
    assert "aipm-week-3-rag" in all_params


# ── FakeCursor: list_todos_for_session ───────────────────────────────────────

def test_list_todos_for_session_executes_select():
    from repositories.todos_repository import list_todos_for_session

    conn = FakeConn()
    result = list_todos_for_session(conn, "sess-99")

    assert result == []
    all_sql = " ".join(sql for sql, _ in conn.executed)
    assert "todos" in all_sql
    assert "session_id" in all_sql


# ── seed_curriculum_export structure test ────────────────────────────────────

def test_seed_curriculum_export_returns_counts_dict():
    from repositories.curriculum_repository import seed_curriculum_export
    from curriculum.seed_export import CurriculumSeedExport

    empty_export = CurriculumSeedExport(tracks=[], modules=[], topics=[])
    conn = FakeConn()
    result = seed_curriculum_export(conn, empty_export)

    assert result == {"tracks": 0, "modules": 0, "topics": 0}


def test_upsert_learning_track_executes_sql_with_track_key():
    from repositories.curriculum_repository import upsert_learning_track
    from curriculum.seed_export import TrackSeedRecord

    conn = FakeConn()
    record = TrackSeedRecord(track_key="aipm", title="AI Product Manager")
    upsert_learning_track(conn, record)

    all_sql = " ".join(sql for sql, _ in conn.executed)
    all_params = [p for _, params in conn.executed for p in (params or [])]
    assert "learning_tracks" in all_sql
    assert "aipm" in all_params
