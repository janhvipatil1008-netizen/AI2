"""Tests for services/generated_learning_read_service.py."""

from __future__ import annotations

import importlib
from pathlib import Path
from unittest.mock import Mock

import pytest

import services.generated_learning_read_service as service


SERVICE_PATH = Path(__file__).parent.parent / "services" / "generated_learning_read_service.py"


def _content_row(**overrides):
    row = {
        "content": "Learning content",
        "model": "claude-test",
        "version": 2,
        "freshness_label": "AI-generated",
        "source": "claude",
        "legacy_topic_id": "rag-basics",
        "metadata": {"source": "write_through"},
        "generated_at": "2026-05-18T10:00:00",
    }
    row.update(overrides)
    return row


def _practice_row(**overrides):
    row = _content_row(practice_type="quiz")
    row.update(overrides)
    return row


def _quiz_row(**overrides):
    row = {
        "answers": "Q1: A",
        "evaluation": "Good",
        "score": 8,
        "model": "claude-test",
        "legacy_topic_id": "rag-basics",
        "metadata": {"rubric": "v1"},
        "submitted_at": "2026-05-18T10:00:00",
        "evaluated_at": "2026-05-18T10:01:00",
    }
    row.update(overrides)
    return row


def _portfolio_row(**overrides):
    row = {
        "submission": "Portfolio work",
        "feedback": "Solid",
        "score": 7,
        "model": "claude-test",
        "legacy_topic_id": "rag-basics",
        "metadata": {"rubric": "v1"},
        "submitted_at": "2026-05-18T10:00:00",
        "reviewed_at": "2026-05-18T10:01:00",
    }
    row.update(overrides)
    return row


def _interview_row(**overrides):
    row = {
        "answer": "Interview answer",
        "feedback": "Strong",
        "score": 9,
        "model": "claude-test",
        "legacy_topic_id": "rag-basics",
        "metadata": {"rubric": "v1"},
        "submitted_at": "2026-05-18T10:00:00",
        "reviewed_at": "2026-05-18T10:01:00",
    }
    row.update(overrides)
    return row


def _notes_row(**overrides):
    row = {
        "reflection": "I understand it",
        "confusions": "None",
        "application_idea": "Build a demo",
        "legacy_topic_id": "rag-basics",
        "metadata": {"source": "write_through"},
        "updated_at": "2026-05-18T10:00:00",
    }
    row.update(overrides)
    return row


def test_module_imports_without_db_connection(monkeypatch):
    import database.pool as pool

    connect = Mock(side_effect=AssertionError("DB connection must not open"))
    monkeypatch.setattr(pool, "_connect", connect)

    importlib.reload(service)

    connect.assert_not_called()


def test_source_does_not_import_database_pool():
    assert "database.pool" not in SERVICE_PATH.read_text(encoding="utf-8")


def test_source_does_not_read_os_environ_or_getenv():
    src = SERVICE_PATH.read_text(encoding="utf-8")
    assert "os.environ" not in src
    assert "os.getenv" not in src
    assert "import os" not in src


def test_source_does_not_import_or_mutate_session_context():
    src = SERVICE_PATH.read_text(encoding="utf-8")
    assert "from context.session" not in src
    assert "import context.session" not in src
    assert "context.session" not in src
    assert ".save_" not in src
    assert ".mark_" not in src


def test_normalize_generated_topic_content_row_full_row():
    result = service.normalize_generated_topic_content_row(_content_row())
    assert result == {
        "content": "Learning content",
        "model": "claude-test",
        "version": "2",
        "freshness_label": "AI-generated",
        "source": "claude",
        "legacy_topic_id": "rag-basics",
        "metadata": {"source": "write_through"},
        "generated_at": "2026-05-18T10:00:00",
    }


def test_normalize_generated_topic_practice_row_full_row():
    result = service.normalize_generated_topic_practice_row(_practice_row(practice_type="portfolio_task"))
    assert result["content"] == "Learning content"
    assert result["practice_type"] == "portfolio_task"
    assert result["version"] == "2"


def test_normalize_quiz_submission_row_full_row():
    result = service.normalize_quiz_submission_row(_quiz_row(score="8"))
    assert result == {
        "answers": "Q1: A",
        "evaluation": "Good",
        "score": 8,
        "model": "claude-test",
        "legacy_topic_id": "rag-basics",
        "metadata": {"rubric": "v1"},
        "submitted_at": "2026-05-18T10:00:00",
        "evaluated_at": "2026-05-18T10:01:00",
    }


def test_normalize_portfolio_submission_row_full_row():
    result = service.normalize_portfolio_submission_row(_portfolio_row(score="7"))
    assert result["submission"] == "Portfolio work"
    assert result["feedback"] == "Solid"
    assert result["score"] == 7
    assert result["reviewed_at"] == "2026-05-18T10:01:00"


def test_normalize_interview_submission_row_full_row():
    result = service.normalize_interview_submission_row(_interview_row(score="9"))
    assert result["answer"] == "Interview answer"
    assert result["feedback"] == "Strong"
    assert result["score"] == 9
    assert result["reviewed_at"] == "2026-05-18T10:01:00"


def test_normalize_topic_notes_row_full_row():
    result = service.normalize_topic_notes_row(_notes_row())
    assert result == {
        "reflection": "I understand it",
        "confusions": "None",
        "application_idea": "Build a demo",
        "legacy_topic_id": "rag-basics",
        "metadata": {"source": "write_through"},
        "updated_at": "2026-05-18T10:00:00",
    }


@pytest.mark.parametrize(
    ("normalizer", "expected"),
    [
        (
            service.normalize_generated_topic_content_row,
            {
                "content": "",
                "model": "",
                "version": "",
                "freshness_label": "",
                "source": "",
                "legacy_topic_id": "",
                "metadata": {},
                "generated_at": "",
            },
        ),
        (
            service.normalize_generated_topic_practice_row,
            {
                "content": "",
                "model": "",
                "version": "",
                "freshness_label": "",
                "source": "",
                "legacy_topic_id": "",
                "metadata": {},
                "generated_at": "",
                "practice_type": "",
            },
        ),
        (
            service.normalize_quiz_submission_row,
            {
                "answers": "",
                "evaluation": "",
                "score": None,
                "model": "",
                "legacy_topic_id": "",
                "metadata": {},
                "submitted_at": "",
                "evaluated_at": "",
            },
        ),
        (
            service.normalize_portfolio_submission_row,
            {
                "submission": "",
                "feedback": "",
                "score": None,
                "model": "",
                "legacy_topic_id": "",
                "metadata": {},
                "submitted_at": "",
                "reviewed_at": "",
            },
        ),
        (
            service.normalize_interview_submission_row,
            {
                "answer": "",
                "feedback": "",
                "score": None,
                "model": "",
                "legacy_topic_id": "",
                "metadata": {},
                "submitted_at": "",
                "reviewed_at": "",
            },
        ),
        (
            service.normalize_topic_notes_row,
            {
                "reflection": "",
                "confusions": "",
                "application_idea": "",
                "legacy_topic_id": "",
                "metadata": {},
                "updated_at": "",
            },
        ),
    ],
)
def test_normalizers_handle_missing_optional_fields(normalizer, expected):
    assert normalizer({"metadata": "not-json", "score": "not-int"}) == expected


def test_generated_content_getter_calls_repository_and_normalizes(monkeypatch):
    from repositories import generated_content_repository

    repo = Mock(return_value=_content_row())
    monkeypatch.setattr(generated_content_repository, "get_generated_topic_content_by_legacy_id", repo)

    conn = object()
    result = service.get_generated_topic_content_from_db(
        conn,
        session_id="s1",
        legacy_topic_id="rag-basics",
    )

    repo.assert_called_once_with(conn, session_id="s1", legacy_topic_id="rag-basics")
    assert result["content"] == "Learning content"


def test_generated_practice_getter_calls_repository_and_normalizes(monkeypatch):
    from repositories import generated_content_repository

    repo = Mock(return_value=_practice_row(practice_type="interview_practice"))
    monkeypatch.setattr(generated_content_repository, "get_generated_topic_practice_by_legacy_id", repo)

    conn = object()
    result = service.get_generated_topic_practice_from_db(
        conn,
        session_id="s1",
        legacy_topic_id="rag-basics",
        practice_type="interview_practice",
    )

    repo.assert_called_once_with(
        conn,
        session_id="s1",
        legacy_topic_id="rag-basics",
        practice_type="interview_practice",
    )
    assert result["practice_type"] == "interview_practice"


@pytest.mark.parametrize(
    ("repo_name", "getter", "row_factory", "expected_key"),
    [
        ("get_quiz_submission_by_legacy_id", service.get_quiz_submission_from_db, _quiz_row, "answers"),
        (
            "get_portfolio_submission_by_legacy_id",
            service.get_portfolio_submission_from_db,
            _portfolio_row,
            "submission",
        ),
        (
            "get_interview_submission_by_legacy_id",
            service.get_interview_submission_from_db,
            _interview_row,
            "answer",
        ),
    ],
)
def test_submission_getters_call_repository_and_normalize(
    monkeypatch,
    repo_name,
    getter,
    row_factory,
    expected_key,
):
    from repositories import submissions_repository

    repo = Mock(return_value=row_factory())
    monkeypatch.setattr(submissions_repository, repo_name, repo)

    conn = object()
    result = getter(conn, session_id="s1", legacy_topic_id="rag-basics")

    repo.assert_called_once_with(conn, session_id="s1", legacy_topic_id="rag-basics")
    assert result[expected_key]


def test_topic_notes_getter_calls_repository_and_normalizes(monkeypatch):
    from repositories import topic_notes_repository

    repo = Mock(return_value=_notes_row(metadata='{"source":"db"}'))
    monkeypatch.setattr(topic_notes_repository, "get_topic_notes_by_legacy_id", repo)

    conn = object()
    result = service.get_topic_notes_from_db(conn, session_id="s1", legacy_topic_id="rag-basics")

    repo.assert_called_once_with(conn, session_id="s1", legacy_topic_id="rag-basics")
    assert result["reflection"] == "I understand it"
    assert result["metadata"] == {"source": "db"}


@pytest.mark.parametrize(
    ("repo_module_name", "repo_name", "getter", "kwargs"),
    [
        (
            "generated_content_repository",
            "get_generated_topic_content_by_legacy_id",
            service.get_generated_topic_content_from_db,
            {},
        ),
        (
            "generated_content_repository",
            "get_generated_topic_practice_by_legacy_id",
            service.get_generated_topic_practice_from_db,
            {"practice_type": "quiz"},
        ),
        ("submissions_repository", "get_quiz_submission_by_legacy_id", service.get_quiz_submission_from_db, {}),
        (
            "submissions_repository",
            "get_portfolio_submission_by_legacy_id",
            service.get_portfolio_submission_from_db,
            {},
        ),
        (
            "submissions_repository",
            "get_interview_submission_by_legacy_id",
            service.get_interview_submission_from_db,
            {},
        ),
        ("topic_notes_repository", "get_topic_notes_by_legacy_id", service.get_topic_notes_from_db, {}),
    ],
)
def test_getters_return_none_when_repository_returns_none(
    monkeypatch,
    repo_module_name,
    repo_name,
    getter,
    kwargs,
):
    repo_module = importlib.import_module(f"repositories.{repo_module_name}")
    monkeypatch.setattr(repo_module, repo_name, Mock(return_value=None))

    result = getter(
        object(),
        session_id="s1",
        legacy_topic_id="rag-basics",
        **kwargs,
    )

    assert result is None


def test_repository_errors_propagate(monkeypatch):
    from repositories import topic_notes_repository

    monkeypatch.setattr(
        topic_notes_repository,
        "get_topic_notes_by_legacy_id",
        Mock(side_effect=RuntimeError("repository failed")),
    )

    with pytest.raises(RuntimeError, match="repository failed"):
        service.get_topic_notes_from_db(object(), session_id="s1", legacy_topic_id="rag-basics")


def test_aggregate_function_calls_all_expected_getters_and_practice_types(monkeypatch):
    calls = []

    def fake_content(conn, *, session_id, legacy_topic_id):
        calls.append(("content", session_id, legacy_topic_id))
        return {"content": "content"}

    def fake_practice(conn, *, session_id, legacy_topic_id, practice_type):
        calls.append(("practice", session_id, legacy_topic_id, practice_type))
        return {"practice_type": practice_type}

    def fake_named(name):
        def _fake(conn, *, session_id, legacy_topic_id):
            calls.append((name, session_id, legacy_topic_id))
            return {name: True}
        return _fake

    monkeypatch.setattr(service, "get_generated_topic_content_from_db", fake_content)
    monkeypatch.setattr(service, "get_generated_topic_practice_from_db", fake_practice)
    monkeypatch.setattr(service, "get_quiz_submission_from_db", fake_named("quiz"))
    monkeypatch.setattr(service, "get_portfolio_submission_from_db", fake_named("portfolio"))
    monkeypatch.setattr(service, "get_interview_submission_from_db", fake_named("interview"))
    monkeypatch.setattr(service, "get_topic_notes_from_db", fake_named("notes"))

    result = service.get_generated_learning_state_from_db(
        object(),
        session_id="s1",
        legacy_topic_id="rag-basics",
    )

    assert result["generated_topic_content"] == {"content": "content"}
    assert result["generated_topic_practice"] == {
        "quiz": {"practice_type": "quiz"},
        "portfolio_task": {"practice_type": "portfolio_task"},
        "interview_practice": {"practice_type": "interview_practice"},
    }
    assert ("practice", "s1", "rag-basics", "quiz") in calls
    assert ("practice", "s1", "rag-basics", "portfolio_task") in calls
    assert ("practice", "s1", "rag-basics", "interview_practice") in calls
    assert ("quiz", "s1", "rag-basics") in calls
    assert ("portfolio", "s1", "rag-basics") in calls
    assert ("interview", "s1", "rag-basics") in calls
    assert ("notes", "s1", "rag-basics") in calls
