"""Tests for learner course enrollment repository helpers."""

from __future__ import annotations

import inspect
from pathlib import Path

import repositories.learner_course_enrollment_repository as repo


REPO_PATH = (
    Path(__file__).parent.parent
    / "repositories"
    / "learner_course_enrollment_repository.py"
)


class FakeCursor:
    def __init__(self, *, fetchone_rows=None, fetchall_rows=None, description=None):
        self.executed: list[tuple[str, tuple]] = []
        self.fetchone_rows = list(fetchone_rows or [])
        self.fetchall_rows = fetchall_rows or []
        self.description = description or [
            ("enrollment_id",),
            ("user_id",),
            ("session_id",),
            ("course_key",),
        ]

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
    def __init__(self, *, fetchone_rows=None, fetchall_rows=None, description=None):
        self.cursor_obj = FakeCursor(
            fetchone_rows=fetchone_rows,
            fetchall_rows=fetchall_rows,
            description=description,
        )
        self.committed = False
        self.rolled_back = False

    def cursor(self):
        return self.cursor_obj

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    @property
    def executed(self):
        return self.cursor_obj.executed


def _src() -> str:
    return REPO_PATH.read_text(encoding="utf-8")


def _last_sql(conn: FakeConn) -> str:
    return conn.executed[-1][0]


def _last_params(conn: FakeConn) -> tuple:
    return conn.executed[-1][1]


def test_module_imports_safely():
    assert repo is not None


def test_all_expected_functions_exist():
    for fn in (
        "upsert_course_enrollment",
        "get_active_enrollment",
        "list_enrollments_for_session",
        "update_current_position",
        "upsert_module_progress",
        "upsert_topic_progress",
        "list_module_progress",
        "list_topic_progress",
        "get_topic_progress_by_legacy_id",
    ):
        assert callable(getattr(repo, fn, None)), f"missing: {fn}"


def test_no_os_environ_or_getenv_usage():
    src = _src()
    assert "os.environ" not in src
    assert "os.getenv" not in src
    assert "getenv(" not in src


def test_no_db_connection_creation_or_pool_imports():
    src = _src()
    assert "database.pool" not in src
    assert "psycopg2.connect" not in src
    assert "get_conn(" not in src


def test_no_app_route_or_service_imports():
    src = _src()
    assert "from app" not in src
    assert "import app" not in src
    assert "from routes" not in src
    assert "import routes" not in src
    assert "from services" not in src
    assert "import services" not in src


def test_parameterized_sql_uses_percent_s_placeholders():
    src = _src()
    assert "%s" in src
    assert "VALUES (%s" in src
    assert ".format(" not in src


def test_upsert_course_enrollment_uses_expected_conflict_target():
    conn = FakeConn(fetchone_rows=[(11,)])
    result = repo.upsert_course_enrollment(
        conn,
        user_id="user-1",
        session_id="session-1",
        course_key="ai2",
        metadata={"source": "test"},
    )

    sql = _last_sql(conn)
    params = _last_params(conn)
    assert result == 11
    assert "INSERT INTO learner_course_enrollments" in sql
    assert "ON CONFLICT(user_id, session_id, course_key) DO UPDATE" in sql
    assert "RETURNING enrollment_id" in sql
    assert params[0] == "user-1"
    assert isinstance(params[0], str)


def test_get_active_enrollment_filters_status_active():
    conn = FakeConn(fetchone_rows=[(1, "u1", "s1", "ai2")])
    result = repo.get_active_enrollment(conn, user_id="u1", session_id="s1")

    sql = _last_sql(conn)
    params = _last_params(conn)
    assert result["enrollment_id"] == 1
    assert "status = %s" in sql
    assert "ORDER BY updated_at DESC, created_at DESC" in sql
    assert params == ("u1", "s1", "active")


def test_get_active_enrollment_filters_optional_course_key():
    conn = FakeConn(fetchone_rows=[(1, "u1", "s1", "ai2")])
    repo.get_active_enrollment(
        conn,
        user_id="u1",
        session_id="s1",
        course_key="ai2",
    )

    sql = _last_sql(conn)
    assert "course_key = %s" in sql
    assert _last_params(conn) == ("u1", "s1", "ai2", "active")


def test_list_enrollments_for_session_filters_user_id_and_session_id():
    conn = FakeConn(fetchall_rows=[(1, "u1", "s1", "ai2")])
    result = repo.list_enrollments_for_session(
        conn,
        user_id="u1",
        session_id="s1",
    )

    sql = _last_sql(conn)
    assert isinstance(result, list)
    assert result == [
        {"enrollment_id": 1, "user_id": "u1", "session_id": "s1", "course_key": "ai2"}
    ]
    assert "WHERE user_id = %s" in sql
    assert "AND session_id = %s" in sql
    assert "CASE WHEN status = %s THEN 0 ELSE 1 END" in sql
    assert _last_params(conn) == ("u1", "s1", "active")


def test_update_current_position_updates_only_position_and_progress_fields():
    conn = FakeConn()
    repo.update_current_position(
        conn,
        enrollment_id=7,
        current_module_key="module-1",
        current_topic_key="topic-1",
        progress_percent=35,
    )

    sql = _last_sql(conn)
    assert "UPDATE learner_course_enrollments" in sql
    assert "current_module_key = %s" in sql
    assert "current_topic_key = %s" in sql
    assert "progress_percent = %s" in sql
    assert "updated_at = NOW()" in sql
    assert "status =" not in sql
    assert "course_key =" not in sql
    assert "metadata =" not in sql
    assert _last_params(conn) == ("module-1", "topic-1", 35, 7)


def test_upsert_module_progress_uses_expected_conflict_target():
    conn = FakeConn(fetchone_rows=[(22,)])
    result = repo.upsert_module_progress(
        conn,
        enrollment_id=7,
        module_key="module-1",
        module_id=3,
    )

    sql = _last_sql(conn)
    assert result == 22
    assert "INSERT INTO learner_module_progress" in sql
    assert "ON CONFLICT(enrollment_id, module_key) DO UPDATE" in sql
    assert "RETURNING module_progress_id" in sql


def test_upsert_topic_progress_uses_expected_conflict_target():
    conn = FakeConn(fetchone_rows=[(33,)])
    result = repo.upsert_topic_progress(
        conn,
        enrollment_id=7,
        module_key="module-1",
        topic_key="topic-1",
        legacy_topic_id="legacy-topic-1",
    )

    sql = _last_sql(conn)
    assert result == 33
    assert "INSERT INTO learner_topic_progress" in sql
    assert "ON CONFLICT(enrollment_id, topic_key) DO UPDATE" in sql
    assert "RETURNING topic_progress_id" in sql


def test_get_topic_progress_by_legacy_id_uses_legacy_topic_id_bridge():
    conn = FakeConn(
        fetchone_rows=[(9, 7, "module-1", "topic-1")],
        description=[
            ("topic_progress_id",),
            ("enrollment_id",),
            ("module_key",),
            ("legacy_topic_id",),
        ],
    )
    result = repo.get_topic_progress_by_legacy_id(
        conn,
        enrollment_id=7,
        legacy_topic_id="legacy-topic-1",
    )

    sql = _last_sql(conn)
    assert result["legacy_topic_id"] == "topic-1"
    assert "legacy_topic_id = %s" in sql
    assert _last_params(conn) == (7, "legacy-topic-1")


def test_list_module_progress_returns_list_of_dicts():
    conn = FakeConn(
        fetchall_rows=[(1, 7, "module-1")],
        description=[("module_progress_id",), ("enrollment_id",), ("module_key",)],
    )
    result = repo.list_module_progress(conn, enrollment_id=7)

    assert isinstance(result, list)
    assert result == [
        {"module_progress_id": 1, "enrollment_id": 7, "module_key": "module-1"}
    ]
    assert "FROM learner_module_progress" in _last_sql(conn)


def test_list_topic_progress_returns_list_of_dicts():
    conn = FakeConn(
        fetchall_rows=[(1, 7, "topic-1")],
        description=[("topic_progress_id",), ("enrollment_id",), ("topic_key",)],
    )
    result = repo.list_topic_progress(conn, enrollment_id=7)

    assert isinstance(result, list)
    assert result == [
        {"topic_progress_id": 1, "enrollment_id": 7, "topic_key": "topic-1"}
    ]
    assert "FROM learner_topic_progress" in _last_sql(conn)


def test_no_commit_or_rollback_called():
    conn = FakeConn(fetchone_rows=[(1,)])
    repo.upsert_course_enrollment(
        conn,
        user_id="user-1",
        session_id="session-1",
        course_key="ai2",
    )
    repo.update_current_position(
        conn,
        enrollment_id=1,
        current_topic_key="topic-1",
    )

    assert conn.committed is False
    assert conn.rolled_back is False
    assert ".commit()" not in _src()
    assert ".rollback()" not in _src()


def test_user_id_annotation_is_string_not_int():
    signature = inspect.signature(repo.upsert_course_enrollment)
    assert signature.parameters["user_id"].annotation in ("str", str)
    assert "user_id: int" not in _src()
