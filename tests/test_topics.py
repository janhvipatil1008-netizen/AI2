import os

os.environ["AI2_TEST_MODE"] = "1"
os.environ["ANTHROPIC_API_KEY"] = "test-key"

import pytest
import re

from curriculum.topics import (
    get_all_topics,
    get_topic,
    get_topics_for_track,
    get_topics_for_week,
)
from config import CareerTrack
from context.session import SessionContext
from app import get_next_topic_step


def test_get_all_topics_returns_topics():
    assert get_all_topics()


def test_get_topics_for_track_returns_topics():
    topics = get_topics_for_track("aipm")
    assert topics
    assert all(topic.track == "aipm" for topic in topics)


def test_get_topics_for_week_returns_topics():
    topics = get_topics_for_week("aipm", 1)
    assert topics
    assert all(topic.track == "aipm" for topic in topics)
    assert all(topic.week_num == 1 for topic in topics)


def test_topic_ids_are_unique_and_url_safe():
    topics = get_all_topics()
    topic_ids = [topic.topic_id for topic in topics]
    assert len(topic_ids) == len(set(topic_ids))
    assert all(re.fullmatch(r"[a-z0-9-]+", topic_id) for topic_id in topic_ids)


def test_prompt_fields_are_non_empty():
    topic = get_topics_for_track("aipm")[0]
    assert topic.learn_prompt
    assert topic.quiz_prompt
    assert topic.portfolio_prompt
    assert topic.interview_prompt
    assert topic.topic_title in topic.learn_prompt
    assert topic.description in topic.quiz_prompt


def test_get_topic_retrieves_by_topic_id():
    topic = get_topics_for_track("aipm")[0]
    found = get_topic("aipm", topic.topic_id)
    assert found == topic


def test_invalid_track_and_missing_topic_are_safe():
    assert get_topics_for_track("unknown") == []
    assert get_topics_for_week("unknown", 1) == []
    assert get_topic("unknown", "anything") is None
    assert get_topic("aipm", "missing-topic") is None


# ── SessionContext topic progress ─────────────────────────────────────────────

def test_session_default_topic_progress_is_empty():
    session = SessionContext(track=CareerTrack.AI_PM)
    assert session.topic_progress == {}


def test_get_topic_progress_returns_defaults():
    session = SessionContext(track=CareerTrack.AI_PM)
    progress = session.get_topic_progress("some-topic")
    assert progress == {
        "learn":              "not_started",
        "quiz":               "not_started",
        "portfolio_task":     "not_started",
        "interview_practice": "not_started",
        "reflection":         "not_started",
    }


def test_mark_topic_step_updates_step():
    session = SessionContext(track=CareerTrack.AI_PM)
    session.mark_topic_step("topic-1", "learn", "in_progress")
    assert session.topic_progress["topic-1"]["learn"] == "in_progress"
    assert session.get_topic_progress("topic-1")["learn"] == "in_progress"
    # Unset steps still default to not_started
    assert session.get_topic_progress("topic-1")["quiz"] == "not_started"


def test_mark_topic_step_invalid_step_raises():
    session = SessionContext(track=CareerTrack.AI_PM)
    with pytest.raises(ValueError):
        session.mark_topic_step("topic-1", "invalid_step")


def test_mark_topic_step_invalid_status_raises():
    session = SessionContext(track=CareerTrack.AI_PM)
    with pytest.raises(ValueError):
        session.mark_topic_step("topic-1", "learn", "bad_status")


def test_topic_completion_percent():
    session = SessionContext(track=CareerTrack.AI_PM)
    assert session.topic_completion_percent("topic-1") == 0
    session.mark_topic_step("topic-1", "learn", "done")
    session.mark_topic_step("topic-1", "quiz",  "done")
    # 2 of 5 steps done = 40%
    assert session.topic_completion_percent("topic-1") == 40
    session.mark_topic_step("topic-1", "portfolio_task",     "done")
    session.mark_topic_step("topic-1", "interview_practice", "done")
    session.mark_topic_step("topic-1", "reflection",         "done")
    assert session.topic_completion_percent("topic-1") == 100


def test_topic_progress_round_trips_serialisation():
    session = SessionContext(track=CareerTrack.AI_PM)
    session.mark_topic_step("topic-1", "learn", "done")
    restored = SessionContext.from_dict(session.to_dict())
    assert restored.topic_progress == session.topic_progress
    assert restored.get_topic_progress("topic-1")["learn"] == "done"


def test_from_dict_missing_topic_progress_defaults_to_empty():
    session = SessionContext(track=CareerTrack.AI_PM)
    d = session.to_dict()
    del d["topic_progress"]
    restored = SessionContext.from_dict(d)
    assert restored.topic_progress == {}


# ── get_next_topic_step unit tests ────────────────────────────────────────────

def _all_not_started():
    return {s: "not_started" for s in ("learn", "quiz", "portfolio_task", "interview_practice", "reflection")}


def test_next_step_all_not_started_returns_learn():
    result = get_next_topic_step(_all_not_started())
    assert result["step"]   == "learn"
    assert result["label"]  == "Continue Learning"
    assert result["anchor"] == "ai-learning-content"


def test_next_step_learn_done_returns_quiz():
    p = {**_all_not_started(), "learn": "done"}
    result = get_next_topic_step(p)
    assert result["step"]   == "quiz"
    assert result["label"]  == "Continue Quiz"
    assert result["anchor"] == "ai-quiz"


def test_next_step_learn_quiz_done_returns_portfolio():
    p = {**_all_not_started(), "learn": "done", "quiz": "done"}
    result = get_next_topic_step(p)
    assert result["step"]   == "portfolio_task"
    assert result["label"]  == "Continue Portfolio Task"
    assert result["anchor"] == "ai-portfolio-task"


def test_next_step_first_three_done_returns_interview():
    p = {**_all_not_started(), "learn": "done", "quiz": "done", "portfolio_task": "done"}
    result = get_next_topic_step(p)
    assert result["step"]   == "interview_practice"
    assert result["label"]  == "Continue Interview Practice"
    assert result["anchor"] == "ai-interview-practice"


def test_next_step_first_four_done_returns_reflection():
    p = {**_all_not_started(), "learn": "done", "quiz": "done",
         "portfolio_task": "done", "interview_practice": "done"}
    result = get_next_topic_step(p)
    assert result["step"]   == "reflection"
    assert result["label"]  == "Continue Reflection"
    assert result["anchor"] == "topic-reflection"


def test_next_step_all_done_returns_review():
    p = {s: "done" for s in ("learn", "quiz", "portfolio_task", "interview_practice", "reflection")}
    result = get_next_topic_step(p)
    assert result["step"]   == ""
    assert result["label"]  == "Review Topic"
    assert result["anchor"] == ""


def test_next_step_in_progress_treated_as_incomplete():
    p = {**_all_not_started(), "learn": "in_progress"}
    result = get_next_topic_step(p)
    assert result["step"] == "learn"


def test_next_step_empty_progress_returns_learn():
    result = get_next_topic_step({})
    assert result["step"] == "learn"
