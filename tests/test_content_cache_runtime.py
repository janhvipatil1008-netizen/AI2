"""Runtime tests for shared content cache wiring in content_service.py.

Verifies that:
- cache hit returns cached content and avoids Claude call
- cache hit updates SessionContext and records source='shared_cache'
- cache miss calls Claude and saves generated content to cache
- cache read/write failures are handled safely (never break user flow)
- session-level cache, refresh=True, test_mode=True all bypass shared cache
- practice generation is not affected by shared cache parameters
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


# ── Helpers ───────────────────────────────────────────────────────────────────

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
    class _FakeContent:
        text = "AI generated content — production mock"

    class _FakeResponse:
        content = [_FakeContent()]

    return _FakeResponse()


def _make_kwargs(session, topic, *, test_mode=False, refresh=False,
                 shared_cache_read=None, shared_cache_write=None):
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
        shared_cache_read=shared_cache_read,
        shared_cache_write=shared_cache_write,
    )


def _cached_row(content="Cached lesson content from shared cache"):
    return {
        "cache_key":  "track:aipm|topic:test|type:base_lesson|level:beginner|lang:en|version:v1",
        "content":    content,
        "model":      "claude-test-cached",
        "status":     "active",
    }


# ── Cache hit ─────────────────────────────────────────────────────────────────

def test_cache_hit_returns_cached_content():
    sid     = _start_session()
    session = _get_session(sid)
    topic   = _first_topic()
    row     = _cached_row()

    result = run(generate_learning_content_for_topic(
        **_make_kwargs(session, topic, shared_cache_read=lambda: row)
    ))

    assert result["content"] == row["content"]


def test_cache_hit_returns_from_cache_true():
    sid     = _start_session()
    session = _get_session(sid)
    topic   = _first_topic()

    result = run(generate_learning_content_for_topic(
        **_make_kwargs(session, topic, shared_cache_read=lambda: _cached_row())
    ))

    assert result["from_cache"] is True


def test_cache_hit_avoids_claude_call():
    sid     = _start_session()
    session = _get_session(sid)
    topic   = _first_topic()
    claude_called = []

    async def _failing_run_blocking(fn):
        claude_called.append(True)
        raise RuntimeError("Claude must not be called on cache hit")

    freshness = classify_topic_freshness(topic.topic_title, topic.description)
    result = run(generate_learning_content_for_topic(
        session=session,
        topic=topic,
        track_label="AI Product Manager",
        make_client=lambda: object(),
        run_blocking=_failing_run_blocking,
        test_mode=False,
        model="test-mock",
        refresh=False,
        freshness_label=freshness,
        shared_cache_read=lambda: _cached_row(),
        shared_cache_write=None,
    ))

    assert not claude_called
    assert result["content"] == _cached_row()["content"]


def test_cache_hit_updates_session_generated_content():
    sid     = _start_session()
    session = _get_session(sid)
    topic   = _first_topic()
    row     = _cached_row("Specific cached text for session check")

    run(generate_learning_content_for_topic(
        **_make_kwargs(session, topic, shared_cache_read=lambda: row)
    ))

    stored = session.get_generated_topic_content(topic.topic_id)
    assert stored["content"] == "Specific cached text for session check"


def test_cache_hit_records_shared_cache_source():
    sid     = _start_session()
    session = _get_session(sid)
    topic   = _first_topic()

    run(generate_learning_content_for_topic(
        **_make_kwargs(session, topic, shared_cache_read=lambda: _cached_row())
    ))

    learn_events = [e for e in session.usage_events if e.get("event_type") == "topic_learning_content"]
    assert learn_events
    assert learn_events[-1]["source"] == "shared_cache"


def test_cache_hit_sets_learn_step_in_progress():
    sid     = _start_session()
    session = _get_session(sid)
    topic   = _first_topic()

    assert session.get_topic_progress(topic.topic_id).get("learn") == "not_started"

    run(generate_learning_content_for_topic(
        **_make_kwargs(session, topic, shared_cache_read=lambda: _cached_row())
    ))

    assert session.get_topic_progress(topic.topic_id).get("learn") == "in_progress"


# ── Cache miss ────────────────────────────────────────────────────────────────

def test_cache_miss_calls_claude():
    sid     = _start_session()
    session = _get_session(sid)
    topic   = _first_topic()
    claude_called = []

    async def _tracking_run_blocking(fn):
        claude_called.append(True)
        class _FakeContent:
            text = "AI generated content — production mock"
        class _FakeResponse:
            content = [_FakeContent()]
        return _FakeResponse()

    freshness = classify_topic_freshness(topic.topic_title, topic.description)
    run(generate_learning_content_for_topic(
        session=session,
        topic=topic,
        track_label="AI Product Manager",
        make_client=lambda: object(),
        run_blocking=_tracking_run_blocking,
        test_mode=False,
        model="test-mock",
        refresh=False,
        freshness_label=freshness,
        shared_cache_read=lambda: None,
        shared_cache_write=None,
    ))

    assert claude_called


def test_cache_miss_saves_generated_content_to_cache():
    sid     = _start_session()
    session = _get_session(sid)
    topic   = _first_topic()
    write_calls = []

    def _mock_write(content, model=None):
        write_calls.append((content, model))

    result = run(generate_learning_content_for_topic(
        **_make_kwargs(session, topic,
                       shared_cache_read=lambda: None,
                       shared_cache_write=_mock_write)
    ))

    assert write_calls, "shared_cache_write should have been called after Claude generation"
    saved_content, saved_model = write_calls[0]
    assert saved_content == result["content"]
    assert saved_model == "test-mock"


def test_cache_miss_returns_from_cache_false():
    sid     = _start_session()
    session = _get_session(sid)
    topic   = _first_topic()

    result = run(generate_learning_content_for_topic(
        **_make_kwargs(session, topic, shared_cache_read=lambda: None)
    ))

    assert result["from_cache"] is False


# ── Failure safety ────────────────────────────────────────────────────────────

def test_cache_read_failure_falls_back_to_claude():
    sid     = _start_session()
    session = _get_session(sid)
    topic   = _first_topic()

    def _failing_read():
        raise RuntimeError("DB connection failed")

    result = run(generate_learning_content_for_topic(
        **_make_kwargs(session, topic, shared_cache_read=_failing_read)
    ))

    assert result["content"]
    assert "AI generated content" in result["content"]
    assert result["from_cache"] is False


def test_cache_write_failure_does_not_break_response():
    sid     = _start_session()
    session = _get_session(sid)
    topic   = _first_topic()

    def _failing_write(content, model=None):
        raise RuntimeError("DB write failed")

    result = run(generate_learning_content_for_topic(
        **_make_kwargs(session, topic,
                       shared_cache_read=lambda: None,
                       shared_cache_write=_failing_write)
    ))

    assert result["content"]
    assert result["from_cache"] is False


# ── Bypass conditions ─────────────────────────────────────────────────────────

def test_session_cache_hit_skips_shared_cache_read():
    """If the session already has content and refresh=False, shared_cache_read is never called."""
    sid     = _start_session()
    session = _get_session(sid)
    topic   = _first_topic()

    # Pre-populate session cache via test_mode (no shared_cache_read needed)
    run(generate_learning_content_for_topic(
        **_make_kwargs(session, topic, test_mode=True)
    ))

    shared_cache_called = []

    def _tracking_read():
        shared_cache_called.append(True)
        return None

    result = run(generate_learning_content_for_topic(
        **_make_kwargs(session, topic, refresh=False, shared_cache_read=_tracking_read)
    ))

    assert not shared_cache_called, "shared_cache_read must not be called when session cache is warm"
    assert result["from_cache"] is True


def test_refresh_true_bypasses_shared_cache_read():
    sid     = _start_session()
    session = _get_session(sid)
    topic   = _first_topic()
    shared_cache_called = []

    def _tracking_read():
        shared_cache_called.append(True)
        return _cached_row("should not be used")

    result = run(generate_learning_content_for_topic(
        **_make_kwargs(session, topic, refresh=True, shared_cache_read=_tracking_read)
    ))

    assert not shared_cache_called, "shared_cache_read must not be called when refresh=True"
    assert result["from_cache"] is False


def test_test_mode_bypasses_shared_cache_read():
    sid     = _start_session()
    session = _get_session(sid)
    topic   = _first_topic()
    shared_cache_called = []

    def _tracking_read():
        shared_cache_called.append(True)
        return None

    result = run(generate_learning_content_for_topic(
        **_make_kwargs(session, topic, test_mode=True, shared_cache_read=_tracking_read)
    ))

    assert not shared_cache_called, "shared_cache_read must not be called in test_mode"
    assert result["from_cache"] is False


def test_no_cache_read_fn_calls_claude_directly():
    sid     = _start_session()
    session = _get_session(sid)
    topic   = _first_topic()

    result = run(generate_learning_content_for_topic(
        **_make_kwargs(session, topic, shared_cache_read=None)
    ))

    assert result["content"]
    assert result["from_cache"] is False


def test_no_cache_write_fn_still_returns_content():
    sid     = _start_session()
    session = _get_session(sid)
    topic   = _first_topic()

    result = run(generate_learning_content_for_topic(
        **_make_kwargs(session, topic,
                       shared_cache_read=lambda: None,
                       shared_cache_write=None)
    ))

    assert result["content"]


# ── Practice generation is NOT cached ────────────────────────────────────────

def test_practice_generation_has_no_shared_cache_params():
    import inspect
    sig = inspect.signature(generate_practice_content_for_topic)
    assert "shared_cache_read"  not in sig.parameters
    assert "shared_cache_write" not in sig.parameters


def test_practice_generation_runs_normally_after_cache_wiring():
    """Ensure practice generation still works correctly after the lesson cache wiring."""
    sid     = _start_session()
    session = _get_session(sid)
    topic   = _first_topic()
    freshness = classify_topic_freshness(topic.topic_title, topic.description)

    result = run(generate_practice_content_for_topic(
        session=session,
        topic=topic,
        track_label="AI Product Manager",
        make_client=lambda: object(),
        run_blocking=_mock_run_blocking,
        test_mode=True,
        model="test-mock",
        refresh=False,
        freshness_label=freshness,
        practice_type="quiz",
    ))

    assert result["content"]
    assert "Quiz" in result["content"]
    assert result["from_cache"] is False
