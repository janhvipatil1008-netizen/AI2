"""Storage-related feature flag helpers.

These helpers only inspect environment flags. They do not open DB
connections, read tables, or change runtime source-of-truth behavior.
"""

from __future__ import annotations

import os


_TRUTHY_VALUES = {"1", "true", "yes", "on"}


def is_truthy_env_flag(name: str) -> bool:
    raw = os.environ.get(name, "")
    return raw.strip().lower() in _TRUTHY_VALUES


def is_db_write_through_enabled() -> bool:
    return is_truthy_env_flag("AI2_DB_WRITE_THROUGH_ENABLED")


def is_curriculum_db_reads_enabled() -> bool:
    return is_truthy_env_flag("AI2_CURRICULUM_DB_READS_ENABLED")


def is_modular_curriculum_reads_enabled() -> bool:
    return is_truthy_env_flag("AI2_MODULAR_CURRICULUM_READS_ENABLED")


def is_progress_db_reads_enabled() -> bool:
    return is_truthy_env_flag("AI2_PROGRESS_DB_READS_ENABLED")


def is_todos_db_reads_enabled() -> bool:
    return is_truthy_env_flag("AI2_TODOS_DB_READS_ENABLED")


def is_usage_limits_enabled() -> bool:
    return is_truthy_env_flag("AI2_USAGE_LIMITS_ENABLED")
