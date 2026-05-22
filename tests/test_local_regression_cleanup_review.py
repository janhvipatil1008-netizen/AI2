"""Tests for the local regression and cleanup review doc."""

from __future__ import annotations

from pathlib import Path


DOC_PATH = Path("docs/ai2-local-regression-cleanup-review.md")


def _doc() -> str:
    return DOC_PATH.read_text(encoding="utf-8")


def test_cleanup_review_doc_exists():
    assert DOC_PATH.exists()
    assert _doc().startswith("# AI² Local Regression and Cleanup Review")


def test_doc_mentions_worktree_summary():
    text = _doc()

    assert "Git Worktree Summary" in text
    assert "Modified tracked files" in text
    assert "Untracked directories/files" in text


def test_doc_mentions_cleanup_candidates():
    text = _doc()

    assert "Local Cleanup Candidates" in text
    assert ".pytest_tmp/" in text
    assert "manual_tmp/" in text
    assert "local database artifacts" in text


def test_doc_mentions_deployment_recommendation():
    text = _doc()

    assert "Deployment Recommendation" in text
    assert "Do not deploy directly from this dirty worktree" in text
    assert "Render" in text


def test_doc_says_no_automatic_deletion():
    text = _doc()

    assert "Do not delete anything automatically" in text
    assert "No automatic deletion was performed" in text
