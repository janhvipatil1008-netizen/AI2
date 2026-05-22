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


def _submit(session_id: str, topic_id: str, answers: str = "Q1: B, Q2: A, Q3: C"):
    return client.post("/quiz/submit", json={
        "session_id": session_id, "topic_id": topic_id, "answers": answers,
    })


def _evaluate(session_id: str, topic_id: str, refresh: bool = False):
    return client.post("/quiz/evaluate", json={
        "session_id": session_id, "topic_id": topic_id, "refresh": refresh,
    })


# ── Unit tests: SessionContext ────────────────────────────────────────────────

def test_quiz_submissions_defaults_to_empty_dict():
    session = _make_session()
    assert session.quiz_submissions == {}


def test_get_quiz_submission_returns_safe_defaults():
    session = _make_session()
    result  = session.get_quiz_submission("nonexistent-topic")
    assert result["answers"]      == ""
    assert result["evaluation"]   == ""
    assert result["score"]        is None
    assert result["submitted_at"] == ""
    assert result["evaluated_at"] == ""
    assert result["model"]        == ""


def test_save_quiz_answers_saves_and_strips():
    session = _make_session()
    saved   = session.save_quiz_answers("t1", "  Q1: B  ")
    assert saved["answers"]      == "Q1: B"
    assert saved["submitted_at"] != ""
    assert saved["evaluation"]   == ""
    assert saved["score"]        is None


def test_save_quiz_answers_changing_answers_clears_evaluation():
    session = _make_session()
    session.save_quiz_answers("t1", "Q1: A")
    session.save_quiz_evaluation("t1", "Good try!", "test-mock", score=7)

    saved = session.save_quiz_answers("t1", "Q1: B, Q2: C")
    assert saved["answers"]      == "Q1: B, Q2: C"
    assert saved["evaluation"]   == ""
    assert saved["score"]        is None
    assert saved["evaluated_at"] == ""
    assert saved["model"]        == ""


def test_save_quiz_answers_same_text_preserves_evaluation():
    session = _make_session()
    session.save_quiz_answers("t1", "Q1: B")
    session.save_quiz_evaluation("t1", "Well done!", "test-mock", score=9)

    saved = session.save_quiz_answers("t1", "Q1: B")
    assert saved["answers"]    == "Q1: B"
    assert saved["evaluation"] == "Well done!"
    assert saved["score"]      == 9


def test_save_quiz_evaluation_saves_all_fields():
    session = _make_session()
    session.save_quiz_answers("t1", "Q1: A")
    saved = session.save_quiz_evaluation("t1", "  Great effort.  ", "claude-sonnet", score=8)
    assert saved["evaluation"]  == "Great effort."
    assert saved["model"]       == "claude-sonnet"
    assert saved["score"]       == 8
    assert saved["evaluated_at"] != ""
    assert saved["answers"]     == "Q1: A"


def test_save_quiz_evaluation_none_score():
    session = _make_session()
    session.save_quiz_answers("t1", "Q1: A")
    saved = session.save_quiz_evaluation("t1", "Partial credit.", "test-mock", score=None)
    assert saved["score"] is None


def test_to_dict_includes_quiz_submissions():
    session = _make_session()
    session.save_quiz_answers("t1", "Q1: B")
    d = session.to_dict()
    assert "quiz_submissions" in d
    assert "t1" in d["quiz_submissions"]
    assert d["quiz_submissions"]["t1"]["answers"] == "Q1: B"


def test_from_dict_preserves_quiz_submissions():
    session = _make_session()
    session.save_quiz_answers("t1", "Q1: B")
    session.save_quiz_evaluation("t1", "Good work", "test-mock", score=8)
    restored = SessionContext.from_dict(session.to_dict())
    sub = restored.get_quiz_submission("t1")
    assert sub["answers"]    == "Q1: B"
    assert sub["evaluation"] == "Good work"
    assert sub["score"]      == 8


def test_from_dict_backward_compatible_missing_quiz_submissions():
    session = _make_session()
    d = session.to_dict()
    del d["quiz_submissions"]
    restored = SessionContext.from_dict(d)
    assert restored.quiz_submissions == {}


# ── Route tests ───────────────────────────────────────────────────────────────

def test_topic_detail_page_contains_quiz_answer_area():
    session_id = _start_session()
    topic      = _first_topic()
    r = client.get(f"/topic/{session_id}/{topic.topic_id}")
    assert r.status_code == 200
    assert "Your Answers" in r.text


def test_topic_detail_page_contains_quiz_submission_textarea():
    session_id = _start_session()
    topic      = _first_topic()
    r = client.get(f"/topic/{session_id}/{topic.topic_id}")
    assert "quiz-submission-text" in r.text


def test_topic_detail_page_contains_save_answers_button():
    session_id = _start_session()
    topic      = _first_topic()
    r = client.get(f"/topic/{session_id}/{topic.topic_id}")
    assert "Save Answers" in r.text


def test_topic_detail_page_contains_evaluate_answers_button():
    session_id = _start_session()
    topic      = _first_topic()
    r = client.get(f"/topic/{session_id}/{topic.topic_id}")
    assert "Evaluate Answers" in r.text


def test_quiz_submit_saves_answers():
    session_id = _start_session()
    topic      = _first_topic()
    r = _submit(session_id, topic.topic_id, "Q1: B, Q2: A, Q3: C")
    assert r.status_code == 200
    data = r.json()
    assert data["quiz_submission"]["answers"] == "Q1: B, Q2: A, Q3: C"
    assert data["topic_id"] == topic.topic_id


def test_quiz_submit_returns_topic_progress_and_completion():
    session_id = _start_session()
    topic      = _first_topic()
    r = _submit(session_id, topic.topic_id)
    assert r.status_code == 200
    data = r.json()
    assert "topic_progress"     in data
    assert "completion_percent" in data


def test_quiz_submit_marks_quiz_step_in_progress_if_not_started():
    session_id = _start_session()
    topic      = _first_topic()
    r = _submit(session_id, topic.topic_id)
    assert r.status_code == 200
    assert r.json()["topic_progress"]["quiz"] == "in_progress"


def test_quiz_submit_empty_answers_returns_422():
    session_id = _start_session()
    topic      = _first_topic()
    r = _submit(session_id, topic.topic_id, "   ")
    assert r.status_code == 422


def test_quiz_submit_invalid_topic_returns_404():
    session_id = _start_session()
    r = _submit(session_id, "nonexistent-topic-id")
    assert r.status_code == 404


def test_quiz_evaluate_returns_mock_in_test_mode():
    session_id = _start_session()
    topic      = _first_topic()
    _submit(session_id, topic.topic_id)
    r = _evaluate(session_id, topic.topic_id)
    assert r.status_code == 200
    data = r.json()
    assert data["quiz_submission"]["evaluation"] != ""
    assert "Overall Score" in data["quiz_submission"]["evaluation"]


def test_quiz_evaluate_marks_quiz_step_done():
    session_id = _start_session()
    topic      = _first_topic()
    _submit(session_id, topic.topic_id)
    r = _evaluate(session_id, topic.topic_id)
    assert r.status_code == 200
    assert r.json()["topic_progress"]["quiz"] == "done"


def test_quiz_evaluate_includes_score_in_test_mode():
    session_id = _start_session()
    topic      = _first_topic()
    _submit(session_id, topic.topic_id)
    r = _evaluate(session_id, topic.topic_id)
    assert r.status_code == 200
    assert r.json()["quiz_submission"]["score"] == 8


def test_quiz_evaluate_requires_answers_first():
    session_id = _start_session()
    topic      = _first_topic()
    r = _evaluate(session_id, topic.topic_id)
    assert r.status_code == 422


def test_quiz_evaluate_cached_when_refresh_false():
    session_id = _start_session()
    topic      = _first_topic()
    _submit(session_id, topic.topic_id)
    _evaluate(session_id, topic.topic_id)
    r2 = _evaluate(session_id, topic.topic_id, refresh=False)
    assert r2.status_code == 200
    assert r2.json()["quiz_submission"]["evaluation"] != ""


def test_quiz_evaluate_invalid_topic_returns_404():
    session_id = _start_session()
    r = _evaluate(session_id, "nonexistent-topic-id")
    assert r.status_code == 404


def test_topic_detail_page_renders_saved_answers():
    session_id = _start_session()
    topic      = _first_topic()
    _submit(session_id, topic.topic_id, "My detailed quiz answers for all five questions")
    r = client.get(f"/topic/{session_id}/{topic.topic_id}")
    assert r.status_code == 200
    assert "My detailed quiz answers for all five questions" in r.text


def test_topic_detail_page_renders_evaluation_block_after_evaluation():
    session_id = _start_session()
    topic      = _first_topic()
    _submit(session_id, topic.topic_id)
    _evaluate(session_id, topic.topic_id)
    r = client.get(f"/topic/{session_id}/{topic.topic_id}")
    assert r.status_code == 200
    assert "AI Evaluation" in r.text
    assert "Overall Score" in r.text


def test_topic_detail_page_renders_score_chip_after_evaluation():
    session_id = _start_session()
    topic      = _first_topic()
    _submit(session_id, topic.topic_id)
    _evaluate(session_id, topic.topic_id)
    r = client.get(f"/topic/{session_id}/{topic.topic_id}")
    assert r.status_code == 200
    assert "Score: 8/10" in r.text


def test_topic_detail_page_renders_refresh_evaluation_button_after_evaluation():
    session_id = _start_session()
    topic      = _first_topic()
    _submit(session_id, topic.topic_id)
    _evaluate(session_id, topic.topic_id)
    r = client.get(f"/topic/{session_id}/{topic.topic_id}")
    assert r.status_code == 200
    assert "Refresh Evaluation" in r.text


def test_save_quiz_answers_js_function_in_page():
    session_id = _start_session()
    topic      = _first_topic()
    r = client.get(f"/topic/{session_id}/{topic.topic_id}")
    assert "saveQuizAnswers" in r.text


def test_evaluate_quiz_js_function_in_page():
    session_id = _start_session()
    topic      = _first_topic()
    r = client.get(f"/topic/{session_id}/{topic.topic_id}")
    assert "evaluateQuiz" in r.text
