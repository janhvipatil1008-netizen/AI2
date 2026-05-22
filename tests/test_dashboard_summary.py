import os

os.environ["AI2_TEST_MODE"] = "1"
os.environ["ANTHROPIC_API_KEY"] = "test-key"

from fastapi.testclient import TestClient

from app import app, _sessions, build_dashboard_learning_summary
from curriculum.topics import get_topics_for_week

client = TestClient(app)


def _start_session(track: str = "aipm", week: int = 1) -> str:
    r = client.post("/session/start", json={"track": track, "week": week})
    assert r.status_code == 200, r.text
    return r.json()["session_id"]


def _get_session(session_id: str):
    return _sessions[session_id]["session"]


# ── Rendering ──────────────────────────────────────────────────────────────────

def test_dashboard_shows_learning_summary_when_session_exists():
    _start_session()
    r = client.get("/dashboard")
    assert r.status_code == 200
    assert "Your Learning Summary" in r.text


def test_dashboard_summary_shows_module_progress_card():
    _start_session()
    r = client.get("/dashboard")
    assert "Module" in r.text
    assert "Progress" in r.text


def test_dashboard_summary_shows_planner_card():
    _start_session()
    r = client.get("/dashboard")
    assert "Planner" in r.text
    assert "Daily todos" in r.text


def test_dashboard_summary_shows_practice_card():
    _start_session()
    r = client.get("/dashboard")
    assert "Practice" in r.text
    assert "Quiz evaluations" in r.text
    assert "Portfolio reviews" in r.text
    assert "Interview feedback" in r.text
    assert "Reflections saved" in r.text


# ── helper: zero state ─────────────────────────────────────────────────────────

def test_summary_helper_zero_for_fresh_session():
    sid     = _start_session()
    session = _get_session(sid)
    summary = build_dashboard_learning_summary(session)
    assert summary["average_completion_percent"] == 0
    assert summary["completed_topics"] == 0
    assert summary["total_todos"] == 0
    assert summary["quiz_evaluations_done"] == 0
    assert summary["portfolio_reviews_done"] == 0
    assert summary["interview_feedback_done"] == 0
    assert summary["reflections_saved"] == 0


def test_summary_helper_total_topics_matches_curriculum():
    sid     = _start_session()
    session = _get_session(sid)
    summary = build_dashboard_learning_summary(session)
    expected = len(get_topics_for_week("aipm", 1))
    assert summary["total_topics"] == expected
    assert summary["not_started_topics"] == expected


# ── helper: topic progress ─────────────────────────────────────────────────────

def test_summary_avg_increases_after_completing_all_steps():
    sid     = _start_session()
    session = _get_session(sid)
    topics  = get_topics_for_week("aipm", 1)
    topic_id = topics[0].topic_id

    for step in ["learn", "quiz", "portfolio_task", "interview_practice", "reflection"]:
        client.post("/topic/progress", json={
            "session_id": sid, "topic_id": topic_id,
            "step": step, "status": "done",
        })

    summary = build_dashboard_learning_summary(_get_session(sid))
    assert summary["average_completion_percent"] > 0
    assert summary["completed_topics"] == 1
    assert summary["not_started_topics"] == summary["total_topics"] - 1


def test_summary_in_progress_counted_when_one_step_done():
    sid      = _start_session()
    topics   = get_topics_for_week("aipm", 1)
    topic_id = topics[0].topic_id

    client.post("/topic/progress", json={
        "session_id": sid, "topic_id": topic_id,
        "step": "learn", "status": "done",
    })

    summary = build_dashboard_learning_summary(_get_session(sid))
    assert summary["in_progress_topics"] == 1
    assert summary["completed_topics"] == 0


# ── helper: todos ──────────────────────────────────────────────────────────────

def test_summary_todo_counts_update_after_create():
    sid     = _start_session()
    client.post("/todos/create", json={"session_id": sid, "title": "Daily task", "todo_type": "daily"})
    client.post("/todos/create", json={"session_id": sid, "title": "Weekly task", "todo_type": "weekly"})

    summary = build_dashboard_learning_summary(_get_session(sid))
    assert summary["total_todos"] == 2
    assert summary["daily_todos"] == 1
    assert summary["weekly_todos"] == 1


def test_summary_done_todos_counted():
    sid     = _start_session()
    client.post("/todos/create", json={"session_id": sid, "title": "Task A", "todo_type": "daily"})
    session = _get_session(sid)
    todo_id = session.get_todos()[0]["todo_id"]
    client.post("/todos/status", json={"session_id": sid, "todo_id": todo_id, "status": "done"})

    summary = build_dashboard_learning_summary(_get_session(sid))
    assert summary["done_todos"] == 1


# ── helper: practice & reflection ─────────────────────────────────────────────

def test_summary_quiz_evaluation_counted():
    sid      = _start_session()
    topics   = get_topics_for_week("aipm", 1)
    topic_id = topics[0].topic_id

    client.post("/quiz/submit",   json={"session_id": sid, "topic_id": topic_id, "answers": "My answers"})
    client.post("/quiz/evaluate", json={"session_id": sid, "topic_id": topic_id, "refresh": False})

    summary = build_dashboard_learning_summary(_get_session(sid))
    assert summary["quiz_evaluations_done"] == 1


def test_summary_portfolio_review_counted():
    sid      = _start_session()
    topics   = get_topics_for_week("aipm", 1)
    topic_id = topics[0].topic_id

    client.post("/portfolio/submit",   json={"session_id": sid, "topic_id": topic_id, "submission": "My work"})
    client.post("/portfolio/feedback", json={"session_id": sid, "topic_id": topic_id, "refresh": False})

    summary = build_dashboard_learning_summary(_get_session(sid))
    assert summary["portfolio_reviews_done"] == 1


def test_summary_interview_feedback_counted():
    sid      = _start_session()
    topics   = get_topics_for_week("aipm", 1)
    topic_id = topics[0].topic_id

    client.post("/interview/submit",   json={"session_id": sid, "topic_id": topic_id, "answer": "My answer"})
    client.post("/interview/feedback", json={"session_id": sid, "topic_id": topic_id, "refresh": False})

    summary = build_dashboard_learning_summary(_get_session(sid))
    assert summary["interview_feedback_done"] == 1


def test_summary_reflection_counted_after_notes_save():
    sid      = _start_session()
    topics   = get_topics_for_week("aipm", 1)
    topic_id = topics[0].topic_id

    client.post("/topic/notes", json={
        "session_id":      sid,
        "topic_id":        topic_id,
        "reflection":      "I learned a lot",
        "confusions":      "",
        "application_idea": "",
    })

    summary = build_dashboard_learning_summary(_get_session(sid))
    assert summary["reflections_saved"] == 1


# ── Links in rendered page ─────────────────────────────────────────────────────

def test_dashboard_summary_links_to_topics_page():
    sid = _start_session()
    r   = client.get("/dashboard")
    assert f"/topics/{sid}" in r.text


def test_dashboard_summary_links_to_todos_page():
    sid = _start_session()
    r   = client.get("/dashboard")
    assert f"/todos/{sid}" in r.text
