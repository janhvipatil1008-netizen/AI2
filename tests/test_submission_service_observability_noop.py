"""Tests for no-op observability wiring in services/submission_service.py.

Verifies that:
- trace_llm_call is imported and used in all three feedback paths
- tracing disabled keeps return shapes and content unchanged
- metadata contains only safe fields (topic_id, activity_type, model, from_cache)
- no answers/submissions/feedback_text/prompt/notes appear in trace metadata
- no LangSmith SDK or network imports are introduced
- existing feedback behavior is unchanged under test_mode
- cache-hit paths are unchanged
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

os.environ.setdefault("AI2_TEST_MODE", "1")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")

from config import CareerTrack
from context.session import SessionContext
from curriculum.topics import get_topics_for_week
from services.submission_service import (
    evaluate_quiz_answers,
    generate_interview_feedback,
    generate_portfolio_feedback,
    submit_interview_answer,
    submit_portfolio_work,
    submit_quiz_answers,
)

SOURCE = Path("services/submission_service.py").read_text(encoding="utf-8")

MOCK_FEEDBACK = "Overall Score: 8/10\n\nMock feedback text."


# ── Helpers ───────────────────────────────────────────────────────────────────

def _session():
    return SessionContext(track=CareerTrack.AI_PM, user_id="obs-sub-user")


def _topic():
    return get_topics_for_week("aipm", 1)[0]


async def _mock_run_blocking(fn):
    class _FakeContent:
        text = MOCK_FEEDBACK

    class _FakeResponse:
        content = [_FakeContent()]

    return _FakeResponse()


def _make_client():
    return object()


def run(coro):
    return asyncio.run(coro)


# ── Source-level checks ───────────────────────────────────────────────────────

def test_submission_service_imports_trace_llm_call():
    assert "trace_llm_call" in SOURCE


def test_submission_service_imports_build_safe_trace_metadata():
    assert "build_safe_trace_metadata" in SOURCE


def test_submission_service_uses_quiz_feedback_trace():
    assert "structured.quiz_feedback" in SOURCE


def test_submission_service_uses_portfolio_feedback_trace():
    assert "structured.portfolio_feedback" in SOURCE


def test_submission_service_uses_interview_feedback_trace():
    assert "structured.interview_feedback" in SOURCE


def test_submission_service_does_not_import_langsmith():
    assert "import langsmith" not in SOURCE
    assert "from langsmith" not in SOURCE


def test_submission_service_does_not_import_requests_or_httpx():
    assert "import requests" not in SOURCE
    assert "import httpx" not in SOURCE


# ── Metadata safety: blocked fields not in trace_llm_call calls ──────────────

def test_quiz_trace_metadata_does_not_pass_answers():
    quiz_block = SOURCE.split("structured.quiz_feedback")[1].split("):")[0]
    assert "answers" not in quiz_block
    assert "evaluation_text" not in quiz_block


def test_portfolio_trace_metadata_does_not_pass_submission():
    portfolio_block = SOURCE.split("structured.portfolio_feedback")[1].split("):")[0]
    assert "submission" not in portfolio_block
    assert "feedback_text" not in portfolio_block


def test_interview_trace_metadata_does_not_pass_answer():
    interview_block = SOURCE.split("structured.interview_feedback")[1].split("):")[0]
    assert "answer" not in interview_block
    assert "feedback_text" not in interview_block


def test_trace_metadata_does_not_pass_prompt():
    for trace_name in ("structured.quiz_feedback", "structured.portfolio_feedback", "structured.interview_feedback"):
        block = SOURCE.split(trace_name)[1].split("):")[0]
        assert "prompt" not in block, f"prompt found in {trace_name} metadata block"


# ── Runtime: quiz feedback return shape unchanged ─────────────────────────────

def test_quiz_feedback_return_shape_unchanged(monkeypatch):
    monkeypatch.delenv("LANGSMITH_TRACING", raising=False)
    monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)

    session = _session()
    topic   = _topic()
    submit_quiz_answers(session=session, topic=topic, answers="Q1: A, Q2: B")

    result = run(evaluate_quiz_answers(
        session=session, topic=topic, track_label="AI PM",
        make_client=_make_client, run_blocking=_mock_run_blocking,
        test_mode=False, model="claude-test",
    ))

    assert "quiz_submission" in result
    assert "topic_progress" in result
    assert "from_cache" in result
    assert result["from_cache"] is False


def test_quiz_feedback_test_mode_unchanged():
    session = _session()
    topic   = _topic()
    submit_quiz_answers(session=session, topic=topic, answers="Q1: A")

    result = run(evaluate_quiz_answers(
        session=session, topic=topic, track_label="AI PM",
        make_client=_make_client, run_blocking=_mock_run_blocking,
        test_mode=True, model="test-mock",
    ))

    assert result["from_cache"] is False
    assert result["quiz_submission"]["evaluation"]


# ── Runtime: portfolio feedback return shape unchanged ────────────────────────

def test_portfolio_feedback_return_shape_unchanged(monkeypatch):
    monkeypatch.delenv("LANGSMITH_TRACING", raising=False)
    monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)

    session = _session()
    topic   = _topic()
    submit_portfolio_work(session=session, topic=topic, submission="My portfolio work")

    result = run(generate_portfolio_feedback(
        session=session, topic=topic, track_label="AI PM",
        make_client=_make_client, run_blocking=_mock_run_blocking,
        test_mode=False, model="claude-test",
    ))

    assert "portfolio_submission" in result
    assert "topic_progress" in result
    assert "from_cache" in result
    assert result["from_cache"] is False


def test_portfolio_feedback_test_mode_unchanged():
    session = _session()
    topic   = _topic()
    submit_portfolio_work(session=session, topic=topic, submission="My work")

    result = run(generate_portfolio_feedback(
        session=session, topic=topic, track_label="AI PM",
        make_client=_make_client, run_blocking=_mock_run_blocking,
        test_mode=True, model="test-mock",
    ))

    assert result["from_cache"] is False
    assert result["portfolio_submission"]["feedback"]


# ── Runtime: interview feedback return shape unchanged ────────────────────────

def test_interview_feedback_return_shape_unchanged(monkeypatch):
    monkeypatch.delenv("LANGSMITH_TRACING", raising=False)
    monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)

    session = _session()
    topic   = _topic()
    submit_interview_answer(session=session, topic=topic, answer="My answer")

    result = run(generate_interview_feedback(
        session=session, topic=topic, track_label="AI PM",
        make_client=_make_client, run_blocking=_mock_run_blocking,
        test_mode=False, model="claude-test",
    ))

    assert "interview_submission" in result
    assert "topic_progress" in result
    assert "from_cache" in result
    assert result["from_cache"] is False


def test_interview_feedback_test_mode_unchanged():
    session = _session()
    topic   = _topic()
    submit_interview_answer(session=session, topic=topic, answer="My answer")

    result = run(generate_interview_feedback(
        session=session, topic=topic, track_label="AI PM",
        make_client=_make_client, run_blocking=_mock_run_blocking,
        test_mode=True, model="test-mock",
    ))

    assert result["from_cache"] is False
    assert result["interview_submission"]["feedback"]


# ── Cache-hit paths bypass Claude and tracing ─────────────────────────────────

def test_quiz_cache_hit_bypasses_claude(monkeypatch):
    monkeypatch.delenv("LANGSMITH_TRACING", raising=False)
    session = _session()
    topic   = _topic()

    submit_quiz_answers(session=session, topic=topic, answers="Q1: A")
    # Populate evaluation cache
    run(evaluate_quiz_answers(
        session=session, topic=topic, track_label="AI PM",
        make_client=_make_client, run_blocking=_mock_run_blocking,
        test_mode=True, model="test-mock",
    ))

    claude_calls: list = []

    async def never_called(fn):
        claude_calls.append(1)
        raise AssertionError("Claude must not be called on cache hit")

    result = run(evaluate_quiz_answers(
        session=session, topic=topic, track_label="AI PM",
        make_client=_make_client, run_blocking=never_called,
        test_mode=False, model="m", refresh=False,
    ))

    assert result["from_cache"] is True
    assert claude_calls == []
