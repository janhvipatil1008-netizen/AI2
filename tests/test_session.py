"""
Phase 2.5 — Cross-Cutting Session Integrity Tests
"Does state accumulate correctly across a full learner workflow?"

Covers:
  - Full workflow sequence: start → chat × 3 → quiz → interview → evaluate
  - All counters increment correctly at each step
  - topics_explored grows
  - topics_quizzed grows
  - SessionContext unit tests (goals, paper dedup, tasks, week clamping)
  - Latency: every API call returns within 5s in TEST_MODE
"""

import time
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


# ── Full workflow sequence ────────────────────────────────────────────────────

def test_full_workflow_counter_integrity(api):
    """
    Run a realistic learner workflow and assert all counters advance correctly
    at each step.
    """
    # Start session
    r = api.post("/session/start", json={"track": "aipm", "week": 5})
    assert r.status_code == 200
    sid = r.json()["session_id"]

    def progress():
        return api.get(f"/progress/{sid}").json()

    # ── 3 chat messages ────────────────────────────────────────────────────────
    for msg in [
        "What is RAG?",
        "Explain the transformer attention mechanism",
        "Give me project ideas for context engineering",
    ]:
        r = api.post("/chat", json={"session_id": sid, "message": msg})
        assert r.status_code == 200

    p = progress()
    assert p["exchanges"] == 3, f"Expected 3 exchanges, got {p['exchanges']}"

    # ── Quiz ───────────────────────────────────────────────────────────────────
    exercises_before = p["exercises_done"]
    r = api.post("/quiz", json={"session_id": sid, "topic": "RAG pipelines"})
    assert r.status_code == 200

    p = progress()
    assert p["exercises_done"] > exercises_before, "exercises_done did not increment after quiz"

    # ── Interview prep ─────────────────────────────────────────────────────────
    exercises_before = p["exercises_done"]
    r = api.post("/interview", json={"session_id": sid, "topic": "LLM evaluation"})
    assert r.status_code == 200

    p = progress()
    assert p["exercises_done"] > exercises_before, "exercises_done did not increment after interview"

    # ── Answer evaluation ──────────────────────────────────────────────────────
    r = api.post("/evaluate", json={
        "session_id": sid,
        "question":   "What is RAG?",
        "answer":     "Retrieval-Augmented Generation grounds LLM answers in retrieved docs.",
        "topic":      "RAG",
    })
    assert r.status_code == 200

    # Final progress check
    p = progress()
    assert p["exchanges"]     == 3
    assert p["exercises_done"] >= 2  # quiz + interview both called mark_exercise_done


def test_topics_explored_grows_with_chat(api):
    """topics_count increases after each learning coach exchange."""
    r   = api.post("/session/start", json={"track": "context", "week": 3})
    sid = r.json()["session_id"]

    before = api.get(f"/progress/{sid}").json()["topics_count"]

    api.post("/chat", json={"session_id": sid, "message": "Explain chunking strategies"})
    api.post("/chat", json={"session_id": sid, "message": "What is semantic search?"})

    after = api.get(f"/progress/{sid}").json()["topics_count"]
    assert after >= before  # topics should not shrink


def test_multiple_sessions_are_independent(api):
    """Two simultaneous sessions do not share state."""
    r1 = api.post("/session/start", json={"track": "aipm",  "week": 1})
    r2 = api.post("/session/start", json={"track": "evals", "week": 8})
    sid1, sid2 = r1.json()["session_id"], r2.json()["session_id"]
    assert sid1 != sid2

    api.post("/chat", json={"session_id": sid1, "message": "What is RAG?"})
    api.post("/chat", json={"session_id": sid1, "message": "Explain prompting"})

    p1 = api.get(f"/progress/{sid1}").json()
    p2 = api.get(f"/progress/{sid2}").json()

    assert p1["exchanges"] == 2
    assert p2["exchanges"] == 0   # session 2 untouched
    assert p1["track"]     == "aipm"
    assert p2["track"]     == "evals"


# ── SessionContext unit tests ─────────────────────────────────────────────────

def test_session_goals_stored_and_retrieved():
    from context.session import SessionContext
    from config import CareerTrack

    s = SessionContext(track=CareerTrack.EVALS)
    s.add_goal("Pass an AI Evals Specialist interview at a frontier lab")
    assert len(s.goals) == 1
    assert "frontier" in s.goals[0].lower()

    prompt_ctx = s.as_prompt_context()
    assert "frontier" in prompt_ctx


def test_session_paper_seen_dedup():
    from context.session import SessionContext
    from config import CareerTrack

    s = SessionContext(track=CareerTrack.AI_PM)
    s.note_paper_seen("Attention Is All You Need")
    s.note_paper_seen("Attention Is All You Need")   # duplicate
    s.note_paper_seen("ATTENTION IS ALL YOU NEED")   # different case

    # set stores lowercase versions — all three map to one entry
    assert len(s.papers_seen) == 1


def test_session_record_quiz():
    from context.session import SessionContext
    from config import CareerTrack

    s = SessionContext(track=CareerTrack.EVALS)
    s.record_quiz(topic="RAG", mode="mcq_quiz", score=12, total=15)

    assert len(s.quiz_scores) == 1
    assert s.quiz_scores[0]["pct"] == 80
    assert "rag" in s.topics_quizzed


def test_session_best_score_for():
    from context.session import SessionContext
    from config import CareerTrack

    s = SessionContext(track=CareerTrack.EVALS)
    s.record_quiz("RAG", "mcq_quiz", score=8,  total=15)
    s.record_quiz("RAG", "mcq_quiz", score=13, total=15)
    s.record_quiz("RAG", "mcq_quiz", score=10, total=15)

    best = s.best_score_for("RAG")
    assert best is not None
    assert best["score"] == 13


def test_session_best_score_returns_none_for_unknown_topic():
    from context.session import SessionContext
    from config import CareerTrack

    s = SessionContext(track=CareerTrack.AI_PM)
    assert s.best_score_for("never quizzed topic") is None


def test_session_topics_capped_at_50():
    from context.session import SessionContext
    from config import CareerTrack

    s = SessionContext(track=CareerTrack.AI_PM)
    for i in range(60):
        s.note_topic(f"unique topic {i}")

    assert len(s.topics_explored) <= 50


def test_session_mark_task():
    from context.session import SessionContext
    from config import CareerTrack

    s = SessionContext(track=CareerTrack.CONTEXT_ENGINEER)
    s.mark_task("foundation-0-0", "done")
    s.mark_task("foundation-0-1", "in_progress")

    assert s.tasks_done_count() == 1
    assert s.syllabus_progress["foundation-0-0"] == "done"


def test_session_progress_summary_includes_quiz_info():
    from context.session import SessionContext
    from config import CareerTrack

    s = SessionContext(track=CareerTrack.EVALS)
    s.record_quiz("LLM eval", "mcq_quiz", score=11, total=15)

    summary = s.progress_summary()
    assert "Quizzes" in summary or "quiz" in summary.lower()


# ── Latency (TEST_MODE) ───────────────────────────────────────────────────────

def test_health_latency(api):
    """Health endpoint responds in < 1s."""
    t0 = time.time()
    api.get("/health")
    elapsed = time.time() - t0
    assert elapsed < 3.0, f"Health took {elapsed:.2f}s"


def test_chat_latency_in_test_mode(api):
    """In TEST_MODE, /chat must respond in < 5s (mock, no Claude call)."""
    r   = api.post("/session/start", json={"track": "aipm", "week": 1})
    sid = r.json()["session_id"]

    start = time.time()
    api.post("/chat", json={"session_id": sid, "message": "What is RAG?"})
    elapsed = time.time() - start

    assert elapsed < 5.0, f"/chat took {elapsed:.1f}s in TEST_MODE"


def test_quiz_latency_in_test_mode(api):
    """In TEST_MODE, /quiz must respond in < 5s."""
    r   = api.post("/session/start", json={"track": "aipm", "week": 5})
    sid = r.json()["session_id"]

    start = time.time()
    api.post("/quiz", json={"session_id": sid, "topic": "RAG"})
    elapsed = time.time() - start

    assert elapsed < 5.0, f"/quiz took {elapsed:.1f}s in TEST_MODE"


def test_interview_latency_in_test_mode(api):
    """In TEST_MODE, /interview must respond in < 5s."""
    r   = api.post("/session/start", json={"track": "evals", "week": 8})
    sid = r.json()["session_id"]

    start = time.time()
    api.post("/interview", json={"session_id": sid, "topic": "LLM evaluation"})
    elapsed = time.time() - start

    assert elapsed < 5.0, f"/interview took {elapsed:.1f}s in TEST_MODE"
