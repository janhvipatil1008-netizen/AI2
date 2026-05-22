"""Tests for private beta feedback schema, helpers, repository, and route."""

from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

os.environ["AI2_TEST_MODE"] = "1"
os.environ["ANTHROPIC_API_KEY"] = "test-key"

from fastapi import HTTPException
from fastapi.testclient import TestClient

from app import app
from curriculum.topics import get_topics_for_week


client = TestClient(app)

SCHEMA_PATH = Path(__file__).parent.parent / "database" / "schema.sql"
REPO_PATH = Path(__file__).parent.parent / "repositories" / "beta_feedback_repository.py"
SERVICE_PATH = Path(__file__).parent.parent / "services" / "beta_feedback_service.py"
TOPIC_ID = get_topics_for_week("aipm", 1)[0].topic_id
SECRET_URL = "postgresql://user:secret@host/db ANTHROPIC_API_KEY=sk-secret"


def _sql() -> str:
    return SCHEMA_PATH.read_text(encoding="utf-8")


def _compact(text: str) -> str:
    return " ".join(text.split())


def _session(user_id: str = "user-1"):
    return SimpleNamespace(track=SimpleNamespace(value="aipm"), user_id=user_id)


def _session_data(session=None):
    return {"session": session or _session(), "orch": None, "client": None, "profile": None}


class FakeCursor:
    def __init__(self):
        self.executed: list[tuple[str, tuple]] = []

    def execute(self, sql: str, params: tuple = ()) -> None:
        self.executed.append((sql.strip(), params))

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


class FakeConn:
    def __init__(self):
        self.cursor_obj = FakeCursor()
        self.committed = False
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


class ReusableConnContext:
    def __init__(self, conn=None):
        self.conn = conn or FakeConn()

    def __enter__(self):
        return self.conn

    def __exit__(self, *args):
        return False


def _body(**overrides):
    body = {
        "session_id": "sess-1",
        "legacy_topic_id": TOPIC_ID,
        "feedback_context": "quiz_feedback",
        "usefulness_score": 5,
        "clarity_score": 4,
        "confusion": "I was confused by the rubric.",
        "improvement_suggestion": "Add one clearer example.",
        "willingness_to_pay": "Maybe after the free trial.",
    }
    body.update(overrides)
    return body


def test_schema_table_exists():
    sql = _sql()
    assert "CREATE TABLE IF NOT EXISTS beta_feedback" in sql
    for column in (
        "user_id",
        "session_id",
        "legacy_topic_id",
        "feedback_context",
        "usefulness_score",
        "clarity_score",
        "confusion",
        "improvement_suggestion",
        "willingness_to_pay",
        "metadata",
        "created_at",
    ):
        assert column in sql


def test_schema_indexes_exist():
    sql = _sql()
    for idx in (
        "idx_beta_feedback_user_id",
        "idx_beta_feedback_session_id",
        "idx_beta_feedback_legacy_topic",
        "idx_beta_feedback_context",
        "idx_beta_feedback_created_at",
    ):
        assert idx in sql


def test_repository_inserts_parameterized_sql():
    from repositories.beta_feedback_repository import insert_beta_feedback

    injection = "nice'); DROP TABLE beta_feedback; --"
    conn = FakeConn()

    insert_beta_feedback(
        conn,
        user_id="u1",
        session_id="s1",
        legacy_topic_id="topic-1",
        feedback_context="quiz_feedback",
        usefulness_score=5,
        clarity_score=4,
        confusion=injection,
        improvement_suggestion="more examples",
        willingness_to_pay="yes",
        metadata={"source": "test"},
    )

    sql, params = conn.executed[-1]
    assert "INSERT INTO beta_feedback" in sql
    assert "%s" in sql
    assert injection not in sql
    assert injection in params


def test_repository_has_no_connection_or_transaction_management():
    src = REPO_PATH.read_text(encoding="utf-8")
    assert "database.pool" not in src
    assert "get_conn(" not in src
    assert ".commit(" not in src
    assert ".rollback(" not in src
    assert "os.environ" not in src
    assert "os.getenv" not in src


def test_service_validates_scores_one_to_five():
    from services.beta_feedback_service import validate_score

    assert validate_score(1) == 1
    assert validate_score("5") == 5
    assert validate_score("") is None
    assert validate_score(None) is None


def test_service_invalid_scores_raise_value_error():
    from services.beta_feedback_service import validate_score

    for score in (0, 6, "bad"):
        try:
            validate_score(score)
        except ValueError as exc:
            assert "between 1 and 5" in str(exc)
        else:
            raise AssertionError(f"invalid score accepted: {score!r}")


def test_context_normalization_works():
    from services.beta_feedback_service import normalize_feedback_context

    assert normalize_feedback_context(" quiz_feedback ") == "quiz_feedback"
    assert normalize_feedback_context("portfolio_feedback") == "portfolio_feedback"
    assert normalize_feedback_context("unknown-context") == "general"


def test_long_text_is_truncated_and_sanitized():
    from services.beta_feedback_service import sanitize_feedback_text

    result = sanitize_feedback_text("  hello\x00" + ("x" * 20), max_length=10)

    assert result == "helloxxxxx"
    assert sanitize_feedback_text("   ") is None


def test_service_has_no_env_reads_or_db_imports():
    src = SERVICE_PATH.read_text(encoding="utf-8")
    assert "os.environ" not in src
    assert "os.getenv" not in src
    assert "database.pool" not in src
    assert "get_conn(" not in src


def test_post_feedback_accepts_valid_json():
    insert = MagicMock()
    with patch("routes.submissions.deps.get_session_data", return_value=_session_data()), patch(
        "database.pool.get_conn", return_value=ReusableConnContext()
    ), patch("repositories.beta_feedback_repository.insert_beta_feedback", insert):
        response = client.post("/feedback/beta", json=_body())

    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["feedback_context"] == "quiz_feedback"
    insert.assert_called_once()
    kwargs = insert.call_args.kwargs
    assert kwargs["session_id"] == "sess-1"
    assert kwargs["user_id"] == "user-1"
    assert kwargs["legacy_topic_id"] == TOPIC_ID
    assert kwargs["usefulness_score"] == 5
    assert kwargs["clarity_score"] == 4


def test_post_feedback_accepts_valid_form_data():
    insert = MagicMock()
    form = _body(
        redirect_to=f"/topic/sess-1/{TOPIC_ID}#ai-quiz",
        usefulness_score="5",
        clarity_score="4",
    )
    with patch("routes.submissions.deps.get_session_data", return_value=_session_data()), patch(
        "database.pool.get_conn", return_value=ReusableConnContext()
    ), patch("repositories.beta_feedback_repository.insert_beta_feedback", insert):
        response = client.post("/feedback/beta", data=form, follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == f"/topic/sess-1/{TOPIC_ID}#ai-quiz"
    insert.assert_called_once()


def test_invalid_score_returns_friendly_error():
    with patch("routes.submissions.deps.get_session_data", return_value=_session_data()):
        response = client.post("/feedback/beta", json=_body(usefulness_score=6))

    assert response.status_code == 422
    assert "between 1 and 5" in response.text


def test_db_error_returns_safe_response():
    with patch("routes.submissions.deps.get_session_data", return_value=_session_data()), patch(
        "database.pool.get_conn", side_effect=RuntimeError(SECRET_URL)
    ):
        response = client.post("/feedback/beta", json=_body())

    assert response.status_code == 503
    assert response.json()["detail"] == "Feedback save failed. Please try again."
    assert "postgresql://" not in response.text
    assert "sk-secret" not in response.text
    assert "ANTHROPIC_API_KEY" not in response.text


def test_session_ownership_helper_is_used():
    loader = MagicMock(return_value=_session_data())
    with patch("routes.submissions.deps.get_session_data", loader), patch(
        "database.pool.get_conn", return_value=ReusableConnContext()
    ), patch("repositories.beta_feedback_repository.insert_beta_feedback"):
        response = client.post("/feedback/beta", json=_body())

    assert response.status_code == 200
    loader.assert_called_once_with("sess-1", "")


def test_no_cross_user_bypass_when_loader_rejects():
    with patch(
        "routes.submissions.deps.get_session_data",
        side_effect=HTTPException(status_code=403, detail="Access denied."),
    ):
        response = client.post("/feedback/beta", json=_body())

    assert response.status_code == 403
    assert "Access denied" in response.text


def test_no_claude_call_is_made():
    with patch("routes.submissions.deps.get_session_data", return_value=_session_data()), patch(
        "database.pool.get_conn", return_value=ReusableConnContext()
    ), patch("repositories.beta_feedback_repository.insert_beta_feedback"), patch(
        "routes.submissions.deps.make_client", side_effect=AssertionError("Claude must not be called")
    ) as make_client:
        response = client.post("/feedback/beta", json=_body())

    assert response.status_code == 200
    make_client.assert_not_called()


def test_no_usage_limit_enforcement_is_triggered():
    with patch("routes.submissions.deps.get_session_data", return_value=_session_data()), patch(
        "database.pool.get_conn", return_value=ReusableConnContext()
    ), patch("repositories.beta_feedback_repository.insert_beta_feedback"), patch(
        "routes.submissions.deps.build_limit_enforcer",
        side_effect=AssertionError("usage limits should not run"),
    ) as build_limit:
        response = client.post("/feedback/beta", json=_body())

    assert response.status_code == 200
    build_limit.assert_not_called()


def test_feedback_form_renders_after_quiz_portfolio_and_interview_feedback():
    session_id = client.post("/session/start", json={"track": "aipm", "week": 1}).json()["session_id"]
    topic = get_topics_for_week("aipm", 1)[0]

    client.post("/quiz/submit", json={
        "session_id": session_id,
        "topic_id": topic.topic_id,
        "answers": "Q1: B",
    })
    client.post("/quiz/evaluate", json={"session_id": session_id, "topic_id": topic.topic_id})
    client.post("/portfolio/submit", json={
        "session_id": session_id,
        "topic_id": topic.topic_id,
        "submission": "portfolio work",
    })
    client.post("/portfolio/feedback", json={"session_id": session_id, "topic_id": topic.topic_id})
    client.post("/interview/submit", json={
        "session_id": session_id,
        "topic_id": topic.topic_id,
        "answer": "interview answer",
    })
    client.post("/interview/feedback", json={"session_id": session_id, "topic_id": topic.topic_id})

    response = client.get(f"/topic/{session_id}/{topic.topic_id}")

    assert response.status_code == 200
    assert response.text.count('action="/feedback/beta"') >= 3
    assert 'value="quiz_feedback"' in response.text
    assert 'value="portfolio_feedback"' in response.text
    assert 'value="interview_feedback"' in response.text
