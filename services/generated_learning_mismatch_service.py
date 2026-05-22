"""Pure mismatch comparison for generated-learning SessionContext vs DB mirrors.

Accepts already-read DB mirror state and a SessionContext-like object. Never
opens DB connections, reads env vars, imports routes, logs, or mutates session.
Output intentionally excludes full generated content, answers, submissions,
interview responses, and notes.
"""

from __future__ import annotations

_PRACTICE_TYPES = ("quiz", "portfolio_task", "interview_practice")


def _text_presence(value: str | None) -> bool:
    return bool(str(value or "").strip())


def _safe_record_presence(record: dict | None, required_field: str) -> bool:
    return bool(record) and _text_presence(record.get(required_field))


def _text_length(record: dict | None, field: str) -> int:
    if not record:
        return 0
    return len(str(record.get(field) or "").strip())


def _metadata_value(record: dict | None, field: str):
    if not record:
        return None
    value = record.get(field)
    if value == "":
        return None
    return value


def _version(record: dict | None):
    value = _metadata_value(record, "version")
    if value is None or value == 0:
        return None
    return str(value)


def _base_text_snapshot(record: dict | None, text_field: str) -> dict:
    return {
        f"{text_field}_present": _safe_record_presence(record, text_field),
        f"{text_field}_length": _text_length(record, text_field),
    }


def _generated_content_snapshot(record: dict | None) -> dict:
    snapshot = _base_text_snapshot(record, "content")
    snapshot.update({
        "model": str(_metadata_value(record, "model") or ""),
        "freshness_label": str(_metadata_value(record, "freshness_label") or ""),
        "version": _version(record),
    })
    return snapshot


def _add_field_mismatch(mismatches: list[dict], field: str, session_value, db_value) -> None:
    if session_value != db_value:
        mismatches.append({
            "field": field,
            "session_value": session_value,
            "db_value": db_value,
        })


def _compare_snapshots(
    *,
    session_snapshot: dict,
    db_snapshot: dict | None,
    db_missing: bool,
    fields: tuple[str, ...],
) -> list[dict]:
    mismatches = []
    if db_missing:
        if any(session_snapshot.get(field) for field in fields if field.endswith("_present")):
            mismatches.append({
                "field": "record_presence",
                "session_value": "present",
                "db_value": "missing",
            })
        return mismatches

    for field in fields:
        _add_field_mismatch(mismatches, field, session_snapshot.get(field), db_snapshot.get(field))
    return mismatches


def _compare_optional_metadata(
    *,
    mismatches: list[dict],
    session_snapshot: dict,
    db_snapshot: dict,
    fields: tuple[str, ...],
) -> None:
    for field in fields:
        session_value = session_snapshot.get(field)
        db_value = db_snapshot.get(field)
        if session_value or db_value:
            _add_field_mismatch(mismatches, field, session_value, db_value)


def compare_generated_topic_content(
    *,
    session,
    legacy_topic_id: str,
    db_content: dict | None,
) -> dict:
    session_record = session.get_generated_topic_content(legacy_topic_id)
    session_snapshot = _generated_content_snapshot(session_record)
    db_missing = db_content is None
    db_snapshot = None if db_missing else _generated_content_snapshot(db_content)

    mismatches = _compare_snapshots(
        session_snapshot=session_snapshot,
        db_snapshot=db_snapshot,
        db_missing=db_missing,
        fields=("content_present", "content_length"),
    )
    if db_snapshot is not None:
        _compare_optional_metadata(
            mismatches=mismatches,
            session_snapshot=session_snapshot,
            db_snapshot=db_snapshot,
            fields=("model", "freshness_label", "version"),
        )

    return {
        "type": "generated_topic_content",
        "legacy_topic_id": legacy_topic_id,
        "matches": len(mismatches) == 0,
        "db_missing": db_missing,
        "mismatches": mismatches,
        "session_snapshot": session_snapshot,
        "db_snapshot": db_snapshot,
    }


def compare_generated_topic_practice(
    *,
    session,
    legacy_topic_id: str,
    db_practice: dict,
) -> dict:
    mismatches = []
    practice_types = {}
    db_practice = db_practice or {}

    for practice_type in _PRACTICE_TYPES:
        session_record = session.get_generated_topic_practice(legacy_topic_id, practice_type)
        db_record = db_practice.get(practice_type)
        db_missing = db_record is None
        session_snapshot = _generated_content_snapshot(session_record)
        db_snapshot = None if db_missing else _generated_content_snapshot(db_record)
        type_mismatches = _compare_snapshots(
            session_snapshot=session_snapshot,
            db_snapshot=db_snapshot,
            db_missing=db_missing,
            fields=("content_present", "content_length"),
        )
        if db_snapshot is not None:
            _compare_optional_metadata(
                mismatches=type_mismatches,
                session_snapshot=session_snapshot,
                db_snapshot=db_snapshot,
                fields=("model", "freshness_label", "version"),
            )

        practice_types[practice_type] = {
            "matches": len(type_mismatches) == 0,
            "db_missing": db_missing,
            "mismatches": type_mismatches,
            "session_snapshot": session_snapshot,
            "db_snapshot": db_snapshot,
        }
        for mismatch in type_mismatches:
            mismatches.append({"practice_type": practice_type, **mismatch})

    return {
        "type": "generated_topic_practice",
        "legacy_topic_id": legacy_topic_id,
        "matches": len(mismatches) == 0,
        "mismatches": mismatches,
        "practice_types": practice_types,
    }


def _submission_snapshot(record: dict | None, text_fields: tuple[str, ...]) -> dict:
    snapshot = {}
    for field in text_fields:
        snapshot.update(_base_text_snapshot(record, field))
    snapshot["score"] = _metadata_value(record, "score")
    snapshot["model"] = str(_metadata_value(record, "model") or "")
    return snapshot


def _compare_submission(
    *,
    comparison_type: str,
    legacy_topic_id: str,
    session_record: dict,
    db_record: dict | None,
    text_fields: tuple[str, ...],
) -> dict:
    session_snapshot = _submission_snapshot(session_record, text_fields)
    db_missing = db_record is None
    db_snapshot = None if db_missing else _submission_snapshot(db_record, text_fields)

    compare_fields = tuple(
        item
        for field in text_fields
        for item in (f"{field}_present", f"{field}_length")
    )
    mismatches = _compare_snapshots(
        session_snapshot=session_snapshot,
        db_snapshot=db_snapshot,
        db_missing=db_missing,
        fields=compare_fields,
    )
    if db_snapshot is not None:
        _add_field_mismatch(mismatches, "score", session_snapshot.get("score"), db_snapshot.get("score"))
        _compare_optional_metadata(
            mismatches=mismatches,
            session_snapshot=session_snapshot,
            db_snapshot=db_snapshot,
            fields=("model",),
        )

    return {
        "type": comparison_type,
        "legacy_topic_id": legacy_topic_id,
        "matches": len(mismatches) == 0,
        "db_missing": db_missing,
        "mismatches": mismatches,
        "session_snapshot": session_snapshot,
        "db_snapshot": db_snapshot,
    }


def compare_quiz_submission(
    *,
    session,
    legacy_topic_id: str,
    db_submission: dict | None,
) -> dict:
    return _compare_submission(
        comparison_type="quiz_submission",
        legacy_topic_id=legacy_topic_id,
        session_record=session.get_quiz_submission(legacy_topic_id),
        db_record=db_submission,
        text_fields=("answers", "evaluation"),
    )


def compare_portfolio_submission(
    *,
    session,
    legacy_topic_id: str,
    db_submission: dict | None,
) -> dict:
    return _compare_submission(
        comparison_type="portfolio_submission",
        legacy_topic_id=legacy_topic_id,
        session_record=session.get_portfolio_submission(legacy_topic_id),
        db_record=db_submission,
        text_fields=("submission", "feedback"),
    )


def compare_interview_submission(
    *,
    session,
    legacy_topic_id: str,
    db_submission: dict | None,
) -> dict:
    return _compare_submission(
        comparison_type="interview_submission",
        legacy_topic_id=legacy_topic_id,
        session_record=session.get_interview_submission(legacy_topic_id),
        db_record=db_submission,
        text_fields=("answer", "feedback"),
    )


def compare_topic_notes(
    *,
    session,
    legacy_topic_id: str,
    db_notes: dict | None,
) -> dict:
    session_record = session.get_topic_notes(legacy_topic_id)
    text_fields = ("reflection", "confusions", "application_idea")
    session_snapshot = {}
    for field in text_fields:
        session_snapshot.update(_base_text_snapshot(session_record, field))
    db_missing = db_notes is None
    db_snapshot = None
    if db_notes is not None:
        db_snapshot = {}
        for field in text_fields:
            db_snapshot.update(_base_text_snapshot(db_notes, field))

    compare_fields = tuple(
        item
        for field in text_fields
        for item in (f"{field}_present", f"{field}_length")
    )
    mismatches = _compare_snapshots(
        session_snapshot=session_snapshot,
        db_snapshot=db_snapshot,
        db_missing=db_missing,
        fields=compare_fields,
    )

    return {
        "type": "topic_notes",
        "legacy_topic_id": legacy_topic_id,
        "matches": len(mismatches) == 0,
        "db_missing": db_missing,
        "mismatches": mismatches,
        "session_snapshot": session_snapshot,
        "db_snapshot": db_snapshot,
    }


def compare_generated_learning_state(
    *,
    session,
    legacy_topic_id: str,
    db_state: dict | None,
) -> dict:
    db_state = db_state or {}
    comparisons = [
        compare_generated_topic_content(
            session=session,
            legacy_topic_id=legacy_topic_id,
            db_content=db_state.get("generated_topic_content"),
        ),
        compare_generated_topic_practice(
            session=session,
            legacy_topic_id=legacy_topic_id,
            db_practice=db_state.get("generated_topic_practice") or {},
        ),
        compare_quiz_submission(
            session=session,
            legacy_topic_id=legacy_topic_id,
            db_submission=db_state.get("quiz_submission"),
        ),
        compare_portfolio_submission(
            session=session,
            legacy_topic_id=legacy_topic_id,
            db_submission=db_state.get("portfolio_submission"),
        ),
        compare_interview_submission(
            session=session,
            legacy_topic_id=legacy_topic_id,
            db_submission=db_state.get("interview_submission"),
        ),
        compare_topic_notes(
            session=session,
            legacy_topic_id=legacy_topic_id,
            db_notes=db_state.get("topic_notes"),
        ),
    ]

    return {
        "matches": all(comparison["matches"] for comparison in comparisons),
        "legacy_topic_id": legacy_topic_id,
        "comparisons": comparisons,
    }
