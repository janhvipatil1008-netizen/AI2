import os

os.environ["AI2_TEST_MODE"] = "1"
os.environ["ANTHROPIC_API_KEY"] = "test-key"

from fastapi.testclient import TestClient

from app import app
from config import CareerTrack
from context.session import SessionContext, VALID_PRACTICE_TYPES
from curriculum.topics import get_topics_for_week

client = TestClient(app)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _start_session(track: str = "aipm", week: int = 1) -> str:
    response = client.post("/session/start", json={"track": track, "week": week})
    assert response.status_code == 200, response.text
    return response.json()["session_id"]


def _first_topic():
    return get_topics_for_week("aipm", 1)[0]


# ── Unit tests: SessionContext ────────────────────────────────────────────────

def test_generated_topic_practice_defaults_to_empty_dict():
    session = SessionContext(track=CareerTrack.AI_PM)
    assert session.generated_topic_practice == {}


def test_valid_practice_types_constant():
    assert VALID_PRACTICE_TYPES == frozenset({"quiz", "portfolio_task", "interview_practice"})


def test_get_generated_topic_practice_returns_safe_defaults_for_type():
    session = SessionContext(track=CareerTrack.AI_PM)
    result = session.get_generated_topic_practice("any-topic", "quiz")
    assert result["content"]         == ""
    assert result["generated_at"]    == ""
    assert result["model"]           == ""
    assert result["version"]         == 0
    assert result["freshness_label"] == ""


def test_get_generated_topic_practice_returns_all_types_when_none():
    session = SessionContext(track=CareerTrack.AI_PM)
    result = session.get_generated_topic_practice("any-topic")
    assert set(result.keys()) == {"quiz", "portfolio_task", "interview_practice"}
    for pt in result.values():
        assert pt["content"]  == ""
        assert pt["version"]  == 0


def test_save_generated_topic_practice_quiz():
    session = SessionContext(track=CareerTrack.AI_PM)
    saved = session.save_generated_topic_practice(
        topic_id="topic-1", practice_type="quiz",
        content="  Q1: What is X?  ", model="claude-test",
    )
    assert saved["content"]         == "Q1: What is X?"
    assert saved["model"]           == "claude-test"
    assert saved["version"]         == 1
    assert saved["generated_at"]    != ""
    assert saved["freshness_label"] == "AI-generated"
    assert "topic-1" in session.generated_topic_practice
    assert "quiz" in session.generated_topic_practice["topic-1"]


def test_save_generated_topic_practice_portfolio_task():
    session = SessionContext(track=CareerTrack.AI_PM)
    saved = session.save_generated_topic_practice(
        topic_id="topic-1", practice_type="portfolio_task",
        content="Build something.", model="m",
    )
    assert saved["content"] == "Build something."
    assert saved["version"] == 1


def test_save_generated_topic_practice_interview_practice():
    session = SessionContext(track=CareerTrack.AI_PM)
    saved = session.save_generated_topic_practice(
        topic_id="topic-1", practice_type="interview_practice",
        content="Q1: How would you…", model="m",
    )
    assert saved["content"] == "Q1: How would you…"
    assert saved["version"] == 1


def test_save_generated_topic_practice_increments_version():
    session = SessionContext(track=CareerTrack.AI_PM)
    session.save_generated_topic_practice("topic-1", "quiz", "v1", "m")
    saved = session.save_generated_topic_practice("topic-1", "quiz", "v2", "m")
    assert saved["version"] == 2
    assert session.get_generated_topic_practice("topic-1", "quiz")["version"] == 2


def test_save_generated_topic_practice_versions_are_independent_per_type():
    session = SessionContext(track=CareerTrack.AI_PM)
    session.save_generated_topic_practice("topic-1", "quiz",           "q1",  "m")
    session.save_generated_topic_practice("topic-1", "quiz",           "q2",  "m")
    session.save_generated_topic_practice("topic-1", "portfolio_task", "pt1", "m")
    assert session.get_generated_topic_practice("topic-1", "quiz")["version"]           == 2
    assert session.get_generated_topic_practice("topic-1", "portfolio_task")["version"] == 1


def test_save_generated_topic_practice_invalid_type_raises():
    session = SessionContext(track=CareerTrack.AI_PM)
    try:
        session.save_generated_topic_practice("topic-1", "bad_type", "x", "m")
        assert False, "Expected ValueError"
    except ValueError as exc:
        assert "bad_type" in str(exc)


def test_to_dict_from_dict_preserves_generated_topic_practice():
    session = SessionContext(track=CareerTrack.AI_PM)
    session.save_generated_topic_practice("topic-1", "quiz", "Q content", "claude-test")
    session.save_generated_topic_practice("topic-1", "portfolio_task", "PT content", "claude-test")
    restored = SessionContext.from_dict(session.to_dict())
    quiz_r = restored.get_generated_topic_practice("topic-1", "quiz")
    pt_r   = restored.get_generated_topic_practice("topic-1", "portfolio_task")
    assert quiz_r["content"] == "Q content"
    assert pt_r["content"]   == "PT content"
    assert quiz_r["version"] == 1


def test_from_dict_missing_generated_topic_practice_defaults_to_empty():
    session = SessionContext(track=CareerTrack.AI_PM)
    d = session.to_dict()
    del d["generated_topic_practice"]
    restored = SessionContext.from_dict(d)
    assert restored.generated_topic_practice == {}
    result = restored.get_generated_topic_practice("any-topic", "quiz")
    assert result["content"] == ""


# ── Route / template tests ────────────────────────────────────────────────────

def test_topic_detail_contains_ai_quiz_section():
    session_id = _start_session()
    topic = _first_topic()
    response = client.get(f"/topic/{session_id}/{topic.topic_id}")
    assert response.status_code == 200
    assert "AI Quiz" in response.text


def test_topic_detail_contains_ai_portfolio_task_section():
    session_id = _start_session()
    topic = _first_topic()
    response = client.get(f"/topic/{session_id}/{topic.topic_id}")
    assert response.status_code == 200
    assert "AI Portfolio Task" in response.text


def test_topic_detail_contains_ai_interview_practice_section():
    session_id = _start_session()
    topic = _first_topic()
    response = client.get(f"/topic/{session_id}/{topic.topic_id}")
    assert response.status_code == 200
    assert "AI Interview Practice" in response.text


def test_topic_detail_contains_generate_quiz_button():
    session_id = _start_session()
    topic = _first_topic()
    response = client.get(f"/topic/{session_id}/{topic.topic_id}")
    assert response.status_code == 200
    assert "Generate Quiz" in response.text


def test_topic_detail_contains_generate_portfolio_task_button():
    session_id = _start_session()
    topic = _first_topic()
    response = client.get(f"/topic/{session_id}/{topic.topic_id}")
    assert response.status_code == 200
    assert "Generate Portfolio Task" in response.text


def test_topic_detail_contains_generate_interview_practice_button():
    session_id = _start_session()
    topic = _first_topic()
    response = client.get(f"/topic/{session_id}/{topic.topic_id}")
    assert response.status_code == 200
    assert "Generate Interview Practice" in response.text


def test_practice_generate_returns_mock_quiz_in_test_mode():
    session_id = _start_session()
    topic = _first_topic()
    response = client.post("/topic/practice/generate", json={
        "session_id":    session_id,
        "topic_id":      topic.topic_id,
        "practice_type": "quiz",
        "refresh":       False,
    })
    assert response.status_code == 200
    data = response.json()
    assert data["topic_id"]      == topic.topic_id
    assert data["practice_type"] == "quiz"
    assert data["content"]       != ""
    assert data["generated_practice"]["version"] == 1


def test_practice_generate_returns_mock_portfolio_task_in_test_mode():
    session_id = _start_session()
    topic = _first_topic()
    response = client.post("/topic/practice/generate", json={
        "session_id":    session_id,
        "topic_id":      topic.topic_id,
        "practice_type": "portfolio_task",
    })
    assert response.status_code == 200
    assert "Portfolio Task" in response.json()["content"]


def test_practice_generate_returns_mock_interview_in_test_mode():
    session_id = _start_session()
    topic = _first_topic()
    response = client.post("/topic/practice/generate", json={
        "session_id":    session_id,
        "topic_id":      topic.topic_id,
        "practice_type": "interview_practice",
    })
    assert response.status_code == 200
    assert "Interview Questions" in response.json()["content"]


def test_practice_generate_cached_content_not_regenerated():
    session_id = _start_session()
    topic = _first_topic()

    # First call — generates mock
    r1 = client.post("/topic/practice/generate", json={
        "session_id":    session_id,
        "topic_id":      topic.topic_id,
        "practice_type": "quiz",
        "refresh":       False,
    })
    assert r1.status_code == 200
    first_content = r1.json()["content"]

    # Second call with refresh=false — must return cached (version stays 1)
    r2 = client.post("/topic/practice/generate", json={
        "session_id":    session_id,
        "topic_id":      topic.topic_id,
        "practice_type": "quiz",
        "refresh":       False,
    })
    assert r2.status_code == 200
    assert r2.json()["content"]                          == first_content
    assert r2.json()["generated_practice"]["version"]    == 1


def test_practice_generate_refresh_increments_version():
    session_id = _start_session()
    topic = _first_topic()

    client.post("/topic/practice/generate", json={
        "session_id": session_id, "topic_id": topic.topic_id,
        "practice_type": "quiz", "refresh": False,
    })
    r2 = client.post("/topic/practice/generate", json={
        "session_id": session_id, "topic_id": topic.topic_id,
        "practice_type": "quiz", "refresh": True,
    })
    assert r2.status_code == 200
    assert r2.json()["generated_practice"]["version"] == 2


def test_practice_generate_marks_quiz_step_in_progress():
    session_id = _start_session()
    topic = _first_topic()

    client.post("/topic/practice/generate", json={
        "session_id": session_id, "topic_id": topic.topic_id,
        "practice_type": "quiz",
    })
    response = client.get(f"/topic/{session_id}/{topic.topic_id}")
    assert response.status_code == 200
    assert "In Progress" in response.text


def test_practice_generate_marks_portfolio_task_step_in_progress():
    session_id = _start_session()
    topic = _first_topic()

    client.post("/topic/practice/generate", json={
        "session_id": session_id, "topic_id": topic.topic_id,
        "practice_type": "portfolio_task",
    })
    response = client.get(f"/topic/{session_id}/{topic.topic_id}")
    assert response.status_code == 200
    assert "In Progress" in response.text


def test_practice_generate_marks_interview_step_in_progress():
    session_id = _start_session()
    topic = _first_topic()

    client.post("/topic/practice/generate", json={
        "session_id": session_id, "topic_id": topic.topic_id,
        "practice_type": "interview_practice",
    })
    response = client.get(f"/topic/{session_id}/{topic.topic_id}")
    assert response.status_code == 200
    assert "In Progress" in response.text


def test_topic_detail_renders_existing_quiz_content():
    session_id = _start_session()
    topic = _first_topic()

    client.post("/topic/practice/generate", json={
        "session_id": session_id, "topic_id": topic.topic_id,
        "practice_type": "quiz",
    })
    response = client.get(f"/topic/{session_id}/{topic.topic_id}")
    assert response.status_code == 200
    assert "5 Questions" in response.text
    assert "Refresh Quiz" in response.text


def test_topic_detail_renders_existing_portfolio_task_content():
    session_id = _start_session()
    topic = _first_topic()

    client.post("/topic/practice/generate", json={
        "session_id": session_id, "topic_id": topic.topic_id,
        "practice_type": "portfolio_task",
    })
    response = client.get(f"/topic/{session_id}/{topic.topic_id}")
    assert response.status_code == 200
    assert "Bonus Challenge" in response.text
    assert "Refresh Portfolio Task" in response.text


def test_topic_detail_renders_existing_interview_practice_content():
    session_id = _start_session()
    topic = _first_topic()

    client.post("/topic/practice/generate", json={
        "session_id": session_id, "topic_id": topic.topic_id,
        "practice_type": "interview_practice",
    })
    response = client.get(f"/topic/{session_id}/{topic.topic_id}")
    assert response.status_code == 200
    assert "8 Interview Questions" in response.text
    assert "Refresh Interview Practice" in response.text


def test_practice_generate_invalid_topic_returns_404():
    session_id = _start_session()
    response = client.post("/topic/practice/generate", json={
        "session_id":    session_id,
        "topic_id":      "nonexistent-topic-xyz",
        "practice_type": "quiz",
    })
    assert response.status_code == 404


def test_practice_generate_invalid_practice_type_returns_422():
    session_id = _start_session()
    topic = _first_topic()
    response = client.post("/topic/practice/generate", json={
        "session_id":    session_id,
        "topic_id":      topic.topic_id,
        "practice_type": "bad_type",
    })
    assert response.status_code == 422


def test_practice_types_are_independent_per_topic():
    session_id = _start_session()
    topic = _first_topic()

    client.post("/topic/practice/generate", json={
        "session_id": session_id, "topic_id": topic.topic_id,
        "practice_type": "quiz",
    })

    # portfolio_task should still show generate button (not yet generated)
    response = client.get(f"/topic/{session_id}/{topic.topic_id}")
    assert response.status_code == 200
    assert "Generate Portfolio Task"     in response.text
    assert "Generate Interview Practice" in response.text
