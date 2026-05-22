"""Generated-learning DB read service for debug and mirror validation.

Design constraints
------------------
- Does not open DB connections; callers pass one in.
- Does not read environment variables.
- Does not run queries at import time.
- Does not mutate SessionContext.
- Low-level read functions let repository exceptions propagate.
- Not wired into learner-facing routes.
"""

from __future__ import annotations

import json
from typing import Any


_PRACTICE_TYPES = ("quiz", "portfolio_task", "interview_practice")


def _metadata(value: Any) -> dict:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except Exception:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _text(value: Any) -> str:
    return str(value) if value is not None else ""


def _score(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def normalize_generated_topic_content_row(row: dict) -> dict:
    return {
        "content": _text(row.get("content")),
        "model": _text(row.get("model")),
        "version": _text(row.get("version")),
        "freshness_label": _text(row.get("freshness_label")),
        "source": _text(row.get("source")),
        "legacy_topic_id": _text(row.get("legacy_topic_id")),
        "metadata": _metadata(row.get("metadata")),
        "generated_at": _text(row.get("generated_at")),
    }


def normalize_generated_topic_practice_row(row: dict) -> dict:
    normalized = normalize_generated_topic_content_row(row)
    normalized["practice_type"] = _text(row.get("practice_type"))
    return normalized


def normalize_quiz_submission_row(row: dict) -> dict:
    return {
        "answers": _text(row.get("answers")),
        "evaluation": _text(row.get("evaluation")),
        "score": _score(row.get("score")),
        "model": _text(row.get("model")),
        "legacy_topic_id": _text(row.get("legacy_topic_id")),
        "metadata": _metadata(row.get("metadata")),
        "submitted_at": _text(row.get("submitted_at")),
        "evaluated_at": _text(row.get("evaluated_at")),
    }


def normalize_portfolio_submission_row(row: dict) -> dict:
    return {
        "submission": _text(row.get("submission")),
        "feedback": _text(row.get("feedback")),
        "score": _score(row.get("score")),
        "model": _text(row.get("model")),
        "legacy_topic_id": _text(row.get("legacy_topic_id")),
        "metadata": _metadata(row.get("metadata")),
        "submitted_at": _text(row.get("submitted_at")),
        "reviewed_at": _text(row.get("reviewed_at")),
    }


def normalize_interview_submission_row(row: dict) -> dict:
    return {
        "answer": _text(row.get("answer")),
        "feedback": _text(row.get("feedback")),
        "score": _score(row.get("score")),
        "model": _text(row.get("model")),
        "legacy_topic_id": _text(row.get("legacy_topic_id")),
        "metadata": _metadata(row.get("metadata")),
        "submitted_at": _text(row.get("submitted_at")),
        "reviewed_at": _text(row.get("reviewed_at")),
    }


def normalize_topic_notes_row(row: dict) -> dict:
    return {
        "reflection": _text(row.get("reflection")),
        "confusions": _text(row.get("confusions")),
        "application_idea": _text(row.get("application_idea")),
        "legacy_topic_id": _text(row.get("legacy_topic_id")),
        "metadata": _metadata(row.get("metadata")),
        "updated_at": _text(row.get("updated_at")),
    }


def get_generated_topic_content_from_db(
    conn,
    *,
    session_id: str,
    legacy_topic_id: str,
) -> dict | None:
    from repositories.generated_content_repository import get_generated_topic_content_by_legacy_id

    row = get_generated_topic_content_by_legacy_id(
        conn,
        session_id=session_id,
        legacy_topic_id=legacy_topic_id,
    )
    if row is None:
        return None
    return normalize_generated_topic_content_row(row)


def get_generated_topic_practice_from_db(
    conn,
    *,
    session_id: str,
    legacy_topic_id: str,
    practice_type: str,
) -> dict | None:
    from repositories.generated_content_repository import get_generated_topic_practice_by_legacy_id

    row = get_generated_topic_practice_by_legacy_id(
        conn,
        session_id=session_id,
        legacy_topic_id=legacy_topic_id,
        practice_type=practice_type,
    )
    if row is None:
        return None
    return normalize_generated_topic_practice_row(row)


def get_quiz_submission_from_db(
    conn,
    *,
    session_id: str,
    legacy_topic_id: str,
) -> dict | None:
    from repositories.submissions_repository import get_quiz_submission_by_legacy_id

    row = get_quiz_submission_by_legacy_id(
        conn,
        session_id=session_id,
        legacy_topic_id=legacy_topic_id,
    )
    if row is None:
        return None
    return normalize_quiz_submission_row(row)


def get_portfolio_submission_from_db(
    conn,
    *,
    session_id: str,
    legacy_topic_id: str,
) -> dict | None:
    from repositories.submissions_repository import get_portfolio_submission_by_legacy_id

    row = get_portfolio_submission_by_legacy_id(
        conn,
        session_id=session_id,
        legacy_topic_id=legacy_topic_id,
    )
    if row is None:
        return None
    return normalize_portfolio_submission_row(row)


def get_interview_submission_from_db(
    conn,
    *,
    session_id: str,
    legacy_topic_id: str,
) -> dict | None:
    from repositories.submissions_repository import get_interview_submission_by_legacy_id

    row = get_interview_submission_by_legacy_id(
        conn,
        session_id=session_id,
        legacy_topic_id=legacy_topic_id,
    )
    if row is None:
        return None
    return normalize_interview_submission_row(row)


def get_topic_notes_from_db(
    conn,
    *,
    session_id: str,
    legacy_topic_id: str,
) -> dict | None:
    from repositories.topic_notes_repository import get_topic_notes_by_legacy_id

    row = get_topic_notes_by_legacy_id(
        conn,
        session_id=session_id,
        legacy_topic_id=legacy_topic_id,
    )
    if row is None:
        return None
    return normalize_topic_notes_row(row)


def get_generated_learning_state_from_db(
    conn,
    *,
    session_id: str,
    legacy_topic_id: str,
) -> dict:
    return {
        "generated_topic_content": get_generated_topic_content_from_db(
            conn,
            session_id=session_id,
            legacy_topic_id=legacy_topic_id,
        ),
        "generated_topic_practice": {
            practice_type: get_generated_topic_practice_from_db(
                conn,
                session_id=session_id,
                legacy_topic_id=legacy_topic_id,
                practice_type=practice_type,
            )
            for practice_type in _PRACTICE_TYPES
        },
        "quiz_submission": get_quiz_submission_from_db(
            conn,
            session_id=session_id,
            legacy_topic_id=legacy_topic_id,
        ),
        "portfolio_submission": get_portfolio_submission_from_db(
            conn,
            session_id=session_id,
            legacy_topic_id=legacy_topic_id,
        ),
        "interview_submission": get_interview_submission_from_db(
            conn,
            session_id=session_id,
            legacy_topic_id=legacy_topic_id,
        ),
        "topic_notes": get_topic_notes_from_db(
            conn,
            session_id=session_id,
            legacy_topic_id=legacy_topic_id,
        ),
    }
