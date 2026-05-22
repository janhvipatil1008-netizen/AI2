"""Tests for services/generated_learning_mismatch_service.py."""

from __future__ import annotations

import json
from pathlib import Path

from config import CareerTrack
from context.session import SessionContext
from services.generated_learning_mismatch_service import (
    compare_generated_learning_state,
    compare_generated_topic_content,
    compare_generated_topic_practice,
    compare_interview_submission,
    compare_portfolio_submission,
    compare_quiz_submission,
    compare_topic_notes,
)

SERVICE_PATH = Path(__file__).parent.parent / "services" / "generated_learning_mismatch_service.py"

TOPIC_ID = "rag-basics"
CONTENT = "Generated learning content for RAG."
QUIZ = "Quiz practice content."
PORTFOLIO_TASK = "Portfolio practice content."
INTERVIEW_PRACTICE = "Interview practice content."
ANSWERS = "Q1: A, Q2: B"
EVALUATION = "Good answer."
PORTFOLIO_SUBMISSION = "My portfolio submission."
PORTFOLIO_FEEDBACK = "Solid portfolio feedback."
INTERVIEW_ANSWER = "My interview answer."
INTERVIEW_FEEDBACK = "Strong interview feedback."
REFLECTION = "I understand retrieval."
CONFUSIONS = "No major confusions."
APPLICATION_IDEA = "Build a small RAG demo."


def _session() -> SessionContext:
    session = SessionContext(track=CareerTrack.AI_PM)
    session.save_generated_topic_content(
        TOPIC_ID,
        content=CONTENT,
        model="claude-test",
        freshness_label="fresh",
    )
    session.save_generated_topic_practice(TOPIC_ID, "quiz", QUIZ, "claude-test", "fresh")
    session.save_generated_topic_practice(
        TOPIC_ID, "portfolio_task", PORTFOLIO_TASK, "claude-test", "fresh"
    )
    session.save_generated_topic_practice(
        TOPIC_ID, "interview_practice", INTERVIEW_PRACTICE, "claude-test", "fresh"
    )
    session.save_quiz_answers(TOPIC_ID, ANSWERS)
    session.save_quiz_evaluation(TOPIC_ID, EVALUATION, "claude-test", score=8)
    session.save_portfolio_submission(TOPIC_ID, PORTFOLIO_SUBMISSION)
    session.save_portfolio_feedback(TOPIC_ID, PORTFOLIO_FEEDBACK, "claude-test", score=7)
    session.save_interview_answer(TOPIC_ID, INTERVIEW_ANSWER)
    session.save_interview_feedback(TOPIC_ID, INTERVIEW_FEEDBACK, "claude-test", score=9)
    session.save_topic_notes(
        TOPIC_ID,
        reflection=REFLECTION,
        confusions=CONFUSIONS,
        application_idea=APPLICATION_IDEA,
    )
    return session


def _db_content(**overrides):
    row = {
        "content": CONTENT,
        "model": "claude-test",
        "freshness_label": "fresh",
        "version": "1",
    }
    row.update(overrides)
    return row


def _db_practice(**overrides):
    state = {
        "quiz": {
            "content": QUIZ,
            "model": "claude-test",
            "freshness_label": "fresh",
            "version": "1",
        },
        "portfolio_task": {
            "content": PORTFOLIO_TASK,
            "model": "claude-test",
            "freshness_label": "fresh",
            "version": "1",
        },
        "interview_practice": {
            "content": INTERVIEW_PRACTICE,
            "model": "claude-test",
            "freshness_label": "fresh",
            "version": "1",
        },
    }
    state.update(overrides)
    return state


def _db_quiz(**overrides):
    row = {
        "answers": ANSWERS,
        "evaluation": EVALUATION,
        "score": 8,
        "model": "claude-test",
    }
    row.update(overrides)
    return row


def _db_portfolio(**overrides):
    row = {
        "submission": PORTFOLIO_SUBMISSION,
        "feedback": PORTFOLIO_FEEDBACK,
        "score": 7,
        "model": "claude-test",
    }
    row.update(overrides)
    return row


def _db_interview(**overrides):
    row = {
        "answer": INTERVIEW_ANSWER,
        "feedback": INTERVIEW_FEEDBACK,
        "score": 9,
        "model": "claude-test",
    }
    row.update(overrides)
    return row


def _db_notes(**overrides):
    row = {
        "reflection": REFLECTION,
        "confusions": CONFUSIONS,
        "application_idea": APPLICATION_IDEA,
    }
    row.update(overrides)
    return row


def _db_state(**overrides):
    state = {
        "generated_topic_content": _db_content(),
        "generated_topic_practice": _db_practice(),
        "quiz_submission": _db_quiz(),
        "portfolio_submission": _db_portfolio(),
        "interview_submission": _db_interview(),
        "topic_notes": _db_notes(),
    }
    state.update(overrides)
    return state


def test_generated_content_matches_when_presence_length_model_freshness_version_match():
    result = compare_generated_topic_content(
        session=_session(),
        legacy_topic_id=TOPIC_ID,
        db_content=_db_content(),
    )

    assert result["matches"] is True
    assert result["mismatches"] == []
    assert result["session_snapshot"] == {
        "content_present": True,
        "content_length": len(CONTENT),
        "model": "claude-test",
        "freshness_label": "fresh",
        "version": "1",
    }


def test_generated_content_mismatch_when_db_missing():
    result = compare_generated_topic_content(
        session=_session(),
        legacy_topic_id=TOPIC_ID,
        db_content=None,
    )

    assert result["matches"] is False
    assert result["db_missing"] is True
    assert result["mismatches"][0]["field"] == "record_presence"


def test_generated_content_mismatch_when_length_differs():
    result = compare_generated_topic_content(
        session=_session(),
        legacy_topic_id=TOPIC_ID,
        db_content=_db_content(content=CONTENT + " extra"),
    )

    assert result["matches"] is False
    assert any(m["field"] == "content_length" for m in result["mismatches"])


def test_practice_comparison_covers_all_three_practice_types():
    result = compare_generated_topic_practice(
        session=_session(),
        legacy_topic_id=TOPIC_ID,
        db_practice=_db_practice(),
    )

    assert result["matches"] is True
    assert set(result["practice_types"].keys()) == {
        "quiz",
        "portfolio_task",
        "interview_practice",
    }


def test_practice_mismatch_when_one_type_missing():
    result = compare_generated_topic_practice(
        session=_session(),
        legacy_topic_id=TOPIC_ID,
        db_practice=_db_practice(portfolio_task=None),
    )

    assert result["matches"] is False
    assert result["practice_types"]["portfolio_task"]["db_missing"] is True
    assert any(m["practice_type"] == "portfolio_task" for m in result["mismatches"])


def test_quiz_submission_comparison_matches():
    result = compare_quiz_submission(
        session=_session(),
        legacy_topic_id=TOPIC_ID,
        db_submission=_db_quiz(),
    )

    assert result["matches"] is True
    assert result["session_snapshot"]["answers_length"] == len(ANSWERS)
    assert result["session_snapshot"]["evaluation_length"] == len(EVALUATION)


def test_quiz_submission_mismatch_on_score():
    result = compare_quiz_submission(
        session=_session(),
        legacy_topic_id=TOPIC_ID,
        db_submission=_db_quiz(score=5),
    )

    assert result["matches"] is False
    assert any(m["field"] == "score" for m in result["mismatches"])


def test_portfolio_submission_comparison_matches():
    result = compare_portfolio_submission(
        session=_session(),
        legacy_topic_id=TOPIC_ID,
        db_submission=_db_portfolio(),
    )

    assert result["matches"] is True
    assert result["session_snapshot"]["submission_length"] == len(PORTFOLIO_SUBMISSION)
    assert result["session_snapshot"]["feedback_length"] == len(PORTFOLIO_FEEDBACK)


def test_interview_submission_comparison_matches():
    result = compare_interview_submission(
        session=_session(),
        legacy_topic_id=TOPIC_ID,
        db_submission=_db_interview(),
    )

    assert result["matches"] is True
    assert result["session_snapshot"]["answer_length"] == len(INTERVIEW_ANSWER)
    assert result["session_snapshot"]["feedback_length"] == len(INTERVIEW_FEEDBACK)


def test_topic_notes_comparison_matches():
    result = compare_topic_notes(
        session=_session(),
        legacy_topic_id=TOPIC_ID,
        db_notes=_db_notes(),
    )

    assert result["matches"] is True
    assert result["session_snapshot"]["reflection_length"] == len(REFLECTION)
    assert result["session_snapshot"]["application_idea_length"] == len(APPLICATION_IDEA)


def test_topic_notes_mismatch_on_length_and_presence():
    result = compare_topic_notes(
        session=_session(),
        legacy_topic_id=TOPIC_ID,
        db_notes=_db_notes(reflection="", application_idea=APPLICATION_IDEA + " extra"),
    )

    assert result["matches"] is False
    fields = {m["field"] for m in result["mismatches"]}
    assert "reflection_present" in fields
    assert "reflection_length" in fields
    assert "application_idea_length" in fields


def test_aggregate_comparison_returns_matches_true_when_all_match():
    result = compare_generated_learning_state(
        session=_session(),
        legacy_topic_id=TOPIC_ID,
        db_state=_db_state(),
    )

    assert result["matches"] is True
    assert result["legacy_topic_id"] == TOPIC_ID
    assert len(result["comparisons"]) == 6


def test_aggregate_comparison_returns_matches_false_when_one_comparison_mismatches():
    result = compare_generated_learning_state(
        session=_session(),
        legacy_topic_id=TOPIC_ID,
        db_state=_db_state(quiz_submission=_db_quiz(score=1)),
    )

    assert result["matches"] is False
    assert any(
        comparison["type"] == "quiz_submission" and not comparison["matches"]
        for comparison in result["comparisons"]
    )


def test_output_does_not_include_full_private_or_generated_text():
    result = compare_generated_learning_state(
        session=_session(),
        legacy_topic_id=TOPIC_ID,
        db_state=_db_state(),
    )
    payload = json.dumps(result)

    for forbidden in (
        CONTENT,
        QUIZ,
        PORTFOLIO_TASK,
        INTERVIEW_PRACTICE,
        ANSWERS,
        EVALUATION,
        PORTFOLIO_SUBMISSION,
        PORTFOLIO_FEEDBACK,
        INTERVIEW_ANSWER,
        INTERVIEW_FEEDBACK,
        REFLECTION,
        CONFUSIONS,
        APPLICATION_IDEA,
    ):
        assert forbidden not in payload


def test_service_does_not_import_database_pool():
    assert "database.pool" not in SERVICE_PATH.read_text(encoding="utf-8")


def test_service_does_not_read_os_environ_or_getenv():
    source = SERVICE_PATH.read_text(encoding="utf-8")
    assert "os.environ" not in source
    assert "os.getenv" not in source
    assert "import os" not in source
