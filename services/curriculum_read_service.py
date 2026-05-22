"""Safe curriculum DB read helpers.

This service is intentionally not wired into learner-facing routes yet.
Callers must pass an existing DB connection; this module never opens one.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from typing import Any

from repositories import curriculum_repository
from services import storage_flags


@dataclass
class CurriculumTrackView:
    id: str = ""
    track_key: str = ""
    title: str = ""
    description: str = ""
    status: str = ""
    version: str = ""
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class CurriculumModuleView:
    id: str = ""
    module_key: str = ""
    title: str = ""
    description: str = ""
    sequence_order: int | None = None
    module_type: str = ""
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class CurriculumTopicView:
    id: str = ""
    topic_key: str = ""
    title: str = ""
    description: str = ""
    freshness_label: str = ""
    estimated_minutes: int | None = None
    legacy_topic_id: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def normalize_track_row(row: dict) -> dict:
    metadata = _metadata_dict(row.get("metadata"))
    return CurriculumTrackView(
        id=_safe_id(row.get("id")),
        track_key=row.get("track_key") or "",
        title=row.get("title") or "",
        description=row.get("description") or "",
        status=row.get("status") or "",
        version=row.get("version") or "",
        metadata=metadata,
    ).to_dict()


def normalize_topic_row(row: dict) -> dict:
    metadata = _metadata_dict(row.get("metadata"))
    return CurriculumTopicView(
        id=_safe_id(row.get("id")),
        topic_key=row.get("topic_key") or "",
        title=row.get("title") or "",
        description=row.get("description") or "",
        freshness_label=row.get("freshness_label") or "",
        estimated_minutes=row.get("estimated_minutes"),
        legacy_topic_id=_safe_id(metadata.get("legacy_topic_id")),
    ).to_dict()


def get_track_by_key_from_db(conn, track_key: str) -> dict | None:
    row = curriculum_repository.get_learning_track_by_key(conn, track_key)
    return normalize_track_row(row) if row else None


def get_topic_by_legacy_id_from_db(conn, legacy_topic_id: str) -> dict | None:
    row = curriculum_repository.get_learning_topic_by_legacy_id(conn, legacy_topic_id)
    return normalize_topic_row(row) if row else None


def maybe_get_track_by_key(conn, track_key: str) -> dict | None:
    if not storage_flags.is_curriculum_db_reads_enabled():
        return None
    if conn is None:
        return None
    if not track_key:
        return None
    return get_track_by_key_from_db(conn, track_key)


def maybe_get_topic_by_legacy_id(conn, legacy_topic_id: str) -> dict | None:
    if not storage_flags.is_curriculum_db_reads_enabled():
        return None
    if conn is None:
        return None
    if not legacy_topic_id:
        return None
    return get_topic_by_legacy_id_from_db(conn, legacy_topic_id)


def _safe_id(value: Any) -> str:
    return "" if value is None else str(value)


def _metadata_dict(value: Any) -> dict:
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str):
        try:
            loaded = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return loaded if isinstance(loaded, dict) else {}
    return {}
