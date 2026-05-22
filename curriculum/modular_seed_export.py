"""Modular curriculum seed/export adapter.

Transforms the existing static WEEKS/ROLE_TRACKS curriculum into the
Course → Module → Topic model with inferred Skills and default Activities.

No DB writes, no DB connections, no env reads.
WEEKS and ROLE_TRACKS are read-only; they are never mutated here.
The caller decides what to do with the returned data structures.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

from curriculum.syllabus import ROLE_TRACKS
from curriculum.topics import get_topics_for_track


# ── Seed dataclasses ──────────────────────────────────────────────────────────

@dataclass
class ModularCourseSeed:
    course_key:      str
    title:           str
    description:     str = ""
    target_audience: str = ""
    level:           str = "beginner"
    status:          str = "draft"
    version:         str = "v1"
    sequence_order:  int = 0
    metadata:        dict = field(default_factory=dict)


@dataclass
class ModularModuleSeed:
    course_key:        str
    module_key:        str
    title:             str
    description:       str = ""
    sequence_order:    int = 0
    estimated_minutes: int | None = None
    status:            str = "active"
    metadata:          dict = field(default_factory=dict)


@dataclass
class ModularSkillSeed:
    skill_key:   str
    title:       str
    description: str = ""
    category:    str = ""
    level:       str = ""


@dataclass
class ModularActivitySeed:
    activity_key:  str
    activity_type: str
    title:         str = ""
    instructions:  str = ""
    rubric_key:    str = ""
    sequence_order: int = 0
    is_required:   bool = True


@dataclass
class ModularTopicSeed:
    course_key:        str
    module_key:        str
    topic_key:         str
    title:             str
    description:       str = ""
    legacy_topic_id:   str = ""
    difficulty_level:  str = "beginner"
    sequence_order:    int = 0
    estimated_minutes: int | None = None
    status:            str = "active"
    skills:            list[ModularSkillSeed]     = field(default_factory=list)
    activities:        list[ModularActivitySeed]  = field(default_factory=list)
    metadata:          dict                       = field(default_factory=dict)


@dataclass
class ModularCurriculumSeedExport:
    courses: list[ModularCourseSeed]
    modules: list[ModularModuleSeed]
    topics:  list[ModularTopicSeed]


# ── Course configuration per track ───────────────────────────────────────────

_COURSE_CONFIG: dict[str, tuple[str, str, str]] = {
    # track_key -> (course_key, title, target_audience)
    "aipm":    (
        "aipm-foundations",
        "AI Product Manager Foundations",
        "Aspiring AI Product Managers",
    ),
    "evals":   (
        "evals-foundations",
        "AI Evaluations Specialist Foundations",
        "Aspiring AI Evaluations Specialists",
    ),
    "context": (
        "context-engineering-foundations",
        "Context Engineering Foundations",
        "Aspiring Context Engineers",
    ),
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def slugify_key(value: str) -> str:
    """Lowercase, trim, replace non-alphanumeric runs with '-', strip edges.

    Returns 'untitled' for empty or whitespace-only input.
    """
    key = re.sub(r"[^a-z0-9]+", "-", value.lower().strip()).strip("-")
    return key or "untitled"


def _unique_key(base: str, seen: set[str]) -> str:
    candidate = base
    suffix = 2
    while candidate in seen:
        candidate = f"{base}-{suffix}"
        suffix += 1
    seen.add(candidate)
    return candidate


# Keyword patterns for skill inference — checked in order; all matches collected.
# Each entry: (regex_pattern, skill_key, skill_title, category)
_SKILL_PATTERNS: list[tuple[str, str, str, str]] = [
    (r"rag|retrieval[\s\-]augmented|grounding",
     "rag",                 "RAG & Retrieval",          "retrieval"),
    (r"prompt",
     "prompt_engineering",  "Prompt Engineering",       "prompting"),
    (r"\beval|evaluation|rubric|benchmark",
     "ai_evaluation",       "AI Evaluation",            "evaluation"),
    (r"portfolio|project\b",
     "portfolio_building",  "Portfolio Building",       "career"),
    (r"interview",
     "interview_readiness", "Interview Readiness",      "career"),
    (r"product\b|prd\b|roadmap|stakeholder",
     "product_management",  "Product Management",       "product"),
    (r"\bagent|orchestrat",
     "agents",              "AI Agents & Orchestration","systems"),
    (r"\bcontext\b",
     "context_engineering", "Context Engineering",      "systems"),
]

_SKILL_AI_FOUNDATIONS = ModularSkillSeed(
    skill_key="ai_foundations",
    title="AI Foundations",
    category="foundations",
)


def infer_skills_for_topic(
    title: str,
    description: str | None = None,
) -> list[ModularSkillSeed]:
    """Return inferred skill seeds based on keywords in title and description.

    Checks all patterns; returns all that match.  Falls back to ai_foundations
    when nothing matches.
    """
    haystack = f"{title} {description or ''}".lower()
    matched: list[ModularSkillSeed] = []
    for pattern, skill_key, skill_title, category in _SKILL_PATTERNS:
        if re.search(pattern, haystack):
            matched.append(ModularSkillSeed(
                skill_key=skill_key,
                title=skill_title,
                category=category,
            ))
    return matched if matched else [_SKILL_AI_FOUNDATIONS]


# Ordered default activities that apply to every topic.
_ACTIVITY_DEFAULTS: list[tuple[str, str, str, int, bool]] = [
    # (activity_key, activity_type, title, sequence_order, is_required)
    ("lesson",     "lesson",             "Read & Learn",    1, True),
    ("practice",   "practice_task",      "Practice Task",   2, True),
    ("quiz",       "quiz",               "Quiz",            3, True),
    ("portfolio",  "portfolio_task",     "Portfolio Task",  4, True),
    ("interview",  "interview_practice", "Interview Prep",  5, True),
    ("reflection", "reflection",         "Reflection",      6, False),
]


def default_activities_for_topic(topic_key: str) -> list[ModularActivitySeed]:
    """Return the standard ordered activity sequence for any topic."""
    return [
        ModularActivitySeed(
            activity_key=act_key,
            activity_type=act_type,
            title=title,
            sequence_order=seq,
            is_required=required,
        )
        for act_key, act_type, title, seq, required in _ACTIVITY_DEFAULTS
    ]


# ── Main export builder ───────────────────────────────────────────────────────

def build_modular_curriculum_seed_export() -> ModularCurriculumSeedExport:
    """Build a full modular curriculum seed export from the current static syllabus.

    Reads ROLE_TRACKS and per-track topics.  Does not touch the database.
    WEEKS and ROLE_TRACKS are not mutated.
    """
    courses: list[ModularCourseSeed]  = []
    modules: list[ModularModuleSeed]  = []
    topics:  list[ModularTopicSeed]   = []

    for course_idx, (track_key, track_info) in enumerate(ROLE_TRACKS.items()):
        cfg_key, cfg_title, cfg_audience = _COURSE_CONFIG.get(
            track_key,
            (
                f"{slugify_key(track_key)}-foundations",
                f"{track_info['label']} Foundations",
                f"Aspiring {track_info['label']}s",
            ),
        )

        courses.append(ModularCourseSeed(
            course_key=cfg_key,
            title=cfg_title,
            description=f"Foundations learning path for {track_info['label']}.",
            target_audience=cfg_audience,
            level="beginner",
            status="draft",
            version="v1",
            sequence_order=course_idx,
            metadata={
                "source_track_key": track_key,
                "icon":             track_info.get("icon", ""),
                "color":            track_info.get("color", ""),
            },
        ))

        track_topics = get_topics_for_track(track_key)

        # Group by week_num to build module records
        by_week: dict[int, list] = {}
        for topic in track_topics:
            by_week.setdefault(topic.week_num, []).append(topic)

        # Track seen topic_keys per course to ensure uniqueness
        seen_topic_keys: set[str] = set()

        for week_num in sorted(by_week.keys()):
            week_topics = by_week[week_num]
            first = week_topics[0]

            # Module key uses zero-padded index instead of "week-N"
            module_key = f"module-{week_num:02d}"

            modules.append(ModularModuleSeed(
                course_key=cfg_key,
                module_key=module_key,
                title=first.module_title,
                description=first.module_theme,
                sequence_order=week_num - 1,
                status="active",
                # source_week_num stored only in metadata, not as a schema field
                metadata={"source_week_num": week_num},
            ))

            for topic_idx, topic in enumerate(week_topics):
                # topic_key derived from title slug — avoids "-week-" language
                base_key = slugify_key(topic.topic_title)
                topic_key = _unique_key(base_key, seen_topic_keys)

                topics.append(ModularTopicSeed(
                    course_key=cfg_key,
                    module_key=module_key,
                    topic_key=topic_key,
                    title=topic.topic_title,
                    description=topic.description,
                    legacy_topic_id=topic.topic_id,
                    difficulty_level="beginner",
                    sequence_order=topic_idx,
                    status="active",
                    skills=infer_skills_for_topic(topic.topic_title, topic.description),
                    activities=default_activities_for_topic(topic_key),
                    metadata={"source_week_num": week_num},
                ))

    return ModularCurriculumSeedExport(
        courses=courses,
        modules=modules,
        topics=topics,
    )


# ── Dict / JSON serialization ─────────────────────────────────────────────────

def modular_seed_export_to_dict(export: ModularCurriculumSeedExport) -> dict:
    """Return a JSON-serializable flat dict for the full modular export.

    Skills are deduplicated globally; topic_skills records link topics to skills.
    Activities are emitted as a flat list keyed by (course_key, topic_key, activity_key).
    """
    courses = [asdict(c) for c in export.courses]
    modules = [asdict(m) for m in export.modules]

    seen_skills: dict[str, dict] = {}   # skill_key -> skill dict (deduped)
    topic_skills: list[dict] = []
    activities:   list[dict] = []
    topics_out:   list[dict] = []

    for topic in export.topics:
        # Flat topic record — skills and activities emitted separately
        t = asdict(topic)
        t.pop("skills",     None)
        t.pop("activities", None)
        topics_out.append(t)

        for skill in topic.skills:
            if skill.skill_key not in seen_skills:
                seen_skills[skill.skill_key] = asdict(skill)
            topic_skills.append({
                "course_key": topic.course_key,
                "topic_key":  topic.topic_key,
                "skill_key":  skill.skill_key,
                "importance": "core",
            })

        for act in topic.activities:
            a = asdict(act)
            a["course_key"] = topic.course_key
            a["topic_key"]  = topic.topic_key
            activities.append(a)

    return {
        "courses":      courses,
        "modules":      modules,
        "topics":       topics_out,
        "skills":       list(seen_skills.values()),
        "topic_skills": topic_skills,
        "activities":   activities,
    }


def export_modular_curriculum_seed_json(path: str | Path) -> Path:
    """Build the export and write it as pretty-printed JSON. Returns the output path.

    Not called automatically — intended for manual or script invocation only.
    """
    output = Path(path)
    data = modular_seed_export_to_dict(build_modular_curriculum_seed_export())
    output.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    return output
