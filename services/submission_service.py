"""Business logic for quiz, portfolio, and interview submissions.

Plain Python service layer: no FastAPI, route, template, or persistence
dependencies. The caller owns topic validation and session persistence.
"""

import re

import anthropic

from core.logging import get_logger, safe_error_metadata
from harness.context_builder import build_task_harness_context
from harness.prompt_templates import (
    build_interview_feedback_prompt,
    build_portfolio_feedback_prompt,
    build_quiz_evaluation_prompt,
)
from services.llm_observability import build_safe_trace_metadata, trace_llm_call


logger = get_logger(__name__)


class SubmissionValidationError(ValueError):
    """Raised when a learner submission is missing required content."""


class SubmissionGenerationError(RuntimeError):
    """Raised when AI feedback generation fails."""


def parse_score(text: str, label: str = "Overall Score") -> int | None:
    """Parse score lines such as 'Overall Score: 8/10'."""
    pattern = rf"{re.escape(label)}:\s*(\d+)\s*/\s*10"
    match = re.search(pattern, text, re.IGNORECASE)
    if not match:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None


def submit_quiz_answers(*, session, topic, answers: str) -> dict:
    if not answers.strip():
        raise SubmissionValidationError("answers cannot be empty")

    saved = session.save_quiz_answers(topic.topic_id, answers)
    if session.get_topic_progress(topic.topic_id).get("quiz") == "not_started":
        session.mark_topic_step(topic.topic_id, "quiz", "in_progress")

    return _result(session, topic.topic_id, "quiz_submission", saved)


async def evaluate_quiz_answers(
    *,
    session,
    topic,
    track_label: str,
    make_client,
    run_blocking,
    test_mode: bool,
    model: str,
    refresh: bool = False,
    limit_enforcer=None,
) -> dict:
    existing = session.get_quiz_submission(topic.topic_id)
    if not existing["answers"]:
        raise SubmissionValidationError("No answers found. Submit your answers first.")

    if not refresh and existing["evaluation"]:
        session.record_usage_event(
            event_type="quiz_evaluation",
            topic_id=topic.topic_id,
            model=existing.get("model", ""),
            source="cache",
            status="success",
            metadata={
                "refresh": refresh,
                "from_cache": True,
                "score": existing.get("score"),
            },
        )
        return _result(session, topic.topic_id, "quiz_submission", existing, from_cache=True)

    if test_mode:
        evaluation_text = _MOCK_QUIZ_EVALUATION
        score = 8
        saved_model = "test-mock"
    else:
        if limit_enforcer is not None:
            limit_enforcer()
        quiz_content = session.get_generated_topic_practice(topic.topic_id, "quiz")
        context = build_task_harness_context(
            session=session,
            topic=topic,
            track_label=track_label,
            task_type="quiz_evaluation",
            learner_input=existing["answers"],
        )
        prompt = build_quiz_evaluation_prompt(
            context,
            quiz_content.get("content", ""),
            existing["answers"],
        )
        with trace_llm_call(
            "structured.quiz_feedback",
            metadata=build_safe_trace_metadata(
                topic_id=topic.topic_id,
                activity_type="quiz_feedback",
                model=model,
                from_cache=False,
            ),
        ):
            try:
                evaluation_text = await _create_message_text(
                    make_client=make_client,
                    run_blocking=run_blocking,
                    model=model,
                    max_tokens=1000,
                    prompt=prompt,
                    error_prefix="Evaluation failed",
                )
            except SubmissionGenerationError as exc:
                metadata = safe_error_metadata(
                    exc,
                    topic_id=topic.topic_id,
                    event_type="quiz_evaluation",
                    model=model,
                    refresh=refresh,
                )
                session.record_usage_event(
                    event_type="quiz_evaluation",
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
                logger.error("Claude quiz evaluation failed", extra={"ai2_metadata": metadata})
                raise
            score = parse_score(evaluation_text)
            saved_model = model

    saved = session.save_quiz_evaluation(
        topic_id=topic.topic_id,
        evaluation=evaluation_text,
        model=saved_model,
        score=score,
    )
    session.mark_topic_step(topic.topic_id, "quiz", "done")
    session.record_usage_event(
        event_type="quiz_evaluation",
        topic_id=topic.topic_id,
        model=saved_model,
        source="test_mode" if test_mode else "claude",
        status="success",
        metadata={
            "refresh": refresh,
            "from_cache": False,
            "score": score,
        },
    )
    return _result(session, topic.topic_id, "quiz_submission", saved)


def submit_portfolio_work(*, session, topic, submission: str) -> dict:
    if not submission.strip():
        raise SubmissionValidationError("submission cannot be empty")

    saved = session.save_portfolio_submission(topic.topic_id, submission)
    if session.get_topic_progress(topic.topic_id).get("portfolio_task") == "not_started":
        session.mark_topic_step(topic.topic_id, "portfolio_task", "in_progress")

    return _result(session, topic.topic_id, "portfolio_submission", saved)


async def generate_portfolio_feedback(
    *,
    session,
    topic,
    track_label: str,
    make_client,
    run_blocking,
    test_mode: bool,
    model: str,
    refresh: bool = False,
    limit_enforcer=None,
) -> dict:
    existing = session.get_portfolio_submission(topic.topic_id)
    if not existing["submission"]:
        raise SubmissionValidationError("No submission found. Submit your work first.")

    if not refresh and existing["feedback"]:
        session.record_usage_event(
            event_type="portfolio_feedback",
            topic_id=topic.topic_id,
            model=existing.get("model", ""),
            source="cache",
            status="success",
            metadata={
                "refresh": refresh,
                "from_cache": True,
                "score": existing.get("score"),
            },
        )
        return _result(
            session,
            topic.topic_id,
            "portfolio_submission",
            existing,
            from_cache=True,
        )

    if test_mode:
        feedback_text = _MOCK_PORTFOLIO_FEEDBACK
        score = 7
        saved_model = "test-mock"
    else:
        if limit_enforcer is not None:
            limit_enforcer()
        portfolio_task_content = session.get_generated_topic_practice(
            topic.topic_id,
            "portfolio_task",
        )
        context = build_task_harness_context(
            session=session,
            topic=topic,
            track_label=track_label,
            task_type="portfolio_feedback",
            learner_input=existing["submission"],
        )
        prompt = build_portfolio_feedback_prompt(
            context,
            portfolio_task_content.get("content", ""),
            existing["submission"],
        )
        with trace_llm_call(
            "structured.portfolio_feedback",
            metadata=build_safe_trace_metadata(
                topic_id=topic.topic_id,
                activity_type="portfolio_feedback",
                model=model,
                from_cache=False,
            ),
        ):
            try:
                feedback_text = await _create_message_text(
                    make_client=make_client,
                    run_blocking=run_blocking,
                    model=model,
                    max_tokens=1200,
                    prompt=prompt,
                    error_prefix="Feedback generation failed",
                )
            except SubmissionGenerationError as exc:
                metadata = safe_error_metadata(
                    exc,
                    topic_id=topic.topic_id,
                    event_type="portfolio_feedback",
                    model=model,
                    refresh=refresh,
                )
                session.record_usage_event(
                    event_type="portfolio_feedback",
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
                logger.error("Claude portfolio feedback failed", extra={"ai2_metadata": metadata})
                raise
            score = parse_score(feedback_text, "Portfolio Readiness Score")
            saved_model = model

    saved = session.save_portfolio_feedback(
        topic_id=topic.topic_id,
        feedback=feedback_text,
        model=saved_model,
        score=score,
    )
    session.mark_topic_step(topic.topic_id, "portfolio_task", "done")
    session.record_usage_event(
        event_type="portfolio_feedback",
        topic_id=topic.topic_id,
        model=saved_model,
        source="test_mode" if test_mode else "claude",
        status="success",
        metadata={
            "refresh": refresh,
            "from_cache": False,
            "score": score,
        },
    )
    return _result(session, topic.topic_id, "portfolio_submission", saved)


def submit_interview_answer(*, session, topic, answer: str) -> dict:
    if not answer.strip():
        raise SubmissionValidationError("answer cannot be empty")

    saved = session.save_interview_answer(topic.topic_id, answer)
    if session.get_topic_progress(topic.topic_id).get("interview_practice") == "not_started":
        session.mark_topic_step(topic.topic_id, "interview_practice", "in_progress")

    return _result(session, topic.topic_id, "interview_submission", saved)


async def generate_interview_feedback(
    *,
    session,
    topic,
    track_label: str,
    make_client,
    run_blocking,
    test_mode: bool,
    model: str,
    refresh: bool = False,
    limit_enforcer=None,
) -> dict:
    existing = session.get_interview_submission(topic.topic_id)
    if not existing["answer"]:
        raise SubmissionValidationError("No answer found. Submit your answer first.")

    if not refresh and existing["feedback"]:
        session.record_usage_event(
            event_type="interview_feedback",
            topic_id=topic.topic_id,
            model=existing.get("model", ""),
            source="cache",
            status="success",
            metadata={
                "refresh": refresh,
                "from_cache": True,
                "score": existing.get("score"),
            },
        )
        return _result(
            session,
            topic.topic_id,
            "interview_submission",
            existing,
            from_cache=True,
        )

    if test_mode:
        feedback_text = _MOCK_INTERVIEW_FEEDBACK
        score = 8
        saved_model = "test-mock"
    else:
        if limit_enforcer is not None:
            limit_enforcer()
        practice_content = session.get_generated_topic_practice(
            topic.topic_id,
            "interview_practice",
        )
        context = build_task_harness_context(
            session=session,
            topic=topic,
            track_label=track_label,
            task_type="interview_feedback",
            learner_input=existing["answer"],
        )
        prompt = build_interview_feedback_prompt(
            context,
            practice_content.get("content", ""),
            existing["answer"],
        )
        with trace_llm_call(
            "structured.interview_feedback",
            metadata=build_safe_trace_metadata(
                topic_id=topic.topic_id,
                activity_type="interview_feedback",
                model=model,
                from_cache=False,
            ),
        ):
            try:
                feedback_text = await _create_message_text(
                    make_client=make_client,
                    run_blocking=run_blocking,
                    model=model,
                    max_tokens=1000,
                    prompt=prompt,
                    error_prefix="Feedback generation failed",
                )
            except SubmissionGenerationError as exc:
                metadata = safe_error_metadata(
                    exc,
                    topic_id=topic.topic_id,
                    event_type="interview_feedback",
                    model=model,
                    refresh=refresh,
                )
                session.record_usage_event(
                    event_type="interview_feedback",
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
                logger.error("Claude interview feedback failed", extra={"ai2_metadata": metadata})
                raise
            score = parse_score(feedback_text)
            saved_model = model

    saved = session.save_interview_feedback(
        topic_id=topic.topic_id,
        feedback=feedback_text,
        model=saved_model,
        score=score,
    )
    session.mark_topic_step(topic.topic_id, "interview_practice", "done")
    session.record_usage_event(
        event_type="interview_feedback",
        topic_id=topic.topic_id,
        model=saved_model,
        source="test_mode" if test_mode else "claude",
        status="success",
        metadata={
            "refresh": refresh,
            "from_cache": False,
            "score": score,
        },
    )
    return _result(session, topic.topic_id, "interview_submission", saved)


async def _create_message_text(
    *,
    make_client,
    run_blocking,
    model: str,
    max_tokens: int,
    prompt: str,
    error_prefix: str,
) -> str:
    try:
        client = make_client()
        response = await run_blocking(
            lambda: client.messages.create(
                model=model,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )
        )
        return response.content[0].text
    except anthropic.APIError as exc:
        raise SubmissionGenerationError(f"Claude API error: {exc}") from exc
    except Exception as exc:
        raise SubmissionGenerationError(f"{error_prefix}: {exc}") from exc


def _result(
    session,
    topic_id: str,
    submission_key: str,
    submission: dict,
    *,
    from_cache: bool = False,
) -> dict:
    return {
        "topic_id": topic_id,
        submission_key: submission,
        "topic_progress": session.get_topic_progress(topic_id),
        "completion_percent": session.topic_completion_percent(topic_id),
        "from_cache": from_cache,
    }


_MOCK_QUIZ_EVALUATION = (
    "Overall Score: 8/10\n\n"
    "Correct Understanding: You demonstrated a clear understanding of the core concepts "
    "covered in the quiz.\n\n"
    "Mistakes / Gaps: Some answers lacked specific examples or quantitative detail.\n\n"
    "Explanation of Correct Answers: The correct answers focus on practical application "
    "and understanding the trade-offs of each approach.\n\n"
    "What To Revise: Review the relationship between the core concepts and their "
    "real-world applications.\n\n"
    "Next Action: Re-read the key concepts section and attempt one more practice "
    "question on the weakest area."
)

_MOCK_PORTFOLIO_FEEDBACK = (
    "Overall Feedback: Your submission demonstrates a solid understanding of the core concepts.\n\n"
    "What Is Strong: Clear problem definition and practical approach to the task.\n\n"
    "What Can Improve: Add more specific examples and quantify the expected impact.\n\n"
    "Missing Details: Trade-off analysis and consideration of edge cases.\n\n"
    "Suggested Improved Version: Extend your submission with one concrete metric and a "
    "brief implementation sketch to make it portfolio-ready.\n\n"
    "Portfolio Readiness Score: 7/10\n\n"
    "Next Action: Expand your deliverable with one concrete example and add it to your portfolio."
)

_MOCK_INTERVIEW_FEEDBACK = (
    "Overall Score: 8/10\n\n"
    "Clarity: Your answer is clearly structured and easy to follow.\n\n"
    "Accuracy: Core concepts are correct with minor gaps in detail.\n\n"
    "Depth: Good coverage of the main idea; could go deeper on trade-offs.\n\n"
    "Interview Readiness: Strong foundation \u2014 add one concrete example to stand out.\n\n"
    "Improved Answer: Start with a crisp definition, add a real-world example, "
    "then discuss trade-offs before concluding with your recommendation.\n\n"
    "What To Practice Next: Rehearse explaining this concept using the STAR format "
    "and focus on quantifying the impact."
)
