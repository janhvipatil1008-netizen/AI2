from pathlib import Path


DOC = Path("docs/ai2-chat-session-route-audit.md")


def _text() -> str:
    return DOC.read_text(encoding="utf-8")


def test_chat_session_route_audit_doc_exists():
    assert DOC.exists()


def test_doc_mentions_chat_orchestrator_path():
    assert "chat/orchestrator path" in _text()


def test_doc_mentions_structured_topic_learning_path():
    assert "structured topic learning path" in _text()


def test_doc_mentions_routes_chat_py():
    assert "routes/chat.py" in _text()


def test_doc_mentions_orchestrator_unchanged():
    assert "orchestrator.py unchanged" in _text()


def test_doc_mentions_test_mode_risk():
    assert "TEST_MODE risk" in _text()


def test_doc_mentions_session_ownership():
    assert "session ownership" in _text()


def test_doc_mentions_route_url_stability():
    assert "route URL stability" in _text()
