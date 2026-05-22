import logging

from core.logging import get_logger, safe_error_metadata


def test_get_logger_returns_logger():
    logger = get_logger("tests.ai2.logger")

    assert isinstance(logger, logging.Logger)
    assert logger.name == "tests.ai2.logger"


def test_repeated_get_logger_calls_do_not_add_duplicate_handlers():
    root = logging.getLogger()
    before = len(root.handlers)

    get_logger("tests.ai2.dup")
    get_logger("tests.ai2.dup")

    expected = before if before else 1
    assert len(root.handlers) == expected


def test_get_logger_respects_ai2_log_level_env(monkeypatch):
    monkeypatch.setenv("AI2_LOG_LEVEL", "DEBUG")

    logger = get_logger("tests.ai2.debug")

    assert logger.level == logging.DEBUG


def test_safe_error_metadata_includes_type_and_truncated_message():
    metadata = safe_error_metadata(RuntimeError("short failure"))

    assert metadata["error_type"] == "RuntimeError"
    assert metadata["error_message"] == "short failure"


def test_safe_error_metadata_includes_extra_fields():
    metadata = safe_error_metadata(ValueError("bad"), topic_id="topic-1", refresh=True)

    assert metadata["topic_id"] == "topic-1"
    assert metadata["refresh"] is True


def test_safe_error_metadata_truncates_long_messages():
    metadata = safe_error_metadata(RuntimeError("x" * 500))

    assert len(metadata["error_message"]) == 300
    assert metadata["error_message"] == "x" * 300
