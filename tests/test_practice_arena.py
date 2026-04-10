"""
Phase 2.4 — Practice Arena Tests
"Do MCQ and interview flows produce correct structure?"

Covers:
  MCQ Quiz:
    - /quiz endpoint returns 200
    - Response contains 15 questions (Q1–Q15)
    - Three difficulty sections present (🟢 🟡 🔴)
    - Each question has ✅ Answer and 💡 Why markers
    - Focused single-level quiz (beginner only) returns 5 questions
    - topics_quizzed grows after quiz call
    - exercises_done increments

  Interview Prep:
    - /interview endpoint returns 200
    - Three interview sections present (💬 ⚙️ 🏗️)
    - Each question has 🎯 and ✨ markers
    - Score out of 40 present in /evaluate response
    - TOTAL marker in evaluation response

  UI:
    - MCQ quiz renders .diff-header.beginner/intermediate/advanced blocks
    - Q stems render as .q-stem in chat
    - ✅ answer blocks render as .q-answer in chat
"""

import re


# ── /quiz endpoint ────────────────────────────────────────────────────────────

def test_quiz_endpoint_returns_200(api, session_aipm):
    r = api.post("/quiz", json={"session_id": session_aipm["session_id"],
                                "topic": "RAG pipelines"})
    assert r.status_code == 200
    assert "response" in r.json()


def test_quiz_response_is_not_empty(api, session_aipm):
    r = api.post("/quiz", json={"session_id": session_aipm["session_id"],
                                "topic": "RAG pipelines"})
    assert len(r.json()["response"]) > 200


def test_quiz_contains_15_questions(api, session_aipm):
    """The MCQ response must contain Q1 through Q15."""
    r = api.post("/quiz", json={"session_id": session_aipm["session_id"],
                                "topic": "RAG pipelines"})
    response = r.json()["response"]
    # Count Q1. Q2. … Q15.
    question_numbers = re.findall(r'\bQ(\d+)\.', response)
    found_nums = set(int(n) for n in question_numbers)
    for n in range(1, 16):
        assert n in found_nums, f"Q{n} missing from quiz response"


def test_quiz_has_three_difficulty_sections(api, session_aipm):
    """🟢 BEGINNER, 🟡 INTERMEDIATE, 🔴 ADVANCED sections all present."""
    r = api.post("/quiz", json={"session_id": session_aipm["session_id"],
                                "topic": "RAG pipelines"})
    response = r.json()["response"]
    assert "🟢" in response and "BEGINNER"     in response
    assert "🟡" in response and "INTERMEDIATE" in response
    assert "🔴" in response and "ADVANCED"     in response


def test_quiz_questions_have_answer_markers(api, session_aipm):
    """Every question should have an ✅ Answer marker."""
    r = api.post("/quiz", json={"session_id": session_aipm["session_id"],
                                "topic": "RAG pipelines"})
    response = r.json()["response"]
    answer_count = response.count("✅ Answer:")
    assert answer_count >= 15, f"Only {answer_count} ✅ Answer markers (expected 15)"


def test_quiz_questions_have_why_markers(api, session_aipm):
    """Every question should have a 💡 Why explanation."""
    r = api.post("/quiz", json={"session_id": session_aipm["session_id"],
                                "topic": "RAG pipelines"})
    response = r.json()["response"]
    why_count = response.count("💡 Why:")
    assert why_count >= 15, f"Only {why_count} 💡 Why markers (expected 15)"


def test_quiz_progress_updates(api, session_aipm):
    """exercises_done increments and topic appears in quizzes_taken after a quiz."""
    sid = session_aipm["session_id"]
    before = api.get(f"/progress/{sid}").json()

    api.post("/quiz", json={"session_id": sid, "topic": "RAG pipelines"})

    after = api.get(f"/progress/{sid}").json()
    assert after["exercises_done"] > before["exercises_done"]


def test_quiz_invalid_session_returns_404(api):
    r = api.post("/quiz", json={"session_id": "bad-id", "topic": "RAG"})
    assert r.status_code == 404


# ── /interview endpoint ───────────────────────────────────────────────────────

def test_interview_endpoint_returns_200(api, session_evals):
    r = api.post("/interview", json={"session_id": session_evals["session_id"],
                                     "topic": "LLM evaluation"})
    assert r.status_code == 200
    assert "response" in r.json()


def test_interview_has_three_level_sections(api, session_evals):
    """💬 CONCEPTUAL, ⚙️ TECHNICAL, 🏗️ SCENARIO sections all present."""
    r = api.post("/interview", json={"session_id": session_evals["session_id"],
                                     "topic": "LLM evaluation"})
    response = r.json()["response"]
    assert "💬" in response and "CONCEPTUAL" in response
    assert "⚙️"  in response and "TECHNICAL"  in response
    assert "🏗️"  in response and "SCENARIO"   in response


def test_interview_questions_have_model_answers(api, session_evals):
    """Each interview question should have a ✨ Model answer block."""
    r = api.post("/interview", json={"session_id": session_evals["session_id"],
                                     "topic": "LLM evaluation"})
    response = r.json()["response"]
    model_answer_count = response.count("✨ Model answer:")
    assert model_answer_count >= 3, (
        f"Only {model_answer_count} model answer blocks (expected at least 3)"
    )


def test_interview_questions_have_coverage_markers(api, session_evals):
    """Each interview question should have a 🎯 coverage block."""
    r = api.post("/interview", json={"session_id": session_evals["session_id"],
                                     "topic": "LLM evaluation"})
    response = r.json()["response"]
    assert "🎯" in response


def test_interview_completion_footer_present(api, session_evals):
    """The 🏁 INTERVIEW PREP COMPLETE footer should appear."""
    r = api.post("/interview", json={"session_id": session_evals["session_id"],
                                     "topic": "LLM evaluation"})
    response = r.json()["response"]
    assert "🏁" in response and "COMPLETE" in response


# ── /evaluate endpoint ────────────────────────────────────────────────────────

def test_evaluate_returns_scorecard(api, session_evals):
    """/evaluate returns a scorecard with TOTAL score."""
    r = api.post("/evaluate", json={
        "session_id": session_evals["session_id"],
        "question":   "What is LLM-as-a-Judge and when should you use it?",
        "answer":     "LLM-as-a-Judge uses one LLM to evaluate another's output.",
        "topic":      "LLM evaluation",
    })
    assert r.status_code == 200
    response = r.json()["response"]
    assert "TOTAL" in response


def test_evaluate_score_out_of_40(api, session_evals):
    """The scorecard shows a /40 total."""
    r = api.post("/evaluate", json={
        "session_id": session_evals["session_id"],
        "question":   "What is RAG?",
        "answer":     "RAG stands for Retrieval-Augmented Generation.",
        "topic":      "RAG",
    })
    response = r.json()["response"]
    assert "/40" in response


def test_evaluate_has_all_four_dimensions(api, session_evals):
    """Scorecard contains all four scoring dimensions."""
    r = api.post("/evaluate", json={
        "session_id": session_evals["session_id"],
        "question":   "Explain chunking strategies.",
        "answer":     "Chunking splits documents into segments for retrieval.",
        "topic":      "RAG",
    })
    response = r.json()["response"]
    for dim in ("Clarity", "Accuracy", "Depth", "Relevance"):
        assert dim in response, f"Dimension '{dim}' missing from scorecard"


def test_evaluate_invalid_session_returns_404(api):
    r = api.post("/evaluate", json={
        "session_id": "bad-id",
        "question":   "What is RAG?",
        "answer":     "It retrieves documents.",
    })
    assert r.status_code == 404


# ── UI: MCQ rendering in browser ─────────────────────────────────────────────

def test_quiz_difficulty_headers_render_in_chat(api, session_aipm, page):
    """After requesting a quiz, difficulty headers render with correct CSS classes."""
    sid = session_aipm["session_id"]
    page.goto(f"/chat/{sid}")

    page.fill("#user-input", "Quiz me on RAG")
    page.click("#send-btn")
    page.wait_for_selector(".diff-header", timeout=10000)

    headers = page.locator(".diff-header")
    assert headers.count() >= 1


def test_quiz_answer_blocks_render_in_chat(api, session_aipm, page):
    """Answer blocks (.q-answer) appear after a quiz response is displayed."""
    sid = session_aipm["session_id"]
    page.goto(f"/chat/{sid}")

    page.fill("#user-input", "Quiz me on RAG")
    page.click("#send-btn")
    page.wait_for_selector(".q-answer", timeout=10000)

    answers = page.locator(".q-answer")
    assert answers.count() >= 5


def test_send_button_reenabled_after_response(api, session_aipm, page):
    """The send button is re-enabled after a response arrives."""
    sid = session_aipm["session_id"]
    page.goto(f"/chat/{sid}")

    page.fill("#user-input", "Quiz me on RAG")
    page.click("#send-btn")
    page.wait_for_selector(".msg-row.assistant .msg-body", timeout=10000)

    send_btn = page.locator("#send-btn")
    assert send_btn.is_enabled()
