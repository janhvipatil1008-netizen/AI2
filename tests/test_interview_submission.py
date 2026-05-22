import os

os.environ["AI2_TEST_MODE"] = "1"
os.environ["ANTHROPIC_API_KEY"] = "test-key"

import pathlib

from fastapi.testclient import TestClient

from app import app
from config import CareerTrack
from context.session import SessionContext
from curriculum.topics import get_topics_for_week

_CSS_PATH = pathlib.Path(__file__).parent.parent / "static" / "style.css"

client = TestClient(app)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _start_session(track: str = "aipm", week: int = 1) -> str:
    response = client.post("/session/start", json={"track": track, "week": week})
    assert response.status_code == 200, response.text
    return response.json()["session_id"]


def _first_topic():
    return get_topics_for_week("aipm", 1)[0]


# ── Unit tests: SessionContext.interview_submissions ──────────────────────────

def test_interview_submissions_defaults_to_empty_dict():
    session = SessionContext(track=CareerTrack.AI_PM)
    assert session.interview_submissions == {}


def test_get_interview_submission_returns_safe_defaults():
    session = SessionContext(track=CareerTrack.AI_PM)
    result = session.get_interview_submission("any-topic")
    assert result["answer"]       == ""
    assert result["feedback"]     == ""
    assert result["score"]        is None
    assert result["submitted_at"] == ""
    assert result["reviewed_at"]  == ""
    assert result["model"]        == ""


def test_save_interview_answer_strips_and_saves():
    session = SessionContext(track=CareerTrack.AI_PM)
    saved = session.save_interview_answer("topic-1", "  My answer  ")
    assert saved["answer"]       == "My answer"
    assert saved["submitted_at"] != ""
    assert saved["feedback"]     == ""
    assert saved["score"]        is None
    assert "topic-1" in session.interview_submissions


def test_save_interview_answer_same_answer_preserves_feedback():
    session = SessionContext(track=CareerTrack.AI_PM)
    session.save_interview_answer("topic-1", "My answer")
    session.save_interview_feedback("topic-1", "Great job!", "test-model", score=9)
    # Save the same answer text again
    saved = session.save_interview_answer("topic-1", "My answer")
    assert saved["feedback"] == "Great job!"
    assert saved["score"] == 9


def test_save_interview_answer_changed_answer_clears_feedback():
    session = SessionContext(track=CareerTrack.AI_PM)
    session.save_interview_answer("topic-1", "Old answer")
    session.save_interview_feedback("topic-1", "Old feedback", "test-model", score=7)
    # Change the answer
    saved = session.save_interview_answer("topic-1", "New answer")
    assert saved["answer"]      == "New answer"
    assert saved["feedback"]    == ""
    assert saved["score"]       is None
    assert saved["reviewed_at"] == ""
    assert saved["model"]       == ""


def test_save_interview_feedback_saves_all_fields():
    session = SessionContext(track=CareerTrack.AI_PM)
    session.save_interview_answer("topic-1", "My answer")
    saved = session.save_interview_feedback(
        "topic-1", "  Good work!  ", model="claude-sonnet", score=8
    )
    assert saved["feedback"]    == "Good work!"
    assert saved["model"]       == "claude-sonnet"
    assert saved["score"]       == 8
    assert saved["reviewed_at"] != ""
    assert saved["answer"]      == "My answer"


def test_save_interview_feedback_score_none_allowed():
    session = SessionContext(track=CareerTrack.AI_PM)
    session.save_interview_answer("topic-1", "Answer")
    saved = session.save_interview_feedback("topic-1", "Feedback", "m")
    assert saved["score"] is None


def test_to_dict_includes_interview_submissions():
    session = SessionContext(track=CareerTrack.AI_PM)
    session.save_interview_answer("topic-1", "My answer")
    d = session.to_dict()
    assert "interview_submissions" in d
    assert d["interview_submissions"]["topic-1"]["answer"] == "My answer"


def test_from_dict_restores_interview_submissions():
    session = SessionContext(track=CareerTrack.AI_PM)
    session.save_interview_answer("topic-1", "My answer")
    session.save_interview_feedback("topic-1", "Great", "m", score=9)
    restored = SessionContext.from_dict(session.to_dict())
    result = restored.get_interview_submission("topic-1")
    assert result["answer"]   == "My answer"
    assert result["feedback"] == "Great"
    assert result["score"]    == 9


def test_from_dict_missing_interview_submissions_defaults_to_empty():
    session = SessionContext(track=CareerTrack.AI_PM)
    d = session.to_dict()
    del d["interview_submissions"]
    restored = SessionContext.from_dict(d)
    assert restored.interview_submissions == {}
    result = restored.get_interview_submission("any-topic")
    assert result["answer"] == ""


# ── Route / template tests ────────────────────────────────────────────────────

def test_topic_detail_contains_interview_answer_area():
    session_id = _start_session()
    topic = _first_topic()
    response = client.get(f"/topic/{session_id}/{topic.topic_id}")
    assert response.status_code == 200
    assert "Your Interview Answer" in response.text
    assert "Save Answer" in response.text
    assert "Get AI Feedback" in response.text


def test_interview_submit_saves_answer():
    session_id = _start_session()
    topic = _first_topic()
    response = client.post("/interview/submit", json={
        "session_id": session_id,
        "topic_id":   topic.topic_id,
        "answer":     "RAG grounds LLM responses in retrieved documents.",
    })
    assert response.status_code == 200
    data = response.json()
    assert data["topic_id"] == topic.topic_id
    assert data["interview_submission"]["answer"] == "RAG grounds LLM responses in retrieved documents."
    assert data["interview_submission"]["submitted_at"] != ""


def test_interview_submit_empty_answer_returns_422():
    session_id = _start_session()
    topic = _first_topic()
    response = client.post("/interview/submit", json={
        "session_id": session_id,
        "topic_id":   topic.topic_id,
        "answer":     "   ",
    })
    assert response.status_code == 422


def test_interview_submit_invalid_topic_returns_404():
    session_id = _start_session()
    response = client.post("/interview/submit", json={
        "session_id": session_id,
        "topic_id":   "nonexistent-topic-xyz",
        "answer":     "Some answer",
    })
    assert response.status_code == 404


def test_interview_submit_marks_step_in_progress():
    session_id = _start_session()
    topic = _first_topic()
    response = client.post("/interview/submit", json={
        "session_id": session_id,
        "topic_id":   topic.topic_id,
        "answer":     "Some answer",
    })
    assert response.status_code == 200
    data = response.json()
    assert data["topic_progress"]["interview_practice"] == "in_progress"


def test_interview_feedback_returns_mock_in_test_mode():
    session_id = _start_session()
    topic = _first_topic()
    # Submit an answer first
    client.post("/interview/submit", json={
        "session_id": session_id,
        "topic_id":   topic.topic_id,
        "answer":     "RAG means Retrieval-Augmented Generation.",
    })
    response = client.post("/interview/feedback", json={
        "session_id": session_id,
        "topic_id":   topic.topic_id,
        "refresh":    False,
    })
    assert response.status_code == 200
    data = response.json()
    assert data["interview_submission"]["feedback"] != ""
    assert "Overall Score" in data["interview_submission"]["feedback"]
    assert data["interview_submission"]["score"] == 8


def test_interview_feedback_marks_step_done():
    session_id = _start_session()
    topic = _first_topic()
    client.post("/interview/submit", json={
        "session_id": session_id,
        "topic_id":   topic.topic_id,
        "answer":     "My answer",
    })
    response = client.post("/interview/feedback", json={
        "session_id": session_id,
        "topic_id":   topic.topic_id,
    })
    assert response.status_code == 200
    assert response.json()["topic_progress"]["interview_practice"] == "done"


def test_interview_feedback_requires_answer_first():
    session_id = _start_session()
    topic = _first_topic()
    response = client.post("/interview/feedback", json={
        "session_id": session_id,
        "topic_id":   topic.topic_id,
    })
    assert response.status_code == 422
    assert "answer" in response.json()["detail"].lower()


def test_interview_feedback_cached_when_refresh_false():
    session_id = _start_session()
    topic = _first_topic()
    client.post("/interview/submit", json={
        "session_id": session_id,
        "topic_id":   topic.topic_id,
        "answer":     "Answer text",
    })
    # Get feedback first time
    r1 = client.post("/interview/feedback", json={
        "session_id": session_id,
        "topic_id":   topic.topic_id,
        "refresh":    False,
    })
    assert r1.status_code == 200
    first_reviewed_at = r1.json()["interview_submission"]["reviewed_at"]

    # Second call with refresh=false — should return cached (reviewed_at unchanged)
    r2 = client.post("/interview/feedback", json={
        "session_id": session_id,
        "topic_id":   topic.topic_id,
        "refresh":    False,
    })
    assert r2.status_code == 200
    assert r2.json()["interview_submission"]["reviewed_at"] == first_reviewed_at


def test_interview_feedback_refresh_regenerates():
    session_id = _start_session()
    topic = _first_topic()
    client.post("/interview/submit", json={
        "session_id": session_id,
        "topic_id":   topic.topic_id,
        "answer":     "Answer text",
    })
    r1 = client.post("/interview/feedback", json={
        "session_id": session_id,
        "topic_id":   topic.topic_id,
        "refresh":    False,
    })
    first_reviewed_at = r1.json()["interview_submission"]["reviewed_at"]

    r2 = client.post("/interview/feedback", json={
        "session_id": session_id,
        "topic_id":   topic.topic_id,
        "refresh":    True,
    })
    assert r2.status_code == 200
    # reviewed_at should be updated (may differ by at most a few ms, but field is refreshed)
    assert r2.json()["interview_submission"]["feedback"] != ""


def test_topic_detail_renders_saved_answer():
    session_id = _start_session()
    topic = _first_topic()
    client.post("/interview/submit", json={
        "session_id": session_id,
        "topic_id":   topic.topic_id,
        "answer":     "My specific interview answer text",
    })
    response = client.get(f"/topic/{session_id}/{topic.topic_id}")
    assert response.status_code == 200
    assert "My specific interview answer text" in response.text


def test_topic_detail_renders_saved_feedback():
    session_id = _start_session()
    topic = _first_topic()
    client.post("/interview/submit", json={
        "session_id": session_id,
        "topic_id":   topic.topic_id,
        "answer":     "Some answer",
    })
    client.post("/interview/feedback", json={
        "session_id": session_id,
        "topic_id":   topic.topic_id,
    })
    response = client.get(f"/topic/{session_id}/{topic.topic_id}")
    assert response.status_code == 200
    assert "AI Feedback" in response.text
    assert "Overall Score" in response.text


# ── CSS presence tests ────────────────────────────────────────────────────────

def test_css_defines_interview_submission_area():
    css = _CSS_PATH.read_text(encoding="utf-8")
    assert ".interview-submission-area" in css


def test_css_defines_interview_action_btn():
    css = _CSS_PATH.read_text(encoding="utf-8")
    assert ".interview-action-btn" in css


def test_css_defines_interview_feedback_block():
    css = _CSS_PATH.read_text(encoding="utf-8")
    assert ".interview-feedback-block" in css


def test_css_defines_interview_score_chip():
    css = _CSS_PATH.read_text(encoding="utf-8")
    assert ".interview-score-chip" in css


def test_topic_detail_html_uses_interview_submission_area_class():
    session_id = _start_session()
    topic = _first_topic()
    response = client.get(f"/topic/{session_id}/{topic.topic_id}")
    assert response.status_code == 200
    assert "interview-submission-area" in response.text
    assert "interview-submission-textarea" in response.text
    assert "interview-action-btn" in response.text
