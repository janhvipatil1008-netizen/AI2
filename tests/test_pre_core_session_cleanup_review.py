"""Tests for the pre-core session cleanup review doc."""

from __future__ import annotations

from pathlib import Path


DOC_PATH = Path("docs/ai2-pre-core-session-cleanup-review.md")


def _doc() -> str:
    return DOC_PATH.read_text(encoding="utf-8")


def test_pre_core_session_cleanup_review_doc_exists():
    assert DOC_PATH.exists()


def test_doc_mentions_remaining_core_session_helpers():
    text = _doc()

    assert "_get_session_data" in text
    assert "_save_session" in text
    assert "_sessions" in text


def test_doc_mentions_session_ownership_and_test_mode():
    text = _doc()

    assert "session ownership" in text.lower()
    assert "TEST_MODE" in text


def test_doc_mentions_focused_regression():
    text = _doc().lower()

    assert "focused regression" in text


def test_doc_recommends_keeping_sessions_cache_until_eviction_policy():
    text = _doc()

    assert "Keep `_sessions` cache in `app.py` until an eviction policy is designed" in text
