"""Quiz, portfolio, and interview submission/feedback routes."""

import os

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from config import AGENT_MODEL, TRACK_DISPLAY_NAMES
from curriculum.topics import get_topic
from services.submission_service import (
    SubmissionGenerationError,
    SubmissionValidationError,
    evaluate_quiz_answers,
    generate_interview_feedback,
    generate_portfolio_feedback,
    submit_interview_answer,
    submit_portfolio_work,
    submit_quiz_answers,
)

from services.usage_limit_service import AIActionLimitError

import routes.deps as deps

router = APIRouter()

TEST_MODE = os.getenv("AI2_TEST_MODE") == "1"


# Pydantic models

class PortfolioSubmitRequest(BaseModel):
    session_id: str
    topic_id:   str
    submission: str


class PortfolioFeedbackRequest(BaseModel):
    session_id: str
    topic_id:   str
    refresh:    bool = False


class QuizSubmitRequest(BaseModel):
    session_id: str
    topic_id:   str
    answers:    str


class QuizEvaluateRequest(BaseModel):
    session_id: str
    topic_id:   str
    refresh:    bool = False


class InterviewSubmitRequest(BaseModel):
    session_id: str
    topic_id:   str
    answer:     str


class InterviewFeedbackRequest(BaseModel):
    session_id: str
    topic_id:   str
    refresh:    bool = False


# Routes

@router.post("/feedback/beta")
async def beta_feedback(request: Request):
    payload, is_form = await _beta_feedback_payload(request)
    session_id = str(payload.get("session_id") or "").strip()
    if not session_id:
        raise HTTPException(status_code=422, detail="session_id is required.")

    session = _get_session(request, session_id)

    try:
        from database.pool import get_conn
        from repositories.beta_feedback_repository import insert_beta_feedback
        from services.beta_feedback_service import (
            normalize_feedback_context,
            sanitize_feedback_text,
            validate_score,
        )

        legacy_topic_id = sanitize_feedback_text(payload.get("legacy_topic_id"), max_length=200)
        if legacy_topic_id:
            _get_topic_or_404(session, legacy_topic_id)

        feedback_context = normalize_feedback_context(str(payload.get("feedback_context") or "general"))
        usefulness_score = validate_score(payload.get("usefulness_score"))
        clarity_score = validate_score(payload.get("clarity_score"))
        confusion = sanitize_feedback_text(payload.get("confusion"))
        improvement_suggestion = sanitize_feedback_text(payload.get("improvement_suggestion"))
        willingness_to_pay = sanitize_feedback_text(payload.get("willingness_to_pay"), max_length=500)

        with get_conn() as conn:
            insert_beta_feedback(
                conn,
                user_id=request.state.user_id or getattr(session, "user_id", "") or None,
                session_id=session_id,
                legacy_topic_id=legacy_topic_id,
                feedback_context=feedback_context,
                usefulness_score=usefulness_score,
                clarity_score=clarity_score,
                confusion=confusion,
                improvement_suggestion=improvement_suggestion,
                willingness_to_pay=willingness_to_pay,
            )
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise _beta_feedback_db_error(exc) from exc

    redirect_to = _safe_feedback_redirect(payload.get("redirect_to"))
    if is_form and redirect_to:
        return RedirectResponse(url=redirect_to, status_code=303)

    return {
        "ok": True,
        "session_id": session_id,
        "legacy_topic_id": legacy_topic_id,
        "feedback_context": feedback_context,
    }


@router.post("/portfolio/submit")
async def portfolio_submit(request: Request, body: PortfolioSubmitRequest):
    session = _get_session(request, body.session_id)
    topic = _get_topic_or_404(session, body.topic_id)

    result = _call_submission_service(
        lambda: submit_portfolio_work(
            session=session,
            topic=topic,
            submission=body.submission,
        )
    )
    deps.save_session(body.session_id, session)
    deps.write_through_topic_progress(
        session,
        session_id=body.session_id,
        user_id=request.state.user_id or getattr(session, "user_id", "") or None,
        legacy_topic_id=body.topic_id,
    )
    deps.write_through_modular_progress_snapshot(
        session,
        session_id=body.session_id,
        user_id=request.state.user_id or getattr(session, "user_id", "") or None,
    )
    deps.write_through_generated_learning_state(
        session,
        session_id=body.session_id,
        user_id=request.state.user_id or getattr(session, "user_id", "") or None,
        legacy_topic_id=body.topic_id,
    )
    return _public_result(result)


@router.post("/portfolio/feedback")
async def portfolio_feedback(request: Request, body: PortfolioFeedbackRequest):
    session = _get_session(request, body.session_id)
    topic = _get_topic_or_404(session, body.topic_id)

    result = await _call_feedback_service(
        generate_portfolio_feedback(
            session=session,
            topic=topic,
            track_label=TRACK_DISPLAY_NAMES[session.track],
            make_client=deps.make_client,
            run_blocking=deps.run_blocking,
            test_mode=TEST_MODE,
            model=AGENT_MODEL,
            refresh=body.refresh,
            limit_enforcer=deps.build_limit_enforcer(session),
        )
    )
    deps.save_session(body.session_id, session)
    deps.write_through_topic_progress(
        session,
        session_id=body.session_id,
        user_id=request.state.user_id or getattr(session, "user_id", "") or None,
        legacy_topic_id=body.topic_id,
    )
    deps.write_through_modular_progress_snapshot(
        session,
        session_id=body.session_id,
        user_id=request.state.user_id or getattr(session, "user_id", "") or None,
    )
    deps.write_through_generated_learning_state(
        session,
        session_id=body.session_id,
        user_id=request.state.user_id or getattr(session, "user_id", "") or None,
        legacy_topic_id=body.topic_id,
    )
    deps.write_through_usage_events(
        session,
        session_id=body.session_id,
        user_id=request.state.user_id or None,
        legacy_topic_id=body.topic_id,
    )
    return _public_result(result)


@router.post("/quiz/submit")
async def quiz_submit(request: Request, body: QuizSubmitRequest):
    session = _get_session(request, body.session_id)
    topic = _get_topic_or_404(session, body.topic_id)

    result = _call_submission_service(
        lambda: submit_quiz_answers(
            session=session,
            topic=topic,
            answers=body.answers,
        )
    )
    deps.save_session(body.session_id, session)
    deps.write_through_topic_progress(
        session,
        session_id=body.session_id,
        user_id=request.state.user_id or None,
        legacy_topic_id=body.topic_id,
    )
    deps.write_through_modular_progress_snapshot(
        session,
        session_id=body.session_id,
        user_id=request.state.user_id or None,
    )
    deps.write_through_generated_learning_state(
        session,
        session_id=body.session_id,
        user_id=request.state.user_id or None,
        legacy_topic_id=body.topic_id,
    )
    return _public_result(result)


@router.post("/quiz/evaluate")
async def quiz_evaluate(request: Request, body: QuizEvaluateRequest):
    session = _get_session(request, body.session_id)
    topic = _get_topic_or_404(session, body.topic_id)

    result = await _call_feedback_service(
        evaluate_quiz_answers(
            session=session,
            topic=topic,
            track_label=TRACK_DISPLAY_NAMES[session.track],
            make_client=deps.make_client,
            run_blocking=deps.run_blocking,
            test_mode=TEST_MODE,
            model=AGENT_MODEL,
            refresh=body.refresh,
            limit_enforcer=deps.build_limit_enforcer(session),
        )
    )
    deps.save_session(body.session_id, session)
    deps.write_through_topic_progress(
        session,
        session_id=body.session_id,
        user_id=request.state.user_id or None,
        legacy_topic_id=body.topic_id,
    )
    deps.write_through_modular_progress_snapshot(
        session,
        session_id=body.session_id,
        user_id=request.state.user_id or None,
    )
    deps.write_through_generated_learning_state(
        session,
        session_id=body.session_id,
        user_id=request.state.user_id or None,
        legacy_topic_id=body.topic_id,
    )
    deps.write_through_usage_events(
        session,
        session_id=body.session_id,
        user_id=request.state.user_id or None,
        legacy_topic_id=body.topic_id,
    )
    return _public_result(result)


@router.post("/interview/submit")
async def interview_submit(request: Request, body: InterviewSubmitRequest):
    session = _get_session(request, body.session_id)
    topic = _get_topic_or_404(session, body.topic_id)

    result = _call_submission_service(
        lambda: submit_interview_answer(
            session=session,
            topic=topic,
            answer=body.answer,
        )
    )
    deps.save_session(body.session_id, session)
    deps.write_through_topic_progress(
        session,
        session_id=body.session_id,
        user_id=request.state.user_id or None,
        legacy_topic_id=body.topic_id,
    )
    deps.write_through_modular_progress_snapshot(
        session,
        session_id=body.session_id,
        user_id=request.state.user_id or None,
    )
    deps.write_through_generated_learning_state(
        session,
        session_id=body.session_id,
        user_id=request.state.user_id or None,
        legacy_topic_id=body.topic_id,
    )
    return _public_result(result)


@router.post("/interview/feedback")
async def interview_feedback_endpoint(request: Request, body: InterviewFeedbackRequest):
    session = _get_session(request, body.session_id)
    topic = _get_topic_or_404(session, body.topic_id)

    result = await _call_feedback_service(
        generate_interview_feedback(
            session=session,
            topic=topic,
            track_label=TRACK_DISPLAY_NAMES[session.track],
            make_client=deps.make_client,
            run_blocking=deps.run_blocking,
            test_mode=TEST_MODE,
            model=AGENT_MODEL,
            refresh=body.refresh,
            limit_enforcer=deps.build_limit_enforcer(session),
        )
    )
    deps.save_session(body.session_id, session)
    deps.write_through_topic_progress(
        session,
        session_id=body.session_id,
        user_id=request.state.user_id or None,
        legacy_topic_id=body.topic_id,
    )
    deps.write_through_modular_progress_snapshot(
        session,
        session_id=body.session_id,
        user_id=request.state.user_id or None,
    )
    deps.write_through_generated_learning_state(
        session,
        session_id=body.session_id,
        user_id=request.state.user_id or None,
        legacy_topic_id=body.topic_id,
    )
    deps.write_through_usage_events(
        session,
        session_id=body.session_id,
        user_id=request.state.user_id or None,
        legacy_topic_id=body.topic_id,
    )
    return _public_result(result)


def _get_session(request: Request, session_id: str):
    data = deps.get_session_data(session_id, request.state.user_id or "")
    return data["session"]


def _get_topic_or_404(session, topic_id: str):
    topic = get_topic(session.track.value, topic_id)
    if topic is None:
        raise HTTPException(status_code=404, detail="Topic not found")
    return topic


def _call_submission_service(fn):
    try:
        return fn()
    except SubmissionValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


async def _call_feedback_service(awaitable):
    try:
        return await awaitable
    except AIActionLimitError as exc:
        raise HTTPException(status_code=429, detail=exc.user_message) from exc
    except SubmissionValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except SubmissionGenerationError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


def _public_result(result: dict) -> dict:
    public = dict(result)
    public.pop("from_cache", None)
    return public


async def _beta_feedback_payload(request: Request) -> tuple[dict, bool]:
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        return dict((await request.json()) or {}), False
    form = await request.form()
    return dict(form), True


def _safe_feedback_redirect(value) -> str:
    redirect_to = str(value or "").strip()
    if not redirect_to:
        return ""
    if redirect_to.startswith("/topic/") and "//" not in redirect_to:
        return redirect_to
    return ""


def _beta_feedback_db_error(exc: Exception) -> HTTPException:
    from core.logging import get_logger, safe_error_metadata

    get_logger("routes.beta_feedback").warning(
        "beta feedback save failed: %s",
        safe_error_metadata(exc),
    )
    return HTTPException(status_code=503, detail="Feedback save failed. Please try again.")
