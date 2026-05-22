import os
import re
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import MagicMock, patch

os.environ["AI2_TEST_MODE"] = "1"
os.environ["ANTHROPIC_API_KEY"] = "test-key"

from fastapi.testclient import TestClient

from app import app
from config import CareerTrack
from context.session import SessionContext
from curriculum.topics import get_topics_for_week


client = TestClient(app)
FLAG = "AI2_MODULAR_CURRICULUM_READS_ENABLED"


@contextmanager
def _conn_context():
    yield MagicMock()


def _start_session() -> str:
    response = client.post("/session/start", json={"track": "aipm", "week": 1})
    assert response.status_code == 200, response.text
    return response.json()["session_id"]


def _fake_course_result(title: str = "Modular Wording Topic"):
    topic = get_topics_for_week("aipm", 1)[0]
    return {
        "source": "db",
        "course_structure": {
            "course": {"course_key": "aipm-foundations", "title": "AI PM Foundations"},
            "modules": [
                {
                    "module_key": "module-01",
                    "title": "Modular Module",
                    "description": "Module description",
                    "sequence_order": 0,
                    "topics": [
                        {
                            "legacy_topic_id": topic.topic_id,
                            "topic_key": "modular-topic",
                            "title": title,
                            "description": "Modular topic description",
                            "sequence_order": 0,
                        }
                    ],
                }
            ],
            "unassigned_topics": [],
        },
        "error": None,
    }


def test_dashboard_no_longer_displays_week_x_of_5_to_learners(monkeypatch):
    monkeypatch.delenv(FLAG, raising=False)
    _start_session()

    response = client.get("/dashboard")

    assert response.status_code == 200
    assert "Module 1" in response.text
    assert "Week 1 / 5" not in response.text
    assert not re.search(r"Week\s+\d+\s*/\s*5", response.text)


def test_topics_page_uses_module_wording_when_static_flag_false(monkeypatch):
    monkeypatch.delenv(FLAG, raising=False)
    session_id = _start_session()

    with patch("database.pool.get_conn", side_effect=AssertionError("DB must not open")):
        response = client.get(f"/topics/{session_id}")

    assert response.status_code == 200
    assert "Module 1 Topics" in response.text
    assert "Topics for Week" not in response.text
    assert "Browse Week Topics" not in response.text


def test_topics_page_uses_module_wording_when_modular_flag_true(monkeypatch):
    monkeypatch.setenv(FLAG, "true")
    session_id = _start_session()

    with patch("database.pool.get_conn", return_value=_conn_context()), patch(
        "services.modular_curriculum_fallback_service.get_course_structure_with_fallback",
        return_value=_fake_course_result(),
    ):
        response = client.get(f"/topics/{session_id}")

    assert response.status_code == 200
    assert "Modular Wording Topic" in response.text
    assert "Module 1" in response.text
    assert "Week 1" not in response.text


def test_no_visible_13_week_copy_appears_in_templates():
    template_text = "\n".join(path.read_text(encoding="utf-8") for path in Path("templates").glob("*.html"))

    assert "13-week" not in template_text


def test_route_urls_remain_unchanged():
    paths = {route.path for route in app.routes}

    assert "/topics/{session_id}" in paths
    assert "/topic/{session_id}/{topic_id}" in paths
    assert "/topic/content/generate" in paths
    assert "/quiz/submit" in paths
    assert "/portfolio/submit" in paths
    assert "/interview/submit" in paths


def test_internal_current_week_remains_supported():
    session = SessionContext(track=CareerTrack.AI_PM, current_week=3)

    assert session.current_week == 3
    assert session.to_dict()["current_week"] == 3


def test_topic_detail_generation_and_submission_routes_still_render(monkeypatch):
    monkeypatch.delenv(FLAG, raising=False)
    session_id = _start_session()
    topic = get_topics_for_week("aipm", 1)[0]

    response = client.get(f"/topic/{session_id}/{topic.topic_id}")

    assert response.status_code == 200
    assert topic.topic_title in response.text
    assert "Module Topics" in response.text
    assert "Add to Module Plan" in response.text
