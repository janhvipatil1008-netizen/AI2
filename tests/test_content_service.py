"""Unit tests for services/content_service.py.

Calls service functions directly (not via HTTP) to verify business logic in isolation.
All tests run without a Claude API key — TEST_MODE paths use mock content; production
paths use a mock run_blocking that returns a fake response.
"""

import asyncio
import os

os.environ["AI2_TEST_MODE"] = "1"
os.environ["ANTHROPIC_API_KEY"] = "test-key"

from fastapi.testclient import TestClient

from app import app, _sessions
from curriculum.freshness import classify_topic_freshness
from curriculum.topics import get_topics_for_week
from services.content_service import (
    generate_learning_content_for_topic,
    generate_practice_content_for_topic,
)

client = TestClient(app)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _start_session(track: str = "aipm", week: int = 1) -> str:
    r = client.post("/session/start", json={"track": track, "week": week})
    assert r.status_code == 200, r.text
    return r.json()["session_id"]


def _get_session(sid: str):
    return _sessions[sid]["session"]


def _first_topic(track: str = "aipm", week: int = 1):
    return get_topics_for_week(track, week)[0]


def run(coro):
    return asyncio.run(coro)


async def _mock_run_blocking(fn):
    """Simulates _run_blocking for production-path tests without a real Claude call."""
    class _FakeContent:
        text = "AI generated content — production mock"

    class _FakeResponse:
        content = [_FakeContent()]

    return _FakeResponse()


def _make_kwargs(session, topic, *, test_mode=True, refresh=False):
    freshness = classify_topic_freshness(topic.topic_title, topic.description)
    return dict(
        session=session,
        topic=topic,
        track_label="AI Product Manager",
        make_client=lambda: object(),
        run_blocking=_mock_run_blocking,
        test_mode=test_mode,
        model="test-mock",
        refresh=refresh,
        freshness_label=freshness,
    )


def _practice_kwargs(session, topic, practice_type, *, test_mode=True, refresh=False):
    return {**_make_kwargs(session, topic, test_mode=test_mode, refresh=refresh), "practice_type": practice_type}


# ── generate_learning_content_for_topic ───────────────────────────────────────

def test_learning_content_testmode_returns_content():
    sid     = _start_session()
    session = _get_session(sid)
    topic   = _first_topic()

    result = run(generate_learning_content_for_topic(**_make_kwargs(session, topic)))

    assert result["content"]
    assert "from_cache" in result
    assert result["from_cache"] is False
    assert result["generated_topic_content"]["content"] == result["content"]


def test_learning_content_testmode_includes_topic_title():
    sid     = _start_session()
    session = _get_session(sid)
    topic   = _first_topic()

    result = run(generate_learning_content_for_topic(**_make_kwargs(session, topic)))

    assert topic.topic_title in result["content"]


def test_learning_content_testmode_marks_learn_in_progress():
    sid     = _start_session()
    session = _get_session(sid)
    topic   = _first_topic()

    assert session.get_topic_progress(topic.topic_id).get("learn") == "not_started"

    run(generate_learning_content_for_topic(**_make_kwargs(session, topic)))

    assert session.get_topic_progress(topic.topic_id).get("learn") == "in_progress"


def test_learning_content_does_not_overwrite_done_step():
    sid     = _start_session()
    session = _get_session(sid)
    topic   = _first_topic()
    session.mark_topic_step(topic.topic_id, "learn", "done")

    run(generate_learning_content_for_topic(**_make_kwargs(session, topic)))

    assert session.get_topic_progress(topic.topic_id).get("learn") == "done"


def test_learning_content_cached_on_second_call():
    sid     = _start_session()
    session = _get_session(sid)
    topic   = _first_topic()

    r1 = run(generate_learning_content_for_topic(**_make_kwargs(session, topic)))
    r2 = run(generate_learning_content_for_topic(**_make_kwargs(session, topic, refresh=False)))

    assert r2["from_cache"] is True
    assert r2["content"] == r1["content"]
    assert r2["generated_topic_content"]["version"] == 1


def test_learning_content_refresh_increments_version():
    sid     = _start_session()
    session = _get_session(sid)
    topic   = _first_topic()

    run(generate_learning_content_for_topic(**_make_kwargs(session, topic)))
    r2 = run(generate_learning_content_for_topic(**_make_kwargs(session, topic, refresh=True)))

    assert r2["from_cache"] is False
    assert r2["generated_topic_content"]["version"] == 2


def test_learning_content_production_path_calls_run_blocking():
    sid     = _start_session()
    session = _get_session(sid)
    topic   = _first_topic()

    result = run(generate_learning_content_for_topic(
        **_make_kwargs(session, topic, test_mode=False, refresh=True)
    ))

    assert result["from_cache"] is False
    assert "AI generated content" in result["content"]


# ── generate_practice_content_for_topic — quiz ────────────────────────────────

def test_practice_quiz_testmode_returns_content():
    sid     = _start_session()
    session = _get_session(sid)
    topic   = _first_topic()

    result = run(generate_practice_content_for_topic(**_practice_kwargs(session, topic, "quiz")))

    assert result["content"]
    assert result["from_cache"] is False
    assert "Quiz" in result["content"]


def test_practice_quiz_marks_step_in_progress():
    sid     = _start_session()
    session = _get_session(sid)
    topic   = _first_topic()

    assert session.get_topic_progress(topic.topic_id).get("quiz") == "not_started"

    run(generate_practice_content_for_topic(**_practice_kwargs(session, topic, "quiz")))

    assert session.get_topic_progress(topic.topic_id).get("quiz") == "in_progress"


def test_practice_quiz_cached_on_second_call():
    sid     = _start_session()
    session = _get_session(sid)
    topic   = _first_topic()

    r1 = run(generate_practice_content_for_topic(**_practice_kwargs(session, topic, "quiz")))
    r2 = run(generate_practice_content_for_topic(**_practice_kwargs(session, topic, "quiz", refresh=False)))

    assert r2["from_cache"] is True
    assert r2["content"] == r1["content"]
    assert r2["generated_practice"]["version"] == 1


def test_practice_quiz_refresh_increments_version():
    sid     = _start_session()
    session = _get_session(sid)
    topic   = _first_topic()

    run(generate_practice_content_for_topic(**_practice_kwargs(session, topic, "quiz")))
    r2 = run(generate_practice_content_for_topic(**_practice_kwargs(session, topic, "quiz", refresh=True)))

    assert r2["from_cache"] is False
    assert r2["generated_practice"]["version"] == 2


# ── generate_practice_content_for_topic — portfolio_task ──────────────────────

def test_practice_portfolio_testmode_returns_content():
    sid     = _start_session()
    session = _get_session(sid)
    topic   = _first_topic()

    result = run(generate_practice_content_for_topic(**_practice_kwargs(session, topic, "portfolio_task")))

    assert result["content"]
    assert result["from_cache"] is False
    assert "Portfolio Task" in result["content"]


def test_practice_portfolio_marks_step_in_progress():
    sid     = _start_session()
    session = _get_session(sid)
    topic   = _first_topic()

    run(generate_practice_content_for_topic(**_practice_kwargs(session, topic, "portfolio_task")))

    assert session.get_topic_progress(topic.topic_id).get("portfolio_task") == "in_progress"


# ── generate_practice_content_for_topic — interview_practice ──────────────────

def test_practice_interview_testmode_returns_content():
    sid     = _start_session()
    session = _get_session(sid)
    topic   = _first_topic()

    result = run(generate_practice_content_for_topic(**_practice_kwargs(session, topic, "interview_practice")))

    assert result["content"]
    assert result["from_cache"] is False
    assert "Interview Practice" in result["content"]


def test_practice_interview_marks_step_in_progress():
    sid     = _start_session()
    session = _get_session(sid)
    topic   = _first_topic()

    run(generate_practice_content_for_topic(**_practice_kwargs(session, topic, "interview_practice")))

    assert session.get_topic_progress(topic.topic_id).get("interview_practice") == "in_progress"


# ── Production path for practice ──────────────────────────────────────────────

def test_practice_production_path_calls_run_blocking():
    sid     = _start_session()
    session = _get_session(sid)
    topic   = _first_topic()

    result = run(generate_practice_content_for_topic(
        **_practice_kwargs(session, topic, "quiz", test_mode=False, refresh=True)
    ))

    assert result["from_cache"] is False
    assert "AI generated content" in result["content"]


# ── Practice types are independent per topic ──────────────────────────────────

def test_practice_types_stored_independently():
    sid     = _start_session()
    session = _get_session(sid)
    topic   = _first_topic()

    r_quiz  = run(generate_practice_content_for_topic(**_practice_kwargs(session, topic, "quiz")))
    r_port  = run(generate_practice_content_for_topic(**_practice_kwargs(session, topic, "portfolio_task")))
    r_inter = run(generate_practice_content_for_topic(**_practice_kwargs(session, topic, "interview_practice")))

    assert "Quiz" in r_quiz["content"]
    assert "Portfolio Task" in r_port["content"]
    assert "Interview Practice" in r_inter["content"]

    # Each is independently cached
    r2 = run(generate_practice_content_for_topic(**_practice_kwargs(session, topic, "quiz", refresh=False)))
    assert r2["from_cache"] is True
