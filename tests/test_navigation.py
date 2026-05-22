import os

os.environ["AI2_TEST_MODE"] = "1"
os.environ["ANTHROPIC_API_KEY"] = "test-key"

from fastapi.testclient import TestClient

from app import app
from curriculum.topics import get_topics_for_week

client = TestClient(app)


def _start_session(track: str = "aipm", week: int = 1) -> str:
    response = client.post("/session/start", json={"track": track, "week": week})
    assert response.status_code == 200, response.text
    return response.json()["session_id"]


# ── Dashboard ─────────────────────────────────────────────────────────────────

def test_dashboard_returns_200():
    response = client.get("/dashboard")
    assert response.status_code == 200


def test_dashboard_template_contains_session_action_link_hrefs():
    """Verify the template source contains the action-link href patterns.

    In TEST_MODE recent_sessions is [], so the rendered page won't show the
    links — read the template file directly instead.
    """
    with open("templates/dashboard.html", encoding="utf-8") as f:
        source = f.read()
    assert "/topics/{{ s.session_id }}" in source
    assert "/todos/{{ s.session_id }}"  in source
    assert "/syllabus/{{ s.session_id }}" in source
    assert "session-action-link" in source


# ── Syllabus page ─────────────────────────────────────────────────────────────

def test_syllabus_contains_browse_module_topics_link():
    session_id = _start_session()
    response = client.get(f"/syllabus/{session_id}")
    assert response.status_code == 200
    assert "Browse Module Topics" in response.text


def test_syllabus_contains_my_planner_link():
    session_id = _start_session()
    response = client.get(f"/syllabus/{session_id}")
    assert response.status_code == 200
    assert "My Planner" in response.text


def test_syllabus_browse_topics_link_points_to_correct_url():
    session_id = _start_session()
    response = client.get(f"/syllabus/{session_id}")
    assert f"/topics/{session_id}" in response.text


def test_syllabus_planner_link_points_to_correct_url():
    session_id = _start_session()
    response = client.get(f"/syllabus/{session_id}")
    assert f"/todos/{session_id}" in response.text


# ── Topics page ───────────────────────────────────────────────────────────────

def test_topics_contains_back_to_dashboard_link():
    session_id = _start_session()
    response = client.get(f"/topics/{session_id}")
    assert response.status_code == 200
    assert "Back to Dashboard" in response.text


def test_topics_back_to_dashboard_points_to_dashboard():
    session_id = _start_session()
    response = client.get(f"/topics/{session_id}")
    assert "/dashboard" in response.text


def test_topics_still_has_view_syllabus_link():
    session_id = _start_session()
    response = client.get(f"/topics/{session_id}")
    assert "View Syllabus" in response.text


def test_topics_still_has_my_planner_link():
    session_id = _start_session()
    response = client.get(f"/topics/{session_id}")
    assert "My Planner" in response.text


# ── Topic detail page ─────────────────────────────────────────────────────────

def test_topic_detail_contains_view_syllabus_link():
    session_id = _start_session()
    topic = get_topics_for_week("aipm", 1)[0]
    response = client.get(f"/topic/{session_id}/{topic.topic_id}")
    assert response.status_code == 200
    assert "View Syllabus" in response.text


def test_topic_detail_view_syllabus_points_to_correct_url():
    session_id = _start_session()
    topic = get_topics_for_week("aipm", 1)[0]
    response = client.get(f"/topic/{session_id}/{topic.topic_id}")
    assert f"/syllabus/{session_id}" in response.text


def test_topic_detail_still_has_open_my_planner_link():
    session_id = _start_session()
    topic = get_topics_for_week("aipm", 1)[0]
    response = client.get(f"/topic/{session_id}/{topic.topic_id}")
    assert "Open My Planner" in response.text
