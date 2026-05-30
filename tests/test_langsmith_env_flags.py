"""Tests for LangSmith environment flag configuration.

Verifies that:
- .env.example documents all four LangSmith vars
- tracing defaults to false when env vars are absent
- missing/empty API key never causes a failure
- no real secret values are committed
- config.py does not import the LangSmith SDK
- observability_flags.py does not import the LangSmith SDK
"""

from __future__ import annotations

import importlib
import os
from pathlib import Path

ENV_EXAMPLE = Path(".env.example")
CONFIG_PY   = Path("config.py")
FLAGS_PY    = Path("services/observability_flags.py")


def _env_example() -> str:
    return ENV_EXAMPLE.read_text(encoding="utf-8")


def _import_flags(monkeypatch=None):
    import services.observability_flags as flags
    importlib.reload(flags)
    return flags


# ── .env.example contains all LangSmith keys ─────────────────────────────────

def test_env_example_contains_langsmith_tracing():
    assert "LANGSMITH_TRACING" in _env_example()


def test_env_example_contains_langsmith_api_key():
    assert "LANGSMITH_API_KEY" in _env_example()


def test_env_example_contains_langsmith_project():
    assert "LANGSMITH_PROJECT" in _env_example()


def test_env_example_contains_langsmith_endpoint():
    assert "LANGSMITH_ENDPOINT" in _env_example()


def test_env_example_langsmith_tracing_defaults_false():
    assert "LANGSMITH_TRACING=false" in _env_example()


# ── No real secrets in .env.example ──────────────────────────────────────────

def test_env_example_api_key_is_empty_placeholder():
    doc = _env_example()
    # LANGSMITH_API_KEY line must have no value after the =
    for line in doc.splitlines():
        if line.startswith("LANGSMITH_API_KEY="):
            value = line.split("=", 1)[1].strip()
            assert value == "", f"LANGSMITH_API_KEY should be empty, got: {value!r}"


def test_env_example_no_real_langsmith_key():
    doc = _env_example()
    assert "lsv2_" not in doc  # LangSmith API key prefix


# ── Default flag behavior (no env vars set) ───────────────────────────────────

def test_tracing_disabled_when_env_var_absent(monkeypatch):
    monkeypatch.delenv("LANGSMITH_TRACING", raising=False)
    monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)
    flags = _import_flags()
    assert flags.is_langsmith_tracing_enabled() is False


def test_tracing_disabled_when_tracing_false(monkeypatch):
    monkeypatch.setenv("LANGSMITH_TRACING", "false")
    monkeypatch.setenv("LANGSMITH_API_KEY", "some-key")
    flags = _import_flags()
    assert flags.is_langsmith_tracing_enabled() is False


def test_tracing_disabled_when_api_key_empty(monkeypatch):
    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    monkeypatch.setenv("LANGSMITH_API_KEY", "")
    flags = _import_flags()
    assert flags.is_langsmith_tracing_enabled() is False


def test_tracing_enabled_when_both_set(monkeypatch):
    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    monkeypatch.setenv("LANGSMITH_API_KEY", "test-ls-key")
    flags = _import_flags()
    assert flags.is_langsmith_tracing_enabled() is True


# ── Missing API key is safe ───────────────────────────────────────────────────

def test_get_api_key_returns_empty_string_when_absent(monkeypatch):
    monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)
    flags = _import_flags()
    assert flags.get_langsmith_api_key() == ""


def test_get_api_key_does_not_raise_when_absent(monkeypatch):
    monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)
    flags = _import_flags()
    result = flags.get_langsmith_api_key()
    assert isinstance(result, str)


# ── Default project and endpoint ──────────────────────────────────────────────

def test_default_project(monkeypatch):
    monkeypatch.delenv("LANGSMITH_PROJECT", raising=False)
    flags = _import_flags()
    assert flags.get_langsmith_project() == "ai2-render-beta"


def test_default_endpoint(monkeypatch):
    monkeypatch.delenv("LANGSMITH_ENDPOINT", raising=False)
    flags = _import_flags()
    assert flags.get_langsmith_endpoint() == "https://api.smith.langchain.com"


# ── No LangSmith SDK import in config.py or observability_flags.py ───────────

def test_config_py_does_not_import_langsmith():
    source = CONFIG_PY.read_text(encoding="utf-8")
    assert "import langsmith" not in source
    assert "from langsmith" not in source


def test_observability_flags_does_not_import_langsmith():
    source = FLAGS_PY.read_text(encoding="utf-8")
    assert "import langsmith" not in source
    assert "from langsmith" not in source


# ── LangSmith stays off by default in the module at import time ───────────────

def test_langsmith_off_by_default_at_import(monkeypatch):
    """With no env vars set, importing the module must not enable tracing."""
    monkeypatch.delenv("LANGSMITH_TRACING", raising=False)
    monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)
    flags = _import_flags()
    assert flags.is_langsmith_tracing_enabled() is False
