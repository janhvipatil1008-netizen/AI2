"""Manual curriculum seed script.

Builds the current temporary syllabus export and upserts it into the DB
tables: learning_tracks, learning_modules, learning_topics.

Usage:
    python scripts/seed_curriculum.py

Requires SUPABASE_DATABASE_URL to be set in the environment (or .env loaded
before running).  The script never runs automatically — it must be invoked
explicitly.

Safe to re-run: all upserts use ON CONFLICT DO UPDATE, so repeated runs are
idempotent once the unique constraints are satisfied.
"""

from __future__ import annotations

import sys


def _get_connection():
    """Open a psycopg2 connection using the existing pool helper.

    Reads SUPABASE_DATABASE_URL only inside this function, never at import time.
    Raises RuntimeError with a clear message if the env var is missing.
    """
    try:
        from database.pool import _connect
        return _connect()
    except RuntimeError as exc:
        raise RuntimeError(
            "Cannot connect to database. "
            "Set SUPABASE_DATABASE_URL before running this script."
        ) from exc


def run_seed(conn) -> dict:
    """Build the curriculum export and seed it via the repository layer.

    Accepts an open psycopg2 connection; does not commit or close it —
    that is the caller's responsibility.
    """
    from curriculum.seed_export import build_curriculum_seed_export
    from repositories.curriculum_repository import seed_curriculum_export

    export = build_curriculum_seed_export()
    return seed_curriculum_export(conn, export)


def main() -> None:
    """Entry point — connect, seed, commit, and report counts."""
    print("AI² Curriculum Seed Script")
    print("Building curriculum export from current syllabus...")

    try:
        conn = _get_connection()
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    try:
        counts = run_seed(conn)
        conn.commit()
        print(f"  Tracks  seeded: {counts['tracks']}")
        print(f"  Modules seeded: {counts['modules']}")
        print(f"  Topics  seeded: {counts['topics']}")
        print("Done.")
    except Exception as exc:
        conn.rollback()
        print(f"ERROR: Seeding failed — {exc}", file=sys.stderr)
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
