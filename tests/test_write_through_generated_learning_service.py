"""Tests for services/write_through_generated_learning_service.py.

All tests run without a real database connection or a real SessionContext.
"""

from __future__ import annotations

import importlib
from pathlib import Path
from unittest.mock import MagicMock, patch

SERVICE_PATH = Path(__file__).parent.parent / "services" / "write_through_generated_learning_service.py"


def _import():
    import services.write_through_generated_learning_service as m
    importlib.reload(m)
    return m


# ── File existence ────────────────────────────────────────────────────────────

def test_service_file_exists():
    assert SERVICE_PATH.exists()


# ── Source-code structural checks ─────────────────────────────────────────────

def test_source_does_not_read_os_environ_directly():
    src = SERVICE_PATH.read_text(encoding="utf-8")
    assert "os.environ" not in src
    assert "os.getenv"  not in src


def test_source_does_not_reference_database_pool():
    src = SERVICE_PATH.read_text(encoding="utf-8")
    assert "database.pool" not in src


def test_source_does_not_open_connection():
    src = SERVICE_PATH.read_text(encoding="utf-8")
    assert "psycopg2.connect(" not in src
    assert "get_conn("         not in src


def test_source_does_not_commit_or_rollback():
    src = SERVICE_PATH.read_text(encoding="utf-8")
    assert ".commit()"   not in src
    assert ".rollback()" not in src


# ── Function existence ────────────────────────────────────────────────────────

def test_module_has_expected_functions():
    m = _import()
    for fn in (
        "maybe_write_generated_topic_content",
        "maybe_write_generated_topic_practice",
        "maybe_write_all_generated_topic_practice",
        "maybe_write_quiz_submission",
        "maybe_write_portfolio_submission",
        "maybe_write_interview_submission",
        "maybe_write_topic_notes",
        "maybe_write_generated_learning_state",
    ):
        assert callable(getattr(m, fn, None)), f"missing: {fn}"


# ── Fake helpers ──────────────────────────────────────────────────────────────

def _fake_session(
    *,
    content=None,
    practice=None,
    quiz_sub=None,
    portfolio_sub=None,
    interview_sub=None,
    notes=None,
):
    session = MagicMock()
    session.get_generated_topic_content.return_value  = content  or {"content": "", "model": ""}
    session.get_generated_topic_practice.return_value = practice or {"content": "", "model": ""}
    session.get_quiz_submission.return_value          = quiz_sub or {"answers": "", "score": None}
    session.get_portfolio_submission.return_value     = portfolio_sub or {"submission": "", "score": None}
    session.get_interview_submission.return_value     = interview_sub or {"answer": "", "score": None}
    session.get_topic_notes.return_value              = notes or {"reflection": "", "confusions": "", "application_idea": ""}
    return session


# ── Flag disabled → all helpers return no-op ─────────────────────────────────

def test_content_returns_false_when_flag_off(monkeypatch):
    monkeypatch.delenv("AI2_DB_WRITE_THROUGH_ENABLED", raising=False)
    m = _import()
    result = m.maybe_write_generated_topic_content(
        conn=MagicMock(), session=_fake_session(), user_id=None,
        session_id="s1", legacy_topic_id="t1",
    )
    assert result is False


def test_practice_returns_false_when_flag_off(monkeypatch):
    monkeypatch.delenv("AI2_DB_WRITE_THROUGH_ENABLED", raising=False)
    m = _import()
    result = m.maybe_write_generated_topic_practice(
        conn=MagicMock(), session=_fake_session(), user_id=None,
        session_id="s1", legacy_topic_id="t1", practice_type="quiz",
    )
    assert result is False


def test_all_practice_returns_zero_when_flag_off(monkeypatch):
    monkeypatch.delenv("AI2_DB_WRITE_THROUGH_ENABLED", raising=False)
    m = _import()
    result = m.maybe_write_all_generated_topic_practice(
        conn=MagicMock(), session=_fake_session(), user_id=None,
        session_id="s1", legacy_topic_id="t1",
    )
    assert result == 0


def test_quiz_submission_returns_false_when_flag_off(monkeypatch):
    monkeypatch.delenv("AI2_DB_WRITE_THROUGH_ENABLED", raising=False)
    m = _import()
    result = m.maybe_write_quiz_submission(
        conn=MagicMock(), session=_fake_session(), user_id=None,
        session_id="s1", legacy_topic_id="t1",
    )
    assert result is False


def test_portfolio_submission_returns_false_when_flag_off(monkeypatch):
    monkeypatch.delenv("AI2_DB_WRITE_THROUGH_ENABLED", raising=False)
    m = _import()
    result = m.maybe_write_portfolio_submission(
        conn=MagicMock(), session=_fake_session(), user_id=None,
        session_id="s1", legacy_topic_id="t1",
    )
    assert result is False


def test_interview_submission_returns_false_when_flag_off(monkeypatch):
    monkeypatch.delenv("AI2_DB_WRITE_THROUGH_ENABLED", raising=False)
    m = _import()
    result = m.maybe_write_interview_submission(
        conn=MagicMock(), session=_fake_session(), user_id=None,
        session_id="s1", legacy_topic_id="t1",
    )
    assert result is False


def test_topic_notes_returns_false_when_flag_off(monkeypatch):
    monkeypatch.delenv("AI2_DB_WRITE_THROUGH_ENABLED", raising=False)
    m = _import()
    result = m.maybe_write_topic_notes(
        conn=MagicMock(), session=_fake_session(), user_id=None,
        session_id="s1", legacy_topic_id="t1",
    )
    assert result is False


# ── conn=None → no-op ─────────────────────────────────────────────────────────

def test_content_returns_false_when_conn_none(monkeypatch):
    monkeypatch.setenv("AI2_DB_WRITE_THROUGH_ENABLED", "1")
    m = _import()
    result = m.maybe_write_generated_topic_content(
        conn=None, session=_fake_session(), user_id=None,
        session_id="s1", legacy_topic_id="t1",
    )
    assert result is False


def test_quiz_submission_returns_false_when_conn_none(monkeypatch):
    monkeypatch.setenv("AI2_DB_WRITE_THROUGH_ENABLED", "1")
    m = _import()
    result = m.maybe_write_quiz_submission(
        conn=None, session=_fake_session(), user_id=None,
        session_id="s1", legacy_topic_id="t1",
    )
    assert result is False


def test_topic_notes_returns_false_when_conn_none(monkeypatch):
    monkeypatch.setenv("AI2_DB_WRITE_THROUGH_ENABLED", "1")
    m = _import()
    result = m.maybe_write_topic_notes(
        conn=None, session=_fake_session(), user_id=None,
        session_id="s1", legacy_topic_id="t1",
    )
    assert result is False


# ── Empty legacy_topic_id → no-op ────────────────────────────────────────────

def test_content_returns_false_when_legacy_topic_id_empty(monkeypatch):
    monkeypatch.setenv("AI2_DB_WRITE_THROUGH_ENABLED", "1")
    m = _import()
    result = m.maybe_write_generated_topic_content(
        conn=MagicMock(), session=_fake_session(), user_id=None,
        session_id="s1", legacy_topic_id="",
    )
    assert result is False


def test_practice_returns_false_when_legacy_topic_id_empty(monkeypatch):
    monkeypatch.setenv("AI2_DB_WRITE_THROUGH_ENABLED", "1")
    m = _import()
    result = m.maybe_write_generated_topic_practice(
        conn=MagicMock(), session=_fake_session(), user_id=None,
        session_id="s1", legacy_topic_id="", practice_type="quiz",
    )
    assert result is False


def test_quiz_submission_returns_false_when_legacy_topic_id_empty(monkeypatch):
    monkeypatch.setenv("AI2_DB_WRITE_THROUGH_ENABLED", "1")
    m = _import()
    result = m.maybe_write_quiz_submission(
        conn=MagicMock(), session=_fake_session(), user_id=None,
        session_id="s1", legacy_topic_id="",
    )
    assert result is False


def test_topic_notes_returns_false_when_legacy_topic_id_empty(monkeypatch):
    monkeypatch.setenv("AI2_DB_WRITE_THROUGH_ENABLED", "1")
    m = _import()
    result = m.maybe_write_topic_notes(
        conn=MagicMock(), session=_fake_session(), user_id=None,
        session_id="s1", legacy_topic_id="",
    )
    assert result is False


# ── Content missing → no-op (session has empty record) ───────────────────────

def test_content_returns_false_when_content_field_empty(monkeypatch):
    monkeypatch.setenv("AI2_DB_WRITE_THROUGH_ENABLED", "1")
    m = _import()
    session = _fake_session(content={"content": "", "model": ""})
    result = m.maybe_write_generated_topic_content(
        conn=MagicMock(), session=session, user_id=None,
        session_id="s1", legacy_topic_id="t1",
    )
    assert result is False


def test_practice_returns_false_when_content_field_empty(monkeypatch):
    monkeypatch.setenv("AI2_DB_WRITE_THROUGH_ENABLED", "1")
    m = _import()
    session = _fake_session(practice={"content": "", "model": ""})
    result = m.maybe_write_generated_topic_practice(
        conn=MagicMock(), session=session, user_id=None,
        session_id="s1", legacy_topic_id="t1", practice_type="quiz",
    )
    assert result is False


def test_quiz_submission_returns_false_when_answers_empty(monkeypatch):
    monkeypatch.setenv("AI2_DB_WRITE_THROUGH_ENABLED", "1")
    m = _import()
    session = _fake_session(quiz_sub={"answers": "", "score": None})
    result = m.maybe_write_quiz_submission(
        conn=MagicMock(), session=session, user_id=None,
        session_id="s1", legacy_topic_id="t1",
    )
    assert result is False


def test_portfolio_submission_returns_false_when_submission_empty(monkeypatch):
    monkeypatch.setenv("AI2_DB_WRITE_THROUGH_ENABLED", "1")
    m = _import()
    session = _fake_session(portfolio_sub={"submission": "", "score": None})
    result = m.maybe_write_portfolio_submission(
        conn=MagicMock(), session=session, user_id=None,
        session_id="s1", legacy_topic_id="t1",
    )
    assert result is False


def test_interview_submission_returns_false_when_answer_empty(monkeypatch):
    monkeypatch.setenv("AI2_DB_WRITE_THROUGH_ENABLED", "1")
    m = _import()
    session = _fake_session(interview_sub={"answer": "", "score": None})
    result = m.maybe_write_interview_submission(
        conn=MagicMock(), session=session, user_id=None,
        session_id="s1", legacy_topic_id="t1",
    )
    assert result is False


def test_topic_notes_returns_false_when_all_note_fields_empty(monkeypatch):
    monkeypatch.setenv("AI2_DB_WRITE_THROUGH_ENABLED", "1")
    m = _import()
    session = _fake_session(notes={"reflection": "", "confusions": "", "application_idea": ""})
    result = m.maybe_write_topic_notes(
        conn=MagicMock(), session=session, user_id=None,
        session_id="s1", legacy_topic_id="t1",
    )
    assert result is False


# ── Content present + flag on → repository called ────────────────────────────

def test_content_returns_true_and_calls_repo_when_enabled(monkeypatch):
    monkeypatch.setenv("AI2_DB_WRITE_THROUGH_ENABLED", "1")
    m = _import()
    session = _fake_session(content={"content": "RAG explained", "model": "claude-sonnet-4-6"})
    fake_upsert = MagicMock()
    with patch("repositories.generated_content_repository.upsert_generated_topic_content", fake_upsert):
        result = m.maybe_write_generated_topic_content(
            conn=MagicMock(), session=session, user_id="u1",
            session_id="s1", legacy_topic_id="rag-basics",
        )
    assert result is True
    fake_upsert.assert_called_once()
    _, kwargs = fake_upsert.call_args
    assert kwargs["legacy_topic_id"] == "rag-basics"


def test_content_helper_reads_session_with_correct_topic_id(monkeypatch):
    monkeypatch.setenv("AI2_DB_WRITE_THROUGH_ENABLED", "1")
    m = _import()
    session = _fake_session(content={"content": "text"})
    with patch("repositories.generated_content_repository.upsert_generated_topic_content"):
        m.maybe_write_generated_topic_content(
            conn=MagicMock(), session=session, user_id=None,
            session_id="s1", legacy_topic_id="rag-basics",
        )
    session.get_generated_topic_content.assert_called_once_with("rag-basics")


def test_practice_returns_true_and_calls_repo_when_enabled(monkeypatch):
    monkeypatch.setenv("AI2_DB_WRITE_THROUGH_ENABLED", "1")
    m = _import()
    session = _fake_session(practice={"content": "Q: What is RAG?"})
    fake_upsert = MagicMock()
    with patch("repositories.generated_content_repository.upsert_generated_topic_practice", fake_upsert):
        result = m.maybe_write_generated_topic_practice(
            conn=MagicMock(), session=session, user_id=None,
            session_id="s1", legacy_topic_id="rag-basics", practice_type="quiz",
        )
    assert result is True
    _, kwargs = fake_upsert.call_args
    assert kwargs["practice_type"] == "quiz"
    assert kwargs["legacy_topic_id"] == "rag-basics"


def test_practice_helper_reads_session_with_correct_args(monkeypatch):
    monkeypatch.setenv("AI2_DB_WRITE_THROUGH_ENABLED", "1")
    m = _import()
    session = _fake_session(practice={"content": "text"})
    with patch("repositories.generated_content_repository.upsert_generated_topic_practice"):
        m.maybe_write_generated_topic_practice(
            conn=MagicMock(), session=session, user_id=None,
            session_id="s1", legacy_topic_id="t1", practice_type="portfolio_task",
        )
    session.get_generated_topic_practice.assert_called_once_with("t1", "portfolio_task")


def test_quiz_submission_returns_true_and_calls_repo(monkeypatch):
    monkeypatch.setenv("AI2_DB_WRITE_THROUGH_ENABLED", "1")
    m = _import()
    session = _fake_session(quiz_sub={"answers": "A, B, C", "score": 80})
    fake_upsert = MagicMock()
    with patch("repositories.submissions_repository.upsert_quiz_submission", fake_upsert):
        result = m.maybe_write_quiz_submission(
            conn=MagicMock(), session=session, user_id="u1",
            session_id="s1", legacy_topic_id="rag-basics",
        )
    assert result is True
    fake_upsert.assert_called_once()
    _, kwargs = fake_upsert.call_args
    assert kwargs["legacy_topic_id"] == "rag-basics"


def test_portfolio_submission_returns_true_and_calls_repo(monkeypatch):
    monkeypatch.setenv("AI2_DB_WRITE_THROUGH_ENABLED", "1")
    m = _import()
    session = _fake_session(portfolio_sub={"submission": "My project", "score": 90})
    fake_upsert = MagicMock()
    with patch("repositories.submissions_repository.upsert_portfolio_submission", fake_upsert):
        result = m.maybe_write_portfolio_submission(
            conn=MagicMock(), session=session, user_id="u1",
            session_id="s1", legacy_topic_id="rag-basics",
        )
    assert result is True
    fake_upsert.assert_called_once()
    _, kwargs = fake_upsert.call_args
    assert kwargs["legacy_topic_id"] == "rag-basics"


def test_interview_submission_returns_true_and_calls_repo(monkeypatch):
    monkeypatch.setenv("AI2_DB_WRITE_THROUGH_ENABLED", "1")
    m = _import()
    session = _fake_session(interview_sub={"answer": "STAR response", "score": 85})
    fake_upsert = MagicMock()
    with patch("repositories.submissions_repository.upsert_interview_submission", fake_upsert):
        result = m.maybe_write_interview_submission(
            conn=MagicMock(), session=session, user_id="u1",
            session_id="s1", legacy_topic_id="rag-basics",
        )
    assert result is True
    fake_upsert.assert_called_once()


def test_topic_notes_returns_true_when_reflection_present(monkeypatch):
    monkeypatch.setenv("AI2_DB_WRITE_THROUGH_ENABLED", "1")
    m = _import()
    session = _fake_session(notes={"reflection": "Key insight", "confusions": "", "application_idea": ""})
    fake_upsert = MagicMock()
    with patch("repositories.topic_notes_repository.upsert_topic_notes", fake_upsert):
        result = m.maybe_write_topic_notes(
            conn=MagicMock(), session=session, user_id=None,
            session_id="s1", legacy_topic_id="t1",
        )
    assert result is True
    fake_upsert.assert_called_once()
    _, kwargs = fake_upsert.call_args
    assert kwargs["legacy_topic_id"] == "t1"


def test_topic_notes_returns_true_when_only_confusions_present(monkeypatch):
    monkeypatch.setenv("AI2_DB_WRITE_THROUGH_ENABLED", "1")
    m = _import()
    session = _fake_session(notes={"reflection": "", "confusions": "Still confused about chunking", "application_idea": ""})
    with patch("repositories.topic_notes_repository.upsert_topic_notes"):
        result = m.maybe_write_topic_notes(
            conn=MagicMock(), session=session, user_id=None,
            session_id="s1", legacy_topic_id="t1",
        )
    assert result is True


def test_topic_notes_returns_true_when_only_application_idea_present(monkeypatch):
    monkeypatch.setenv("AI2_DB_WRITE_THROUGH_ENABLED", "1")
    m = _import()
    session = _fake_session(notes={"reflection": "", "confusions": "", "application_idea": "Use RAG for docs"})
    with patch("repositories.topic_notes_repository.upsert_topic_notes"):
        result = m.maybe_write_topic_notes(
            conn=MagicMock(), session=session, user_id=None,
            session_id="s1", legacy_topic_id="t1",
        )
    assert result is True


# ── all-practice helper ───────────────────────────────────────────────────────

def test_all_practice_returns_correct_count_when_all_types_have_content(monkeypatch):
    monkeypatch.setenv("AI2_DB_WRITE_THROUGH_ENABLED", "1")
    m = _import()
    session = _fake_session(practice={"content": "Some practice content"})
    with patch("repositories.generated_content_repository.upsert_generated_topic_practice"):
        result = m.maybe_write_all_generated_topic_practice(
            conn=MagicMock(), session=session, user_id=None,
            session_id="s1", legacy_topic_id="t1",
        )
    assert result == 3


def test_all_practice_returns_zero_when_no_content(monkeypatch):
    monkeypatch.setenv("AI2_DB_WRITE_THROUGH_ENABLED", "1")
    m = _import()
    session = _fake_session(practice={"content": ""})
    result = m.maybe_write_all_generated_topic_practice(
        conn=MagicMock(), session=session, user_id=None,
        session_id="s1", legacy_topic_id="t1",
    )
    assert result == 0


def test_all_practice_calls_each_practice_type(monkeypatch):
    monkeypatch.setenv("AI2_DB_WRITE_THROUGH_ENABLED", "1")
    m = _import()
    session = _fake_session(practice={"content": "practice"})
    called_types = []

    def fake_write(*, conn, session, user_id, session_id, legacy_topic_id, practice_type):
        called_types.append(practice_type)
        return True

    with patch.object(m, "maybe_write_generated_topic_practice", side_effect=fake_write):
        m.maybe_write_all_generated_topic_practice(
            conn=MagicMock(), session=session, user_id=None,
            session_id="s1", legacy_topic_id="t1",
        )
    assert set(called_types) == {"quiz", "portfolio_task", "interview_practice"}


# ── aggregate helper ──────────────────────────────────────────────────────────

def test_aggregate_returns_dict_with_expected_keys(monkeypatch):
    monkeypatch.delenv("AI2_DB_WRITE_THROUGH_ENABLED", raising=False)
    m = _import()
    result = m.maybe_write_generated_learning_state(
        conn=MagicMock(), session=_fake_session(), user_id=None,
        session_id="s1", legacy_topic_id="t1",
    )
    assert isinstance(result, dict)
    for key in (
        "generated_topic_content_written",
        "generated_topic_practice_written",
        "quiz_submission_written",
        "portfolio_submission_written",
        "interview_submission_written",
        "topic_notes_written",
    ):
        assert key in result, f"missing key: {key}"


def test_aggregate_all_false_when_flag_off(monkeypatch):
    monkeypatch.delenv("AI2_DB_WRITE_THROUGH_ENABLED", raising=False)
    m = _import()
    result = m.maybe_write_generated_learning_state(
        conn=MagicMock(), session=_fake_session(), user_id=None,
        session_id="s1", legacy_topic_id="t1",
    )
    assert result["generated_topic_content_written"] is False
    assert result["generated_topic_practice_written"] == 0
    assert result["quiz_submission_written"]          is False
    assert result["portfolio_submission_written"]     is False
    assert result["interview_submission_written"]     is False
    assert result["topic_notes_written"]              is False


def test_aggregate_delegates_to_sub_helpers(monkeypatch):
    monkeypatch.setenv("AI2_DB_WRITE_THROUGH_ENABLED", "1")
    m = _import()
    fake_content   = MagicMock(return_value=True)
    fake_practice  = MagicMock(return_value=2)
    fake_quiz      = MagicMock(return_value=True)
    fake_portfolio = MagicMock(return_value=False)
    fake_interview = MagicMock(return_value=True)
    fake_notes     = MagicMock(return_value=True)

    with patch.object(m, "maybe_write_generated_topic_content",     fake_content):
        with patch.object(m, "maybe_write_all_generated_topic_practice", fake_practice):
            with patch.object(m, "maybe_write_quiz_submission",      fake_quiz):
                with patch.object(m, "maybe_write_portfolio_submission", fake_portfolio):
                    with patch.object(m, "maybe_write_interview_submission", fake_interview):
                        with patch.object(m, "maybe_write_topic_notes",     fake_notes):
                            result = m.maybe_write_generated_learning_state(
                                conn=MagicMock(), session=_fake_session(),
                                user_id="u1", session_id="s1", legacy_topic_id="t1",
                            )
    assert result == {
        "generated_topic_content_written":  True,
        "generated_topic_practice_written": 2,
        "quiz_submission_written":          True,
        "portfolio_submission_written":     False,
        "interview_submission_written":     True,
        "topic_notes_written":              True,
    }
    fake_content.assert_called_once()
    fake_practice.assert_called_once()
    fake_quiz.assert_called_once()
    fake_portfolio.assert_called_once()
    fake_interview.assert_called_once()
    fake_notes.assert_called_once()


# ── Session not mutated ───────────────────────────────────────────────────────

def test_content_helper_does_not_mutate_session(monkeypatch):
    monkeypatch.setenv("AI2_DB_WRITE_THROUGH_ENABLED", "1")
    m = _import()
    session = _fake_session(content={"content": "text"})
    with patch("repositories.generated_content_repository.upsert_generated_topic_content"):
        m.maybe_write_generated_topic_content(
            conn=MagicMock(), session=session, user_id=None,
            session_id="s1", legacy_topic_id="t1",
        )
    # Only read methods should have been called, not any save/mark/update methods
    session.save_generated_topic_content.assert_not_called()


def test_notes_helper_does_not_mutate_session(monkeypatch):
    monkeypatch.setenv("AI2_DB_WRITE_THROUGH_ENABLED", "1")
    m = _import()
    session = _fake_session(notes={"reflection": "insight", "confusions": "", "application_idea": ""})
    with patch("repositories.topic_notes_repository.upsert_topic_notes"):
        m.maybe_write_topic_notes(
            conn=MagicMock(), session=session, user_id=None,
            session_id="s1", legacy_topic_id="t1",
        )
    session.save_topic_notes.assert_not_called()


# ── No DB connection created ──────────────────────────────────────────────────

def test_content_helper_does_not_call_session_read_when_flag_off(monkeypatch):
    monkeypatch.delenv("AI2_DB_WRITE_THROUGH_ENABLED", raising=False)
    m = _import()
    session = _fake_session()
    m.maybe_write_generated_topic_content(
        conn=MagicMock(), session=session, user_id=None,
        session_id="s1", legacy_topic_id="t1",
    )
    session.get_generated_topic_content.assert_not_called()


def test_quiz_helper_does_not_call_session_read_when_flag_off(monkeypatch):
    monkeypatch.delenv("AI2_DB_WRITE_THROUGH_ENABLED", raising=False)
    m = _import()
    session = _fake_session()
    m.maybe_write_quiz_submission(
        conn=MagicMock(), session=session, user_id=None,
        session_id="s1", legacy_topic_id="t1",
    )
    session.get_quiz_submission.assert_not_called()
