"""Business logic for AI topic content generation.

Pure Python — no FastAPI, no route, no template dependencies.
All Claude calls are dispatched via the run_blocking callable passed by the caller.
Mutates session in-memory; caller is responsible for persisting to the DB.
"""

from core.logging import get_logger, safe_error_metadata
from harness.context_builder import _PRACTICE_TASK_TYPES, build_task_harness_context
from harness.prompt_templates import (
    build_learning_content_prompt,
    build_practice_generation_prompt,
)


logger = get_logger(__name__)


async def generate_learning_content_for_topic(
    *,
    session,
    topic,
    track_label: str,
    make_client,
    run_blocking,
    test_mode: bool,
    model: str,
    refresh: bool,
    freshness_label: str,
    shared_cache_read=None,
    shared_cache_write=None,
    limit_enforcer=None,
) -> dict:
    """Generate or retrieve cached learning content for a topic.

    Returns dict: {content, generated_topic_content, from_cache}.
    from_cache=True means no content was regenerated.
    """
    existing = session.get_generated_topic_content(topic.topic_id)
    if not refresh and existing["content"]:
        session.record_usage_event(
            event_type="topic_learning_content",
            topic_id=topic.topic_id,
            model=existing.get("model", ""),
            source="cache",
            status="success",
            metadata={
                "refresh": refresh,
                "version": existing.get("version", 0),
                "from_cache": True,
            },
        )
        return {
            "content":                 existing["content"],
            "generated_topic_content": existing,
            "from_cache":              True,
        }

    if not test_mode and not refresh and shared_cache_read is not None:
        try:
            shared_row = shared_cache_read()
        except Exception:
            shared_row = None
        if shared_row and shared_row.get("content"):
            shared_content = shared_row["content"]
            shared_model   = shared_row.get("model") or ""
            saved = session.save_generated_topic_content(
                topic_id=topic.topic_id,
                content=shared_content,
                model=shared_model,
                freshness_label=freshness_label,
            )
            if session.get_topic_progress(topic.topic_id).get("learn") == "not_started":
                session.mark_topic_step(topic.topic_id, "learn", "in_progress")
            session.record_usage_event(
                event_type="topic_learning_content",
                topic_id=topic.topic_id,
                model=shared_model,
                source="shared_cache",
                status="success",
                metadata={
                    "refresh": refresh,
                    "version": saved.get("version", 0),
                    "from_cache": True,
                },
            )
            return {
                "content":                 saved["content"],
                "generated_topic_content": saved,
                "from_cache":              True,
            }

    if test_mode:
        mock_content = (
            f"Title: {topic.topic_title}\n\n"
            "Simple Explanation: This concept is about understanding the core mechanism "
            "behind the topic in a practical way.\n\n"
            "Why This Matters: Mastering this builds the foundation for more advanced skills "
            "and is directly applicable in real-world AI product roles.\n\n"
            "Real-World Example: Consider a scenario in an AI product where this pattern "
            "is applied to improve user experience or system reliability.\n\n"
            "Key Concepts: foundational principle, practical application, common trade-offs.\n\n"
            "Common Mistakes: Overcomplicating the solution when simplicity works, or skipping "
            "validation of assumptions.\n\n"
            "How To Apply This: Start small — implement the simplest version first, then "
            "iterate based on feedback and metrics.\n\n"
            "Quick Recap: Understand the core idea, see it in action, apply it in your project."
        )
        saved = session.save_generated_topic_content(
            topic_id=topic.topic_id,
            content=mock_content,
            model="test-mock",
            freshness_label=freshness_label,
        )
        if session.get_topic_progress(topic.topic_id).get("learn") == "not_started":
            session.mark_topic_step(topic.topic_id, "learn", "in_progress")
        session.record_usage_event(
            event_type="topic_learning_content",
            topic_id=topic.topic_id,
            model="test-mock",
            source="test_mode",
            status="success",
            metadata={
                "refresh": refresh,
                "version": saved.get("version", 0),
                "from_cache": False,
            },
        )
        return {
            "content":                 saved["content"],
            "generated_topic_content": saved,
            "from_cache":              False,
        }

    if limit_enforcer is not None:
        limit_enforcer()

    context = build_task_harness_context(
        session=session,
        topic=topic,
        track_label=track_label,
        task_type="learning_content",
        freshness_label=freshness_label,
    )
    prompt = build_learning_content_prompt(context)

    try:
        client   = make_client()
        response = await run_blocking(
            lambda: client.messages.create(
                model=model,
                max_tokens=1500,
                messages=[{"role": "user", "content": prompt}],
            )
        )
    except Exception as exc:
        metadata = safe_error_metadata(
            exc,
            topic_id=topic.topic_id,
            event_type="topic_learning_content",
            model=model,
            refresh=refresh,
        )
        session.record_usage_event(
            event_type="topic_learning_content",
            topic_id=topic.topic_id,
            model=model,
            source="claude",
            status="error",
            metadata={
                "refresh": refresh,
                "from_cache": False,
                "error": metadata["error_message"],
            },
        )
        logger.error("Claude learning content generation failed", extra={"ai2_metadata": metadata})
        raise
    content = response.content[0].text

    saved = session.save_generated_topic_content(
        topic_id=topic.topic_id,
        content=content,
        model=model,
        freshness_label=freshness_label,
    )

    if session.get_topic_progress(topic.topic_id).get("learn") == "not_started":
        session.mark_topic_step(topic.topic_id, "learn", "in_progress")
    session.record_usage_event(
        event_type="topic_learning_content",
        topic_id=topic.topic_id,
        model=model,
        source="claude",
        status="success",
        metadata={
            "refresh": refresh,
            "version": saved.get("version", 0),
            "from_cache": False,
        },
    )

    if shared_cache_write is not None:
        try:
            shared_cache_write(content, model)
        except Exception as exc:
            logger.warning(
                "shared content_cache write failed: %s",
                safe_error_metadata(exc, topic_id=topic.topic_id, model=model),
            )

    return {
        "content":                 saved["content"],
        "generated_topic_content": saved,
        "from_cache":              False,
    }


async def generate_practice_content_for_topic(
    *,
    session,
    topic,
    track_label: str,
    practice_type: str,
    make_client,
    run_blocking,
    test_mode: bool,
    model: str,
    refresh: bool,
    freshness_label: str,
    limit_enforcer=None,
) -> dict:
    """Generate or retrieve cached practice content for a topic.

    Returns dict: {content, generated_practice, from_cache}.
    from_cache=True means no practice content was regenerated.
    """
    event_type = f"topic_practice_{practice_type}"
    existing = session.get_generated_topic_practice(topic.topic_id, practice_type)
    if not refresh and existing["content"]:
        session.record_usage_event(
            event_type=event_type,
            topic_id=topic.topic_id,
            model=existing.get("model", ""),
            source="cache",
            status="success",
            metadata={
                "refresh": refresh,
                "version": existing.get("version", 0),
                "from_cache": True,
                "practice_type": practice_type,
            },
        )
        return {
            "content":            existing["content"],
            "generated_practice": existing,
            "from_cache":         True,
        }

    if test_mode:
        if practice_type == "quiz":
            mock_content = (
                f"Title: Quiz — {topic.topic_title}\n\n"
                "Instructions: Answer the following five questions to test your understanding.\n\n"
                "5 Questions:\n"
                "1. What is the core idea behind this topic?\n"
                "2. Why is this concept important in an AI product context?\n"
                "3. How would you apply this in a real-world scenario?\n"
                "4. What is a common misconception about this topic?\n"
                "5. When would you prioritise this approach over alternatives?\n\n"
                "Answer Key:\n"
                "1. The core idea focuses on structured understanding and practical application.\n"
                "2. It enables practitioners to build more reliable and scalable AI systems.\n"
                "3. By mapping the concept to a concrete use case and validating assumptions.\n"
                "4. That it only applies to advanced use cases — it is foundational at all levels.\n"
                "5. When the problem requires grounded, verifiable outcomes over speed alone.\n\n"
                "Explanation: Review each answer by connecting it back to the core definition "
                "and a real example from your track."
            )
        elif practice_type == "portfolio_task":
            mock_content = (
                f"Title: Portfolio Task — {topic.topic_title}\n\n"
                "Goal: Build a small artifact that demonstrates practical understanding of this topic.\n\n"
                "Scenario: You are an AI practitioner working on a project where this concept "
                "is directly relevant.\n\n"
                "Task Instructions:\n"
                "1. Define the problem this topic solves in one paragraph.\n"
                "2. Create a one-page concept note or design sketch.\n"
                "3. Identify two trade-offs in applying this approach.\n"
                "4. Write a brief reflection on what you learned.\n\n"
                "Expected Deliverable: A short document (1–2 pages) covering the above steps.\n\n"
                "Simple Rubric:\n"
                "- Clarity of problem definition (25%)\n"
                "- Depth of trade-off analysis (25%)\n"
                "- Practical applicability (25%)\n"
                "- Reflection quality (25%)\n\n"
                "Bonus Challenge: Extend your deliverable with a real dataset or code snippet."
            )
        else:  # interview_practice
            mock_content = (
                f"Title: Interview Practice — {topic.topic_title}\n\n"
                "How To Practice: Read each question, draft your answer mentally or in writing, "
                "then compare with the strong-answer guidance below.\n\n"
                "8 Interview Questions:\n"
                "1. How would you explain this concept to a non-technical stakeholder?\n"
                "2. What problem does this solve, and what are its limitations?\n"
                "3. Describe a real-world application of this concept.\n"
                "4. What metrics would you use to evaluate success?\n"
                "5. How does this relate to other AI concepts you know?\n"
                "6. What is the most common mistake practitioners make with this?\n"
                "7. How would you approach implementing this in a new project?\n"
                "8. What are the ethical considerations, if any?\n\n"
                "What Strong Answers Should Include:\n"
                "- Clear definition in plain language\n"
                "- At least one concrete example\n"
                "- Honest acknowledgement of trade-offs\n"
                "- Awareness of context (scale, team, constraints)\n\n"
                "Common Mistakes:\n"
                "- Overcomplicating the explanation\n"
                "- Ignoring limitations\n"
                "- Failing to connect theory to practical application"
            )

        saved = session.save_generated_topic_practice(
            topic_id=topic.topic_id,
            practice_type=practice_type,
            content=mock_content,
            model="test-mock",
            freshness_label=freshness_label,
        )
        if session.get_topic_progress(topic.topic_id).get(practice_type) == "not_started":
            session.mark_topic_step(topic.topic_id, practice_type, "in_progress")
        session.record_usage_event(
            event_type=event_type,
            topic_id=topic.topic_id,
            model="test-mock",
            source="test_mode",
            status="success",
            metadata={
                "refresh": refresh,
                "version": saved.get("version", 0),
                "from_cache": False,
                "practice_type": practice_type,
            },
        )
        return {
            "content":            saved["content"],
            "generated_practice": saved,
            "from_cache":         False,
        }

    if limit_enforcer is not None:
        limit_enforcer()

    context = build_task_harness_context(
        session=session,
        topic=topic,
        track_label=track_label,
        task_type=_PRACTICE_TASK_TYPES.get(practice_type, practice_type),
        freshness_label=freshness_label,
    )
    prompt = build_practice_generation_prompt(context, practice_type)

    try:
        client   = make_client()
        response = await run_blocking(
            lambda: client.messages.create(
                model=model,
                max_tokens=1800,
                messages=[{"role": "user", "content": prompt}],
            )
        )
    except Exception as exc:
        metadata = safe_error_metadata(
            exc,
            topic_id=topic.topic_id,
            event_type=event_type,
            practice_type=practice_type,
            model=model,
            refresh=refresh,
        )
        session.record_usage_event(
            event_type=event_type,
            topic_id=topic.topic_id,
            model=model,
            source="claude",
            status="error",
            metadata={
                "refresh": refresh,
                "from_cache": False,
                "practice_type": practice_type,
                "error": metadata["error_message"],
            },
        )
        logger.error("Claude practice content generation failed", extra={"ai2_metadata": metadata})
        raise
    content = response.content[0].text

    saved = session.save_generated_topic_practice(
        topic_id=topic.topic_id,
        practice_type=practice_type,
        content=content,
        model=model,
        freshness_label=freshness_label,
    )

    if session.get_topic_progress(topic.topic_id).get(practice_type) == "not_started":
        session.mark_topic_step(topic.topic_id, practice_type, "in_progress")
    session.record_usage_event(
        event_type=event_type,
        topic_id=topic.topic_id,
        model=model,
        source="claude",
        status="success",
        metadata={
            "refresh": refresh,
            "version": saved.get("version", 0),
            "from_cache": False,
            "practice_type": practice_type,
        },
    )

    return {
        "content":            saved["content"],
        "generated_practice": saved,
        "from_cache":         False,
    }
