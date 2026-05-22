"""Repository functions for curriculum DB tables.

All functions accept an open psycopg2 connection.  They do not open
connections themselves, read env vars, or mutate SessionContext.
The caller is responsible for commit/rollback (use database.pool.get_conn).

Not wired into routes or services yet.
"""

from __future__ import annotations

import json

import psycopg2.extras

from curriculum.seed_export import (
    CurriculumSeedExport,
    ModuleSeedRecord,
    TopicSeedRecord,
    TrackSeedRecord,
)


def upsert_learning_track(conn, track_record: TrackSeedRecord) -> None:
    """Insert or update a learning_tracks row keyed on track_key."""
    sql = """
        INSERT INTO learning_tracks
            (track_key, title, description, status, version, metadata)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (track_key) DO UPDATE
            SET title       = EXCLUDED.title,
                description = EXCLUDED.description,
                status      = EXCLUDED.status,
                version     = EXCLUDED.version,
                metadata    = EXCLUDED.metadata,
                updated_at  = NOW()
    """
    with conn.cursor() as cur:
        cur.execute(sql, (
            track_record.track_key,
            track_record.title,
            track_record.description,
            track_record.status,
            track_record.version,
            json.dumps(track_record.metadata),
        ))


def upsert_learning_module(conn, module_record: ModuleSeedRecord) -> None:
    """Insert or update a learning_modules row keyed on (track_id, module_key).

    Looks up track_id from track_key first.  Skips silently if track not found
    (which can happen if seeding is run out of order or against an empty DB).
    """
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            "SELECT id FROM learning_tracks WHERE track_key = %s",
            (module_record.track_key,),
        )
        row = cur.fetchone()

    if not row:
        return

    track_id = row["id"]
    sql = """
        INSERT INTO learning_modules
            (track_id, module_key, title, description, sequence_order, module_type, metadata)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (track_id, module_key) DO UPDATE
            SET title          = EXCLUDED.title,
                description    = EXCLUDED.description,
                sequence_order = EXCLUDED.sequence_order,
                module_type    = EXCLUDED.module_type,
                metadata       = EXCLUDED.metadata,
                updated_at     = NOW()
    """
    with conn.cursor() as cur:
        cur.execute(sql, (
            track_id,
            module_record.module_key,
            module_record.title,
            module_record.description,
            module_record.sequence_order,
            module_record.module_type,
            json.dumps(module_record.metadata),
        ))


def upsert_learning_topic(conn, topic_record: TopicSeedRecord) -> None:
    """Insert or update a learning_topics row keyed on (module_id, topic_key).

    Looks up track_id then module_id from (track_key, module_key).  Stores
    legacy_topic_id inside the JSONB metadata column so it can be queried
    during the SessionContext → DB migration transition.

    Skips silently if the parent module is not found.
    """
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            "SELECT id FROM learning_tracks WHERE track_key = %s",
            (topic_record.track_key,),
        )
        track_row = cur.fetchone()

    if not track_row:
        return

    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            "SELECT id FROM learning_modules WHERE track_id = %s AND module_key = %s",
            (track_row["id"], topic_record.module_key),
        )
        module_row = cur.fetchone()

    if not module_row:
        return

    module_id = module_row["id"]
    metadata = {**topic_record.metadata, "legacy_topic_id": topic_record.legacy_topic_id}

    sql = """
        INSERT INTO learning_topics
            (module_id, topic_key, title, description, sequence_order,
             difficulty, freshness_label, metadata)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (module_id, topic_key) DO UPDATE
            SET title          = EXCLUDED.title,
                description    = EXCLUDED.description,
                sequence_order = EXCLUDED.sequence_order,
                difficulty     = EXCLUDED.difficulty,
                freshness_label = EXCLUDED.freshness_label,
                metadata       = EXCLUDED.metadata,
                updated_at     = NOW()
    """
    with conn.cursor() as cur:
        cur.execute(sql, (
            module_id,
            topic_record.topic_key,
            topic_record.title,
            topic_record.description,
            topic_record.sequence_order,
            topic_record.difficulty,
            topic_record.freshness_label,
            json.dumps(metadata),
        ))


def seed_curriculum_export(conn, export: CurriculumSeedExport) -> dict:
    """Upsert all records from a CurriculumSeedExport.  Returns counts dict."""
    for track in export.tracks:
        upsert_learning_track(conn, track)
    for module in export.modules:
        upsert_learning_module(conn, module)
    for topic in export.topics:
        upsert_learning_topic(conn, topic)
    return {
        "tracks":  len(export.tracks),
        "modules": len(export.modules),
        "topics":  len(export.topics),
    }


def get_learning_track_by_key(conn, track_key: str) -> dict | None:
    """Return a learning_tracks row as a dict, or None if not found."""
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            "SELECT * FROM learning_tracks WHERE track_key = %s",
            (track_key,),
        )
        row = cur.fetchone()
    return dict(row) if row else None


def get_learning_topic_by_legacy_id(conn, legacy_topic_id: str) -> dict | None:
    """Return a learning_topics row whose metadata.legacy_topic_id matches.

    legacy_topic_id is stored in the JSONB metadata column during seeding.
    """
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            "SELECT * FROM learning_topics WHERE metadata->>'legacy_topic_id' = %s",
            (legacy_topic_id,),
        )
        row = cur.fetchone()
    return dict(row) if row else None
