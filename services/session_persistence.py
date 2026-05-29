"""Session persistence helpers shared by app and route dependency wiring."""

import json
import logging
import os
from datetime import datetime
from typing import Optional

from context.learner_profile import LearnerProfile, load_profile, save_profile
from database.pool import get_conn

_logger = logging.getLogger(__name__)


def _is_test_mode(test_mode: bool | None) -> bool:
    if test_mode is None:
        return os.getenv("AI2_TEST_MODE") == "1"
    return test_mode


def save_exchange_to_history(
    user_id: str,
    session_id: str,
    user_message: str,
    assistant_reply: str,
    agent_used: str,
    *,
    test_mode: bool | None = None,
    logger: logging.Logger | None = None,
) -> None:
    """Append a single exchange to the permanent conversation_history table."""
    if _is_test_mode(test_mode) or not user_id:
        return
    now = datetime.now().isoformat()
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO conversation_history "
                    "(user_id, session_id, user_message, assistant_reply, agent_used, timestamp) "
                    "VALUES (%s, %s, %s, %s, %s, %s)",
                    (user_id, session_id, user_message, assistant_reply, agent_used, now),
                )
    except Exception as exc:
        (logger or _logger).warning(f"_save_exchange_to_history failed (non-fatal): {exc}")


def get_user_history(
    user_id: str,
    limit: int = 200,
    *,
    test_mode: bool | None = None,
) -> list[dict]:
    """Return full conversation history for a user from the permanent table."""
    if _is_test_mode(test_mode) or not user_id:
        return []
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT session_id, user_message, assistant_reply, agent_used, timestamp "
                    "FROM conversation_history WHERE user_id = %s ORDER BY timestamp DESC LIMIT %s",
                    (user_id, limit),
                )
                rows = cur.fetchall()
        return [
            {
                "session_id":      r[0],
                "user_message":    r[1],
                "assistant_reply": r[2],
                "agent_used":      r[3],
                "timestamp":       r[4],
            }
            for r in rows
        ]
    except Exception:
        return []


def save_profile_db(
    profile: LearnerProfile,
    *,
    test_mode: bool | None = None,
    logger: logging.Logger | None = None,
) -> None:
    """Persist a LearnerProfile to PostgreSQL."""
    if _is_test_mode(test_mode):
        return
    try:
        with get_conn() as conn:
            save_profile(profile, conn)
    except Exception as exc:
        (logger or _logger).warning(f"_save_profile_db failed (non-fatal): {exc}")


def load_profile_db(
    user_id: str,
    *,
    test_mode: bool | None = None,
) -> Optional[LearnerProfile]:
    if _is_test_mode(test_mode) or not user_id:
        return None
    try:
        with get_conn() as conn:
            return load_profile(user_id, conn)
    except Exception:
        return None


def get_user_sessions(
    user_id: str,
    limit: int = 10,
    *,
    test_mode: bool | None = None,
) -> list[dict]:
    """Return recent sessions for a user, ordered by updated_at desc."""
    if _is_test_mode(test_mode) or not user_id:
        return []
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT session_id, session_data, updated_at FROM sessions "
                    "WHERE user_id = %s ORDER BY updated_at DESC LIMIT %s",
                    (user_id, limit),
                )
                rows = cur.fetchall()
        result = []
        for session_id, data_json, updated_at in rows:
            try:
                data = json.loads(data_json)
                result.append({
                    "session_id":   session_id,
                    "track":        data.get("track", ""),
                    "current_week": data.get("current_week", 1),
                    "updated_at":   updated_at,
                })
            except Exception:
                continue
        return result
    except Exception:
        return []
