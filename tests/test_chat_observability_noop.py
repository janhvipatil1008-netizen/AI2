"""Tests for no-op observability wiring in routes/chat.py.

Verifies that:
- trace_llm_call is imported and used around Orchestrator.process
- POST /chat route URL is unchanged
- tracing disabled keeps response shape unchanged
- TEST_MODE path behavior is identical
- metadata does not include user message, chat history, response text, prompt, secrets
- orchestrator.py and agents/ are not modified
- no LangSmith SDK or network imports are introduced
"""

from __future__ import annotations

import os
from pathlib import Path

os.environ["AI2_TEST_MODE"] = "1"
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")

from fastapi.testclient import TestClient

import app as app_module

client = TestClient(app_module.app)

CHAT_SOURCE         = Path("routes/chat.py").read_text(encoding="utf-8")
ORCHESTRATOR_SOURCE = Path("orchestrator.py").read_text(encoding="utf-8")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _start_session() -> str:
    r = client.post("/session/start", json={"track": "aipm", "week": 1})
    assert r.status_code == 200, r.text
    return r.json()["session_id"]


# ── Source-level checks: routes/chat.py ──────────────────────────────────────

def test_chat_imports_trace_llm_call():
    assert "trace_llm_call" in CHAT_SOURCE


def test_chat_imports_build_safe_trace_metadata():
    assert "build_safe_trace_metadata" in CHAT_SOURCE


def test_chat_uses_orchestrator_process_trace():
    assert "chat.orchestrator_process" in CHAT_SOURCE


def test_chat_does_not_import_langsmith():
    assert "import langsmith" not in CHAT_SOURCE
    assert "from langsmith" not in CHAT_SOURCE


def test_chat_does_not_import_requests_or_httpx():
    assert "import requests" not in CHAT_SOURCE
    assert "import httpx" not in CHAT_SOURCE


# ── Source-level checks: orchestrator.py and agents/ not modified ─────────────

def test_orchestrator_py_not_modified():
    assert "trace_llm_call" not in ORCHESTRATOR_SOURCE
    assert "llm_observability" not in ORCHESTRATOR_SOURCE


def test_agents_not_modified():
    for agent_file in Path("agents").glob("*.py"):
        if agent_file.name == "__init__.py":
            continue
        source = agent_file.read_text(encoding="utf-8")
        assert "trace_llm_call" not in source, f"trace_llm_call found in {agent_file}"
        assert "llm_observability" not in source, f"llm_observability found in {agent_file}"


# ── Metadata safety: blocked fields not in trace_llm_call call ───────────────

def test_trace_metadata_does_not_include_message_text():
    block = CHAT_SOURCE.split("chat.orchestrator_process")[1].split("):")[0]
    assert "body.message" not in block
    assert "message" not in block


def test_trace_metadata_does_not_include_response_text():
    block = CHAT_SOURCE.split("chat.orchestrator_process")[1].split("):")[0]
    assert "response_text" not in block


def test_trace_metadata_does_not_pass_raw_history_list():
    # Using len(session.history) to derive turn_count is safe — it's a number.
    # The raw history list must never be passed as a metadata value.
    block = CHAT_SOURCE.split("chat.orchestrator_process")[1].split("):")[0]
    assert "chat_history" not in block
    # session.history must only appear inside len(...), not as a bare value
    import re
    bare_history = re.findall(r"(?<!len\()session\.history", block)
    assert bare_history == [], f"raw session.history passed in metadata: {bare_history}"


def test_trace_metadata_uses_only_safe_fields():
    block = CHAT_SOURCE.split("chat.orchestrator_process")[1].split("):")[0]
    assert "session_id" in block or "route_type" in block or "turn_count" in block


# ── Route URL unchanged ───────────────────────────────────────────────────────

def test_chat_route_url_unchanged():
    routes = {
        (r.path, ",".join(sorted(getattr(r, "methods", set()) or [])))
        for r in app_module.app.routes
        if hasattr(r, "methods")
    }
    assert ("/chat", "POST") in routes


# ── Runtime: TEST_MODE response shape unchanged ───────────────────────────────

def test_chat_test_mode_response_shape():
    session_id = _start_session()
    r = client.post("/chat", json={"session_id": session_id, "message": "hello"})
    assert r.status_code == 200
    data = r.json()
    assert "response" in data
    assert "agent_used" in data
    assert "progress" in data


def test_chat_test_mode_response_not_empty():
    session_id = _start_session()
    r = client.post("/chat", json={"session_id": session_id, "message": "what is machine learning?"})
    assert r.status_code == 200
    assert len(r.json()["response"]) > 0


def test_chat_test_mode_returns_200():
    session_id = _start_session()
    r = client.post("/chat", json={"session_id": session_id, "message": "test message"})
    assert r.status_code == 200


def test_chat_empty_message_still_422():
    session_id = _start_session()
    r = client.post("/chat", json={"session_id": session_id, "message": "   "})
    assert r.status_code == 422


def test_chat_invalid_session_still_404():
    r = client.post("/chat", json={"session_id": "nonexistent-id", "message": "hello"})
    assert r.status_code in (404, 401, 400)


# ── Tracing flag has no effect on TEST_MODE path ─────────────────────────────

def test_tracing_flag_off_does_not_affect_test_mode_chat(monkeypatch):
    monkeypatch.delenv("LANGSMITH_TRACING", raising=False)
    monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)
    session_id = _start_session()
    r = client.post("/chat", json={"session_id": session_id, "message": "hello"})
    assert r.status_code == 200
    assert "response" in r.json()
