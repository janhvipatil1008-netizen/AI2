"""Tests for repositories/learning_outcomes_repository.py.

All tests use fake connection/cursor objects. No real database is required.
"""

from __future__ import annotations

from pathlib import Path


REPO_PATH = Path(__file__).parent.parent / "repositories" / "learning_outcomes_repository.py"


def _src() -> str:
    return REPO_PATH.read_text(encoding="utf-8")


class FakeCursor:
    def __init__(self, *, fetchone_rows=None, fetchall_rows=None):
        self.executed: list[tuple[str, tuple]] = []
        self.fetchone_rows = list(fetchone_rows or [])
        self.fetchall_rows = fetchall_rows or []

    def execute(self, sql: str, params: tuple = ()) -> None:
        self.executed.append((sql.strip(), params))

    def fetchone(self):
        if self.fetchone_rows:
            return self.fetchone_rows.pop(0)
        return None

    def fetchall(self):
        return self.fetchall_rows

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


class FakeConn:
    def __init__(self, *, fetchone_rows=None, fetchall_rows=None):
        self.cursor_obj = FakeCursor(
            fetchone_rows=fetchone_rows,
            fetchall_rows=fetchall_rows,
        )
        self.cursor_kwargs: list[dict] = []
        self.committed = False
        self.rolled_back = False

    def cursor(self, **kwargs):
        self.cursor_kwargs.append(kwargs)
        return self.cursor_obj

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    @property
    def executed(self):
        return self.cursor_obj.executed


def _all_sql(conn: FakeConn) -> str:
    return " ".join(sql for sql, _ in conn.executed)


def _all_params(conn: FakeConn) -> list:
    return [param for _, params in conn.executed for param in (params or [])]


def test_learning_outcomes_repository_imports_safely():
    import repositories.learning_outcomes_repository  # noqa: F401


def test_learning_outcomes_repository_has_expected_functions():
    from repositories import learning_outcomes_repository as repo

    for fn in (
        "upsert_baseline_outcome",
        "upsert_post_outcome",
        "get_learning_outcome",
        "list_learning_outcomes_for_session",
    ):
        assert callable(getattr(repo, fn, None)), f"missing: {fn}"


def test_repository_does_not_read_env_vars():
    src = _src()
    assert "os.environ" not in src
    assert "os.getenv" not in src
    assert "getenv(" not in src


def test_repository_does_not_open_db_connections():
    src = _src()
    assert "database.pool" not in src
    assert "psycopg2.connect" not in src
    assert "get_conn(" not in src


def test_repository_references_learning_outcomes_table():
    assert "learning_outcomes" in _src()


def test_upsert_baseline_uses_on_conflict_and_parameterized_sql():
    from repositories.learning_outcomes_repository import upsert_baseline_outcome

    conn = FakeConn()
    upsert_baseline_outcome(
        conn,
        user_id="u1",
        session_id="s1",
        legacy_topic_id="topic-1",
        baseline_prompt="What do you know?",
        baseline_answer="baseline answer",
        baseline_score=40,
        metadata={"source": "test"},
    )

    assert conn.executed
    sql, params = conn.executed[-1]
    assert "INSERT INTO learning_outcomes" in sql
    assert "ON CONFLICT (session_id, legacy_topic_id) DO UPDATE" in sql
    assert "%s" in sql
    assert isinstance(params, tuple)
    assert "s1" in params
    assert "topic-1" in params
    assert "baseline_completed" in sql


def test_upsert_post_calculates_and_stores_improvement_delta():
    from repositories.learning_outcomes_repository import upsert_post_outcome

    conn = FakeConn(fetchone_rows=[{"baseline_score": 50}])
    upsert_post_outcome(
        conn,
        user_id="u1",
        session_id="s1",
        legacy_topic_id="topic-1",
        post_prompt="What do you know now?",
        post_answer="post answer",
        post_score=80,
        metadata={"source": "test"},
    )

    assert len(conn.executed) == 2
    sql = conn.executed[-1][0]
    params = conn.executed[-1][1]
    assert "ON CONFLICT (session_id, legacy_topic_id) DO UPDATE" in sql
    assert "improvement_delta" in sql
    assert 30 in params
    assert "improved" in params


def test_upsert_post_negative_delta_uses_needs_review_status():
    from repositories.learning_outcomes_repository import upsert_post_outcome

    conn = FakeConn(fetchone_rows=[{"baseline_score": 90}])
    upsert_post_outcome(
        conn,
        user_id=None,
        session_id="s1",
        legacy_topic_id="topic-1",
        post_prompt=None,
        post_answer=None,
        post_score=75,
    )

    params = conn.executed[-1][1]
    assert -15 in params
    assert "needs_review" in params


def test_upsert_post_missing_score_uses_completed_status():
    from repositories.learning_outcomes_repository import upsert_post_outcome

    conn = FakeConn(fetchone_rows=[{"baseline_score": 90}])
    upsert_post_outcome(
        conn,
        user_id=None,
        session_id="s1",
        legacy_topic_id="topic-1",
        post_prompt=None,
        post_answer=None,
        post_score=None,
    )

    params = conn.executed[-1][1]
    assert "completed" in params


def test_get_learning_outcome_returns_dict():
    from repositories.learning_outcomes_repository import get_learning_outcome

    row = {"session_id": "s1", "legacy_topic_id": "topic-1", "baseline_score": 40}
    conn = FakeConn(fetchone_rows=[row])

    result = get_learning_outcome(conn, session_id="s1", legacy_topic_id="topic-1")

    assert result == row
    sql, params = conn.executed[-1]
    assert "WHERE session_id = %s AND legacy_topic_id = %s" in sql
    assert params == ("s1", "topic-1")


def test_get_learning_outcome_returns_none():
    from repositories.learning_outcomes_repository import get_learning_outcome

    conn = FakeConn(fetchone_rows=[None])

    assert get_learning_outcome(conn, session_id="s1", legacy_topic_id="topic-1") is None


def test_list_learning_outcomes_for_session_returns_list():
    from repositories.learning_outcomes_repository import list_learning_outcomes_for_session

    rows = [
        {"session_id": "s1", "legacy_topic_id": "topic-2"},
        {"session_id": "s1", "legacy_topic_id": "topic-1"},
    ]
    conn = FakeConn(fetchall_rows=rows)

    result = list_learning_outcomes_for_session(conn, session_id="s1")

    assert result == rows
    assert all(isinstance(row, dict) for row in result)
    sql, params = conn.executed[-1]
    assert "WHERE session_id = %s" in sql
    assert params == ("s1",)


def test_repository_uses_parameterized_sql_only_for_inputs():
    from repositories.learning_outcomes_repository import upsert_baseline_outcome

    injection = "topic-1'; DROP TABLE learning_outcomes; --"
    conn = FakeConn()
    upsert_baseline_outcome(
        conn,
        user_id=None,
        session_id="s1",
        legacy_topic_id=injection,
        baseline_prompt=None,
        baseline_answer=None,
        baseline_score=None,
    )

    sql = _all_sql(conn)
    params = _all_params(conn)
    assert "%s" in sql
    assert injection not in sql
    assert injection in params


def test_repository_does_not_commit_or_rollback():
    from repositories.learning_outcomes_repository import (
        get_learning_outcome,
        list_learning_outcomes_for_session,
        upsert_baseline_outcome,
        upsert_post_outcome,
    )

    conn = FakeConn(fetchone_rows=[{"baseline_score": 50}, None])
    upsert_baseline_outcome(
        conn,
        user_id=None,
        session_id="s1",
        legacy_topic_id="topic-1",
        baseline_prompt=None,
        baseline_answer=None,
        baseline_score=None,
    )
    upsert_post_outcome(
        conn,
        user_id=None,
        session_id="s1",
        legacy_topic_id="topic-1",
        post_prompt=None,
        post_answer=None,
        post_score=60,
    )
    get_learning_outcome(conn, session_id="s1", legacy_topic_id="topic-1")
    list_learning_outcomes_for_session(conn, session_id="s1")

    assert conn.committed is False
    assert conn.rolled_back is False
