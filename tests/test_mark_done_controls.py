import os

os.environ["AI2_TEST_MODE"] = "1"
os.environ["ANTHROPIC_API_KEY"] = "test-key"

from fastapi.testclient import TestClient

from app import app
from curriculum.topics import get_topics_for_week

client = TestClient(app)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _start_session(track: str = "aipm", week: int = 1) -> str:
    response = client.post("/session/start", json={"track": track, "week": week})
    assert response.status_code == 200, response.text
    return response.json()["session_id"]


def _first_topic():
    return get_topics_for_week("aipm", 1)[0]


def _generate_content(session_id: str, topic_id: str) -> None:
    r = client.post("/topic/content/generate", json={
        "session_id": session_id, "topic_id": topic_id,
    })
    assert r.status_code == 200


def _generate_practice(session_id: str, topic_id: str, practice_type: str) -> None:
    r = client.post("/topic/practice/generate", json={
        "session_id": session_id, "topic_id": topic_id, "practice_type": practice_type,
    })
    assert r.status_code == 200


# ── Button visibility: absent when no content ─────────────────────────────────

def test_mark_learn_done_absent_when_no_content():
    session_id = _start_session()
    topic = _first_topic()
    response = client.get(f"/topic/{session_id}/{topic.topic_id}")
    assert response.status_code == 200
    assert "Mark Learn Done" not in response.text


def test_mark_quiz_done_absent_when_no_quiz_content():
    session_id = _start_session()
    topic = _first_topic()
    response = client.get(f"/topic/{session_id}/{topic.topic_id}")
    assert "Mark Quiz Done" not in response.text


def test_mark_portfolio_task_done_absent_when_no_content():
    session_id = _start_session()
    topic = _first_topic()
    response = client.get(f"/topic/{session_id}/{topic.topic_id}")
    assert "Mark Portfolio Task Done" not in response.text


def test_mark_interview_practice_done_absent_when_no_content():
    session_id = _start_session()
    topic = _first_topic()
    response = client.get(f"/topic/{session_id}/{topic.topic_id}")
    assert "Mark Interview Practice Done" not in response.text


# ── Button visibility: present when content exists ────────────────────────────

def test_mark_learn_done_button_appears_when_content_exists():
    session_id = _start_session()
    topic = _first_topic()
    _generate_content(session_id, topic.topic_id)

    response = client.get(f"/topic/{session_id}/{topic.topic_id}")
    assert response.status_code == 200
    assert "Mark Learn Done" in response.text


def test_mark_quiz_done_button_appears_when_quiz_content_exists():
    session_id = _start_session()
    topic = _first_topic()
    _generate_practice(session_id, topic.topic_id, "quiz")

    response = client.get(f"/topic/{session_id}/{topic.topic_id}")
    assert response.status_code == 200
    assert "Mark Quiz Done" in response.text


def test_mark_portfolio_task_done_button_appears_when_content_exists():
    session_id = _start_session()
    topic = _first_topic()
    _generate_practice(session_id, topic.topic_id, "portfolio_task")

    response = client.get(f"/topic/{session_id}/{topic.topic_id}")
    assert response.status_code == 200
    assert "Mark Portfolio Task Done" in response.text


def test_mark_interview_practice_done_button_appears_when_content_exists():
    session_id = _start_session()
    topic = _first_topic()
    _generate_practice(session_id, topic.topic_id, "interview_practice")

    response = client.get(f"/topic/{session_id}/{topic.topic_id}")
    assert response.status_code == 200
    assert "Mark Interview Practice Done" in response.text


# ── JS wiring ─────────────────────────────────────────────────────────────────

def test_markstepfromcontent_function_present_in_page():
    session_id = _start_session()
    topic = _first_topic()
    _generate_content(session_id, topic.topic_id)

    response = client.get(f"/topic/{session_id}/{topic.topic_id}")
    assert "markStepFromContent" in response.text


def test_mark_learn_done_onclick_references_learn_step():
    session_id = _start_session()
    topic = _first_topic()
    _generate_content(session_id, topic.topic_id)

    response = client.get(f"/topic/{session_id}/{topic.topic_id}")
    assert "markStepFromContent(this, 'learn')" in response.text


def test_mark_quiz_done_onclick_references_quiz_step():
    session_id = _start_session()
    topic = _first_topic()
    _generate_practice(session_id, topic.topic_id, "quiz")

    response = client.get(f"/topic/{session_id}/{topic.topic_id}")
    assert "markStepFromContent(this, 'quiz')" in response.text


def test_mark_portfolio_task_done_onclick_references_portfolio_step():
    session_id = _start_session()
    topic = _first_topic()
    _generate_practice(session_id, topic.topic_id, "portfolio_task")

    response = client.get(f"/topic/{session_id}/{topic.topic_id}")
    assert "markStepFromContent(this, 'portfolio_task')" in response.text


def test_mark_interview_practice_done_onclick_references_interview_step():
    session_id = _start_session()
    topic = _first_topic()
    _generate_practice(session_id, topic.topic_id, "interview_practice")

    response = client.get(f"/topic/{session_id}/{topic.topic_id}")
    assert "markStepFromContent(this, 'interview_practice')" in response.text


# ── Existing journey-card buttons still present ───────────────────────────────

def test_existing_mark_in_progress_buttons_still_present():
    session_id = _start_session()
    topic = _first_topic()
    response = client.get(f"/topic/{session_id}/{topic.topic_id}")
    assert "Mark In Progress" in response.text


def test_existing_mark_done_buttons_still_present_in_journey_cards():
    session_id = _start_session()
    topic = _first_topic()
    response = client.get(f"/topic/{session_id}/{topic.topic_id}")
    assert "Mark Done" in response.text


# ── markStep wiring: clicking mark-done should update progress ────────────────

def test_mark_step_endpoint_still_works_after_template_change():
    session_id = _start_session()
    topic = _first_topic()

    response = client.post("/topic/progress", json={
        "session_id": session_id,
        "topic_id":   topic.topic_id,
        "step":       "learn",
        "status":     "done",
    })
    assert response.status_code == 200
    assert response.json()["topic_progress"]["learn"] == "done"
    assert response.json()["completion_percent"] == 20
