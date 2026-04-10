"""
Phase 2.2 — Orchestrator & Session Flow Tests
"Does conversation routing work end-to-end?"

Covers:
  - Session creation for all three tracks
  - /chat routing to correct agent based on message type
  - Session history accumulation
  - Progress counters update after each exchange
  - Empty message rejected gracefully
  - Invalid session_id returns 404
  - Chat page (UI) loads and shows sidebar stats
"""


# ── Session creation ──────────────────────────────────────────────────────────

def test_start_session_aipm(api):
    """Starting an AIPM session returns a session_id and correct track metadata."""
    r = api.post("/session/start", json={"track": "aipm", "week": 1})
    assert r.status_code == 200
    data = r.json()
    assert "session_id" in data
    assert data["progress"]["track"] == "aipm"
    assert data["progress"]["track_label"] == "AI Product Manager"
    assert data["progress"]["current_week"] == 1
    assert data["progress"]["total_weeks"] == 13


def test_start_session_evals(api):
    r = api.post("/session/start", json={"track": "evals", "week": 8})
    assert r.status_code == 200
    data = r.json()
    assert data["progress"]["track"] == "evals"
    assert data["progress"]["current_week"] == 8


def test_start_session_context(api):
    r = api.post("/session/start", json={"track": "context", "week": 6})
    assert r.status_code == 200
    data = r.json()
    assert data["progress"]["track"] == "context"


def test_start_session_invalid_track(api):
    """An invalid track value returns 422."""
    r = api.post("/session/start", json={"track": "invalid_track"})
    assert r.status_code == 422


def test_start_session_week_clamped(api):
    """Weeks outside 1–13 are clamped, not errored."""
    r = api.post("/session/start", json={"track": "aipm", "week": 99})
    assert r.status_code == 200
    assert r.json()["progress"]["current_week"] == 13


# ── Routing: learning coach ───────────────────────────────────────────────────

def test_teaching_query_routes_to_learning_coach(api, session_aipm):
    sid = session_aipm["session_id"]
    r = api.post("/chat", json={"session_id": sid, "message": "What is attention in transformers?"})
    assert r.status_code == 200
    data = r.json()
    assert "response" in data
    assert len(data["response"]) > 50
    assert data["agent_used"] == "learning_coach"


def test_explain_query_routes_to_learning_coach(api, session_aipm):
    sid = session_aipm["session_id"]
    r = api.post("/chat", json={"session_id": sid, "message": "Explain RAG pipelines to me"})
    assert r.status_code == 200
    assert r.json()["agent_used"] == "learning_coach"


# ── Routing: practice arena ───────────────────────────────────────────────────

def test_quiz_request_routes_to_practice_arena(api, session_aipm):
    sid = session_aipm["session_id"]
    r = api.post("/chat", json={"session_id": sid, "message": "Quiz me on RAG"})
    assert r.status_code == 200
    data = r.json()
    assert data["agent_used"] == "practice_arena"
    assert "Q1." in data["response"] or "QUIZ" in data["response"]


def test_interview_request_routes_to_practice_arena(api, session_aipm):
    sid = session_aipm["session_id"]
    r = api.post("/chat", json={"session_id": sid, "message": "Give me interview prep questions"})
    assert r.status_code == 200
    assert r.json()["agent_used"] == "practice_arena"


# ── Routing: idea generator ───────────────────────────────────────────────────

def test_ideas_request_routes_to_idea_generator(api, session_aipm):
    sid = session_aipm["session_id"]
    r = api.post("/chat", json={"session_id": sid, "message": "Give me project ideas for RAG"})
    assert r.status_code == 200
    assert r.json()["agent_used"] == "idea_generator"


# ── Progress tracking ─────────────────────────────────────────────────────────

def test_exchanges_accumulate(api):
    """After 3 chat messages the exchanges counter equals 3."""
    r = api.post("/session/start", json={"track": "aipm", "week": 1})
    sid = r.json()["session_id"]

    for msg in ["What is an LLM?", "Explain tokens", "What is temperature?"]:
        api.post("/chat", json={"session_id": sid, "message": msg})

    r = api.get(f"/progress/{sid}")
    assert r.status_code == 200
    assert r.json()["exchanges"] == 3


def test_progress_endpoint_returns_all_fields(api, session_aipm):
    sid = session_aipm["session_id"]
    r = api.get(f"/progress/{sid}")
    assert r.status_code == 200
    data = r.json()
    for field in ["track", "track_label", "current_week", "total_weeks",
                  "phase_id", "phase_title", "exchanges", "exercises_done",
                  "tasks_done", "quizzes_taken", "goals"]:
        assert field in data, f"Missing field: {field}"


# ── Error handling ────────────────────────────────────────────────────────────

def test_empty_message_rejected(api, session_aipm):
    """Sending an empty message returns 422, not a server crash."""
    r = api.post("/chat", json={"session_id": session_aipm["session_id"], "message": ""})
    assert r.status_code == 422


def test_invalid_session_id_returns_404(api):
    """Using a nonexistent session_id returns 404."""
    r = api.post("/chat", json={"session_id": "00000000-dead-beef-0000-000000000000",
                                "message": "hello"})
    assert r.status_code == 404


def test_progress_invalid_session_returns_404(api):
    r = api.get("/progress/nonexistent-session")
    assert r.status_code == 404


# ── Chat UI page ──────────────────────────────────────────────────────────────

def test_chat_page_loads(api, session_aipm, page):
    """The /chat/<id> page loads and shows the sidebar with correct track."""
    sid = session_aipm["session_id"]
    page.goto(f"/chat/{sid}")

    # Sidebar track badge
    badge = page.locator(".track-badge")
    assert badge.is_visible()
    assert "AI Product Manager" in badge.inner_text()


def test_chat_page_shows_quick_actions(api, session_aipm, page):
    """Quick action buttons are rendered in the sidebar."""
    sid = session_aipm["session_id"]
    page.goto(f"/chat/{sid}")
    buttons = page.locator(".qa-btn")
    assert buttons.count() >= 3


def test_chat_page_has_input_bar(api, session_aipm, page):
    """The textarea input and send button are present and enabled."""
    sid = session_aipm["session_id"]
    page.goto(f"/chat/{sid}")
    assert page.locator("#user-input").is_visible()
    assert page.locator("#send-btn").is_visible()
    assert page.locator("#send-btn").is_enabled()


def test_chat_page_stat_counters_visible(api, session_aipm, page):
    """Sidebar stat counters (Exchanges, Exercises, etc.) are rendered."""
    sid = session_aipm["session_id"]
    page.goto(f"/chat/{sid}")
    for stat_id in ["stat-exchanges", "stat-exercises", "stat-tasks", "stat-quizzes"]:
        assert page.locator(f"#{stat_id}").is_visible(), f"#{stat_id} not visible"
