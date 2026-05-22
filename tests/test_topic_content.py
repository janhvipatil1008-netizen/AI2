import os

os.environ["AI2_TEST_MODE"] = "1"
os.environ["ANTHROPIC_API_KEY"] = "test-key"

from fastapi.testclient import TestClient

from app import app
from config import CareerTrack
from context.session import SessionContext
from curriculum.topics import get_topics_for_week

client = TestClient(app)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _start_session(track: str = "aipm", week: int = 1) -> str:
    response = client.post("/session/start", json={"track": track, "week": week})
    assert response.status_code == 200, response.text
    return response.json()["session_id"]


# ── Unit tests: SessionContext ────────────────────────────────────────────────

def test_generated_topic_content_defaults_to_empty_dict():
    session = SessionContext(track=CareerTrack.AI_PM)
    assert session.generated_topic_content == {}


def test_get_generated_topic_content_returns_empty_default():
    session = SessionContext(track=CareerTrack.AI_PM)
    result = session.get_generated_topic_content("any-topic")
    assert result["content"]         == ""
    assert result["generated_at"]    == ""
    assert result["model"]           == ""
    assert result["version"]         == 0
    assert result["freshness_label"] == ""


def test_save_generated_topic_content_saves_content():
    session = SessionContext(track=CareerTrack.AI_PM)
    saved = session.save_generated_topic_content(
        topic_id="topic-1",
        content="  Some learning content.  ",
        model="claude-test",
        freshness_label="AI-generated",
    )
    assert saved["content"]         == "Some learning content."
    assert saved["model"]           == "claude-test"
    assert saved["freshness_label"] == "AI-generated"
    assert saved["generated_at"]    != ""
    assert saved["version"]         == 1
    assert "topic-1" in session.generated_topic_content


def test_save_generated_topic_content_increments_version():
    session = SessionContext(track=CareerTrack.AI_PM)
    session.save_generated_topic_content("topic-1", content="v1", model="m")
    saved = session.save_generated_topic_content("topic-1", content="v2", model="m")
    assert saved["version"] == 2
    assert session.get_generated_topic_content("topic-1")["version"] == 2


def test_save_generated_topic_content_default_freshness_label():
    session = SessionContext(track=CareerTrack.AI_PM)
    saved = session.save_generated_topic_content("topic-1", content="x", model="m")
    assert saved["freshness_label"] == "AI-generated"


def test_to_dict_from_dict_preserves_generated_topic_content():
    session = SessionContext(track=CareerTrack.AI_PM)
    session.save_generated_topic_content("topic-1", content="Key insight", model="claude-test")
    restored = SessionContext.from_dict(session.to_dict())
    result = restored.get_generated_topic_content("topic-1")
    assert result["content"] == "Key insight"
    assert result["version"] == 1


def test_from_dict_missing_generated_topic_content_defaults_to_empty():
    session = SessionContext(track=CareerTrack.AI_PM)
    d = session.to_dict()
    del d["generated_topic_content"]
    restored = SessionContext.from_dict(d)
    assert restored.generated_topic_content == {}
    assert restored.get_generated_topic_content("any-topic")["content"] == ""


# ── Route / template tests ────────────────────────────────────────────────────

def test_topic_detail_contains_ai_learning_content_section():
    session_id = _start_session()
    topic = get_topics_for_week("aipm", 1)[0]

    response = client.get(f"/topic/{session_id}/{topic.topic_id}")

    assert response.status_code == 200
    assert "AI Learning Content" in response.text


def test_topic_detail_contains_generate_button_when_no_content():
    session_id = _start_session()
    topic = get_topics_for_week("aipm", 1)[0]

    response = client.get(f"/topic/{session_id}/{topic.topic_id}")

    assert response.status_code == 200
    assert "Generate Learning Content" in response.text


def test_generate_endpoint_returns_mock_content_in_test_mode():
    session_id = _start_session()
    topic = get_topics_for_week("aipm", 1)[0]

    response = client.post("/topic/content/generate", json={
        "session_id": session_id,
        "topic_id":   topic.topic_id,
        "refresh":    False,
    })

    assert response.status_code == 200
    data = response.json()
    assert data["topic_id"] == topic.topic_id
    assert data["content"]  != ""
    assert "generated_topic_content" in data
    assert data["generated_topic_content"]["version"] == 1


def test_generate_returns_cached_content_without_claude_when_refresh_false():
    session_id = _start_session()
    topic = get_topics_for_week("aipm", 1)[0]

    # First call — generates (mock in TEST_MODE)
    r1 = client.post("/topic/content/generate", json={
        "session_id": session_id,
        "topic_id":   topic.topic_id,
        "refresh":    False,
    })
    assert r1.status_code == 200
    first_content = r1.json()["content"]

    # Second call with refresh=false — must return cached (version stays 1)
    r2 = client.post("/topic/content/generate", json={
        "session_id": session_id,
        "topic_id":   topic.topic_id,
        "refresh":    False,
    })
    assert r2.status_code == 200
    assert r2.json()["content"]                              == first_content
    assert r2.json()["generated_topic_content"]["version"]   == 1


def test_generate_refresh_true_increments_version():
    session_id = _start_session()
    topic = get_topics_for_week("aipm", 1)[0]

    client.post("/topic/content/generate", json={
        "session_id": session_id,
        "topic_id":   topic.topic_id,
        "refresh":    False,
    })
    r2 = client.post("/topic/content/generate", json={
        "session_id": session_id,
        "topic_id":   topic.topic_id,
        "refresh":    True,
    })
    assert r2.status_code == 200
    assert r2.json()["generated_topic_content"]["version"] == 2


def test_topic_detail_renders_existing_content():
    session_id = _start_session()
    topic = get_topics_for_week("aipm", 1)[0]

    # Generate content first
    client.post("/topic/content/generate", json={
        "session_id": session_id,
        "topic_id":   topic.topic_id,
    })

    # Reload the detail page and confirm content appears
    response = client.get(f"/topic/{session_id}/{topic.topic_id}")
    assert response.status_code == 200
    assert "Simple Explanation" in response.text
    assert "Refresh Content"    in response.text


def test_generate_marks_learn_in_progress_when_not_started():
    session_id = _start_session()
    topic = get_topics_for_week("aipm", 1)[0]

    client.post("/topic/content/generate", json={
        "session_id": session_id,
        "topic_id":   topic.topic_id,
    })

    # The topic detail page should now show "In Progress" for the learn step
    response = client.get(f"/topic/{session_id}/{topic.topic_id}")
    assert response.status_code == 200
    assert "In Progress" in response.text


def test_generate_invalid_topic_returns_404():
    session_id = _start_session()

    response = client.post("/topic/content/generate", json={
        "session_id": session_id,
        "topic_id":   "nonexistent-topic-xyz",
        "refresh":    False,
    })

    assert response.status_code == 404
