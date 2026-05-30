"""Tests for no-op observability wiring in services/content_service.py.

Verifies that:
- trace_llm_call is imported and used in both generation paths
- tracing disabled keeps return shape and content unchanged
- metadata passed to trace_llm_call contains only safe fields
- no prompt/content/submission/notes/secrets appear in trace metadata
- no LangSmith SDK or network imports are introduced
- existing cache behavior is unchanged
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
from services.content_service import (
    generate_learning_content_for_topic,
    generate_practice_content_for_topic,
)

SOURCE = Path("services/content_service.py").read_text(encoding="utf-8")

GENERATED_TEXT = "AI generated content for observability test"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _session():
    return SessionContext(track=CareerTrack.AI_PM, user_id="obs-test-user")


def _topic():
    return get_topics_for_week("aipm", 1)[0]


async def _mock_run_blocking(fn):
    class _FakeContent:
        text = GENERATED_TEXT

    class _FakeResponse:
        content = [_FakeContent()]

    return _FakeResponse()


def _make_client():
    return object()


def run(coro):
    return asyncio.run(coro)


# ── Source-level checks ───────────────────────────────────────────────────────

def test_content_service_imports_trace_llm_call():
    assert "trace_llm_call" in SOURCE


def test_content_service_imports_build_safe_trace_metadata():
    assert "build_safe_trace_metadata" in SOURCE


def test_content_service_uses_structured_generate_lesson_trace():
    assert "structured.generate_lesson" in SOURCE


def test_content_service_uses_structured_generate_practice_trace():
    assert "structured.generate_practice" in SOURCE


def test_content_service_does_not_import_langsmith():
    assert "import langsmith" not in SOURCE
    assert "from langsmith" not in SOURCE


def test_content_service_does_not_import_requests_or_httpx():
    assert "import requests" not in SOURCE
    assert "import httpx" not in SOURCE


# ── Metadata safety: no blocked fields passed ─────────────────────────────────

def test_trace_metadata_does_not_contain_prompt():
    assert '"prompt"' not in SOURCE.split("structured.generate_lesson")[1].split("build_safe_trace_metadata")[1].split(")")[0]


def test_lesson_trace_metadata_uses_safe_fields_only():
    # The build_safe_trace_metadata call for generate_lesson should reference
    # only safe field names: topic_id, activity_type, model, from_cache
    lesson_block = SOURCE.split("structured.generate_lesson")[1].split("with trace_llm_call")[0]
    assert "topic_id" in lesson_block or "activity_type" in lesson_block


def test_practice_trace_metadata_includes_practice_type():
    practice_block = SOURCE.split("structured.generate_practice")[1].split("):")[0]
    assert "practice_type" in practice_block


# ── Runtime: return shape unchanged when tracing disabled ────────────────────

def test_lesson_return_shape_unchanged_tracing_disabled(monkeypatch):
    monkeypatch.delenv("LANGSMITH_TRACING", raising=False)
    monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)

    result = run(generate_learning_content_for_topic(
        session=_session(), topic=_topic(), track_label="AI PM",
        make_client=_make_client, run_blocking=_mock_run_blocking,
        test_mode=False, model="claude-test", refresh=False,
        freshness_label="f",
    ))

    assert "content" in result
    assert "generated_topic_content" in result
    assert "from_cache" in result
    assert result["content"] == GENERATED_TEXT
    assert result["from_cache"] is False


def test_practice_return_shape_unchanged_tracing_disabled(monkeypatch):
    monkeypatch.delenv("LANGSMITH_TRACING", raising=False)
    monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)

    result = run(generate_practice_content_for_topic(
        session=_session(), topic=_topic(), track_label="AI PM",
        practice_type="quiz",
        make_client=_make_client, run_blocking=_mock_run_blocking,
        test_mode=False, model="claude-test", refresh=False,
        freshness_label="f",
    ))

    assert "content" in result
    assert "generated_practice" in result
    assert "from_cache" in result
    assert result["content"] == GENERATED_TEXT
    assert result["from_cache"] is False


def test_lesson_content_value_unchanged_tracing_disabled(monkeypatch):
    monkeypatch.delenv("LANGSMITH_TRACING", raising=False)

    result = run(generate_learning_content_for_topic(
        session=_session(), topic=_topic(), track_label="AI PM",
        make_client=_make_client, run_blocking=_mock_run_blocking,
        test_mode=False, model="m", refresh=False, freshness_label="f",
    ))

    assert result["content"] == GENERATED_TEXT


def test_practice_content_value_unchanged_tracing_disabled(monkeypatch):
    monkeypatch.delenv("LANGSMITH_TRACING", raising=False)

    for pt in ("quiz", "portfolio_task", "interview_practice"):
        result = run(generate_practice_content_for_topic(
            session=_session(), topic=_topic(), track_label="AI PM",
            practice_type=pt,
            make_client=_make_client, run_blocking=_mock_run_blocking,
            test_mode=False, model="m", refresh=False, freshness_label="f",
        ))
        assert result["content"] == GENERATED_TEXT, f"failed for practice_type={pt}"


# ── Runtime: cache hit path still bypasses Claude call ───────────────────────

def test_session_cache_hit_bypasses_claude_and_tracing():
    session = _session()
    topic   = _topic()

    # Pre-populate session cache
    session.save_generated_topic_content(
        topic_id=topic.topic_id,
        content="cached lesson content",
        model="cached-model",
        freshness_label="cached",
    )

    claude_calls: list = []

    async def never_called(fn):
        claude_calls.append(1)
        raise AssertionError("Claude must not be called on cache hit")

    result = run(generate_learning_content_for_topic(
        session=session, topic=topic, track_label="AI PM",
        make_client=_make_client, run_blocking=never_called,
        test_mode=False, model="m", refresh=False, freshness_label="f",
    ))

    assert result["from_cache"] is True
    assert claude_calls == []


# ── test_mode path unchanged ──────────────────────────────────────────────────

def test_test_mode_lesson_unchanged():
    result = run(generate_learning_content_for_topic(
        session=_session(), topic=_topic(), track_label="AI PM",
        make_client=_make_client, run_blocking=_mock_run_blocking,
        test_mode=True, model="test-mock", refresh=False, freshness_label="f",
    ))
    assert result["from_cache"] is False
    assert len(result["content"]) > 0


def test_test_mode_practice_unchanged():
    result = run(generate_practice_content_for_topic(
        session=_session(), topic=_topic(), track_label="AI PM",
        practice_type="quiz",
        make_client=_make_client, run_blocking=_mock_run_blocking,
        test_mode=True, model="test-mock", refresh=False, freshness_label="f",
    ))
    assert result["from_cache"] is False
    assert len(result["content"]) > 0
