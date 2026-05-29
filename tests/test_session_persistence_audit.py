from pathlib import Path


DOC = Path("docs/ai2-session-persistence-audit.md")


def _text() -> str:
    return DOC.read_text(encoding="utf-8")


def test_session_persistence_audit_doc_exists():
    assert DOC.exists()


def test_doc_mentions_core_session_helpers():
    text = _text()
    assert "_sessions" in text
    assert "_get_session_data" in text
    assert "_save_session" in text


def test_doc_mentions_recommended_service_destination():
    assert "services/session_persistence.py" in _text()


def test_doc_mentions_session_ownership_risk():
    text = _text().lower()
    assert "session ownership" in text
    assert "cross-user data leakage" in text


def test_doc_mentions_test_mode_behavior():
    assert "TEST_MODE behavior" in _text()


def test_doc_mentions_eviction_policy():
    text = _text().lower()
    assert "eviction policy" in text
    assert "ttl" in text or "lru" in text


def test_doc_recommends_small_migration_slices():
    text = _text().lower()
    assert "small migration slices" in text
    assert "move history helpers" in text
