import os

os.environ["AI2_TEST_MODE"] = "1"
os.environ["ANTHROPIC_API_KEY"] = "test-key"

from fastapi.testclient import TestClient

from app import app

client = TestClient(app)


def _start_session(track: str = "aipm", week: int = 1) -> str:
    response = client.post("/session/start", json={"track": track, "week": week})
    assert response.status_code == 200, response.text
    return response.json()["session_id"]


def _create_todo(session_id: str, title: str = "Test task", todo_type: str = "daily") -> dict:
    response = client.post("/todos/create", json={
        "session_id": session_id,
        "title":      title,
        "todo_type":  todo_type,
    })
    assert response.status_code == 200, response.text
    return response.json()


# ── Page ──────────────────────────────────────────────────────────────────────

def test_todos_page_returns_200():
    session_id = _start_session()
    response = client.get(f"/todos/{session_id}")
    assert response.status_code == 200
    assert "My Learning Planner" in response.text


def test_todos_page_shows_planner_sections():
    session_id = _start_session()
    response = client.get(f"/todos/{session_id}")
    assert "Daily" in response.text or "daily" in response.text.lower()
    assert "Weekly" in response.text or "weekly" in response.text.lower()


# ── Create ────────────────────────────────────────────────────────────────────

def test_todos_create_creates_todo():
    session_id = _start_session()
    response = client.post("/todos/create", json={
        "session_id": session_id,
        "title":      "Read the paper",
        "todo_type":  "daily",
    })
    assert response.status_code == 200
    data = response.json()
    assert data["todo"]["title"]     == "Read the paper"
    assert data["todo"]["status"]    == "todo"
    assert data["todo"]["todo_type"] == "daily"
    assert "todo_id" in data["todo"]
    assert data["todo_counts"]["total"] == 1


def test_todos_create_weekly_type():
    session_id = _start_session()
    response = client.post("/todos/create", json={
        "session_id": session_id,
        "title":      "Build pipeline",
        "todo_type":  "weekly",
        "due_label":  "Friday",
    })
    assert response.status_code == 200
    data = response.json()
    assert data["todo"]["todo_type"] == "weekly"
    assert data["todo"]["due_label"] == "Friday"


def test_todos_create_invalid_type_returns_422():
    session_id = _start_session()
    response = client.post("/todos/create", json={
        "session_id": session_id,
        "title":      "Task",
        "todo_type":  "monthly",
    })
    assert response.status_code == 422


def test_todos_create_empty_title_returns_422():
    session_id = _start_session()
    response = client.post("/todos/create", json={
        "session_id": session_id,
        "title":      "   ",
        "todo_type":  "daily",
    })
    assert response.status_code == 422


def test_todos_create_invalid_linked_topic_returns_404():
    session_id = _start_session()
    response = client.post("/todos/create", json={
        "session_id":       session_id,
        "title":            "Task linked to bad topic",
        "todo_type":        "daily",
        "linked_topic_id":  "nonexistent-topic-xyz",
    })
    assert response.status_code == 404


# ── Status ────────────────────────────────────────────────────────────────────

def test_todos_status_updates_to_done():
    session_id = _start_session()
    data = _create_todo(session_id)
    todo_id = data["todo"]["todo_id"]

    response = client.post("/todos/status", json={
        "session_id": session_id,
        "todo_id":    todo_id,
        "status":     "done",
    })
    assert response.status_code == 200
    result = response.json()
    assert result["todo"]["status"]    == "done"
    assert result["todo_counts"]["done"] == 1


def test_todos_status_updates_to_in_progress():
    session_id = _start_session()
    data = _create_todo(session_id)
    todo_id = data["todo"]["todo_id"]

    response = client.post("/todos/status", json={
        "session_id": session_id,
        "todo_id":    todo_id,
        "status":     "in_progress",
    })
    assert response.status_code == 200
    assert response.json()["todo"]["status"] == "in_progress"


def test_todos_status_missing_todo_returns_404():
    session_id = _start_session()
    response = client.post("/todos/status", json={
        "session_id": session_id,
        "todo_id":    "nonexistent-todo-id",
        "status":     "done",
    })
    assert response.status_code == 404


def test_todos_status_invalid_status_returns_422():
    session_id = _start_session()
    data = _create_todo(session_id)
    response = client.post("/todos/status", json={
        "session_id": session_id,
        "todo_id":    data["todo"]["todo_id"],
        "status":     "cancelled",
    })
    assert response.status_code == 422


# ── Persistence ───────────────────────────────────────────────────────────────

def test_todo_appears_in_planner_page_after_create():
    session_id = _start_session()
    _create_todo(session_id, title="Learn transformers", todo_type="daily")

    response = client.get(f"/todos/{session_id}")
    assert response.status_code == 200
    assert "Learn transformers" in response.text


def test_todo_counts_update_after_multiple_creates():
    session_id = _start_session()
    _create_todo(session_id, title="Task 1", todo_type="daily")
    _create_todo(session_id, title="Task 2", todo_type="weekly")
    data = _create_todo(session_id, title="Task 3", todo_type="daily")
    assert data["todo_counts"]["total"] == 3
