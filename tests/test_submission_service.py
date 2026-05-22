import asyncio
import time

import pytest

from config import CareerTrack
from context.session import SessionContext
from curriculum.topics import get_topics_for_week
from services.submission_service import (
    SubmissionValidationError,
    evaluate_quiz_answers,
    generate_interview_feedback,
    generate_portfolio_feedback,
    parse_score,
    submit_interview_answer,
    submit_portfolio_work,
    submit_quiz_answers,
)


def run(coro):
    return asyncio.run(coro)


def _session():
    return SessionContext(track=CareerTrack.AI_PM)


def _topic():
    return get_topics_for_week("aipm", 1)[0]


def _unused_client():
    raise AssertionError("Claude client should not be created")


async def _unused_run_blocking(fn):
    raise AssertionError("run_blocking should not be called")


def _kwargs(session, topic, *, test_mode=True, refresh=False):
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


def test_submit_quiz_answers_saves_answers_and_marks_quiz_in_progress():
    session = _session()
    topic = _topic()

    result = submit_quiz_answers(session=session, topic=topic, answers="  Q1: B  ")

    assert result["quiz_submission"]["answers"] == "Q1: B"
    assert result["topic_progress"]["quiz"] == "in_progress"
    assert session.get_topic_progress(topic.topic_id)["quiz"] == "in_progress"


def test_evaluate_quiz_answers_returns_cached_evaluation_when_refresh_false():
    session = _session()
    topic = _topic()
    session.save_quiz_answers(topic.topic_id, "Q1: B")
    cached = session.save_quiz_evaluation(topic.topic_id, "Cached evaluation", "cached", score=6)

    result = run(
        evaluate_quiz_answers(**_kwargs(session, topic, test_mode=False, refresh=False))
    )

    assert result["from_cache"] is True
    assert result["quiz_submission"] == cached
    assert result["quiz_submission"]["evaluated_at"] == cached["evaluated_at"]


def test_evaluate_quiz_answers_test_mode_saves_mock_and_marks_quiz_done():
    session = _session()
    topic = _topic()
    submit_quiz_answers(session=session, topic=topic, answers="Q1: B")

    result = run(evaluate_quiz_answers(**_kwargs(session, topic)))

    assert result["from_cache"] is False
    assert "Overall Score" in result["quiz_submission"]["evaluation"]
    assert result["quiz_submission"]["score"] == 8
    assert result["quiz_submission"]["model"] == "test-mock"
    assert result["topic_progress"]["quiz"] == "done"


def test_refresh_evaluation_updates_score_and_timestamp_without_version_field():
    session = _session()
    topic = _topic()
    submit_quiz_answers(session=session, topic=topic, answers="Q1: B")
    first = run(evaluate_quiz_answers(**_kwargs(session, topic)))
    first_at = first["quiz_submission"]["evaluated_at"]

    time.sleep(0.001)
    refreshed = run(evaluate_quiz_answers(**_kwargs(session, topic, refresh=True)))

    assert refreshed["from_cache"] is False
    assert refreshed["quiz_submission"]["score"] == 8
    assert "version" not in refreshed["quiz_submission"]
    assert refreshed["quiz_submission"]["evaluated_at"] != first_at


def test_submit_portfolio_work_saves_submission_and_marks_portfolio_in_progress():
    session = _session()
    topic = _topic()

    result = submit_portfolio_work(session=session, topic=topic, submission="  My work  ")

    assert result["portfolio_submission"]["submission"] == "My work"
    assert result["topic_progress"]["portfolio_task"] == "in_progress"


def test_generate_portfolio_feedback_test_mode_saves_feedback_and_marks_done():
    session = _session()
    topic = _topic()
    submit_portfolio_work(session=session, topic=topic, submission="My work")

    result = run(generate_portfolio_feedback(**_kwargs(session, topic)))

    assert "Overall Feedback" in result["portfolio_submission"]["feedback"]
    assert result["portfolio_submission"]["score"] == 7
    assert result["portfolio_submission"]["model"] == "test-mock"
    assert result["topic_progress"]["portfolio_task"] == "done"


def test_submit_interview_answer_saves_answer_and_marks_interview_in_progress():
    session = _session()
    topic = _topic()

    result = submit_interview_answer(session=session, topic=topic, answer="  My answer  ")

    assert result["interview_submission"]["answer"] == "My answer"
    assert result["topic_progress"]["interview_practice"] == "in_progress"


def test_generate_interview_feedback_test_mode_saves_feedback_and_marks_done():
    session = _session()
    topic = _topic()
    submit_interview_answer(session=session, topic=topic, answer="My answer")

    result = run(generate_interview_feedback(**_kwargs(session, topic)))

    assert "Overall Score" in result["interview_submission"]["feedback"]
    assert result["interview_submission"]["score"] == 8
    assert result["interview_submission"]["model"] == "test-mock"
    assert result["topic_progress"]["interview_practice"] == "done"


def test_score_parsing_works_for_overall_score():
    assert parse_score("Overall Score: 9/10") == 9
    assert parse_score("overall score: 4 / 10") == 4
    assert parse_score("No score here") is None


def test_missing_answers_submission_and_answer_are_rejected_consistently():
    session = _session()
    topic = _topic()

    with pytest.raises(SubmissionValidationError, match="answers cannot be empty"):
        submit_quiz_answers(session=session, topic=topic, answers="   ")

    with pytest.raises(SubmissionValidationError, match="No answers found"):
        run(evaluate_quiz_answers(**_kwargs(session, topic)))

    with pytest.raises(SubmissionValidationError, match="submission cannot be empty"):
        submit_portfolio_work(session=session, topic=topic, submission="   ")

    with pytest.raises(SubmissionValidationError, match="No submission found"):
        run(generate_portfolio_feedback(**_kwargs(session, topic)))

    with pytest.raises(SubmissionValidationError, match="answer cannot be empty"):
        submit_interview_answer(session=session, topic=topic, answer="   ")

    with pytest.raises(SubmissionValidationError, match="No answer found"):
        run(generate_interview_feedback(**_kwargs(session, topic)))
