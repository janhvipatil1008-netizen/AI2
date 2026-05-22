"""Tests for the git staging plan doc."""

from __future__ import annotations

from pathlib import Path


DOC_PATH = Path("docs/ai2-git-staging-plan.md")


def _doc() -> str:
    return DOC_PATH.read_text(encoding="utf-8")


def test_git_staging_plan_doc_exists():
    assert DOC_PATH.exists()
    assert _doc().startswith("# AI² Git Staging Plan Before Render Smoke Deploy")


def test_doc_mentions_safe_to_stage():
    text = _doc()

    assert "Safe To Stage" in text
    assert "database/schema.sql" in text
    assert "services/" in text
    assert "repositories/" in text


def test_doc_mentions_needs_manual_review():
    text = _doc()

    assert "Needs Manual Review" in text
    assert "auth.py" in text
    assert ".env.example" in text
    assert "static/style.css" in text


def test_doc_mentions_do_not_stage_local_files():
    text = _doc()

    assert "Do Not Stage" in text
    assert ".pytest_tmp/" in text
    assert "local database files" in text
    assert "jobs.db" in text
    assert "sessions.db" in text


def test_doc_mentions_render_smoke_deploy_and_no_auto_commit_push():
    text = _doc()

    assert "Render Smoke Deploy" in text
    assert "Render smoke deploy" in text
    assert "No automatic commit or push" in text
    assert "Nothing has been staged, committed, pushed, or deleted" in text
