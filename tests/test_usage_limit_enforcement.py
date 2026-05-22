"""Tests for usage limit enforcement (AI2_USAGE_LIMITS_ENABLED flag).

Coverage:
- flag off: all generation/evaluation paths behave as before
- flag on + under limit: Claude action allowed
- flag on + over limit: Claude action blocked with 429 and friendly message
- cache hits allowed even when over limit
- practice, quiz, portfolio, interview all blocked when over limit
- cache/shared_cache/test_mode events not counted as expensive AI actions
- no DB connection required
- no route URLs changed
- limit_blocked events recorded on block
"""

import asyncio
import os
from unittest.mock import patch

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
from services.submission_service import (
    evaluate_quiz_answers,
    generate_portfolio_feedback,
    generate_interview_feedback,
)
from services.usage_limit_service import (
    AIActionLimitError,
    DAILY_AI_ACTION_LIMIT,
    LIMIT_MESSAGE,
    count_expensive_ai_actions,
    enforce_ai_action_limit,
    is_expensive_ai_action_allowed,
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


def _base_kwargs(session, topic, *, test_mode=False, refresh=False, limit_enforcer=None):
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
        limit_enforcer=limit_enforcer,
    )


def _submission_kwargs(session, topic, *, test_mode=False, refresh=False, limit_enforcer=None):
    return dict(
        session=session,
        topic=topic,
        track_label="AI Product Manager",
        make_client=lambda: object(),
        run_blocking=_mock_run_blocking,
        test_mode=test_mode,
        model="test-mock",
        refresh=refresh,
        limit_enforcer=limit_enforcer,
    )


def _fill_claude_events(session, topic_id: str, count: int = DAILY_AI_ACTION_LIMIT) -> None:
    """Record `count` claude-source events to push session over the limit."""
    for _ in range(count):
        session.record_usage_event(
            event_type="topic_learning_content",
            topic_id=topic_id,
            model="test-mock",
            source="claude",
            status="success",
            metadata={},
        )


def _always_raise_enforcer():
    """Callable that always raises AIActionLimitError."""
    raise AIActionLimitError()


# ── is_expensive_ai_action_allowed (unit) ─────────────────────────────────────

def test_flag_off_always_allowed():
    sid     = _start_session()
    session = _get_session(sid)
    topic   = _first_topic()
    _fill_claude_events(session, topic.topic_id)

    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("AI2_USAGE_LIMITS_ENABLED", None)
        decision = is_expensive_ai_action_allowed(session)

    assert decision["allowed"] is True
    assert decision["reason"] == "limits_disabled"


def test_flag_on_under_limit_allowed():
    sid     = _start_session()
    session = _get_session(sid)
    topic   = _first_topic()
    _fill_claude_events(session, topic.topic_id, count=5)

    with patch.dict(os.environ, {"AI2_USAGE_LIMITS_ENABLED": "1"}):
        decision = is_expensive_ai_action_allowed(session)

    assert decision["allowed"] is True
    assert decision["reason"] == "allowed"
    assert decision["ai_action_count"] == 5


def test_flag_on_at_limit_blocked():
    sid     = _start_session()
    session = _get_session(sid)
    topic   = _first_topic()
    _fill_claude_events(session, topic.topic_id, count=DAILY_AI_ACTION_LIMIT)

    with patch.dict(os.environ, {"AI2_USAGE_LIMITS_ENABLED": "1"}):
        decision = is_expensive_ai_action_allowed(session)

    assert decision["allowed"] is False
    assert decision["reason"] == "daily_limit_reached"
    assert decision["ai_action_count"] == DAILY_AI_ACTION_LIMIT


# ── count_expensive_ai_actions (unit) ─────────────────────────────────────────

def test_cache_events_not_counted():
    sid     = _start_session()
    session = _get_session(sid)
    topic   = _first_topic()
    for source in ("cache", "shared_cache", "test_mode", "manual"):
        session.record_usage_event(
            event_type="topic_learning_content",
            topic_id=topic.topic_id,
            model="",
            source=source,
            status="success",
            metadata={},
        )
    assert count_expensive_ai_actions(session) == 0


def test_only_claude_source_counted():
    sid     = _start_session()
    session = _get_session(sid)
    topic   = _first_topic()
    session.record_usage_event(
        event_type="topic_learning_content",
        topic_id=topic.topic_id,
        model="test-mock",
        source="claude",
        status="success",
        metadata={},
    )
    assert count_expensive_ai_actions(session) == 1


def test_limit_blocked_events_not_counted():
    sid     = _start_session()
    session = _get_session(sid)
    session.record_usage_event(
        event_type="ai_action_limit_blocked",
        model="",
        source="limit_blocked",
        status="success",
        metadata={},
    )
    assert count_expensive_ai_actions(session) == 0


# ── enforce_ai_action_limit records event + raises ────────────────────────────

def test_enforce_records_limit_blocked_event_then_raises():
    sid     = _start_session()
    session = _get_session(sid)
    topic   = _first_topic()
    _fill_claude_events(session, topic.topic_id)

    with patch.dict(os.environ, {"AI2_USAGE_LIMITS_ENABLED": "1"}):
        try:
            enforce_ai_action_limit(session)
            assert False, "Expected AIActionLimitError"
        except AIActionLimitError:
            pass

    blocked = [e for e in session.usage_events if e.get("source") == "limit_blocked"]
    assert len(blocked) == 1
    assert blocked[0]["event_type"] == "ai_action_limit_blocked"


def test_enforce_noop_when_flag_off():
    sid     = _start_session()
    session = _get_session(sid)
    topic   = _first_topic()
    _fill_claude_events(session, topic.topic_id)

    os.environ.pop("AI2_USAGE_LIMITS_ENABLED", None)
    enforce_ai_action_limit(session)  # must not raise


# ── Service-level: base lesson generation ────────────────────────────────────

def test_flag_off_content_generation_runs_normally():
    sid     = _start_session()
    session = _get_session(sid)
    topic   = _first_topic()
    _fill_claude_events(session, topic.topic_id)

    result = run(generate_learning_content_for_topic(
        **_base_kwargs(session, topic)
    ))
    assert result["content"]


def test_flag_on_under_limit_content_allowed():
    sid     = _start_session()
    session = _get_session(sid)
    topic   = _first_topic()
    _fill_claude_events(session, topic.topic_id, count=3)

    with patch.dict(os.environ, {"AI2_USAGE_LIMITS_ENABLED": "1"}):
        from services.usage_limit_service import enforce_ai_action_limit as enf
        enforcer = lambda: enf(session)
        result = run(generate_learning_content_for_topic(
            **_base_kwargs(session, topic, limit_enforcer=enforcer)
        ))

    assert result["content"]


def test_flag_on_over_limit_content_blocked():
    sid     = _start_session()
    session = _get_session(sid)
    topic   = _first_topic()
    _fill_claude_events(session, topic.topic_id)

    with patch.dict(os.environ, {"AI2_USAGE_LIMITS_ENABLED": "1"}):
        from services.usage_limit_service import enforce_ai_action_limit as enf
        enforcer = lambda: enf(session)
        try:
            run(generate_learning_content_for_topic(
                **_base_kwargs(session, topic, limit_enforcer=enforcer)
            ))
            assert False, "Expected AIActionLimitError"
        except AIActionLimitError as exc:
            assert LIMIT_MESSAGE in exc.user_message


def test_over_limit_does_not_call_claude():
    sid     = _start_session()
    session = _get_session(sid)
    topic   = _first_topic()
    _fill_claude_events(session, topic.topic_id)
    claude_called = []

    async def _tracking_run_blocking(fn):
        claude_called.append(True)
        class _Resp:
            content = [type("C", (), {"text": "text"})()]
        return _Resp()

    freshness = classify_topic_freshness(topic.topic_title, topic.description)
    try:
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
            limit_enforcer=_always_raise_enforcer,
        ))
    except AIActionLimitError:
        pass

    assert not claude_called, "Claude must not be called when limit is enforced"


def test_session_cache_hit_allowed_when_over_limit():
    """Session-cached content must be returned even when over limit (enforcer not called)."""
    sid     = _start_session()
    session = _get_session(sid)
    topic   = _first_topic()

    # Warm session cache with test_mode
    run(generate_learning_content_for_topic(**_base_kwargs(session, topic, test_mode=True)))
    _fill_claude_events(session, topic.topic_id)

    result = run(generate_learning_content_for_topic(
        **_base_kwargs(session, topic, refresh=False, limit_enforcer=_always_raise_enforcer)
    ))
    assert result["from_cache"] is True
    assert result["content"]


def test_shared_cache_hit_allowed_when_over_limit():
    """Shared cache hit must be returned even when the enforcer would block Claude."""
    sid     = _start_session()
    session = _get_session(sid)
    topic   = _first_topic()
    _fill_claude_events(session, topic.topic_id)
    cached_row = {"content": "cached lesson", "model": "cached-model", "status": "active"}

    result = run(generate_learning_content_for_topic(
        **_base_kwargs(session, topic,
                       limit_enforcer=_always_raise_enforcer),
        shared_cache_read=lambda: cached_row,
    ))
    assert result["content"] == "cached lesson"
    assert result["from_cache"] is True


def test_cache_miss_over_limit_blocked_before_claude():
    """No cached content + over limit → blocked before Claude call."""
    sid     = _start_session()
    session = _get_session(sid)
    topic   = _first_topic()
    _fill_claude_events(session, topic.topic_id)

    try:
        run(generate_learning_content_for_topic(
            **_base_kwargs(session, topic,
                           limit_enforcer=_always_raise_enforcer),
            shared_cache_read=lambda: None,
        ))
        assert False, "Expected AIActionLimitError"
    except AIActionLimitError:
        pass


# ── Service-level: practice generation ───────────────────────────────────────

def test_practice_generation_blocked_when_over_limit():
    sid     = _start_session()
    session = _get_session(sid)
    topic   = _first_topic()
    freshness = classify_topic_freshness(topic.topic_title, topic.description)

    try:
        run(generate_practice_content_for_topic(
            session=session,
            topic=topic,
            track_label="AI Product Manager",
            make_client=lambda: object(),
            run_blocking=_mock_run_blocking,
            test_mode=False,
            model="test-mock",
            refresh=False,
            freshness_label=freshness,
            practice_type="quiz",
            limit_enforcer=_always_raise_enforcer,
        ))
        assert False, "Expected AIActionLimitError"
    except AIActionLimitError:
        pass


# ── Service-level: quiz, portfolio, interview ─────────────────────────────────

def test_quiz_evaluation_blocked_when_over_limit():
    sid     = _start_session()
    session = _get_session(sid)
    topic   = _first_topic()
    session.save_quiz_answers(topic.topic_id, "My quiz answers")

    try:
        run(evaluate_quiz_answers(
            **_submission_kwargs(session, topic, test_mode=False,
                                 limit_enforcer=_always_raise_enforcer)
        ))
        assert False, "Expected AIActionLimitError"
    except AIActionLimitError:
        pass


def test_portfolio_feedback_blocked_when_over_limit():
    sid     = _start_session()
    session = _get_session(sid)
    topic   = _first_topic()
    session.save_portfolio_submission(topic.topic_id, "My portfolio work")

    try:
        run(generate_portfolio_feedback(
            **_submission_kwargs(session, topic, test_mode=False,
                                 limit_enforcer=_always_raise_enforcer)
        ))
        assert False, "Expected AIActionLimitError"
    except AIActionLimitError:
        pass


def test_interview_feedback_blocked_when_over_limit():
    sid     = _start_session()
    session = _get_session(sid)
    topic   = _first_topic()
    session.save_interview_answer(topic.topic_id, "My interview answer")

    try:
        run(generate_interview_feedback(
            **_submission_kwargs(session, topic, test_mode=False,
                                 limit_enforcer=_always_raise_enforcer)
        ))
        assert False, "Expected AIActionLimitError"
    except AIActionLimitError:
        pass


# ── test_mode bypasses enforcer ───────────────────────────────────────────────

def test_test_mode_content_not_blocked():
    """In test_mode the mock path runs before the enforcer is reached."""
    sid     = _start_session()
    session = _get_session(sid)
    topic   = _first_topic()

    result = run(generate_learning_content_for_topic(
        **_base_kwargs(session, topic, test_mode=True,
                       limit_enforcer=_always_raise_enforcer)
    ))
    assert result["content"]
    assert result["from_cache"] is False


def test_test_mode_practice_not_blocked():
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
        limit_enforcer=_always_raise_enforcer,
    ))
    assert result["content"]


# ── HTTP route tests ──────────────────────────────────────────────────────────

def test_route_content_generate_returns_429_when_over_limit():
    from unittest.mock import patch as _patch
    with patch.dict(os.environ, {"AI2_USAGE_LIMITS_ENABLED": "1"}):
        with _patch("routes.topics.TEST_MODE", False):
            sid     = _start_session()
            session = _get_session(sid)
            topic   = _first_topic()
            _fill_claude_events(session, topic.topic_id)

            resp = client.post(
                "/topic/content/generate",
                json={"session_id": sid, "topic_id": topic.topic_id},
            )

    assert resp.status_code == 429
    assert LIMIT_MESSAGE in resp.json()["detail"]


def test_route_practice_generate_returns_429_when_over_limit():
    from unittest.mock import patch as _patch
    with patch.dict(os.environ, {"AI2_USAGE_LIMITS_ENABLED": "1"}):
        with _patch("routes.topics.TEST_MODE", False):
            sid     = _start_session()
            session = _get_session(sid)
            topic   = _first_topic()
            _fill_claude_events(session, topic.topic_id)

            resp = client.post(
                "/topic/practice/generate",
                json={"session_id": sid, "topic_id": topic.topic_id, "practice_type": "quiz"},
            )

    assert resp.status_code == 429


def test_route_quiz_evaluate_returns_429_when_over_limit():
    from unittest.mock import patch as _patch
    with patch.dict(os.environ, {"AI2_USAGE_LIMITS_ENABLED": "1"}):
        with _patch("routes.submissions.TEST_MODE", False):
            sid     = _start_session()
            session = _get_session(sid)
            topic   = _first_topic()
            client.post("/quiz/submit",
                        json={"session_id": sid, "topic_id": topic.topic_id,
                              "answers": "My answers"})
            _fill_claude_events(session, topic.topic_id)

            resp = client.post(
                "/quiz/evaluate",
                json={"session_id": sid, "topic_id": topic.topic_id},
            )

    assert resp.status_code == 429


def test_route_portfolio_feedback_returns_429_when_over_limit():
    from unittest.mock import patch as _patch
    with patch.dict(os.environ, {"AI2_USAGE_LIMITS_ENABLED": "1"}):
        with _patch("routes.submissions.TEST_MODE", False):
            sid     = _start_session()
            session = _get_session(sid)
            topic   = _first_topic()
            client.post("/portfolio/submit",
                        json={"session_id": sid, "topic_id": topic.topic_id,
                              "submission": "My work"})
            _fill_claude_events(session, topic.topic_id)

            resp = client.post(
                "/portfolio/feedback",
                json={"session_id": sid, "topic_id": topic.topic_id},
            )

    assert resp.status_code == 429


def test_route_interview_feedback_returns_429_when_over_limit():
    from unittest.mock import patch as _patch
    with patch.dict(os.environ, {"AI2_USAGE_LIMITS_ENABLED": "1"}):
        with _patch("routes.submissions.TEST_MODE", False):
            sid     = _start_session()
            session = _get_session(sid)
            topic   = _first_topic()
            client.post("/interview/submit",
                        json={"session_id": sid, "topic_id": topic.topic_id,
                              "answer": "My answer"})
            _fill_claude_events(session, topic.topic_id)

            resp = client.post(
                "/interview/feedback",
                json={"session_id": sid, "topic_id": topic.topic_id},
            )

    assert resp.status_code == 429


def test_response_detail_contains_friendly_message():
    from unittest.mock import patch as _patch
    with patch.dict(os.environ, {"AI2_USAGE_LIMITS_ENABLED": "1"}):
        with _patch("routes.topics.TEST_MODE", False):
            sid     = _start_session()
            session = _get_session(sid)
            topic   = _first_topic()
            _fill_claude_events(session, topic.topic_id)

            resp = client.post(
                "/topic/content/generate",
                json={"session_id": sid, "topic_id": topic.topic_id},
            )

    assert resp.status_code == 429
    detail = resp.json()["detail"]
    assert "free AI practice limit" in detail
    assert "review saved lessons" in detail


def test_response_detail_contains_no_internal_policy_info():
    from unittest.mock import patch as _patch
    with patch.dict(os.environ, {"AI2_USAGE_LIMITS_ENABLED": "1"}):
        with _patch("routes.topics.TEST_MODE", False):
            sid     = _start_session()
            session = _get_session(sid)
            topic   = _first_topic()
            _fill_claude_events(session, topic.topic_id)

            resp = client.post(
                "/topic/content/generate",
                json={"session_id": sid, "topic_id": topic.topic_id},
            )

    assert resp.status_code == 429
    detail = resp.json()["detail"]
    for internal_word in ("daily_limit_reached", "DAILY_AI_ACTION_LIMIT", "ai_action_count", "daily_limit"):
        assert internal_word not in detail, f"internal policy key '{internal_word}' leaked into response"


def test_flag_off_route_returns_200_not_blocked():
    os.environ.pop("AI2_USAGE_LIMITS_ENABLED", None)
    sid     = _start_session()
    session = _get_session(sid)
    topic   = _first_topic()
    _fill_claude_events(session, topic.topic_id)

    resp = client.post(
        "/topic/content/generate",
        json={"session_id": sid, "topic_id": topic.topic_id},
    )
    # test_mode is on globally so this will return 200 with mock content
    assert resp.status_code == 200


def test_route_urls_unchanged():
    urls = [
        "/topic/content/generate",
        "/topic/practice/generate",
        "/quiz/evaluate",
        "/portfolio/feedback",
        "/interview/feedback",
    ]
    for url in urls:
        # Just ensure the app has a route for each URL (405 = exists, 422 = exists)
        resp = client.post(url, json={})
        assert resp.status_code not in (404,), f"route {url} missing"


def test_no_db_connection_required_for_limit_check():
    """Limit enforcement works purely from session.usage_events — no DB needed."""
    sid     = _start_session()
    session = _get_session(sid)
    topic   = _first_topic()
    _fill_claude_events(session, topic.topic_id)

    with patch.dict(os.environ, {"AI2_USAGE_LIMITS_ENABLED": "1"}):
        # Patch get_conn to raise — must still return a limit decision
        with patch("database.pool.get_conn", side_effect=RuntimeError("no DB")):
            decision = is_expensive_ai_action_allowed(session)

    assert decision["allowed"] is False
