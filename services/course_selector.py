"""Course selector — two-level course/role structure for the learner-facing chooser.

Curated display config (role labels, "for you if" copy) lives in COURSE_ROLE_CONFIG.
DB data (course titles, descriptions, sequence order) is read at runtime from the
seeded courses table so the selector reflects what is actually available.

ai-foundations is the optional shared on-ramp; it is NOT a selectable course in the
chooser and is returned separately under "on_ramp".

No env reads, no DB connection creation, no route/session imports.
"""

from __future__ import annotations

# ── Curated role display configuration ────────────────────────────────────────
# Each entry maps a course_key to the roles exposed in the selector UI.
# track_key must match the value in course_topics.metadata->>'track' in the DB.
# Roles are presented in the order listed here.

COURSE_ROLE_CONFIG: dict[str, list[dict]] = {
    "ai-product-business": [
        {
            "track_key":  "business-analyst",
            "label":      "Business Analyst",
            "for_you_if": "find where AI creates business value and make the case for it",
        },
        {
            "track_key":  "product-manager",
            "label":      "Product Manager",
            "for_you_if": "decide what AI products to build and lead them to ship",
        },
    ],
    "ai-engineering-building": [
        {
            "track_key":  "builder",
            "label":      "Builder",
            "for_you_if": "ship working AI apps fast, even without deep engineering",
        },
        {
            "track_key":  "engineer",
            "label":      "Engineer",
            "for_you_if": "build production AI systems properly, with the architecture to back it",
        },
    ],
    "ai-evaluation-quality": [
        {
            "track_key":  "evals-specialist",
            "label":      "AI Evals Specialist",
            "for_you_if": "learn to measure and improve AI quality from the ground up",
        },
        {
            "track_key":  "qa-transition",
            "label":      "Moving into AI from QA",
            "for_you_if": "bring your testing background into AI evaluation",
        },
    ],
    "ai-data-analytics": [
        {
            "track_key":  "data-analyst",
            "label":      "Data Analyst",
            "for_you_if": "turn data into insight using AI tools",
        },
        {
            "track_key":  "data-engineer",
            "label":      "Data Engineer",
            "for_you_if": "build the pipelines and infrastructure that feed AI systems",
        },
    ],
    "ai-experience-growth": [
        {
            "track_key":  "marketing-growth",
            "label":      "Marketing & Growth",
            "for_you_if": "use AI to grow products and reach people",
        },
        {
            "track_key":  "ux-design",
            "label":      "UX Design",
            "for_you_if": "design experiences for AI-powered products",
        },
    ],
}

_ON_RAMP_COURSE_KEY = "ai-foundations"


def get_selector_data(conn) -> dict:
    """Return the two-level selector structure merged from DB + curated config.

    Returns:
        {
            "on_ramp":  dict | None,   # ai-foundations course, or None if absent from DB
            "courses":  list[dict],    # selectable courses ordered by DB sequence_order
        }

    Shape of each item in "courses":
        {
            "course_key":  str,
            "title":       str,
            "description": str,
            "roles": [
                {
                    "track_key":  str,   # matches metadata->>'track' in course_topics
                    "label":      str,
                    "for_you_if": str,
                },
                ...
            ]
        }

    Courses absent from the DB are silently omitted so the selector degrades
    gracefully if a course has not yet been seeded.
    """
    from services.modular_curriculum_read_service import list_available_courses

    db_courses = list_available_courses(conn, status=None)
    db_by_key: dict[str, dict] = {c["course_key"]: c for c in db_courses}

    on_ramp: dict | None = None
    raw_onramp = db_by_key.get(_ON_RAMP_COURSE_KEY)
    if raw_onramp:
        on_ramp = {
            "course_key":  raw_onramp["course_key"],
            "title":       raw_onramp["title"],
            "description": raw_onramp["description"],
        }

    courses: list[dict] = []
    for course_key, roles_config in COURSE_ROLE_CONFIG.items():
        raw = db_by_key.get(course_key)
        if raw is None:
            continue
        courses.append({
            "course_key":  raw["course_key"],
            "title":       raw["title"],
            "description": raw["description"],
            "sequence_order": raw.get("sequence_order", 99),
            "roles": [dict(r) for r in roles_config],
        })

    courses.sort(key=lambda c: c.pop("sequence_order", 99))

    return {"on_ramp": on_ramp, "courses": courses}
