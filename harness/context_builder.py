"""Context assembly helpers for harness-backed AI learning workflows."""

from dataclasses import dataclass, field


@dataclass
class HarnessContext:
    track_label: str
    topic_id: str
    topic_title: str
    topic_description: str
    module_title: str = ""
    freshness_label: str = ""
    progress: dict = field(default_factory=dict)
    notes: dict = field(default_factory=dict)
    prior_content: dict = field(default_factory=dict)
    usage_summary: dict = field(default_factory=dict)
    # Task-specific fields (optional, default to safe empty values)
    task_type: str = ""
    generated_learning_content: str = ""
    generated_practice_content: str = ""
    learner_input_summary: str = ""
    completion_percent: int = 0


def summarize_text_for_context(text: str, max_chars: int = 700) -> str:
    """Return text stripped and truncated to max_chars with a trailing marker."""
    stripped = text.strip()
    if len(stripped) <= max_chars:
        return stripped
    return stripped[:max_chars] + "... [truncated]"


def build_basic_harness_context(
    *,
    session,
    topic,
    track_label: str,
    freshness_label: str = "",
) -> HarnessContext:
    """Build a task-agnostic context object without mutating session."""
    topic_id = topic.topic_id
    usage_summary = session.usage_summary() if hasattr(session, "usage_summary") else {}
    completion_percent = (
        session.topic_completion_percent(topic_id)
        if hasattr(session, "topic_completion_percent")
        else 0
    )
    raw_learning_content = session.get_generated_topic_content(topic_id).get("content", "")

    return HarnessContext(
        track_label=track_label,
        topic_id=topic_id,
        topic_title=topic.topic_title,
        topic_description=topic.description,
        module_title=getattr(topic, "module_title", ""),
        freshness_label=freshness_label,
        progress=session.get_topic_progress(topic_id),
        notes=session.get_topic_notes(topic_id),
        prior_content=session.get_generated_topic_content(topic_id),
        usage_summary=usage_summary,
        completion_percent=completion_percent,
        generated_learning_content=summarize_text_for_context(raw_learning_content, max_chars=3000),
    )


_PRACTICE_TYPE_FOR_TASK = {
    "quiz_evaluation": "quiz",
    "portfolio_feedback": "portfolio_task",
    "interview_feedback": "interview_practice",
}

_PRACTICE_TASK_TYPES = {
    "quiz": "quiz_generation",
    "portfolio_task": "portfolio_task_generation",
    "interview_practice": "interview_practice_generation",
}


def build_task_harness_context(
    *,
    session,
    topic,
    track_label: str,
    task_type: str,
    freshness_label: str = "",
    learner_input: str = "",
) -> HarnessContext:
    """Build a task-specific harness context, extending the basic context."""
    context = build_basic_harness_context(
        session=session,
        topic=topic,
        track_label=track_label,
        freshness_label=freshness_label,
    )
    context.task_type = task_type
    context.learner_input_summary = summarize_text_for_context(learner_input)

    practice_type = _PRACTICE_TYPE_FOR_TASK.get(task_type)
    if practice_type is not None:
        raw_practice = session.get_generated_topic_practice(
            topic.topic_id, practice_type
        ).get("content", "")
        context.generated_practice_content = summarize_text_for_context(raw_practice)

    return context
