"""Session persistence helpers shared by app and route dependency wiring."""

import logging
import os
from datetime import datetime

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
