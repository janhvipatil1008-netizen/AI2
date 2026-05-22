import os

os.environ["AI2_TEST_MODE"] = "1"
os.environ["ANTHROPIC_API_KEY"] = "test-key"

from fastapi.testclient import TestClient

from app import app
from context.session import SessionContext
from config import CareerTrack
from curriculum.topics import get_topics_for_week

client = TestClient(app)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_session() -> SessionContext:
    return SessionContext(track=CareerTrack("aipm"))


def _start_session(track: str = "aipm", week: int = 1) -> str:
    r = client.post("/session/start", json={"track": track, "week": week})
    assert r.status_code == 200, r.text
    return r.json()["session_id"]


def _first_topic():
    return get_topics_for_week("aipm", 1)[0]


def _submit(session_id: str, topic_id: str, submission: str = "My portfolio work"):
    return client.post("/portfolio/submit", json={
        "session_id": session_id, "topic_id": topic_id, "submission": submission,
    })


def _feedback(session_id: str, topic_id: str, refresh: bool = False):
    return client.post("/portfolio/feedback", json={
        "session_id": session_id, "topic_id": topic_id, "refresh": refresh,
    })


# ── Unit tests: SessionContext ────────────────────────────────────────────────

def test_portfolio_submissions_defaults_to_empty_dict():
    session = _make_session()
    assert session.portfolio_submissions == {}


def test_get_portfolio_submission_returns_safe_defaults():
    session = _make_session()
    result  = session.get_portfolio_submission("nonexistent-topic")
    assert result["submission"]   == ""
    assert result["feedback"]     == ""
    assert result["score"]        is None
    assert result["submitted_at"] == ""
    assert result["reviewed_at"]  == ""
    assert result["model"]        == ""


def test_save_portfolio_submission_saves_and_strips():
    session = _make_session()
    saved   = session.save_portfolio_submission("t1", "  My work  ")
    assert saved["submission"]   == "My work"
    assert saved["submitted_at"] != ""
    assert saved["feedback"]     == ""
    assert saved["score"]        is None


def test_save_portfolio_submission_changing_submission_clears_feedback():
    session = _make_session()
    session.save_portfolio_submission("t1", "First draft")
    session.save_portfolio_feedback("t1", "Great job!", "test-mock", score=8)

    # Now change the submission — feedback should be wiped
    saved = session.save_portfolio_submission("t1", "Second draft")
    assert saved["submission"] == "Second draft"
    assert saved["feedback"]   == ""
    assert saved["score"]      is None
    assert saved["reviewed_at"] == ""
    assert saved["model"]       == ""


def test_save_portfolio_submission_same_text_preserves_feedback():
    session = _make_session()
    session.save_portfolio_submission("t1", "Draft v1")
    session.save_portfolio_feedback("t1", "Good work!", "test-mock", score=6)

    # Re-submit the same text — feedback should be preserved
    saved = session.save_portfolio_submission("t1", "Draft v1")
    assert saved["submission"] == "Draft v1"
    assert saved["feedback"]   == "Good work!"
    assert saved["score"]      == 6


def test_save_portfolio_feedback_saves_all_fields():
    session = _make_session()
    session.save_portfolio_submission("t1", "My work")
    saved = session.save_portfolio_feedback("t1", "  Solid effort.  ", "claude-sonnet", score=7)
    assert saved["feedback"]    == "Solid effort."
    assert saved["model"]       == "claude-sonnet"
    assert saved["score"]       == 7
    assert saved["reviewed_at"] != ""
    assert saved["submission"]  == "My work"


def test_save_portfolio_feedback_none_score():
    session = _make_session()
    session.save_portfolio_submission("t1", "My work")
    saved = session.save_portfolio_feedback("t1", "Good attempt.", "test-mock", score=None)
    assert saved["score"] is None


def test_to_dict_includes_portfolio_submissions():
    session = _make_session()
    session.save_portfolio_submission("t1", "Draft")
    d = session.to_dict()
    assert "portfolio_submissions" in d
    assert "t1" in d["portfolio_submissions"]
    assert d["portfolio_submissions"]["t1"]["submission"] == "Draft"


def test_from_dict_preserves_portfolio_submissions():
    session = _make_session()
    session.save_portfolio_submission("t1", "Draft")
    session.save_portfolio_feedback("t1", "Nice work", "test-mock", score=8)
    restored = SessionContext.from_dict(session.to_dict())
    sub = restored.get_portfolio_submission("t1")
    assert sub["submission"] == "Draft"
    assert sub["feedback"]   == "Nice work"
    assert sub["score"]      == 8


def test_from_dict_backward_compatible_missing_portfolio_submissions():
    session = _make_session()
    d = session.to_dict()
    del d["portfolio_submissions"]
    restored = SessionContext.from_dict(d)
    assert restored.portfolio_submissions == {}


# ── Route tests ───────────────────────────────────────────────────────────────

def test_topic_detail_page_contains_submission_area():
    session_id = _start_session()
    topic      = _first_topic()
    r = client.get(f"/topic/{session_id}/{topic.topic_id}")
    assert r.status_code == 200
    assert "Your Submission" in r.text


def test_topic_detail_page_contains_submission_textarea():
    session_id = _start_session()
    topic      = _first_topic()
    r = client.get(f"/topic/{session_id}/{topic.topic_id}")
    assert "portfolio-submission-text" in r.text


def test_topic_detail_page_contains_save_submission_button():
    session_id = _start_session()
    topic      = _first_topic()
    r = client.get(f"/topic/{session_id}/{topic.topic_id}")
    assert "Save Submission" in r.text


def test_topic_detail_page_contains_get_ai_feedback_button():
    session_id = _start_session()
    topic      = _first_topic()
    r = client.get(f"/topic/{session_id}/{topic.topic_id}")
    assert "Get AI Feedback" in r.text


def test_portfolio_submit_saves_submission():
    session_id = _start_session()
    topic      = _first_topic()
    r = _submit(session_id, topic.topic_id, "My structured answer")
    assert r.status_code == 200
    data = r.json()
    assert data["portfolio_submission"]["submission"] == "My structured answer"
    assert data["topic_id"] == topic.topic_id


def test_portfolio_submit_returns_topic_progress_and_completion():
    session_id = _start_session()
    topic      = _first_topic()
    r = _submit(session_id, topic.topic_id)
    assert r.status_code == 200
    data = r.json()
    assert "topic_progress"     in data
    assert "completion_percent" in data


def test_portfolio_submit_marks_portfolio_task_in_progress_if_not_started():
    session_id = _start_session()
    topic      = _first_topic()
    r = _submit(session_id, topic.topic_id)
    assert r.status_code == 200
    assert r.json()["topic_progress"]["portfolio_task"] == "in_progress"


def test_portfolio_submit_empty_submission_returns_422():
    session_id = _start_session()
    topic      = _first_topic()
    r = _submit(session_id, topic.topic_id, "   ")
    assert r.status_code == 422


def test_portfolio_submit_invalid_topic_returns_404():
    session_id = _start_session()
    r = _submit(session_id, "nonexistent-topic-id")
    assert r.status_code == 404


def test_portfolio_feedback_returns_mock_in_test_mode():
    session_id = _start_session()
    topic      = _first_topic()
    _submit(session_id, topic.topic_id)
    r = _feedback(session_id, topic.topic_id)
    assert r.status_code == 200
    data = r.json()
    assert data["portfolio_submission"]["feedback"] != ""
    assert "Overall Feedback" in data["portfolio_submission"]["feedback"]


def test_portfolio_feedback_marks_portfolio_task_done():
    session_id = _start_session()
    topic      = _first_topic()
    _submit(session_id, topic.topic_id)
    r = _feedback(session_id, topic.topic_id)
    assert r.status_code == 200
    assert r.json()["topic_progress"]["portfolio_task"] == "done"


def test_portfolio_feedback_includes_score_in_test_mode():
    session_id = _start_session()
    topic      = _first_topic()
    _submit(session_id, topic.topic_id)
    r = _feedback(session_id, topic.topic_id)
    assert r.status_code == 200
    assert r.json()["portfolio_submission"]["score"] == 7


def test_portfolio_feedback_requires_submission_first():
    session_id = _start_session()
    topic      = _first_topic()
    r = _feedback(session_id, topic.topic_id)
    assert r.status_code == 422


def test_portfolio_feedback_cached_when_refresh_false():
    session_id = _start_session()
    topic      = _first_topic()
    _submit(session_id, topic.topic_id)
    # First call generates feedback
    _feedback(session_id, topic.topic_id)
    # Second call should return cached (no change in content)
    r2 = _feedback(session_id, topic.topic_id, refresh=False)
    assert r2.status_code == 200
    assert r2.json()["portfolio_submission"]["feedback"] != ""


def test_portfolio_feedback_invalid_topic_returns_404():
    session_id = _start_session()
    r = _feedback(session_id, "nonexistent-topic-id")
    assert r.status_code == 404


def test_topic_detail_page_renders_saved_submission():
    session_id = _start_session()
    topic      = _first_topic()
    _submit(session_id, topic.topic_id, "My detailed portfolio answer")
    r = client.get(f"/topic/{session_id}/{topic.topic_id}")
    assert r.status_code == 200
    assert "My detailed portfolio answer" in r.text


def test_topic_detail_page_renders_feedback_block_after_feedback():
    session_id = _start_session()
    topic      = _first_topic()
    _submit(session_id, topic.topic_id)
    _feedback(session_id, topic.topic_id)
    r = client.get(f"/topic/{session_id}/{topic.topic_id}")
    assert r.status_code == 200
    assert "AI Feedback" in r.text
    assert "Overall Feedback" in r.text


def test_topic_detail_page_renders_score_chip_after_feedback():
    session_id = _start_session()
    topic      = _first_topic()
    _submit(session_id, topic.topic_id)
    _feedback(session_id, topic.topic_id)
    r = client.get(f"/topic/{session_id}/{topic.topic_id}")
    assert r.status_code == 200
    assert "Score: 7/10" in r.text


def test_topic_detail_page_renders_refresh_feedback_button_after_feedback():
    session_id = _start_session()
    topic      = _first_topic()
    _submit(session_id, topic.topic_id)
    _feedback(session_id, topic.topic_id)
    r = client.get(f"/topic/{session_id}/{topic.topic_id}")
    assert r.status_code == 200
    assert "Refresh Feedback" in r.text


def test_save_portfolio_submission_js_function_in_page():
    session_id = _start_session()
    topic      = _first_topic()
    r = client.get(f"/topic/{session_id}/{topic.topic_id}")
    assert "savePortfolioSubmission" in r.text


def test_get_portfolio_feedback_js_function_in_page():
    session_id = _start_session()
    topic      = _first_topic()
    r = client.get(f"/topic/{session_id}/{topic.topic_id}")
    assert "getPortfolioFeedback" in r.text
