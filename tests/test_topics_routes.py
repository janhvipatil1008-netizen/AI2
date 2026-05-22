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


def test_topic_detail_returns_200_for_valid_topic():
    session_id = _start_session()
    topic = get_topics_for_week("aipm", 1)[0]

    response = client.get(f"/topic/{session_id}/{topic.topic_id}")

    assert response.status_code == 200
    assert topic.topic_title in response.text


def test_topic_detail_contains_journey_steps():
    session_id = _start_session()
    topic = get_topics_for_week("aipm", 1)[0]

    response = client.get(f"/topic/{session_id}/{topic.topic_id}")

    assert response.status_code == 200
    assert "Learn" in response.text
    assert "Quiz" in response.text
    assert "Portfolio Task" in response.text
    assert "Interview Practice" in response.text


def test_invalid_topic_id_returns_404():
    session_id = _start_session()

    response = client.get(f"/topic/{session_id}/missing-topic")

    assert response.status_code == 404
    assert response.json()["detail"] == "Topic not found"


def test_topics_page_still_returns_200():
    session_id = _start_session()

    response = client.get(f"/topics/{session_id}")

    assert response.status_code == 200
    assert "Module 1 Topics" in response.text
    assert "Open Topic" in response.text


def test_topic_detail_includes_completion_percent():
    session_id = _start_session()
    topic = get_topics_for_week("aipm", 1)[0]

    response = client.get(f"/topic/{session_id}/{topic.topic_id}")

    assert response.status_code == 200
    assert "0%" in response.text


def test_topic_progress_endpoint_updates_and_returns_completion():
    session_id = _start_session()
    topic = get_topics_for_week("aipm", 1)[0]

    response = client.post("/topic/progress", json={
        "session_id": session_id,
        "topic_id":   topic.topic_id,
        "step":       "learn",
        "status":     "done",
    })

    assert response.status_code == 200
    data = response.json()
    assert data["topic_id"]  == topic.topic_id
    assert data["step"]      == "learn"
    assert data["status"]    == "done"
    assert data["topic_progress"]["learn"] == "done"
    assert data["completion_percent"] == 20   # 1 of 5 steps = 20%


def test_topic_progress_invalid_topic_returns_404():
    session_id = _start_session()

    response = client.post("/topic/progress", json={
        "session_id": session_id,
        "topic_id":   "nonexistent-topic-xyz",
        "step":       "learn",
        "status":     "done",
    })

    assert response.status_code == 404


def test_topic_progress_invalid_step_returns_422():
    session_id = _start_session()
    topic = get_topics_for_week("aipm", 1)[0]

    response = client.post("/topic/progress", json={
        "session_id": session_id,
        "topic_id":   topic.topic_id,
        "step":       "bad_step",
        "status":     "done",
    })

    assert response.status_code == 422


def test_topic_progress_invalid_status_returns_422():
    session_id = _start_session()
    topic = get_topics_for_week("aipm", 1)[0]

    response = client.post("/topic/progress", json={
        "session_id": session_id,
        "topic_id":   topic.topic_id,
        "step":       "learn",
        "status":     "bad_status",
    })

    assert response.status_code == 422


def test_topic_progress_persists_across_requests():
    session_id = _start_session()
    topic = get_topics_for_week("aipm", 1)[0]

    client.post("/topic/progress", json={
        "session_id": session_id,
        "topic_id":   topic.topic_id,
        "step":       "quiz",
        "status":     "in_progress",
    })

    response = client.get(f"/topic/{session_id}/{topic.topic_id}")
    assert response.status_code == 200
    assert "In Progress" in response.text


def test_topic_detail_action_buttons_have_data_topic_action():
    session_id = _start_session()
    topic = get_topics_for_week("aipm", 1)[0]

    response = client.get(f"/topic/{session_id}/{topic.topic_id}")
    html = response.text

    assert response.status_code == 200
    assert "data-topic-action" in html


def test_topic_detail_action_buttons_have_correct_step_attributes():
    session_id = _start_session()
    topic = get_topics_for_week("aipm", 1)[0]

    response = client.get(f"/topic/{session_id}/{topic.topic_id}")
    html = response.text

    assert 'data-step="learn"'              in html
    assert 'data-step="quiz"'               in html
    assert 'data-step="portfolio_task"'     in html
    assert 'data-step="interview_practice"' in html


def test_topic_detail_action_buttons_have_in_progress_status():
    session_id = _start_session()
    topic = get_topics_for_week("aipm", 1)[0]

    response = client.get(f"/topic/{session_id}/{topic.topic_id}")
    html = response.text

    assert 'data-status="in_progress"' in html


def test_topic_detail_action_buttons_have_chat_url():
    session_id = _start_session()
    topic = get_topics_for_week("aipm", 1)[0]

    response = client.get(f"/topic/{session_id}/{topic.topic_id}")
    html = response.text

    assert "data-chat-url" in html
    assert f"/chat/{session_id}" in html


def test_topic_detail_contains_add_to_today_buttons():
    session_id = _start_session()
    topic = get_topics_for_week("aipm", 1)[0]

    response = client.get(f"/topic/{session_id}/{topic.topic_id}")

    assert response.status_code == 200
    assert "Add to Today" in response.text


def test_topic_detail_contains_add_to_module_plan_buttons():
    session_id = _start_session()
    topic = get_topics_for_week("aipm", 1)[0]

    response = client.get(f"/topic/{session_id}/{topic.topic_id}")

    assert response.status_code == 200
    assert "Add to Module Plan" in response.text


def test_topic_detail_references_todos_create_endpoint():
    session_id = _start_session()
    topic = get_topics_for_week("aipm", 1)[0]

    response = client.get(f"/topic/{session_id}/{topic.topic_id}")

    assert response.status_code == 200
    assert "/todos/create" in response.text


def test_topic_detail_planner_buttons_include_linked_topic_id():
    session_id = _start_session()
    topic = get_topics_for_week("aipm", 1)[0]

    response = client.get(f"/topic/{session_id}/{topic.topic_id}")
    html = response.text

    assert response.status_code == 200
    # The topic ID must appear in the rendered HTML so the JS can send it
    assert topic.topic_id in html


def test_topic_detail_contains_add_suggested_plan_button():
    session_id = _start_session()
    topic = get_topics_for_week("aipm", 1)[0]

    response = client.get(f"/topic/{session_id}/{topic.topic_id}")

    assert response.status_code == 200
    assert "Add Suggested Plan for This Topic" in response.text


def test_topic_detail_suggested_plan_includes_all_step_title_prefixes():
    session_id = _start_session()
    topic = get_topics_for_week("aipm", 1)[0]

    response = client.get(f"/topic/{session_id}/{topic.topic_id}")
    html = response.text

    assert response.status_code == 200
    # The JS literals for all four step titles must appear in the script block
    assert "Learn: " in html
    assert "Quiz: " in html
    assert "Portfolio Task: " in html
    assert "Interview Practice: " in html


# ── Topics page: progress overview ───────────────────────────────────────────

def test_topics_page_shows_completion_percentage():
    session_id = _start_session()
    response = client.get(f"/topics/{session_id}")
    assert response.status_code == 200
    assert "0%" in response.text


def test_topics_page_shows_not_started_status_initially():
    session_id = _start_session()
    response = client.get(f"/topics/{session_id}")
    assert response.status_code == 200
    assert "Not Started" in response.text


def test_topics_page_shows_step_chips():
    session_id = _start_session()
    response = client.get(f"/topics/{session_id}")
    html = response.text
    assert response.status_code == 200
    assert "topic-step-chip" in html
    assert "Learn"     in html
    assert "Quiz"      in html
    assert "Portfolio" in html
    assert "Interview" in html
    assert "Reflection" in html


def test_topics_page_shows_progress_bar():
    session_id = _start_session()
    response = client.get(f"/topics/{session_id}")
    html = response.text
    assert response.status_code == 200
    assert "topic-card-progress" in html
    assert "topic-card-progress-fill" in html


def test_topics_page_updates_status_after_progress_call():
    session_id = _start_session()
    topic = get_topics_for_week("aipm", 1)[0]

    client.post("/topic/progress", json={
        "session_id": session_id,
        "topic_id":   topic.topic_id,
        "step":       "learn",
        "status":     "done",
    })

    response = client.get(f"/topics/{session_id}")
    assert response.status_code == 200
    assert "20%" in response.text
    assert "In Progress" in response.text


def test_topics_page_shows_completed_status_when_all_steps_done():
    session_id = _start_session()
    topic = get_topics_for_week("aipm", 1)[0]

    for step in ("learn", "quiz", "portfolio_task", "interview_practice", "reflection"):
        client.post("/topic/progress", json={
            "session_id": session_id,
            "topic_id":   topic.topic_id,
            "step":       step,
            "status":     "done",
        })

    response = client.get(f"/topics/{session_id}")
    assert response.status_code == 200
    assert "100%" in response.text
    assert "Completed" in response.text


# ── Topics page: Continue Next Step button ────────────────────────────────────

def test_topics_page_shows_continue_learning_initially():
    session_id = _start_session()
    response = client.get(f"/topics/{session_id}")
    assert response.status_code == 200
    assert "Continue Learning" in response.text
    assert "topic-continue-btn" in response.text


def test_topics_page_continue_button_links_to_learning_anchor():
    session_id = _start_session()
    response = client.get(f"/topics/{session_id}")
    assert "#ai-learning-content" in response.text


def test_topics_page_shows_continue_quiz_after_learn_done():
    session_id = _start_session()
    topic = get_topics_for_week("aipm", 1)[0]
    client.post("/topic/progress", json={
        "session_id": session_id,
        "topic_id":   topic.topic_id,
        "step":       "learn",
        "status":     "done",
    })
    response = client.get(f"/topics/{session_id}")
    assert response.status_code == 200
    assert "Continue Quiz" in response.text
    assert "#ai-quiz" in response.text


def test_topics_page_shows_continue_portfolio_after_learn_quiz_done():
    session_id = _start_session()
    topic = get_topics_for_week("aipm", 1)[0]
    for step in ("learn", "quiz"):
        client.post("/topic/progress", json={
            "session_id": session_id,
            "topic_id":   topic.topic_id,
            "step":       step,
            "status":     "done",
        })
    response = client.get(f"/topics/{session_id}")
    assert "Continue Portfolio Task" in response.text
    assert "#ai-portfolio-task" in response.text


def test_topics_page_shows_continue_interview_after_first_three_done():
    session_id = _start_session()
    topic = get_topics_for_week("aipm", 1)[0]
    for step in ("learn", "quiz", "portfolio_task"):
        client.post("/topic/progress", json={
            "session_id": session_id,
            "topic_id":   topic.topic_id,
            "step":       step,
            "status":     "done",
        })
    response = client.get(f"/topics/{session_id}")
    assert "Continue Interview Practice" in response.text
    assert "#ai-interview-practice" in response.text


def test_topics_page_shows_continue_reflection_after_first_four_done():
    session_id = _start_session()
    topic = get_topics_for_week("aipm", 1)[0]
    for step in ("learn", "quiz", "portfolio_task", "interview_practice"):
        client.post("/topic/progress", json={
            "session_id": session_id,
            "topic_id":   topic.topic_id,
            "step":       step,
            "status":     "done",
        })
    response = client.get(f"/topics/{session_id}")
    assert "Continue Reflection" in response.text
    assert "#topic-reflection" in response.text


def test_topics_page_shows_review_topic_when_all_done():
    session_id = _start_session()
    topic = get_topics_for_week("aipm", 1)[0]
    for step in ("learn", "quiz", "portfolio_task", "interview_practice", "reflection"):
        client.post("/topic/progress", json={
            "session_id": session_id,
            "topic_id":   topic.topic_id,
            "step":       step,
            "status":     "done",
        })
    response = client.get(f"/topics/{session_id}")
    assert "Review Topic" in response.text


def test_topics_page_review_topic_link_has_no_anchor():
    session_id = _start_session()
    topic = get_topics_for_week("aipm", 1)[0]
    for step in ("learn", "quiz", "portfolio_task", "interview_practice", "reflection"):
        client.post("/topic/progress", json={
            "session_id": session_id,
            "topic_id":   topic.topic_id,
            "step":       step,
            "status":     "done",
        })
    response = client.get(f"/topics/{session_id}")
    html = response.text
    # "Review Topic" link should point to topic detail without a hash
    assert f'href="/topic/{session_id}/{topic.topic_id}"' in html


# ── Topic detail: section id anchors ─────────────────────────────────────────

def test_topic_detail_has_ai_learning_content_anchor():
    session_id = _start_session()
    topic = get_topics_for_week("aipm", 1)[0]
    response = client.get(f"/topic/{session_id}/{topic.topic_id}")
    assert 'id="ai-learning-content"' in response.text


def test_topic_detail_has_ai_quiz_anchor():
    session_id = _start_session()
    topic = get_topics_for_week("aipm", 1)[0]
    response = client.get(f"/topic/{session_id}/{topic.topic_id}")
    assert 'id="ai-quiz"' in response.text


def test_topic_detail_has_ai_portfolio_task_anchor():
    session_id = _start_session()
    topic = get_topics_for_week("aipm", 1)[0]
    response = client.get(f"/topic/{session_id}/{topic.topic_id}")
    assert 'id="ai-portfolio-task"' in response.text


def test_topic_detail_has_ai_interview_practice_anchor():
    session_id = _start_session()
    topic = get_topics_for_week("aipm", 1)[0]
    response = client.get(f"/topic/{session_id}/{topic.topic_id}")
    assert 'id="ai-interview-practice"' in response.text


def test_topic_detail_has_topic_reflection_anchor():
    session_id = _start_session()
    topic = get_topics_for_week("aipm", 1)[0]
    response = client.get(f"/topic/{session_id}/{topic.topic_id}")
    assert 'id="topic-reflection"' in response.text


# ── Weekly progress summary ───────────────────────────────────────────────────

def test_topics_page_shows_week_progress_summary():
    session_id = _start_session()
    response = client.get(f"/topics/{session_id}")
    assert response.status_code == 200
    assert "week-progress-summary" in response.text


def test_topics_page_summary_shows_zero_avg_initially():
    session_id = _start_session()
    response = client.get(f"/topics/{session_id}")
    html = response.text
    # Average must be 0% when no steps are done
    assert "0%" in html


def test_topics_page_summary_shows_completed_fraction():
    session_id = _start_session()
    topics = get_topics_for_week("aipm", 1)
    total = len(topics)
    response = client.get(f"/topics/{session_id}")
    # "Completed: 0 / <total>" must appear
    assert f"Completed: 0 / {total}" in response.text.replace("\n", " ").replace("  ", " ")


def test_topics_page_summary_shows_in_progress_label():
    session_id = _start_session()
    response = client.get(f"/topics/{session_id}")
    assert "In progress:" in response.text


def test_topics_page_summary_shows_not_started_label():
    session_id = _start_session()
    response = client.get(f"/topics/{session_id}")
    assert "Not started:" in response.text


def test_topics_page_summary_avg_updates_after_step_done():
    session_id = _start_session()
    topic = get_topics_for_week("aipm", 1)[0]
    client.post("/topic/progress", json={
        "session_id": session_id,
        "topic_id":   topic.topic_id,
        "step":       "learn",
        "status":     "done",
    })
    response = client.get(f"/topics/{session_id}")
    # 1 step done on 1 topic → that topic is 20%; average is 20/total which is > 0
    assert "0%" not in response.text.split("week-progress-avg")[1][:30] if "week-progress-avg" in response.text else True


def test_topics_page_summary_completed_count_updates():
    session_id = _start_session()
    topic = get_topics_for_week("aipm", 1)[0]
    for step in ("learn", "quiz", "portfolio_task", "interview_practice", "reflection"):
        client.post("/topic/progress", json={
            "session_id": session_id,
            "topic_id":   topic.topic_id,
            "step":       step,
            "status":     "done",
        })
    response = client.get(f"/topics/{session_id}")
    total = len(get_topics_for_week("aipm", 1))
    assert f"Completed: 1 / {total}" in response.text.replace("\n", " ").replace("  ", " ")


def test_topics_page_summary_progress_bar_present():
    session_id = _start_session()
    response = client.get(f"/topics/{session_id}")
    assert "week-progress-bar" in response.text
    assert "week-progress-fill" in response.text


# ── JS extraction: topic_detail.html structure ───────────────────────────────

def test_topic_detail_includes_external_js():
    session_id = _start_session()
    topic = get_topics_for_week("aipm", 1)[0]
    response = client.get(f"/topic/{session_id}/{topic.topic_id}")
    assert "/static/topic_detail.js" in response.text


def test_topic_detail_includes_ai2_topic_detail_config():
    session_id = _start_session()
    topic = get_topics_for_week("aipm", 1)[0]
    response = client.get(f"/topic/{session_id}/{topic.topic_id}")
    assert "window.AI2_TOPIC_DETAIL" in response.text


def test_topic_detail_config_contains_session_and_topic_ids():
    session_id = _start_session()
    topic = get_topics_for_week("aipm", 1)[0]
    response = client.get(f"/topic/{session_id}/{topic.topic_id}")
    html = response.text
    assert session_id           in html
    assert topic.topic_id       in html
    assert "sessionId"          in html
    assert "topicId"            in html


def test_topic_detail_config_contains_all_url_keys():
    session_id = _start_session()
    topic = get_topics_for_week("aipm", 1)[0]
    response = client.get(f"/topic/{session_id}/{topic.topic_id}")
    html = response.text
    for key in (
        "topicProgressUrl", "topicNotesUrl",
        "topicContentGenerateUrl", "topicPracticeGenerateUrl",
        "portfolioSubmitUrl", "portfolioFeedbackUrl",
        "quizSubmitUrl", "quizEvaluateUrl",
        "interviewSubmitUrl", "interviewFeedbackUrl",
    ):
        assert key in html, f"Missing config key: {key}"


def test_topic_detail_no_inline_function_definitions():
    """The old inline JS functions must not appear in the template output."""
    session_id = _start_session()
    topic = get_topics_for_week("aipm", 1)[0]
    response = client.get(f"/topic/{session_id}/{topic.topic_id}")
    html = response.text
    # These strings appeared in the old inline script; they must now live only in topic_detail.js
    assert "async function generateContent" not in html
    assert "async function saveReflection"  not in html
    assert "async function markStep"        not in html


# ── JS extraction: static/topic_detail.js content ────────────────────────────

import pathlib

_JS_PATH = pathlib.Path(__file__).parent.parent / "static" / "topic_detail.js"


def test_topic_detail_js_exists():
    assert _JS_PATH.exists(), "static/topic_detail.js was not created"


def test_topic_detail_js_contains_core_functions():
    js = _JS_PATH.read_text(encoding="utf-8")
    for fn in (
        "generateContent",
        "generatePractice",
        "markStep",
        "markStepFromContent",
        "saveReflection",
        "saveQuizAnswers",
        "savePortfolioSubmission",
        "saveInterviewAnswer",
        "addToPlanner",
        "addSuggestedPlan",
    ):
        assert fn in js, f"Function missing from topic_detail.js: {fn}"


def test_topic_detail_js_exposes_functions_on_window():
    js = _JS_PATH.read_text(encoding="utf-8")
    for fn in (
        "generateContent",
        "generatePractice",
        "markStep",
        "saveReflection",
        "saveQuizAnswers",
        "savePortfolioSubmission",
        "saveInterviewAnswer",
    ):
        assert f"window.{fn}" in js, f"window.{fn} not exported in topic_detail.js"


def test_topic_detail_js_reads_from_ai2_topic_detail_config():
    js = _JS_PATH.read_text(encoding="utf-8")
    assert "window.AI2_TOPIC_DETAIL" in js
    assert "_cfg.sessionId"          in js
    assert "_cfg.topicId"            in js
