"""Curriculum seed/export mapping layer.

Converts the current temporary syllabus into structured records that match the
new DB schema tables (learning_tracks, learning_modules, learning_topics).

Nothing here writes to the database — this is a pure data-mapping layer.
The caller decides what to do with the returned records.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

from curriculum.freshness import classify_topic_freshness
from curriculum.syllabus import ROLE_TRACKS
from curriculum.topics import get_topics_for_track


# ── Seed record dataclasses ───────────────────────────────────────────────────

@dataclass
class TrackSeedRecord:
    track_key: str
    title: str
    description: str = ""
    status: str = "active"
    version: str = "v1"
    metadata: dict = field(default_factory=dict)


@dataclass
class ModuleSeedRecord:
    track_key: str
    module_key: str
    title: str
    description: str = ""
    sequence_order: int = 0
    module_type: str = "week"
    metadata: dict = field(default_factory=dict)


@dataclass
class TopicSeedRecord:
    track_key: str
    module_key: str
    topic_key: str
    title: str
    description: str = ""
    sequence_order: int = 0
    difficulty: str = ""
    freshness_label: str = ""
    estimated_minutes: int | None = None
    legacy_topic_id: str = ""
    metadata: dict = field(default_factory=dict)


@dataclass
class CurriculumSeedExport:
    tracks: list[TrackSeedRecord]
    modules: list[ModuleSeedRecord]
    topics: list[TopicSeedRecord]


# ── Helpers ───────────────────────────────────────────────────────────────────

def slugify_key(value: str) -> str:
    """Lowercase and replace non-alphanumeric groups with '-'. Returns 'item' if empty."""
    key = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return key or "item"


def build_curriculum_seed_export() -> CurriculumSeedExport:
    """Build a full curriculum seed export from the current temporary syllabus.

    Reads ROLE_TRACKS and per-track topics. Does not touch the database.
    Preserves each topic's existing topic_id as legacy_topic_id.
    """
    tracks: list[TrackSeedRecord] = []
    modules: list[ModuleSeedRecord] = []
    topics: list[TopicSeedRecord] = []

    for track_key, track_info in ROLE_TRACKS.items():
        tracks.append(TrackSeedRecord(
            track_key=track_key,
            title=track_info["label"],
            metadata={
                "icon":  track_info.get("icon", ""),
                "color": track_info.get("color", ""),
            },
        ))

        track_topics = get_topics_for_track(track_key)

        # Group topics by week_num to build module records
        by_week: dict[int, list] = {}
        for topic in track_topics:
            by_week.setdefault(topic.week_num, []).append(topic)

        for week_num in sorted(by_week.keys()):
            week_topics = by_week[week_num]
            first = week_topics[0]
            module_key = f"week-{week_num}"

            modules.append(ModuleSeedRecord(
                track_key=track_key,
                module_key=module_key,
                title=first.module_title,
                description=first.module_theme,
                sequence_order=week_num - 1,
                module_type="week",
            ))

            for topic_idx, topic in enumerate(week_topics):
                freshness = classify_topic_freshness(topic.topic_title, topic.description)
                topics.append(TopicSeedRecord(
                    track_key=track_key,
                    module_key=module_key,
                    topic_key=slugify_key(topic.topic_id),
                    title=topic.topic_title,
                    description=topic.description,
                    sequence_order=topic_idx,
                    freshness_label=freshness,
                    legacy_topic_id=topic.topic_id,
                ))

    return CurriculumSeedExport(tracks=tracks, modules=modules, topics=topics)


def curriculum_seed_export_to_dict(export: CurriculumSeedExport) -> dict:
    """Return a JSON-serializable dict representation of the seed export."""
    return asdict(export)


def export_curriculum_seed_json(path: str | Path) -> Path:
    """Build the export and write it as pretty-printed JSON. Returns the output path.

    Not called automatically — intended for manual or test invocation only.
    """
    output = Path(path)
    data = curriculum_seed_export_to_dict(build_curriculum_seed_export())
    output.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return output
