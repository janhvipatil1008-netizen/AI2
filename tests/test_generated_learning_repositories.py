"""Tests for the three new generated-learning repository modules.

All tests run without a real database connection.
Source-code structural tests verify safe patterns at the file level.
FakeCursor tests verify SQL is executed with parameters.
"""

from __future__ import annotations

from pathlib import Path

# ── Helpers ───────────────────────────────────────────────────────────────────

REPO_ROOT = Path(__file__).parent.parent / "repositories"


def _src(filename: str) -> str:
    return (REPO_ROOT / filename).read_text(encoding="utf-8")


class FakeCursor:
    """Records every (sql, params) pair; fetchone returns None by default."""

    def __init__(self, row=None):
        self.executed: list[tuple[str, tuple]] = []
        self._row = row

    def execute(self, sql: str, params: tuple = ()) -> None:
        self.executed.append((sql.strip(), params))

    def fetchone(self):
        return self._row

    def fetchall(self):
        return []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


class FakeConn:
    """Returns the same FakeCursor for every cursor() call; tracks commit/rollback."""

    def __init__(self, row=None):
        self.cursor_obj  = FakeCursor(row=row)
        self.committed   = False
        self.rolled_back = False

    def cursor(self, **kwargs):
        return self.cursor_obj

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    @property
    def executed(self):
        return self.cursor_obj.executed


# ── Module import tests ───────────────────────────────────────────────────────

def test_generated_content_repository_imports():
    import repositories.generated_content_repository  # noqa: F401


def test_submissions_repository_imports():
    import repositories.submissions_repository  # noqa: F401


def test_topic_notes_repository_imports():
    import repositories.topic_notes_repository  # noqa: F401


# ── Function existence ────────────────────────────────────────────────────────

def test_generated_content_repository_has_expected_functions():
    from repositories import generated_content_repository as gcr
    for fn in (
        "upsert_generated_topic_content",
        "get_generated_topic_content_by_legacy_id",
        "upsert_generated_topic_practice",
        "get_generated_topic_practice_by_legacy_id",
    ):
        assert callable(getattr(gcr, fn, None)), f"missing: generated_content_repository.{fn}"


def test_submissions_repository_has_expected_functions():
    from repositories import submissions_repository as sr
    for fn in (
        "upsert_quiz_submission",
        "get_quiz_submission_by_legacy_id",
        "upsert_portfolio_submission",
        "get_portfolio_submission_by_legacy_id",
        "upsert_interview_submission",
        "get_interview_submission_by_legacy_id",
    ):
        assert callable(getattr(sr, fn, None)), f"missing: submissions_repository.{fn}"


def test_topic_notes_repository_has_expected_functions():
    from repositories import topic_notes_repository as tnr
    for fn in ("upsert_topic_notes", "get_topic_notes_by_legacy_id"):
        assert callable(getattr(tnr, fn, None)), f"missing: topic_notes_repository.{fn}"


# ── Source-code safety: no env vars ──────────────────────────────────────────

def test_generated_content_repository_no_os_environ():
    src = _src("generated_content_repository.py")
    assert "os.environ" not in src
    assert "os.getenv"  not in src


def test_submissions_repository_no_os_environ():
    src = _src("submissions_repository.py")
    assert "os.environ" not in src
    assert "os.getenv"  not in src


def test_topic_notes_repository_no_os_environ():
    src = _src("topic_notes_repository.py")
    assert "os.environ" not in src
    assert "os.getenv"  not in src


# ── Source-code safety: no direct DB connections ──────────────────────────────

def test_generated_content_repository_no_direct_connection():
    src = _src("generated_content_repository.py")
    assert "psycopg2.connect(" not in src
    assert "database.pool"     not in src
    assert "get_conn("         not in src


def test_submissions_repository_no_direct_connection():
    src = _src("submissions_repository.py")
    assert "psycopg2.connect(" not in src
    assert "database.pool"     not in src
    assert "get_conn("         not in src


def test_topic_notes_repository_no_direct_connection():
    src = _src("topic_notes_repository.py")
    assert "psycopg2.connect(" not in src
    assert "database.pool"     not in src
    assert "get_conn("         not in src


# ── Source-code safety: parameterized queries ─────────────────────────────────

def test_generated_content_repository_uses_parameterized_queries():
    assert "%s" in _src("generated_content_repository.py")


def test_submissions_repository_uses_parameterized_queries():
    assert "%s" in _src("submissions_repository.py")


def test_topic_notes_repository_uses_parameterized_queries():
    assert "%s" in _src("topic_notes_repository.py")


# ── Table name presence ───────────────────────────────────────────────────────

def test_generated_content_repository_references_content_table():
    assert "generated_topic_content" in _src("generated_content_repository.py")


def test_generated_content_repository_references_practice_table():
    assert "generated_topic_practice" in _src("generated_content_repository.py")


def test_submissions_repository_references_quiz_submissions():
    assert "quiz_submissions" in _src("submissions_repository.py")


def test_submissions_repository_references_portfolio_submissions():
    assert "portfolio_submissions" in _src("submissions_repository.py")


def test_submissions_repository_references_interview_submissions():
    assert "interview_submissions" in _src("submissions_repository.py")


def test_topic_notes_repository_references_topic_notes():
    assert "topic_notes" in _src("topic_notes_repository.py")


# ── FakeCursor: upsert_generated_topic_content ────────────────────────────────

def test_upsert_generated_topic_content_executes_sql():
    from repositories.generated_content_repository import upsert_generated_topic_content

    conn = FakeConn()
    upsert_generated_topic_content(
        conn,
        user_id="u1",
        session_id="s1",
        legacy_topic_id="rag-basics",
        content_record={"content": "Intro to RAG", "model": "claude-sonnet-4-6"},
    )

    all_sql = " ".join(sql for sql, _ in conn.executed)
    assert "generated_topic_content" in all_sql
    assert "legacy_topic_id" in all_sql


def test_upsert_generated_topic_content_passes_legacy_topic_id_as_param():
    from repositories.generated_content_repository import upsert_generated_topic_content

    conn = FakeConn()
    upsert_generated_topic_content(
        conn,
        user_id=None,
        session_id="s1",
        legacy_topic_id="rag-basics",
        content_record={"content": "Intro to RAG"},
    )

    all_params = [p for _, params in conn.executed for p in (params or [])]
    assert "rag-basics" in all_params


def test_upsert_generated_topic_content_no_commit_or_rollback():
    from repositories.generated_content_repository import upsert_generated_topic_content

    conn = FakeConn()
    upsert_generated_topic_content(
        conn,
        user_id=None,
        session_id="s1",
        legacy_topic_id="topic-x",
        content_record={"content": "text"},
    )

    assert conn.committed   is False
    assert conn.rolled_back is False


# ── FakeCursor: upsert_generated_topic_practice ───────────────────────────────

def test_upsert_generated_topic_practice_executes_sql():
    from repositories.generated_content_repository import upsert_generated_topic_practice

    conn = FakeConn()
    upsert_generated_topic_practice(
        conn,
        user_id="u1",
        session_id="s1",
        legacy_topic_id="rag-basics",
        practice_type="quiz",
        practice_record={"content": "Q: What is RAG?"},
    )

    all_sql = " ".join(sql for sql, _ in conn.executed)
    assert "generated_topic_practice" in all_sql


def test_upsert_generated_topic_practice_passes_practice_type_as_param():
    from repositories.generated_content_repository import upsert_generated_topic_practice

    conn = FakeConn()
    upsert_generated_topic_practice(
        conn,
        user_id=None,
        session_id="s1",
        legacy_topic_id="rag-basics",
        practice_type="case_study",
        practice_record={"content": "Analyze this case"},
    )

    all_params = [p for _, params in conn.executed for p in (params or [])]
    assert "case_study" in all_params


def test_upsert_generated_topic_practice_no_commit_or_rollback():
    from repositories.generated_content_repository import upsert_generated_topic_practice

    conn = FakeConn()
    upsert_generated_topic_practice(
        conn,
        user_id=None,
        session_id="s1",
        legacy_topic_id="t",
        practice_type="quiz",
        practice_record={},
    )

    assert conn.committed   is False
    assert conn.rolled_back is False


# ── FakeCursor: upsert_quiz_submission ────────────────────────────────────────

def test_upsert_quiz_submission_executes_sql():
    from repositories.submissions_repository import upsert_quiz_submission

    conn = FakeConn()
    upsert_quiz_submission(
        conn,
        user_id="u1",
        session_id="s1",
        legacy_topic_id="rag-basics",
        submission={"answers": "A, B, C", "score": 80},
    )

    all_sql = " ".join(sql for sql, _ in conn.executed)
    assert "quiz_submissions" in all_sql
    assert "legacy_topic_id" in all_sql


def test_upsert_quiz_submission_passes_answers_as_param():
    from repositories.submissions_repository import upsert_quiz_submission

    conn = FakeConn()
    upsert_quiz_submission(
        conn,
        user_id=None,
        session_id="s1",
        legacy_topic_id="rag-basics",
        submission={"answers": "my answers here", "score": 70},
    )

    all_params = [p for _, params in conn.executed for p in (params or [])]
    assert "my answers here" in all_params


def test_upsert_quiz_submission_no_commit_or_rollback():
    from repositories.submissions_repository import upsert_quiz_submission

    conn = FakeConn()
    upsert_quiz_submission(
        conn,
        user_id=None,
        session_id="s1",
        legacy_topic_id="t",
        submission={"answers": "x"},
    )

    assert conn.committed   is False
    assert conn.rolled_back is False


# ── FakeCursor: upsert_portfolio_submission ───────────────────────────────────

def test_upsert_portfolio_submission_executes_sql():
    from repositories.submissions_repository import upsert_portfolio_submission

    conn = FakeConn()
    upsert_portfolio_submission(
        conn,
        user_id="u1",
        session_id="s1",
        legacy_topic_id="rag-basics",
        submission={"submission": "My project write-up"},
    )

    all_sql = " ".join(sql for sql, _ in conn.executed)
    assert "portfolio_submissions" in all_sql


def test_upsert_portfolio_submission_passes_submission_text_as_param():
    from repositories.submissions_repository import upsert_portfolio_submission

    conn = FakeConn()
    upsert_portfolio_submission(
        conn,
        user_id=None,
        session_id="s1",
        legacy_topic_id="rag-basics",
        submission={"submission": "portfolio write-up text"},
    )

    all_params = [p for _, params in conn.executed for p in (params or [])]
    assert "portfolio write-up text" in all_params


def test_upsert_portfolio_submission_no_commit_or_rollback():
    from repositories.submissions_repository import upsert_portfolio_submission

    conn = FakeConn()
    upsert_portfolio_submission(
        conn,
        user_id=None,
        session_id="s1",
        legacy_topic_id="t",
        submission={"submission": "x"},
    )

    assert conn.committed   is False
    assert conn.rolled_back is False


# ── FakeCursor: upsert_interview_submission ───────────────────────────────────

def test_upsert_interview_submission_executes_sql():
    from repositories.submissions_repository import upsert_interview_submission

    conn = FakeConn()
    upsert_interview_submission(
        conn,
        user_id="u1",
        session_id="s1",
        legacy_topic_id="rag-basics",
        submission={"answer": "STAR method response"},
    )

    all_sql = " ".join(sql for sql, _ in conn.executed)
    assert "interview_submissions" in all_sql


def test_upsert_interview_submission_passes_answer_as_param():
    from repositories.submissions_repository import upsert_interview_submission

    conn = FakeConn()
    upsert_interview_submission(
        conn,
        user_id=None,
        session_id="s1",
        legacy_topic_id="rag-basics",
        submission={"answer": "interview answer text"},
    )

    all_params = [p for _, params in conn.executed for p in (params or [])]
    assert "interview answer text" in all_params


def test_upsert_interview_submission_no_commit_or_rollback():
    from repositories.submissions_repository import upsert_interview_submission

    conn = FakeConn()
    upsert_interview_submission(
        conn,
        user_id=None,
        session_id="s1",
        legacy_topic_id="t",
        submission={"answer": "x"},
    )

    assert conn.committed   is False
    assert conn.rolled_back is False


# ── FakeCursor: upsert_topic_notes ────────────────────────────────────────────

def test_upsert_topic_notes_executes_sql():
    from repositories.topic_notes_repository import upsert_topic_notes

    conn = FakeConn()
    upsert_topic_notes(
        conn,
        user_id="u1",
        session_id="s1",
        legacy_topic_id="rag-basics",
        notes={"reflection": "I learned a lot", "confusions": "Chunking strategies"},
    )

    all_sql = " ".join(sql for sql, _ in conn.executed)
    assert "topic_notes" in all_sql
    assert "legacy_topic_id" in all_sql


def test_upsert_topic_notes_passes_reflection_as_param():
    from repositories.topic_notes_repository import upsert_topic_notes

    conn = FakeConn()
    upsert_topic_notes(
        conn,
        user_id=None,
        session_id="s1",
        legacy_topic_id="rag-basics",
        notes={"reflection": "key insight here"},
    )

    all_params = [p for _, params in conn.executed for p in (params or [])]
    assert "key insight here" in all_params


def test_upsert_topic_notes_no_commit_or_rollback():
    from repositories.topic_notes_repository import upsert_topic_notes

    conn = FakeConn()
    upsert_topic_notes(
        conn,
        user_id=None,
        session_id="s1",
        legacy_topic_id="t",
        notes={},
    )

    assert conn.committed   is False
    assert conn.rolled_back is False


# ── Getter: returns dict when row found ───────────────────────────────────────

def test_get_generated_topic_content_returns_dict_when_row_found():
    from repositories.generated_content_repository import get_generated_topic_content_by_legacy_id

    fake_row = {"id": 1, "session_id": "s1", "legacy_topic_id": "rag-basics", "content": "text"}
    conn = FakeConn(row=fake_row)
    result = get_generated_topic_content_by_legacy_id(
        conn, session_id="s1", legacy_topic_id="rag-basics"
    )
    assert isinstance(result, dict)
    assert result["content"] == "text"


def test_get_generated_topic_content_returns_none_when_no_row():
    from repositories.generated_content_repository import get_generated_topic_content_by_legacy_id

    conn = FakeConn()
    result = get_generated_topic_content_by_legacy_id(
        conn, session_id="s1", legacy_topic_id="missing"
    )
    assert result is None


def test_get_generated_topic_practice_returns_dict_when_row_found():
    from repositories.generated_content_repository import get_generated_topic_practice_by_legacy_id

    fake_row = {"id": 2, "session_id": "s1", "practice_type": "quiz", "content": "Q?"}
    conn = FakeConn(row=fake_row)
    result = get_generated_topic_practice_by_legacy_id(
        conn, session_id="s1", legacy_topic_id="t", practice_type="quiz"
    )
    assert isinstance(result, dict)
    assert result["practice_type"] == "quiz"


def test_get_generated_topic_practice_returns_none_when_no_row():
    from repositories.generated_content_repository import get_generated_topic_practice_by_legacy_id

    conn = FakeConn()
    result = get_generated_topic_practice_by_legacy_id(
        conn, session_id="s1", legacy_topic_id="missing", practice_type="quiz"
    )
    assert result is None


def test_get_quiz_submission_returns_dict_when_row_found():
    from repositories.submissions_repository import get_quiz_submission_by_legacy_id

    fake_row = {"id": 3, "session_id": "s1", "answers": "A, B", "score": 80}
    conn = FakeConn(row=fake_row)
    result = get_quiz_submission_by_legacy_id(
        conn, session_id="s1", legacy_topic_id="rag-basics"
    )
    assert isinstance(result, dict)
    assert result["score"] == 80


def test_get_quiz_submission_returns_none_when_no_row():
    from repositories.submissions_repository import get_quiz_submission_by_legacy_id

    conn = FakeConn()
    result = get_quiz_submission_by_legacy_id(
        conn, session_id="s1", legacy_topic_id="missing"
    )
    assert result is None


def test_get_portfolio_submission_returns_dict_when_row_found():
    from repositories.submissions_repository import get_portfolio_submission_by_legacy_id

    fake_row = {"id": 4, "session_id": "s1", "submission": "my project", "score": 90}
    conn = FakeConn(row=fake_row)
    result = get_portfolio_submission_by_legacy_id(
        conn, session_id="s1", legacy_topic_id="rag-basics"
    )
    assert isinstance(result, dict)
    assert result["submission"] == "my project"


def test_get_portfolio_submission_returns_none_when_no_row():
    from repositories.submissions_repository import get_portfolio_submission_by_legacy_id

    conn = FakeConn()
    result = get_portfolio_submission_by_legacy_id(
        conn, session_id="s1", legacy_topic_id="missing"
    )
    assert result is None


def test_get_interview_submission_returns_dict_when_row_found():
    from repositories.submissions_repository import get_interview_submission_by_legacy_id

    fake_row = {"id": 5, "session_id": "s1", "answer": "STAR response", "score": 85}
    conn = FakeConn(row=fake_row)
    result = get_interview_submission_by_legacy_id(
        conn, session_id="s1", legacy_topic_id="rag-basics"
    )
    assert isinstance(result, dict)
    assert result["answer"] == "STAR response"


def test_get_interview_submission_returns_none_when_no_row():
    from repositories.submissions_repository import get_interview_submission_by_legacy_id

    conn = FakeConn()
    result = get_interview_submission_by_legacy_id(
        conn, session_id="s1", legacy_topic_id="missing"
    )
    assert result is None


def test_get_topic_notes_returns_dict_when_row_found():
    from repositories.topic_notes_repository import get_topic_notes_by_legacy_id

    fake_row = {"id": 6, "session_id": "s1", "reflection": "insight", "confusions": None}
    conn = FakeConn(row=fake_row)
    result = get_topic_notes_by_legacy_id(
        conn, session_id="s1", legacy_topic_id="rag-basics"
    )
    assert isinstance(result, dict)
    assert result["reflection"] == "insight"


def test_get_topic_notes_returns_none_when_no_row():
    from repositories.topic_notes_repository import get_topic_notes_by_legacy_id

    conn = FakeConn()
    result = get_topic_notes_by_legacy_id(
        conn, session_id="s1", legacy_topic_id="missing"
    )
    assert result is None
