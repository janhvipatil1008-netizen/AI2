"""
Audit doc existence and content checks for the debug/admin route audit.

These tests do not start the app or open DB connections.
They verify only that docs/ai2-debug-admin-route-audit.md exists
and contains all required sections and keywords.
"""

import os

_DOC_PATH = os.path.join(
    os.path.dirname(__file__), "..", "docs", "ai2-debug-admin-route-audit.md"
)


def _doc_text() -> str:
    with open(_DOC_PATH, encoding="utf-8") as f:
        return f.read()


def test_audit_doc_exists():
    assert os.path.isfile(_DOC_PATH), f"Audit doc not found: {_DOC_PATH}"


def test_doc_mentions_debug_routes():
    assert "/debug/" in _doc_text()


def test_doc_mentions_admin_routes():
    assert "/admin/" in _doc_text()


def test_doc_mentions_debug_token():
    assert "AI2_DEBUG_TOKEN" in _doc_text()


def test_doc_mentions_404_without_token():
    text = _doc_text()
    assert "404" in text
    assert "without" in text.lower() or "not found" in text.lower()


def test_doc_mentions_db_connections():
    text = _doc_text()
    assert "DB" in text or "DB connection" in text
    assert "get_conn" in text or "DB Connection" in text or "Opens DB" in text


def test_doc_mentions_response_sanitization():
    text = _doc_text()
    assert "sanitiz" in text.lower() or "redact" in text.lower() or "_safe_debug_error_message" in text


def test_doc_mentions_debug_module():
    assert "routes/debug.py" in _doc_text()


def test_doc_mentions_admin_module():
    assert "routes/admin.py" in _doc_text()


def test_doc_recommends_safe_split_plan():
    text = _doc_text()
    assert "Safe Split Plan" in text or "safe split" in text.lower()
    # Should recommend incremental slices
    assert "one slice" in text.lower() or "at a time" in text.lower() or "each with its own commit" in text.lower()
