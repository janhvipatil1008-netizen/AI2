"""Tests for chat/session route module split."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

os.environ["AI2_TEST_MODE"] = "1"
os.environ["ANTHROPIC_API_KEY"] = "test-key"

from fastapi.testclient import TestClient

import app as app_module


client = TestClient(app_module.app)


def _read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def _routes() -> set[tuple[str, str]]:
    return {
        (route.path, ",".join(sorted(getattr(route, "methods", set()) or [])))
        for route in app_module.app.routes
        if hasattr(route, "methods")
    }


def _start_session() -> str:
    response = client.post("/session/start", json={"track": "aipm", "week": 1})
    assert response.status_code == 200
    return response.json()["session_id"]


def test_chat_py_exists_and_defines_router():
    source = _read("routes/chat.py")
    assert "router = APIRouter()" in source
    assert '@router.get("/history", response_class=HTMLResponse)' in source
    assert '@router.post("/session/start")' in source
    assert '@router.post("/chat")' in source
    assert '@router.get("/progress/{session_id}")' in source
    assert '@router.post("/quiz")' in source
    assert '@router.post("/interview")' in source
    assert '@router.post("/evaluate")' in source
    assert '@router.get("/chat/{session_id}", response_class=HTMLResponse)' in source


def test_app_includes_chat_router():
    source = _read("app.py")
    assert "from routes.chat import router as chat_router" in source
    assert "app.include_router(chat_router)" in source


def test_chat_route_urls_unchanged():
    routes = _routes()
    assert ("/history", "GET") in routes
    assert ("/session/start", "POST") in routes
    assert ("/chat", "POST") in routes
    assert ("/progress/{session_id}", "GET") in routes
    assert ("/quiz", "POST") in routes
    assert ("/interview", "POST") in routes
    assert ("/evaluate", "POST") in routes
    assert ("/chat/{session_id}", "GET") in routes


def test_chat_page_still_loads_chat_template():
    session_id = _start_session()
    response = client.get(f"/chat/{session_id}")

    assert response.status_code == 200
    assert "Orchestrator" in response.text
    assert f'const SESSION_ID = "{session_id}"' in response.text


def test_prompt_query_param_behavior_is_preserved():
    template = _read("templates/chat.html")
    assert "new URLSearchParams(window.location.search).get('prompt')" in template
    assert "window.history.replaceState" in template
    assert "setTimeout(() => sendMessage(), 100)" in template

    session_id = _start_session()
    response = client.get(f"/chat/{session_id}?prompt=Explain%20RAG")
    assert response.status_code == 200


def test_post_chat_test_mode_mock_behavior_is_preserved():
    session_id = _start_session()
    response = client.post(
        "/chat",
        json={"session_id": session_id, "message": "Explain transformers"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["agent_used"] == "learning_coach"
    assert "Great question!" in data["response"]
    assert data["progress"]["exchanges"] == 1


def test_practice_routes_test_mode_behavior_is_preserved():
    session_id = _start_session()

    quiz = client.post(
        "/quiz",
        json={"session_id": session_id, "topic": "RAG Pipelines", "difficulty": "all"},
    )
    interview = client.post(
        "/interview",
        json={"session_id": session_id, "topic": "RAG Pipelines", "difficulty": "all"},
    )
    evaluate = client.post(
        "/evaluate",
        json={
            "session_id": session_id,
            "question": "What is RAG?",
            "answer": "Retrieval augmented generation",
            "topic": "RAG Pipelines",
        },
    )

    assert quiz.status_code == 200
    assert "QUIZ" in quiz.json()["response"]
    assert interview.status_code == 200
    assert "INTERVIEW" in interview.json()["response"]
    assert evaluate.status_code == 200
    assert "ANSWER EVALUATION" in evaluate.json()["response"]


def test_app_no_longer_defines_chat_route_handlers_directly():
    source = _read("app.py")
    assert '@app.get("/history"' not in source
    assert '@app.post("/session/start")' not in source
    assert '@app.post("/chat")' not in source
    assert '@app.get("/progress/{session_id}")' not in source
    assert '@app.post("/quiz")' not in source
    assert '@app.post("/interview")' not in source
    assert '@app.post("/evaluate")' not in source
    assert '@app.get("/chat/{session_id}"' not in source


def test_orchestrator_and_agents_are_not_modified():
    result = subprocess.run(
        ["git", "diff", "--quiet", "--", "orchestrator.py", "agents"],
        check=False,
    )
    assert result.returncode == 0


def test_structured_topic_routes_still_live_in_topic_modules():
    topics_source = _read("routes/topics.py")
    submissions_source = _read("routes/submissions.py")
    chat_source = _read("routes/chat.py")

    assert '@router.get("/topics/{session_id}", response_class=HTMLResponse)' in topics_source
    assert '@router.post("/topic/content/generate")' in topics_source
    assert '@router.post("/topic/practice/generate")' in topics_source
    assert '@router.post("/quiz/submit")' in submissions_source
    assert '@router.post("/portfolio/submit")' in submissions_source
    assert '@router.post("/interview/submit")' in submissions_source

    assert '"/topic/content/generate"' not in chat_source
    assert '"/topic/practice/generate"' not in chat_source
    assert '"/quiz/submit"' not in chat_source
    assert '"/portfolio/submit"' not in chat_source
    assert '"/interview/submit"' not in chat_source


def test_non_chat_routes_not_moved_in_this_step():
    app_source = _read("app.py")
    chat_source = _read("routes/chat.py")

    assert "from routes.public import router as public_router" in app_source
    assert "from routes.auth_routes import router as auth_router" in app_source
    assert "from routes.dashboard import router as dashboard_router" in app_source
    assert "from routes.onboarding import router as onboarding_router" in app_source
    assert "from routes.syllabus import router as syllabus_router" in app_source
    assert "from routes.jobs import router as jobs_router" in app_source
    assert "from routes.debug import router as debug_router" in app_source
    assert "from routes.admin import router as admin_router" in app_source

    assert '"/health"' not in chat_source
    assert '"/login"' not in chat_source
    assert '"/dashboard"' not in chat_source
    assert '"/onboarding/' not in chat_source
    assert '"/syllabus/{session_id}"' not in chat_source
    assert '"/jobs"' not in chat_source
    assert '"/debug/' not in chat_source
    assert '"/admin/' not in chat_source
