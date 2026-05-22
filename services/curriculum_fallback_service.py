"""Fallback-safe curriculum reader.

Attempts DB reads when AI2_CURRICULUM_DB_READS_ENABLED is ON and a
connection is provided; falls back to the existing syllabus helpers
when the flag is off, the connection is absent, the row is missing,
or the DB raises.

Design constraints
------------------
- Does not open DB connections at import time or ever.
- Does not run seed scripts.
- Does not mutate SessionContext.
- Does not change runtime routes.
- Does not read environment variables directly — delegates to storage_flags.
- Never touches the database package.
"""

from __future__ import annotations

from config import CareerTrack, TRACK_TAGLINES
from core.logging import safe_error_metadata
from curriculum.syllabus import ROLE_TRACKS
from curriculum.topics import get_all_topics, get_topics_for_track
from services.storage_flags import is_curriculum_db_reads_enabled


# ── Track ─────────────────────────────────────────────────────────────────────

def get_track_with_fallback(*, conn, track_key: str) -> dict:
    """Return track info, preferring DB when enabled, else syllabus fallback.

    Returns:
        {
            "source": "db" | "fallback" | "error_fallback",
            "track_key": str,
            "track": dict | None,
            "error": str | None,
            "notes": list[str],
        }
    """
    notes: list[str] = []

    if is_curriculum_db_reads_enabled() and conn is not None:
        try:
            from services.curriculum_read_service import get_track_by_key_from_db
            row = get_track_by_key_from_db(conn, track_key)
            if row is not None:
                return {
                    "source":    "db",
                    "track_key": track_key,
                    "track":     row,
                    "error":     None,
                    "notes":     notes,
                }
            notes.append(f"No DB row for track_key={track_key!r}; using fallback.")
            return {
                "source":    "fallback",
                "track_key": track_key,
                "track":     _track_from_syllabus(track_key),
                "error":     None,
                "notes":     notes,
            }
        except Exception as exc:
            meta = safe_error_metadata(exc)
            err  = f"{meta['error_type']}: {meta['error_message']}"
            notes.append("DB read failed; using fallback.")
            return {
                "source":    "error_fallback",
                "track_key": track_key,
                "track":     _track_from_syllabus(track_key),
                "error":     err,
                "notes":     notes,
            }

    return {
        "source":    "fallback",
        "track_key": track_key,
        "track":     _track_from_syllabus(track_key),
        "error":     None,
        "notes":     notes,
    }


# ── Topic ─────────────────────────────────────────────────────────────────────

def get_topic_with_fallback(*, conn, legacy_topic_id: str) -> dict:
    """Return topic info, preferring DB when enabled, else syllabus fallback.

    Returns:
        {
            "source": "db" | "fallback" | "error_fallback",
            "legacy_topic_id": str,
            "topic": dict | None,
            "error": str | None,
            "notes": list[str],
        }
    """
    notes: list[str] = []

    if is_curriculum_db_reads_enabled() and conn is not None:
        try:
            from services.curriculum_read_service import get_topic_by_legacy_id_from_db
            row = get_topic_by_legacy_id_from_db(conn, legacy_topic_id)
            if row is not None:
                return {
                    "source":          "db",
                    "legacy_topic_id": legacy_topic_id,
                    "topic":           row,
                    "error":           None,
                    "notes":           notes,
                }
            notes.append(f"No DB row for legacy_topic_id={legacy_topic_id!r}; using fallback.")
            return {
                "source":          "fallback",
                "legacy_topic_id": legacy_topic_id,
                "topic":           _topic_from_syllabus(legacy_topic_id),
                "error":           None,
                "notes":           notes,
            }
        except Exception as exc:
            meta = safe_error_metadata(exc)
            err  = f"{meta['error_type']}: {meta['error_message']}"
            notes.append("DB read failed; using fallback.")
            return {
                "source":          "error_fallback",
                "legacy_topic_id": legacy_topic_id,
                "topic":           _topic_from_syllabus(legacy_topic_id),
                "error":           err,
                "notes":           notes,
            }

    return {
        "source":          "fallback",
        "legacy_topic_id": legacy_topic_id,
        "topic":           _topic_from_syllabus(legacy_topic_id),
        "error":           None,
        "notes":           notes,
    }


# ── Topics list ───────────────────────────────────────────────────────────────

def get_topics_for_track_with_fallback(*, conn, track_key: str) -> dict:
    """Return topics list for a track, always using syllabus fallback for now.

    DB list-track-topics is not yet implemented. When the flag is on a note
    is added to indicate the DB path was skipped.

    Returns:
        {
            "source": "fallback",
            "track_key": str,
            "topics": list[dict],
            "error": None,
            "notes": list[str],
        }
    """
    notes: list[str] = []
    if is_curriculum_db_reads_enabled():
        notes.append(
            "DB list-topics read is not implemented yet; fallback used."
        )

    topic_cards = get_topics_for_track(track_key)
    topics = [_topic_card_to_dict(tc) for tc in topic_cards]

    return {
        "source":    "fallback",
        "track_key": track_key,
        "topics":    topics,
        "error":     None,
        "notes":     notes,
    }


# ── Internal syllabus helpers ─────────────────────────────────────────────────

def _track_from_syllabus(track_key: str) -> dict | None:
    if track_key not in ROLE_TRACKS:
        return None
    info    = ROLE_TRACKS[track_key]
    tagline = ""
    try:
        ct      = CareerTrack(track_key)
        tagline = TRACK_TAGLINES.get(ct, "")
    except ValueError:
        pass
    return {
        "track_key":   track_key,
        "title":       info.get("label", ""),
        "description": tagline,
        "status":      "active",
        "version":     "",
        "metadata":    {"icon": info.get("icon", ""), "color": info.get("color", "")},
    }


def _topic_from_syllabus(legacy_topic_id: str) -> dict | None:
    for topic in get_all_topics():
        if topic.topic_id == legacy_topic_id:
            return _topic_card_to_dict(topic)
    return None


def _topic_card_to_dict(topic) -> dict:
    return {
        "legacy_topic_id":  topic.topic_id,
        "topic_key":        topic.topic_id,
        "title":            topic.topic_title,
        "description":      topic.description,
        "freshness_label":  "",
        "estimated_minutes": None,
    }
