"""Structural tests for .github/workflows/test.yml.

Verifies the workflow file exists and satisfies the minimum CI requirements
without executing any application code.
"""

from __future__ import annotations

from pathlib import Path

import pytest

WORKFLOW = Path(".github/workflows/test.yml")


def _doc() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


# ── File exists ───────────────────────────────────────────────────────────────

def test_workflow_file_exists():
    assert WORKFLOW.exists(), f"{WORKFLOW} not found"


def test_workflow_file_is_not_empty():
    assert len(_doc()) > 100


# ── Triggers ──────────────────────────────────────────────────────────────────

def test_workflow_triggers_on_push():
    assert "push" in _doc()


def test_workflow_triggers_on_pull_request():
    assert "pull_request" in _doc()


# ── Runner and Python version ─────────────────────────────────────────────────

def test_workflow_uses_ubuntu():
    assert "ubuntu" in _doc()


def test_workflow_uses_python_311():
    assert "3.11" in _doc()


# ── Dependency installation ───────────────────────────────────────────────────

def test_workflow_installs_requirements_txt():
    assert "requirements.txt" in _doc()


# ── Test execution ────────────────────────────────────────────────────────────

def test_workflow_runs_pytest():
    assert "pytest" in _doc()


# ── Test mode env vars ────────────────────────────────────────────────────────

def test_workflow_sets_test_mode():
    doc = _doc()
    assert "TEST_MODE" in doc or "AI2_TEST_MODE" in doc


def test_workflow_sets_ai2_test_mode_to_1():
    doc = _doc()
    assert 'AI2_TEST_MODE: "1"' in doc or "AI2_TEST_MODE: '1'" in doc or "AI2_TEST_MODE=1" in doc


# ── Safety: no real secrets ───────────────────────────────────────────────────

def test_workflow_does_not_contain_real_api_key():
    doc = _doc()
    assert "sk-ant-" not in doc


def test_workflow_does_not_contain_real_db_url():
    doc = _doc()
    # placeholder value is fine; a real Supabase/prod URL would contain 'supabase.co' or 'aws'
    assert "supabase.co" not in doc
    assert ".amazonaws.com" not in doc


def test_workflow_anthropic_api_key_is_placeholder():
    doc = _doc()
    # must reference ANTHROPIC_API_KEY but only with a safe placeholder value
    assert "ANTHROPIC_API_KEY" in doc
    assert "test-key" in doc or "${{" in doc
