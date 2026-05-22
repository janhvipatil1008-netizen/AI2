"""
Topic catalog helpers derived from the existing syllabus data.

This module intentionally treats curriculum.syllabus as the source of truth.
It does not mutate syllabus structures or introduce persistence; it only
projects week/day tasks into stable topic cards for future topic-based flows.

compatibility-only: this module is the static fallback for old sessions and
legacy topic IDs. New modular curriculum features should use course/module/topic
sequence_order plus learner enrollment/progress state.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata

from curriculum.syllabus import ROLE_TRACKS, WEEKS, get_task_key


RECOMMENDED_ACTIONS = ["learn", "quiz", "portfolio_task", "interview_practice"]


@dataclass(frozen=True)
class TopicCard:
    topic_id: str
    track: str
    week_num: int
    module_title: str
    module_theme: str
    topic_title: str
    description: str
    source_task_keys: list[str]
    recommended_actions: list[str]
    learn_prompt: str
    quiz_prompt: str
    portfolio_prompt: str
    interview_prompt: str


def get_all_topics() -> list[TopicCard]:
    """Return topic cards for every known role track."""
    topics: list[TopicCard] = []
    for track in ROLE_TRACKS:
        topics.extend(get_topics_for_track(track))
    return topics


def get_topics_for_track(track: str) -> list[TopicCard]:
    """Return all derived topic cards for a track, or [] for unknown tracks."""
    if track not in ROLE_TRACKS:
        return []

    topics: list[TopicCard] = []
    seen_ids: set[str] = set()

    for week in WEEKS:
        week_num = int(week["num"])
        module_title = str(week["title"])
        module_theme = str(week["theme"])

        for day in week["days"]:
            day_idx = int(day["day_idx"])

            for task_idx, task_text in enumerate(day["all_tracks"]):
                topics.append(
                    _build_topic_card(
                        track=track,
                        week_num=week_num,
                        module_title=module_title,
                        module_theme=module_theme,
                        task_text=str(task_text),
                        task_key=get_task_key(week_num, day_idx, "all", task_idx),
                        seen_ids=seen_ids,
                    )
                )

            role_tasks = day["tracks"].get(track, [])
            task_list = role_tasks if isinstance(role_tasks, list) else [role_tasks]
            for task_idx, task_text in enumerate(task_list):
                if not task_text:
                    continue
                topics.append(
                    _build_topic_card(
                        track=track,
                        week_num=week_num,
                        module_title=module_title,
                        module_theme=module_theme,
                        task_text=str(task_text),
                        task_key=get_task_key(week_num, day_idx, track, task_idx),
                        seen_ids=seen_ids,
                    )
                )

    return topics


def get_topics_for_week(track: str, week_num: int) -> list[TopicCard]:
    """compatibility-only static fallback topic lookup.

    Do not use for new modular curriculum features. Modular runtime should use
    course/module/topic sequence_order plus learner enrollment/progress state.
    Kept temporarily for old sessions/static fallback and legacy topic IDs.
    """
    return [topic for topic in get_topics_for_track(track) if topic.week_num == week_num]


def get_topic(track: str, topic_id: str) -> TopicCard | None:
    """Return a single topic card by id for a track, or None if not found."""
    for topic in get_topics_for_track(track):
        if topic.topic_id == topic_id:
            return topic
    return None


def _build_topic_card(
    *,
    track: str,
    week_num: int,
    module_title: str,
    module_theme: str,
    task_text: str,
    task_key: str,
    seen_ids: set[str],
) -> TopicCard:
    topic_title = _make_topic_title(task_text)
    topic_id = _unique_topic_id(
        base=f"{track}-week-{week_num}-{_slugify(topic_title)}",
        seen_ids=seen_ids,
    )

    return TopicCard(
        topic_id=topic_id,
        track=track,
        week_num=week_num,
        module_title=module_title,
        module_theme=module_theme,
        topic_title=topic_title,
        description=task_text,
        source_task_keys=[task_key],
        recommended_actions=list(RECOMMENDED_ACTIONS),
        learn_prompt=(
            "Teach me this topic in a structured beginner-friendly way: "
            f"{topic_title}. Context: {task_text}"
        ),
        quiz_prompt=(
            "Create a quiz to test my understanding of this topic: "
            f"{topic_title}. Context: {task_text}"
        ),
        portfolio_prompt=(
            "Give me a small hands-on portfolio task for this topic: "
            f"{topic_title}. Context: {task_text}"
        ),
        interview_prompt=(
            "Give me interview practice questions for this topic: "
            f"{topic_title}. Context: {task_text}"
        ),
    )


def _make_topic_title(task_text: str) -> str:
    """Create a concise display title from the first meaningful phrase."""
    text = " ".join(task_text.strip().split())
    for separator in (" — ", " – ", " - ", ": ", "; "):
        if separator in text:
            text = text.split(separator, 1)[0]
            break

    text = text.strip(" .,-:;")
    words = text.split()
    if len(words) > 8:
        text = " ".join(words[:8])
    return text or "Untitled Topic"


def _slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_value.lower()).strip("-")
    return slug or "topic"


def _unique_topic_id(base: str, seen_ids: set[str]) -> str:
    candidate = base
    suffix = 2
    while candidate in seen_ids:
        candidate = f"{base}-{suffix}"
        suffix += 1
    seen_ids.add(candidate)
    return candidate


__all__ = [
    "TopicCard",
    "get_all_topics",
    "get_topics_for_track",
    "get_topics_for_week",
    "get_topic",
]
