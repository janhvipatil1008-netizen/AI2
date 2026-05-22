"""Small standard-library logging helpers for AI2."""

import logging
import os


_DEFAULT_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


def get_logger(name: str) -> logging.Logger:
    """Return a named logger with a basic handler if logging is unconfigured."""
    level = _log_level_from_env()
    root = logging.getLogger()

    if not root.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(_DEFAULT_FORMAT))
        root.addHandler(handler)
        root.setLevel(level)

    logger = logging.getLogger(name)
    logger.setLevel(level)
    return logger


def safe_error_metadata(error: Exception, **extra) -> dict:
    """Return short, prompt-safe metadata for an exception."""
    return {
        "error_type": type(error).__name__,
        "error_message": str(error)[:300],
        **extra,
    }


def _log_level_from_env() -> int:
    value = os.getenv("AI2_LOG_LEVEL", "INFO").upper()
    return getattr(logging, value, logging.INFO)
