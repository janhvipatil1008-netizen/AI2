"""Adapters from modular curriculum dicts to existing topic-card objects."""

from __future__ import annotations

from curriculum.topics import RECOMMENDED_ACTIONS, TopicCard


def modular_topic_to_topic_card(
    topic: dict,
    *,
    track_key: str,
    module: dict | None = None,
) -> TopicCard:
    """Return a TopicCard-compatible object without mutating modular input."""
    topic_id = str(
        topic.get("legacy_topic_id")
        or topic.get("topic_key")
        or topic.get("topic_id")
        or "modular-topic"
    )
    title = str(topic.get("title") or topic.get("topic_key") or "Untitled Topic")
    description = str(topic.get("description") or "")
    module_data = dict(module or {})
    module_title = str(module_data.get("title") or "Modular Curriculum")
    module_theme = str(module_data.get("description") or "")
    sequence_order = _safe_int(module_data.get("sequence_order"), default=0)

    return TopicCard(
        topic_id=topic_id,
        track=track_key,
        week_num=sequence_order + 1,
        module_title=module_title,
        module_theme=module_theme,
        topic_title=title,
        description=description,
        source_task_keys=[topic_id],
        recommended_actions=list(RECOMMENDED_ACTIONS),
        learn_prompt=(
            "Teach me this topic in a structured beginner-friendly way: "
            f"{title}. Context: {description}"
        ),
        quiz_prompt=(
            "Create a quiz to test my understanding of this topic: "
            f"{title}. Context: {description}"
        ),
        portfolio_prompt=(
            "Give me a small hands-on portfolio task for this topic: "
            f"{title}. Context: {description}"
        ),
        interview_prompt=(
            "Give me interview practice questions for this topic: "
            f"{title}. Context: {description}"
        ),
    )


def course_structure_to_topic_cards(course_structure: dict | None, *, track_key: str) -> list[TopicCard]:
    """Flatten a modular course structure into template-compatible topic cards."""
    if not course_structure:
        return []

    cards: list[TopicCard] = []
    modules = sorted(
        list(course_structure.get("modules") or []),
        key=lambda module: _safe_int(module.get("sequence_order"), default=0),
    )
    for module in modules:
        topics = sorted(
            list(module.get("topics") or []),
            key=lambda topic: _safe_int(topic.get("sequence_order"), default=0),
        )
        for topic in topics:
            cards.append(modular_topic_to_topic_card(topic, track_key=track_key, module=module))

    unassigned = sorted(
        list(course_structure.get("unassigned_topics") or []),
        key=lambda topic: _safe_int(topic.get("sequence_order"), default=0),
    )
    for topic in unassigned:
        cards.append(modular_topic_to_topic_card(topic, track_key=track_key, module=None))

    return cards


def course_structure_to_role_topic_cards(
    course_structure: dict | None,
    *,
    track_key: str,
    role_key: str,
) -> list[TopicCard]:
    """Return TopicCards for one role: core topics first, then the role's branch topics.

    Reads topic.metadata["track"] to classify each topic:
    - "core"     → always included; forms the shared foundation
    - role_key   → this learner's branch; appended after core
    - anything else → excluded (another role's branch; never shown)

    Within each group, module.sequence_order then topic.sequence_order is preserved,
    so a learner always sees topics in the order the curriculum defines.
    """
    if not course_structure:
        return []

    # Flatten modules → topics while keeping (topic, parent_module) paired.
    # Sort by module first, then topic within each module.
    paired: list[tuple[dict, dict | None]] = []
    modules = sorted(
        list(course_structure.get("modules") or []),
        key=lambda m: _safe_int(m.get("sequence_order"), default=0),
    )
    for module in modules:
        topics = sorted(
            list(module.get("topics") or []),
            key=lambda t: _safe_int(t.get("sequence_order"), default=0),
        )
        for topic in topics:
            paired.append((topic, module))

    for topic in sorted(
        list(course_structure.get("unassigned_topics") or []),
        key=lambda t: _safe_int(t.get("sequence_order"), default=0),
    ):
        paired.append((topic, None))

    core_cards:   list[TopicCard] = []
    branch_cards: list[TopicCard] = []

    for topic, module in paired:
        t_track = (topic.get("metadata") or {}).get("track", "")
        if t_track == "core":
            core_cards.append(
                modular_topic_to_topic_card(topic, track_key=track_key, module=module)
            )
        elif t_track == role_key:
            branch_cards.append(
                modular_topic_to_topic_card(topic, track_key=track_key, module=module)
            )
        # other branch tracks: silently excluded

    return core_cards + branch_cards


def _safe_int(value, *, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
