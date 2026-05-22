import asyncio
import logging
import uuid

import pytest

from config import CareerTrack
from context.session import SessionContext
from curriculum.freshness import classify_topic_freshness
from curriculum.topics import get_topics_for_week
from services.content_service import (
    generate_learning_content_for_topic,
    generate_practice_content_for_topic,
)
from services.submission_service import (
    SubmissionGenerationError,
    evaluate_quiz_answers,
    generate_portfolio_feedback,
    submit_portfolio_work,
    submit_quiz_answers,
)


def run(coro):
    return asyncio.run(coro)


def _session():
    return SessionContext(track=CareerTrack.AI_PM)


def _topic():
    return get_topics_for_week("aipm", 1)[0]


def _freshness(topic):
    return classify_topic_freshness(topic.topic_title, topic.description)


def _content_kwargs(session, topic, *, test_mode=True, refresh=False):
    return {
        "session": session,
        "topic": topic,
        "track_label": "AI Product Manager",
        "make_client": lambda: object(),
        "run_blocking": _unused_run_blocking,
        "test_mode": test_mode,
        "model": "test-model",
        "refresh": refresh,
        "freshness_label": _freshness(topic),
    }


def _practice_kwargs(session, topic, practice_type, *, test_mode=True, refresh=False):
    return {
        **_content_kwargs(session, topic, test_mode=test_mode, refresh=refresh),
        "practice_type": practice_type,
    }


def _submission_kwargs(session, topic, *, test_mode=True, refresh=False):
    return {
        "session": session,
        "topic": topic,
        "track_label": "AI Product Manager",
        "make_client": _unused_client,
        "run_blocking": _unused_run_blocking,
        "test_mode": test_mode,
        "model": "test-model",
        "refresh": refresh,
    }


def _unused_client():
    raise AssertionError("Claude client should not be created")


async def _unused_run_blocking(fn):
    raise AssertionError("run_blocking should not be called")


async def _failing_run_blocking(fn):
    raise RuntimeError("Claude transport failed " + ("x" * 400))


def test_usage_events_default_empty():
    assert _session().usage_events == []


def test_record_usage_event_returns_same_shape_as_before():
    session = _session()
    event = session.record_usage_event(
        "topic_learning_content",
        topic_id="topic-1",
        model="claude-test",
        source="manual",
        status="success",
        metadata={"k": "v"},
    )
    required_keys = {"event_id", "event_type", "topic_id", "model", "source", "status", "metadata", "created_at"}
    assert required_keys == set(event.keys())


def test_record_usage_event_event_id_is_valid_uuid():
    session = _session()
    event = session.record_usage_event("topic_learning_content", source="manual")
    # event_id now comes from HarnessRunRecord.run_id — must be a valid UUID
    parsed = uuid.UUID(event["event_id"])
    assert str(parsed) == event["event_id"]


def test_record_usage_event_event_ids_are_unique():
    session = _session()
    e1 = session.record_usage_event("x", source="manual")
    e2 = session.record_usage_event("x", source="manual")
    assert e1["event_id"] != e2["event_id"]


def test_record_usage_event_creates_required_fields():
    session = _session()

    event = session.record_usage_event(
        "topic_learning_content",
        topic_id="topic-1",
        model="claude-test",
        source="claude",
        metadata={"refresh": False},
    )

    assert event["event_id"]
    assert event["event_type"] == "topic_learning_content"
    assert event["topic_id"] == "topic-1"
    assert event["model"] == "claude-test"
    assert event["source"] == "claude"
    assert event["status"] == "success"
    assert event["metadata"] == {"refresh": False}
    assert event["created_at"]


def test_record_usage_event_invalid_source_raises_value_error():
    with pytest.raises(ValueError, match="Invalid usage source"):
        _session().record_usage_event("x", source="bad")


def test_record_usage_event_invalid_status_raises_value_error():
    with pytest.raises(ValueError, match="Invalid usage status"):
        _session().record_usage_event("x", status="bad")


def test_usage_summary_counts_source_status_and_type():
    session = _session()
    session.record_usage_event("topic_learning_content", source="claude")
    session.record_usage_event("topic_learning_content", source="cache")
    session.record_usage_event("quiz_evaluation", source="test_mode")
    session.record_usage_event("quiz_evaluation", source="claude", status="error")

    summary = session.usage_summary()

    assert summary["total_events"] == 4
    assert summary["claude_events"] == 2
    assert summary["cache_events"] == 1
    assert summary["test_mode_events"] == 1
    assert summary["error_events"] == 1
    assert summary["by_event_type"] == {
        "topic_learning_content": 2,
        "quiz_evaluation": 2,
    }


def test_to_dict_from_dict_preserves_usage_events():
    session = _session()
    session.record_usage_event("topic_learning_content", topic_id="topic-1", source="manual")

    restored = SessionContext.from_dict(session.to_dict())

    assert restored.usage_events == session.usage_events


def test_from_dict_missing_usage_events_defaults_to_empty():
    session = _session()
    data = session.to_dict()
    del data["usage_events"]

    restored = SessionContext.from_dict(data)

    assert restored.usage_events == []


def test_content_service_cache_hit_records_cache_event():
    session = _session()
    topic = _topic()
    run(generate_learning_content_for_topic(**_content_kwargs(session, topic)))

    run(generate_learning_content_for_topic(**_content_kwargs(session, topic, refresh=False)))

    event = session.usage_events[-1]
    assert event["event_type"] == "topic_learning_content"
    assert event["source"] == "cache"
    assert event["status"] == "success"
    assert event["metadata"]["from_cache"] is True


def test_content_service_test_mode_records_test_mode_event():
    session = _session()
    topic = _topic()

    run(generate_learning_content_for_topic(**_content_kwargs(session, topic)))

    event = session.usage_events[-1]
    assert event["event_type"] == "topic_learning_content"
    assert event["source"] == "test_mode"
    assert event["status"] == "success"


def test_practice_service_test_mode_records_correct_event_type():
    session = _session()
    topic = _topic()

    run(generate_practice_content_for_topic(**_practice_kwargs(session, topic, "portfolio_task")))

    event = session.usage_events[-1]
    assert event["event_type"] == "topic_practice_portfolio_task"
    assert event["source"] == "test_mode"
    assert event["metadata"]["practice_type"] == "portfolio_task"


def test_submission_service_cache_hit_records_cache_event():
    session = _session()
    topic = _topic()
    session.save_quiz_answers(topic.topic_id, "Q1: B")
    session.save_quiz_evaluation(topic.topic_id, "Cached evaluation", "test-mock", score=8)

    run(evaluate_quiz_answers(**_submission_kwargs(session, topic, test_mode=False)))

    event = session.usage_events[-1]
    assert event["event_type"] == "quiz_evaluation"
    assert event["source"] == "cache"
    assert event["status"] == "success"
    assert event["metadata"]["from_cache"] is True


def test_submission_service_test_mode_records_test_mode_event():
    session = _session()
    topic = _topic()
    submit_portfolio_work(session=session, topic=topic, submission="My work")

    run(generate_portfolio_feedback(**_submission_kwargs(session, topic)))

    event = session.usage_events[-1]
    assert event["event_type"] == "portfolio_feedback"
    assert event["source"] == "test_mode"
    assert event["status"] == "success"


def test_content_service_claude_error_records_usage_event_and_safe_log(caplog):
    session = _session()
    topic = _topic()
    kwargs = _content_kwargs(session, topic, test_mode=False, refresh=True)
    kwargs["run_blocking"] = _failing_run_blocking

    with caplog.at_level(logging.ERROR, logger="services.content_service"):
        with pytest.raises(RuntimeError):
            run(generate_learning_content_for_topic(**kwargs))

    event = session.usage_events[-1]
    assert event["event_type"] == "topic_learning_content"
    assert event["source"] == "claude"
    assert event["status"] == "error"
    assert len(event["metadata"]["error"]) == 300

    record = next(r for r in caplog.records if r.name == "services.content_service")
    assert record.ai2_metadata["topic_id"] == topic.topic_id
    assert record.ai2_metadata["event_type"] == "topic_learning_content"
    assert record.ai2_metadata["model"] == "test-model"
    assert record.ai2_metadata["refresh"] is True
    assert "Generate content using exactly this structure" not in record.getMessage()


def test_submission_service_claude_error_records_usage_event_and_safe_log(caplog):
    session = _session()
    topic = _topic()
    learner_answer = "FULL_LEARNER_ANSWER_SHOULD_NOT_APPEAR"
    submit_quiz_answers(session=session, topic=topic, answers=learner_answer)
    kwargs = _submission_kwargs(session, topic, test_mode=False, refresh=True)
    kwargs["make_client"] = lambda: object()
    kwargs["run_blocking"] = _failing_run_blocking

    with caplog.at_level(logging.ERROR, logger="services.submission_service"):
        with pytest.raises(SubmissionGenerationError):
            run(evaluate_quiz_answers(**kwargs))

    event = session.usage_events[-1]
    assert event["event_type"] == "quiz_evaluation"
    assert event["source"] == "claude"
    assert event["status"] == "error"
    assert len(event["metadata"]["error"]) == 300

    record = next(r for r in caplog.records if r.name == "services.submission_service")
    assert record.ai2_metadata["topic_id"] == topic.topic_id
    assert record.ai2_metadata["event_type"] == "quiz_evaluation"
    assert record.ai2_metadata["model"] == "test-model"
    assert record.ai2_metadata["refresh"] is True
    assert learner_answer not in record.getMessage()
    assert learner_answer not in str(record.ai2_metadata)
