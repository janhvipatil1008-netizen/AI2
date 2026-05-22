"""Repository functions for the content_cache DB table.

All functions accept an open psycopg2 connection.  They do not open
connections themselves, read env vars, or make Claude/provider calls.

content_cache stores shared canonical AI-generated content keyed by a
deterministic cache_key that encodes all content dimensions (track, topic,
content type, difficulty, language, version).  Rows are not tied to any
session or user — they are shared across all learners.

Not wired into routes or services yet.
"""

from __future__ import annotations

import json
import re


def build_content_cache_key(
    *,
    track_key: str | None,
    legacy_topic_id: str,
    content_type: str,
    difficulty_level: str = "beginner",
    language: str = "en",
    version: str = "v1",
) -> str:
    """Return a stable, deterministic cache key encoding all content dimensions.

    The key is lowercase, whitespace-normalised, and safe for use as a TEXT
    lookup in the content_cache table.  An absent or empty track_key is
    normalised to 'unknown'.

    Example:
        track:aipm|topic:rag-basics|type:base_lesson|level:beginner|lang:en|version:v1
    """
    def _norm(value: str | None, fallback: str = "unknown") -> str:
        if not value or not value.strip():
            return fallback
        return re.sub(r"\s+", "-", value.strip().lower())

    return (
        f"track:{_norm(track_key)}"
        f"|topic:{_norm(legacy_topic_id)}"
        f"|type:{_norm(content_type)}"
        f"|level:{_norm(difficulty_level, 'beginner')}"
        f"|lang:{_norm(language, 'en')}"
        f"|version:{_norm(version, 'v1')}"
    )


def get_cached_content(
    conn,
    *,
    cache_key: str,
) -> dict | None:
    """Return the active content_cache row matching cache_key, or None."""
    import psycopg2.extras

    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """
            SELECT * FROM content_cache
            WHERE cache_key = %s AND status = 'active'
            LIMIT 1
            """,
            (cache_key,),
        )
        row = cur.fetchone()
    return dict(row) if row else None


def upsert_cached_content(
    conn,
    *,
    cache_key: str,
    track_key: str | None,
    legacy_topic_id: str,
    content_type: str,
    content: str,
    difficulty_level: str = "beginner",
    language: str = "en",
    version: str = "v1",
    provider: str | None = None,
    model: str | None = None,
    metadata: dict | None = None,
    status: str = "active",
) -> None:
    """Insert or update a content_cache row keyed on cache_key.

    On conflict (cache_key already exists) the content, provider, model,
    metadata, status, and updated_at are overwritten; created_at is preserved.
    """
    meta_json = json.dumps(metadata or {})
    sql = """
        INSERT INTO content_cache
            (cache_key, track_key, legacy_topic_id, content_type, content,
             difficulty_level, language, version, provider, model, metadata, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (cache_key) DO UPDATE SET
            content    = EXCLUDED.content,
            provider   = EXCLUDED.provider,
            model      = EXCLUDED.model,
            metadata   = EXCLUDED.metadata,
            status     = EXCLUDED.status,
            updated_at = NOW()
    """
    with conn.cursor() as cur:
        cur.execute(sql, (
            cache_key,
            track_key or None,
            legacy_topic_id,
            content_type,
            content,
            difficulty_level,
            language,
            version,
            provider,
            model,
            meta_json,
            status,
        ))


def mark_cached_content_stale(
    conn,
    *,
    cache_key: str,
) -> bool:
    """Set status='stale' for the content_cache row matching cache_key.

    Returns True if a row was updated, False if no matching row existed.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE content_cache
            SET status     = 'stale',
                updated_at = NOW()
            WHERE cache_key = %s
            """,
            (cache_key,),
        )
        return cur.rowcount > 0
