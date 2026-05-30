"""Observability feature flag helpers.

These helpers only inspect environment variables. They do not import
the LangSmith SDK, make network calls, or change AI generation behavior.
LangSmith tracing is off by default; it activates only when
LANGSMITH_TRACING=true and LANGSMITH_API_KEY is non-empty.
"""

from __future__ import annotations

import os

from services.storage_flags import is_truthy_env_flag


def is_langsmith_tracing_enabled() -> bool:
    """True only when LANGSMITH_TRACING=true AND LANGSMITH_API_KEY is set."""
    return is_truthy_env_flag("LANGSMITH_TRACING") and bool(get_langsmith_api_key())


def get_langsmith_api_key() -> str:
    """Return LANGSMITH_API_KEY or empty string if absent. Never raises."""
    return os.environ.get("LANGSMITH_API_KEY", "").strip()


def get_langsmith_project() -> str:
    return os.environ.get("LANGSMITH_PROJECT", "ai2-render-beta").strip()


def get_langsmith_endpoint() -> str:
    return os.environ.get("LANGSMITH_ENDPOINT", "https://api.smith.langchain.com").strip()
