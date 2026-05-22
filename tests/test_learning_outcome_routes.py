"""Tests for simple learning outcome routes.

These tests use patched repository/DB dependencies and do not require a real DB.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

os.environ["AI2_TEST_MODE"] = "1"
os.environ["ANTHROPIC_API_KEY"] = "test-key"

from fastapi import HTTPException
from fastapi.testclient import TestClient

from app import app
from curriculum.topics import get_topics_for_week


client = TestClient(app)

TOPIC_ID = get_topics_for_week("aipm", 1)[0].topic_id
PRIVATE_BASELINE = "private baseline answer should not be returned"
PRIVATE_POST = "private post answer should not be returned"
SECRET_URL = "postgresql://user:secret@host/db"


def _session(user_id: str = "user-1"):
    return SimpleNamespace(
        track=SimpleNamespace(value="aipm"),
        user_id=user_id,
    )


def _session_data(session=None):
    return {"session": session or _session(), "orch": None, "client": None, "profile": None}


class _ReusableConnContext:
    def __init__(self, conn=None):
        self.conn = conn or MagicMock()

    def __enter__(self):
        return self.conn

    def __exit__(self, *args):
        return False


def _ctx_conn(conn=None):
    return _ReusableConnContext(conn)


def _baseline_body(**overrides):
    body = {
        "session_id": "sess-1",
        "topic_id": TOPIC_ID,
        "baseline_answer": PRIVATE_BASELINE,
        "baseline_score": 4,
    }
    body.update(overrides)
    return body


def _post_body(**overrides):
    body = {
        "session_id": "sess-1",
        "topic_id": TOPIC_ID,
        "post_answer": PRIVATE_POST,
        "post_score": 8,
    }
    body.update(overrides)
    return body


def _outcome(**overrides):
    outcome = {
        "baseline_answer": PRIVATE_BASELINE,
        "baseline_score": 4,
        "post_answer": PRIVATE_POST,
        "post_score": 8,
        "improvement_delta": 4,
        "status": "improved",
    }
    outcome.update(overrides)
    return outcome


def _patch_success(outcome=None):
    patches = [
        patch("routes.topics.deps.get_session_data", return_value=_session_data()),
        patch("database.pool.get_conn", return_value=_ctx_conn()),
        patch("repositories.learning_outcomes_repository.upsert_baseline_outcome"),
        patch("repositories.learning_outcomes_repository.upsert_post_outcome"),
        patch(
            "repositories.learning_outcomes_repository.get_learning_outcome",
            return_value=outcome if outcome is not None else _outcome(),
        ),
    ]
    return patches


def test_baseline_endpoint_exists():
    with _patch_success()[0], _patch_success()[1], _patch_success()[2], _patch_success()[4]:
        response = client.post("/topic/outcome/baseline", json=_baseline_body())

    assert response.status_code == 200


def test_post_endpoint_exists():
    with _patch_success()[0], _patch_success()[1], _patch_success()[3], _patch_success()[4]:
        response = client.post("/topic/outcome/post", json=_post_body())

    assert response.status_code == 200


def test_summary_endpoint_exists():
    with _patch_success()[0], _patch_success()[1], _patch_success()[4]:
        response = client.get(f"/topic/outcome/sess-1/{TOPIC_ID}")

    assert response.status_code == 200


def test_baseline_save_calls_repository_with_session_user_and_topic():
    session = _session(user_id="owner-1")
    upsert = MagicMock()
    with patch("routes.topics.deps.get_session_data", return_value=_session_data(session)), patch(
        "database.pool.get_conn", return_value=_ctx_conn()
    ), patch(
        "repositories.learning_outcomes_repository.upsert_baseline_outcome", upsert
    ), patch(
        "repositories.learning_outcomes_repository.get_learning_outcome", return_value=_outcome()
    ):
        response = client.post("/topic/outcome/baseline", json=_baseline_body())

    assert response.status_code == 200
    upsert.assert_called_once()
    kwargs = upsert.call_args.kwargs
    assert kwargs["user_id"] == "owner-1"
    assert kwargs["session_id"] == "sess-1"
    assert kwargs["legacy_topic_id"] == TOPIC_ID
    assert kwargs["baseline_answer"] == PRIVATE_BASELINE
    assert kwargs["baseline_score"] == 4


def test_post_save_calls_repository_with_session_user_and_topic():
    session = _session(user_id="owner-1")
    upsert = MagicMock()
    with patch("routes.topics.deps.get_session_data", return_value=_session_data(session)), patch(
        "database.pool.get_conn", return_value=_ctx_conn()
    ), patch(
        "repositories.learning_outcomes_repository.upsert_post_outcome", upsert
    ), patch(
        "repositories.learning_outcomes_repository.get_learning_outcome", return_value=_outcome()
    ):
        response = client.post("/topic/outcome/post", json=_post_body())

    assert response.status_code == 200
    upsert.assert_called_once()
    kwargs = upsert.call_args.kwargs
    assert kwargs["user_id"] == "owner-1"
    assert kwargs["session_id"] == "sess-1"
    assert kwargs["legacy_topic_id"] == TOPIC_ID
    assert kwargs["post_answer"] == PRIVATE_POST
    assert kwargs["post_score"] == 8


def test_score_zero_to_ten_accepted():
    upsert = MagicMock()
    with patch("routes.topics.deps.get_session_data", return_value=_session_data()), patch(
        "database.pool.get_conn", return_value=_ctx_conn()
    ), patch(
        "repositories.learning_outcomes_repository.upsert_baseline_outcome", upsert
    ), patch(
        "repositories.learning_outcomes_repository.get_learning_outcome", return_value=_outcome(baseline_score=0)
    ):
        r0 = client.post("/topic/outcome/baseline", json=_baseline_body(baseline_score=0))
        r10 = client.post("/topic/outcome/baseline", json=_baseline_body(baseline_score=10))

    assert r0.status_code == 200
    assert r10.status_code == 200
    assert upsert.call_args_list[0].kwargs["baseline_score"] == 0
    assert upsert.call_args_list[1].kwargs["baseline_score"] == 10


def test_missing_score_is_accepted_as_none():
    upsert = MagicMock()
    body = _baseline_body()
    body.pop("baseline_score")
    with patch("routes.topics.deps.get_session_data", return_value=_session_data()), patch(
        "database.pool.get_conn", return_value=_ctx_conn()
    ), patch(
        "repositories.learning_outcomes_repository.upsert_baseline_outcome", upsert
    ), patch(
        "repositories.learning_outcomes_repository.get_learning_outcome", return_value=_outcome(baseline_score=None)
    ):
        response = client.post("/topic/outcome/baseline", json=body)

    assert response.status_code == 200
    assert upsert.call_args.kwargs["baseline_score"] is None


def test_invalid_score_handled_safely():
    with patch("routes.topics.deps.get_session_data", return_value=_session_data()):
        response = client.post("/topic/outcome/baseline", json=_baseline_body(baseline_score=11))

    assert response.status_code == 422
    assert "between 0 and 10" in response.text


def test_post_outcome_returns_improvement_summary():
    with patch("routes.topics.deps.get_session_data", return_value=_session_data()), patch(
        "database.pool.get_conn", return_value=_ctx_conn()
    ), patch(
        "repositories.learning_outcomes_repository.upsert_post_outcome"
    ), patch(
        "repositories.learning_outcomes_repository.get_learning_outcome", return_value=_outcome()
    ):
        data = client.post("/topic/outcome/post", json=_post_body()).json()

    assert data["summary"] == {
        "has_baseline": True,
        "has_post": True,
        "baseline_score": 4,
        "post_score": 8,
        "improvement_delta": 4,
        "status": "improved",
    }


def test_summary_excludes_full_baseline_and_post_answers():
    with patch("routes.topics.deps.get_session_data", return_value=_session_data()), patch(
        "database.pool.get_conn", return_value=_ctx_conn()
    ), patch(
        "repositories.learning_outcomes_repository.get_learning_outcome", return_value=_outcome()
    ):
        response = client.get(f"/topic/outcome/sess-1/{TOPIC_ID}")

    assert response.status_code == 200
    assert PRIVATE_BASELINE not in response.text
    assert PRIVATE_POST not in response.text
    assert "baseline_answer" not in response.text
    assert "post_answer" not in response.text


def test_empty_summary_when_no_outcome_exists():
    with patch("routes.topics.deps.get_session_data", return_value=_session_data()), patch(
        "database.pool.get_conn", return_value=_ctx_conn()
    ), patch(
        "repositories.learning_outcomes_repository.get_learning_outcome", return_value=None
    ):
        data = client.get(f"/topic/outcome/sess-1/{TOPIC_ID}").json()

    assert data["summary"]["has_baseline"] is False
    assert data["summary"]["has_post"] is False
    assert data["summary"]["status"] is None


def test_db_save_error_returns_friendly_safe_response():
    with patch("routes.topics.deps.get_session_data", return_value=_session_data()), patch(
        "database.pool.get_conn", side_effect=RuntimeError(f"connect failed {SECRET_URL} ANTHROPIC_API_KEY=sk-secret")
    ):
        response = client.post("/topic/outcome/baseline", json=_baseline_body())

    assert response.status_code == 503
    assert response.json()["detail"] == "Learning outcome save failed. Please try again."
    assert "postgresql://" not in response.text
    assert "sk-secret" not in response.text
    assert "ANTHROPIC_API_KEY" not in response.text


def test_db_error_does_not_expose_db_url_or_secrets_in_summary():
    with patch("routes.topics.deps.get_session_data", return_value=_session_data()), patch(
        "database.pool.get_conn", side_effect=RuntimeError(f"connect failed {SECRET_URL} DATABASE_URL=secret")
    ):
        response = client.get(f"/topic/outcome/sess-1/{TOPIC_ID}")

    assert response.status_code == 503
    assert response.json()["detail"] == "Learning outcome summary unavailable. Please try again."
    assert "postgresql://" not in response.text
    assert "DATABASE_URL" not in response.text


def test_ownership_session_loading_helper_is_used():
    loader = MagicMock(return_value=_session_data())
    with patch("routes.topics.deps.get_session_data", loader), patch(
        "database.pool.get_conn", return_value=_ctx_conn()
    ), patch(
        "repositories.learning_outcomes_repository.upsert_baseline_outcome"
    ), patch(
        "repositories.learning_outcomes_repository.get_learning_outcome", return_value=_outcome()
    ):
        response = client.post("/topic/outcome/baseline", json=_baseline_body())

    assert response.status_code == 200
    loader.assert_called_once_with("sess-1", "")


def test_no_cross_user_bypass_when_loader_rejects():
    with patch(
        "routes.topics.deps.get_session_data",
        side_effect=HTTPException(status_code=403, detail="Access denied."),
    ):
        response = client.post("/topic/outcome/baseline", json=_baseline_body())

    assert response.status_code == 403
    assert "Access denied" in response.text


def test_no_claude_call_is_made():
    with patch("routes.topics.deps.get_session_data", return_value=_session_data()), patch(
        "database.pool.get_conn", return_value=_ctx_conn()
    ), patch(
        "repositories.learning_outcomes_repository.upsert_baseline_outcome"
    ), patch(
        "repositories.learning_outcomes_repository.get_learning_outcome", return_value=_outcome()
    ), patch(
        "routes.topics.deps.make_client", side_effect=AssertionError("Claude must not be called")
    ) as make_client:
        response = client.post("/topic/outcome/baseline", json=_baseline_body())

    assert response.status_code == 200
    make_client.assert_not_called()


def test_no_usage_limit_enforcement_is_triggered():
    with patch("routes.topics.deps.get_session_data", return_value=_session_data()), patch(
        "database.pool.get_conn", return_value=_ctx_conn()
    ), patch(
        "repositories.learning_outcomes_repository.upsert_post_outcome"
    ), patch(
        "repositories.learning_outcomes_repository.get_learning_outcome", return_value=_outcome()
    ), patch(
        "routes.topics.deps.build_limit_enforcer", side_effect=AssertionError("usage limits not part of outcome flow")
    ) as build_limit:
        response = client.post("/topic/outcome/post", json=_post_body())

    assert response.status_code == 200
    build_limit.assert_not_called()


def test_existing_topic_content_generation_still_works():
    response = client.post("/session/start", json={"track": "aipm", "week": 1})
    assert response.status_code == 200, response.text
    session_id = response.json()["session_id"]

    response = client.post("/topic/content/generate", json={
        "session_id": session_id,
        "topic_id": TOPIC_ID,
        "refresh": False,
    })

    assert response.status_code == 200
    assert response.json()["topic_id"] == TOPIC_ID
    assert "content" in response.json()


def test_route_urls_for_existing_pages_unchanged():
    paths = {route.path for route in app.routes}
    assert {
        "/topics/{session_id}",
        "/topic/{session_id}/{topic_id}",
        "/topic/content/generate",
        "/topic/practice/generate",
        "/topic/outcome/baseline",
        "/topic/outcome/post",
        "/topic/outcome/{session_id}/{topic_id}",
    }.issubset(paths)
