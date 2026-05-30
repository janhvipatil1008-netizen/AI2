"""Tests for the no-op LLM observability wrapper.

Verifies that:
- services/llm_observability.py exists and has no LangSmith SDK import
- is_tracing_active() defaults to False
- missing API key keeps tracing inactive
- trace_llm_call context manager never raises
- sanitize_trace_metadata removes blocked/secret keys
- sanitize_trace_metadata keeps known-safe keys
- build_safe_trace_metadata only produces safe fields
- no network-capable module is imported
"""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest

MODULE_PATH = Path("services/llm_observability.py")


def _reload():
    import services.llm_observability as mod
    importlib.reload(mod)
    return mod


# ── File and source checks ────────────────────────────────────────────────────

def test_module_file_exists():
    assert MODULE_PATH.exists()


def test_no_langsmith_sdk_import():
    source = MODULE_PATH.read_text(encoding="utf-8")
    assert "import langsmith" not in source
    assert "from langsmith" not in source


def test_no_requests_or_httpx_import():
    source = MODULE_PATH.read_text(encoding="utf-8")
    assert "import requests" not in source
    assert "import httpx" not in source
    assert "import urllib" not in source


# ── is_tracing_active defaults ────────────────────────────────────────────────

def test_tracing_inactive_by_default(monkeypatch):
    monkeypatch.delenv("LANGSMITH_TRACING", raising=False)
    monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)
    mod = _reload()
    assert mod.is_tracing_active() is False


def test_tracing_inactive_when_flag_false(monkeypatch):
    monkeypatch.setenv("LANGSMITH_TRACING", "false")
    monkeypatch.setenv("LANGSMITH_API_KEY", "some-key")
    mod = _reload()
    assert mod.is_tracing_active() is False


def test_tracing_inactive_when_api_key_missing(monkeypatch):
    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)
    mod = _reload()
    assert mod.is_tracing_active() is False


def test_tracing_inactive_when_api_key_empty(monkeypatch):
    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    monkeypatch.setenv("LANGSMITH_API_KEY", "")
    mod = _reload()
    assert mod.is_tracing_active() is False


def test_tracing_active_when_both_set(monkeypatch):
    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    monkeypatch.setenv("LANGSMITH_API_KEY", "test-ls-key")
    mod = _reload()
    assert mod.is_tracing_active() is True


# ── trace_llm_call context manager ───────────────────────────────────────────

def test_context_manager_does_not_raise_when_disabled(monkeypatch):
    monkeypatch.delenv("LANGSMITH_TRACING", raising=False)
    monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)
    mod = _reload()
    with mod.trace_llm_call("test_call"):
        pass  # must not raise


def test_context_manager_does_not_raise_when_enabled(monkeypatch):
    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    monkeypatch.setenv("LANGSMITH_API_KEY", "test-ls-key")
    mod = _reload()
    with mod.trace_llm_call("test_call", metadata={"topic_id": "t1"}):
        pass  # still no-op — SDK not wired yet


def test_context_manager_accepts_none_metadata(monkeypatch):
    monkeypatch.delenv("LANGSMITH_TRACING", raising=False)
    mod = _reload()
    with mod.trace_llm_call("test_call", metadata=None):
        pass


def test_context_manager_yields_control():
    mod = _reload()
    ran = []
    with mod.trace_llm_call("test_call"):
        ran.append(1)
    assert ran == [1]


# ── sanitize_trace_metadata: blocked keys removed ────────────────────────────

def test_sanitizer_removes_api_key():
    mod = _reload()
    result = mod.sanitize_trace_metadata({"api_key": "secret", "topic_id": "t1"})
    assert "api_key" not in result
    assert result.get("topic_id") == "t1"


def test_sanitizer_removes_database_url():
    mod = _reload()
    result = mod.sanitize_trace_metadata({"database_url": "postgres://...", "model": "claude"})
    assert "database_url" not in result
    assert result.get("model") == "claude"


def test_sanitizer_removes_content_field():
    mod = _reload()
    result = mod.sanitize_trace_metadata({"content": "generated text here", "topic_id": "t2"})
    assert "content" not in result


def test_sanitizer_removes_submission_field():
    mod = _reload()
    result = mod.sanitize_trace_metadata({"submission": "my answer", "activity_type": "quiz"})
    assert "submission" not in result
    assert result.get("activity_type") == "quiz"


def test_sanitizer_removes_answers_field():
    mod = _reload()
    result = mod.sanitize_trace_metadata({"answers": "A, B, C", "topic_id": "t3"})
    assert "answers" not in result


def test_sanitizer_removes_notes_field():
    mod = _reload()
    result = mod.sanitize_trace_metadata({"notes": "private learner note", "model": "m"})
    assert "notes" not in result


def test_sanitizer_removes_prompt_field():
    mod = _reload()
    result = mod.sanitize_trace_metadata({"prompt": "full prompt text", "topic_id": "t4"})
    assert "prompt" not in result


def test_sanitizer_removes_email():
    mod = _reload()
    result = mod.sanitize_trace_metadata({"email": "user@example.com", "track_key": "aipm"})
    assert "email" not in result


def test_sanitizer_removes_auth_cookie():
    mod = _reload()
    result = mod.sanitize_trace_metadata({"auth_cookie": "abc123", "status": "success"})
    assert "auth_cookie" not in result


# ── sanitize_trace_metadata: safe keys preserved ─────────────────────────────

def test_sanitizer_keeps_topic_id():
    mod = _reload()
    result = mod.sanitize_trace_metadata({"topic_id": "week1-aipm-1"})
    assert result["topic_id"] == "week1-aipm-1"


def test_sanitizer_keeps_track_key():
    mod = _reload()
    result = mod.sanitize_trace_metadata({"track_key": "aipm"})
    assert result["track_key"] == "aipm"


def test_sanitizer_keeps_activity_type():
    mod = _reload()
    result = mod.sanitize_trace_metadata({"activity_type": "generate_lesson"})
    assert result["activity_type"] == "generate_lesson"


def test_sanitizer_keeps_model():
    mod = _reload()
    result = mod.sanitize_trace_metadata({"model": "claude-sonnet-4-6"})
    assert result["model"] == "claude-sonnet-4-6"


def test_sanitizer_keeps_latency_ms():
    mod = _reload()
    result = mod.sanitize_trace_metadata({"latency_ms": 423})
    assert result["latency_ms"] == 423


def test_sanitizer_keeps_from_cache():
    mod = _reload()
    result = mod.sanitize_trace_metadata({"from_cache": False})
    assert result["from_cache"] is False


def test_sanitizer_keeps_status():
    mod = _reload()
    result = mod.sanitize_trace_metadata({"status": "success"})
    assert result["status"] == "success"


# ── build_safe_trace_metadata ─────────────────────────────────────────────────

def test_build_safe_metadata_basic():
    mod = _reload()
    result = mod.build_safe_trace_metadata(
        topic_id="t1",
        track_key="aipm",
        activity_type="generate_lesson",
        model="claude-sonnet-4-6",
        from_cache=False,
        latency_ms=310,
        status="success",
    )
    assert result["topic_id"]      == "t1"
    assert result["track_key"]     == "aipm"
    assert result["activity_type"] == "generate_lesson"
    assert result["model"]         == "claude-sonnet-4-6"
    assert result["from_cache"]    is False
    assert result["latency_ms"]    == 310
    assert result["status"]        == "success"


def test_build_safe_metadata_strips_extra_blocked_keys():
    mod = _reload()
    result = mod.build_safe_trace_metadata(
        topic_id="t1",
        content="should be stripped",
        api_key="should also be stripped",
    )
    assert "content" not in result
    assert "api_key" not in result
    assert result["topic_id"] == "t1"


def test_build_safe_metadata_omits_none_values():
    mod = _reload()
    result = mod.build_safe_trace_metadata(topic_id="t1", model=None)
    assert "model" not in result
    assert result["topic_id"] == "t1"
