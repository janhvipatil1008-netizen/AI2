"""Optional write-through helper for generated content, practice, submissions, and topic notes.

Controlled entirely by the AI2_DB_WRITE_THROUGH_ENABLED environment variable.
When the flag is off (the default), every public function is a no-op.

Design constraints
------------------
- Never opens a DB connection — callers pass one in.
- Never commits or rolls back — that is the caller's responsibility.
- Never mutates SessionContext — reads only.
- Not wired into any route or service yet.
"""

from __future__ import annotations

from services.storage_flags import is_db_write_through_enabled

_PRACTICE_TYPES = ("quiz", "portfolio_task", "interview_practice")


# ── Generated topic content ───────────────────────────────────────────────────

def maybe_write_generated_topic_content(
    *,
    conn,
    session,
    user_id: str | None,
    session_id: str | None,
    legacy_topic_id: str,
) -> bool:
    """Write AI-generated topic content from SessionContext to DB if the flag is on.

    Returns True when a write was attempted, False when skipped.
    Raises on DB errors so the caller can decide to rollback.
    """
    if not is_db_write_through_enabled() or conn is None or not legacy_topic_id:
        return False

    record = session.get_generated_topic_content(legacy_topic_id)
    if not record.get("content"):
        return False

    from repositories.generated_content_repository import upsert_generated_topic_content

    upsert_generated_topic_content(
        conn,
        user_id=user_id,
        session_id=session_id,
        legacy_topic_id=legacy_topic_id,
        content_record=record,
    )
    return True


# ── Generated topic practice ──────────────────────────────────────────────────

def maybe_write_generated_topic_practice(
    *,
    conn,
    session,
    user_id: str | None,
    session_id: str | None,
    legacy_topic_id: str,
    practice_type: str,
) -> bool:
    """Write AI-generated practice content from SessionContext to DB if the flag is on.

    Returns True when a write was attempted, False when skipped.
    Raises on DB errors so the caller can decide to rollback.
    """
    if not is_db_write_through_enabled() or conn is None or not legacy_topic_id or not practice_type:
        return False

    record = session.get_generated_topic_practice(legacy_topic_id, practice_type)
    if not record.get("content"):
        return False

    from repositories.generated_content_repository import upsert_generated_topic_practice

    upsert_generated_topic_practice(
        conn,
        user_id=user_id,
        session_id=session_id,
        legacy_topic_id=legacy_topic_id,
        practice_type=practice_type,
        practice_record=record,
    )
    return True


def maybe_write_all_generated_topic_practice(
    *,
    conn,
    session,
    user_id: str | None,
    session_id: str | None,
    legacy_topic_id: str,
) -> int:
    """Attempt to write all three practice types for a topic.

    Returns the number of repository calls made (0 when skipped).
    Raises on the first DB error so the caller can decide to rollback.
    """
    count = 0
    for practice_type in _PRACTICE_TYPES:
        if maybe_write_generated_topic_practice(
            conn=conn,
            session=session,
            user_id=user_id,
            session_id=session_id,
            legacy_topic_id=legacy_topic_id,
            practice_type=practice_type,
        ):
            count += 1
    return count


# ── Quiz submission ───────────────────────────────────────────────────────────

def maybe_write_quiz_submission(
    *,
    conn,
    session,
    user_id: str | None,
    session_id: str | None,
    legacy_topic_id: str,
) -> bool:
    """Write the quiz submission from SessionContext to DB if the flag is on.

    Returns True when a write was attempted, False when skipped.
    Raises on DB errors so the caller can decide to rollback.
    """
    if not is_db_write_through_enabled() or conn is None or not legacy_topic_id:
        return False

    record = session.get_quiz_submission(legacy_topic_id)
    if not record.get("answers"):
        return False

    from repositories.submissions_repository import upsert_quiz_submission

    upsert_quiz_submission(
        conn,
        user_id=user_id,
        session_id=session_id,
        legacy_topic_id=legacy_topic_id,
        submission=record,
    )
    return True


# ── Portfolio submission ──────────────────────────────────────────────────────

def maybe_write_portfolio_submission(
    *,
    conn,
    session,
    user_id: str | None,
    session_id: str | None,
    legacy_topic_id: str,
) -> bool:
    """Write the portfolio submission from SessionContext to DB if the flag is on.

    Returns True when a write was attempted, False when skipped.
    Raises on DB errors so the caller can decide to rollback.
    """
    if not is_db_write_through_enabled() or conn is None or not legacy_topic_id:
        return False

    record = session.get_portfolio_submission(legacy_topic_id)
    if not record.get("submission"):
        return False

    from repositories.submissions_repository import upsert_portfolio_submission

    upsert_portfolio_submission(
        conn,
        user_id=user_id,
        session_id=session_id,
        legacy_topic_id=legacy_topic_id,
        submission=record,
    )
    return True


# ── Interview submission ──────────────────────────────────────────────────────

def maybe_write_interview_submission(
    *,
    conn,
    session,
    user_id: str | None,
    session_id: str | None,
    legacy_topic_id: str,
) -> bool:
    """Write the interview submission from SessionContext to DB if the flag is on.

    Returns True when a write was attempted, False when skipped.
    Raises on DB errors so the caller can decide to rollback.
    """
    if not is_db_write_through_enabled() or conn is None or not legacy_topic_id:
        return False

    record = session.get_interview_submission(legacy_topic_id)
    if not record.get("answer"):
        return False

    from repositories.submissions_repository import upsert_interview_submission

    upsert_interview_submission(
        conn,
        user_id=user_id,
        session_id=session_id,
        legacy_topic_id=legacy_topic_id,
        submission=record,
    )
    return True


# ── Topic notes ───────────────────────────────────────────────────────────────

def maybe_write_topic_notes(
    *,
    conn,
    session,
    user_id: str | None,
    session_id: str | None,
    legacy_topic_id: str,
) -> bool:
    """Write topic notes from SessionContext to DB if the flag is on.

    Skips if all note fields (reflection, confusions, application_idea) are empty.
    Returns True when a write was attempted, False when skipped.
    Raises on DB errors so the caller can decide to rollback.
    """
    if not is_db_write_through_enabled() or conn is None or not legacy_topic_id:
        return False

    notes = session.get_topic_notes(legacy_topic_id)
    if not any((
        notes.get("reflection"),
        notes.get("confusions"),
        notes.get("application_idea"),
    )):
        return False

    from repositories.topic_notes_repository import upsert_topic_notes

    upsert_topic_notes(
        conn,
        user_id=user_id,
        session_id=session_id,
        legacy_topic_id=legacy_topic_id,
        notes=notes,
    )
    return True


# ── Aggregate ─────────────────────────────────────────────────────────────────

def maybe_write_generated_learning_state(
    *,
    conn,
    session,
    user_id: str | None,
    session_id: str | None,
    legacy_topic_id: str,
) -> dict:
    """Convenience wrapper: write all generated-learning state for one topic.

    Returns a summary dict indicating what was written.
    Raises on the first DB error so the caller can decide to rollback.
    """
    return {
        "generated_topic_content_written": maybe_write_generated_topic_content(
            conn=conn, session=session, user_id=user_id,
            session_id=session_id, legacy_topic_id=legacy_topic_id,
        ),
        "generated_topic_practice_written": maybe_write_all_generated_topic_practice(
            conn=conn, session=session, user_id=user_id,
            session_id=session_id, legacy_topic_id=legacy_topic_id,
        ),
        "quiz_submission_written": maybe_write_quiz_submission(
            conn=conn, session=session, user_id=user_id,
            session_id=session_id, legacy_topic_id=legacy_topic_id,
        ),
        "portfolio_submission_written": maybe_write_portfolio_submission(
            conn=conn, session=session, user_id=user_id,
            session_id=session_id, legacy_topic_id=legacy_topic_id,
        ),
        "interview_submission_written": maybe_write_interview_submission(
            conn=conn, session=session, user_id=user_id,
            session_id=session_id, legacy_topic_id=legacy_topic_id,
        ),
        "topic_notes_written": maybe_write_topic_notes(
            conn=conn, session=session, user_id=user_id,
            session_id=session_id, legacy_topic_id=legacy_topic_id,
        ),
    }
