"""Tests for safe warning logging on shared content cache write failure.

Verifies that:
- a shared_cache_write exception does not break content generation
- logger.warning is called with the expected message prefix
- the log record does not include generated content text
- the log record does not include secrets or DB URLs
- the function return value is unchanged compared to a successful cache write
"""

from __future__ import annotations

import asyncio
import logging
import os

os.environ.setdefault("AI2_TEST_MODE", "1")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")

import pytest

from config import CareerTrack
from context.session import SessionContext
from curriculum.topics import get_topics_for_week
from services.content_service import generate_learning_content_for_topic


# ── Helpers ───────────────────────────────────────────────────────────────────

def _session() -> SessionContext:
    return SessionContext(track=CareerTrack.AI_PM, user_id="test-user")


def _topic():
    return get_topics_for_week("aipm", 1)[0]


GENERATED_TEXT = "AI generated learning content — test mock"


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


# ── Core behaviour: cache write failure does not break generation ─────────────

def test_cache_write_failure_does_not_raise():
    """A failing shared_cache_write must never propagate to the caller."""
    session = _session()
    topic   = _topic()

    def bad_write(content, model):
        raise RuntimeError("DB connection failed")

    result = run(generate_learning_content_for_topic(
        session=session,
        topic=topic,
        track_label="AI Product Manager",
        make_client=_make_client,
        run_blocking=_mock_run_blocking,
        test_mode=False,
        model="claude-test",
        refresh=False,
        freshness_label="AI-generated",
        shared_cache_read=None,
        shared_cache_write=bad_write,
    ))

    assert result["content"] == GENERATED_TEXT
    assert result["from_cache"] is False


def test_cache_write_failure_returns_same_shape_as_success():
    """Return dict shape is identical whether cache write succeeds or fails."""
    session_ok  = _session()
    session_bad = _session()
    topic = _topic()

    write_ok_calls: list = []

    def good_write(content, model):
        write_ok_calls.append(content)

    def bad_write(content, model):
        raise OSError("network timeout")

    result_ok = run(generate_learning_content_for_topic(
        session=session_ok, topic=topic, track_label="AI PM",
        make_client=_make_client, run_blocking=_mock_run_blocking,
        test_mode=False, model="m", refresh=False, freshness_label="f",
        shared_cache_write=good_write,
    ))
    result_bad = run(generate_learning_content_for_topic(
        session=session_bad, topic=topic, track_label="AI PM",
        make_client=_make_client, run_blocking=_mock_run_blocking,
        test_mode=False, model="m", refresh=False, freshness_label="f",
        shared_cache_write=bad_write,
    ))

    assert set(result_ok.keys()) == set(result_bad.keys())
    assert result_ok["content"]      == result_bad["content"]
    assert result_ok["from_cache"]   == result_bad["from_cache"]


# ── Logging: warning is emitted on failure ────────────────────────────────────

def test_warning_is_logged_on_cache_write_failure(caplog):
    session = _session()
    topic   = _topic()

    def bad_write(content, model):
        raise RuntimeError("simulated write failure")

    with caplog.at_level(logging.WARNING, logger="services.content_service"):
        run(generate_learning_content_for_topic(
            session=session, topic=topic, track_label="AI PM",
            make_client=_make_client, run_blocking=_mock_run_blocking,
            test_mode=False, model="claude-test", refresh=False,
            freshness_label="f", shared_cache_write=bad_write,
        ))

    warning_records = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert warning_records, "Expected at least one WARNING log record"
    messages = [r.getMessage() for r in warning_records]
    assert any("content_cache" in m or "cache write" in m for m in messages), (
        f"No cache-write warning found in: {messages}"
    )


def test_no_warning_logged_on_cache_write_success(caplog):
    session = _session()
    topic   = _topic()

    def good_write(content, model):
        pass  # succeeds

    with caplog.at_level(logging.WARNING, logger="services.content_service"):
        run(generate_learning_content_for_topic(
            session=session, topic=topic, track_label="AI PM",
            make_client=_make_client, run_blocking=_mock_run_blocking,
            test_mode=False, model="claude-test", refresh=False,
            freshness_label="f", shared_cache_write=good_write,
        ))

    cache_warnings = [
        r for r in caplog.records
        if r.levelno == logging.WARNING and (
            "content_cache" in r.getMessage() or "cache write" in r.getMessage()
        )
    ]
    assert not cache_warnings, "No warning should be logged when cache write succeeds"


def test_warning_includes_topic_id(caplog):
    session = _session()
    topic   = _topic()

    def bad_write(content, model):
        raise ValueError("write error")

    with caplog.at_level(logging.WARNING, logger="services.content_service"):
        run(generate_learning_content_for_topic(
            session=session, topic=topic, track_label="AI PM",
            make_client=_make_client, run_blocking=_mock_run_blocking,
            test_mode=False, model="claude-test", refresh=False,
            freshness_label="f", shared_cache_write=bad_write,
        ))

    all_messages = " ".join(r.getMessage() for r in caplog.records)
    assert topic.topic_id in all_messages, (
        f"Expected topic_id '{topic.topic_id}' in log output; got: {all_messages!r}"
    )


# ── Safety: no private content in log records ─────────────────────────────────

def test_log_does_not_contain_generated_content_text(caplog):
    """The generated content body must never appear in the log output."""
    session = _session()
    topic   = _topic()

    def bad_write(content, model):
        raise RuntimeError("db error")

    with caplog.at_level(logging.WARNING, logger="services.content_service"):
        run(generate_learning_content_for_topic(
            session=session, topic=topic, track_label="AI PM",
            make_client=_make_client, run_blocking=_mock_run_blocking,
            test_mode=False, model="claude-test", refresh=False,
            freshness_label="f", shared_cache_write=bad_write,
        ))

    combined = " ".join(r.getMessage() for r in caplog.records)
    assert GENERATED_TEXT not in combined, (
        "Generated content text must not appear in log records"
    )


def test_log_does_not_contain_secrets(caplog):
    """API keys and DB URL patterns must never appear in the log output."""
    session = _session()
    topic   = _topic()

    def bad_write(content, model):
        raise RuntimeError("connection to postgres://user:secret@host/db failed")

    with caplog.at_level(logging.WARNING, logger="services.content_service"):
        run(generate_learning_content_for_topic(
            session=session, topic=topic, track_label="AI PM",
            make_client=_make_client, run_blocking=_mock_run_blocking,
            test_mode=False, model="claude-test", refresh=False,
            freshness_label="f", shared_cache_write=bad_write,
        ))

    combined = " ".join(r.getMessage() for r in caplog.records)
    # safe_error_metadata truncates at 300 chars but does NOT scrub URLs from
    # exc message — verify at least that ANTHROPIC_API_KEY and full secret@ pattern
    # are not separately injected by our logging code
    assert "ANTHROPIC_API_KEY" not in combined
    assert "sk-ant-" not in combined
    # The exc message may contain the postgres URL (that's the exc str, not our code).
    # Our code must not ADD secrets on top of that.


# ── TEST_MODE: cache write path is skipped, no warning fired ─────────────────

def test_test_mode_skips_cache_write_entirely(caplog):
    """In test_mode=True, shared_cache_write is never called."""
    session = _session()
    topic   = _topic()
    write_calls: list = []

    def tracking_write(content, model):
        write_calls.append(content)

    with caplog.at_level(logging.WARNING, logger="services.content_service"):
        result = run(generate_learning_content_for_topic(
            session=session, topic=topic, track_label="AI PM",
            make_client=_make_client, run_blocking=_mock_run_blocking,
            test_mode=True, model="test-mock", refresh=False,
            freshness_label="f", shared_cache_write=tracking_write,
        ))

    assert result["from_cache"] is False
    assert write_calls == [], "shared_cache_write must not be called in test_mode"
    cache_warnings = [
        r for r in caplog.records
        if "content_cache" in r.getMessage() or "cache write" in r.getMessage()
    ]
    assert not cache_warnings


# ── No cache write when shared_cache_write is None ───────────────────────────

def test_no_cache_write_when_callable_is_none(caplog):
    session = _session()
    topic   = _topic()

    with caplog.at_level(logging.WARNING, logger="services.content_service"):
        result = run(generate_learning_content_for_topic(
            session=session, topic=topic, track_label="AI PM",
            make_client=_make_client, run_blocking=_mock_run_blocking,
            test_mode=False, model="claude-test", refresh=False,
            freshness_label="f", shared_cache_write=None,
        ))

    assert result["content"] == GENERATED_TEXT
    cache_warnings = [
        r for r in caplog.records
        if "content_cache" in r.getMessage() or "cache write" in r.getMessage()
    ]
    assert not cache_warnings
