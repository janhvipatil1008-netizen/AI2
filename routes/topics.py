"""Topic-related routes: /topics, /topic, /topic/progress, /topic/notes,
/topic/content/generate, /topic/practice/generate."""

import os

import anthropic
from core.logging import get_logger
from fastapi import APIRouter, HTTPException, Request
from services.usage_limit_service import AIActionLimitError
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel, ValidationError

from config import AGENT_MODEL, TRACK_DISPLAY_NAMES
from context.session import VALID_PRACTICE_TYPES
from curriculum.freshness import classify_topic_freshness, freshness_guidance
from curriculum.topics import get_topic, get_topics_for_week
from services.content_service import (
    generate_learning_content_for_topic,
    generate_practice_content_for_topic,
)
from services.submission_service import generate_reflection_response

import routes.deps as deps

router = APIRouter()

TEST_MODE = os.getenv("AI2_TEST_MODE") == "1"
_logger = get_logger(__name__)


# ── Pydantic models ───────────────────────────────────────────────────────────

class TopicProgressRequest(BaseModel):
    session_id: str
    topic_id:   str
    step:       str
    status:     str


class TopicNotesRequest(BaseModel):
    session_id:       str
    topic_id:         str
    reflection:       str = ""
    confusions:       str = ""
    application_idea: str = ""


class TopicContentGenerateRequest(BaseModel):
    session_id: str
    topic_id:   str
    refresh:    bool = False


class TopicPracticeGenerateRequest(BaseModel):
    session_id:    str
    topic_id:      str
    practice_type: str
    refresh:       bool = False


class TopicOutcomeBaselineRequest(BaseModel):
    session_id:       str
    topic_id:         str
    baseline_answer:  str = ""
    baseline_score:   int | None = None


class TopicOutcomePostRequest(BaseModel):
    session_id:    str
    topic_id:      str
    post_answer:   str = ""
    post_score:    int | None = None


# ── Step metadata ─────────────────────────────────────────────────────────────

_NEXT_STEP_META = [
    ("learn",              "Continue Learning",           "ai-learning-content"),
    ("quiz",               "Continue Quiz",               "ai-quiz"),
    ("portfolio_task",     "Continue Portfolio Task",     "ai-portfolio-task"),
    ("interview_practice", "Continue Interview Practice", "ai-interview-practice"),
    ("reflection",         "Continue Reflection",         "topic-reflection"),
]


def get_next_topic_step(progress: dict[str, str]) -> dict:
    for step, label, anchor in _NEXT_STEP_META:
        if progress.get(step, "not_started") != "done":
            return {"step": step, "label": label, "anchor": anchor}
    return {"step": "", "label": "Review Topic", "anchor": ""}


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/topics/{session_id}", response_class=HTMLResponse)
async def topics_page(request: Request, session_id: str):
    data    = deps.get_session_data(session_id, request.state.user_id or "")
    session = data["session"]
    track   = session.track.value
    current_week = session.current_week
    topics  = _topics_for_listing(track=track, current_week=current_week)

    progress_by_topic = {}
    for topic in topics:
        tp_result = deps.read_topic_progress_with_fallback(
            session,
            session_id=session_id,
            user_id=request.state.user_id,
            legacy_topic_id=topic.topic_id,
        )
        progress_by_topic[topic.topic_id] = {
            "topic_progress":     tp_result["topic_progress"],
            "completion_percent": tp_result["completion_percent"],
            "next_step":          get_next_topic_step(tp_result["topic_progress"]),
        }

    _pcts        = [v["completion_percent"] for v in progress_by_topic.values()]
    total_topics = len(topics)
    completed_topics   = sum(1 for v in progress_by_topic.values() if v["completion_percent"] == 100)
    in_progress_topics = sum(
        1 for v in progress_by_topic.values()
        if v["completion_percent"] < 100
        and (v["completion_percent"] > 0 or "in_progress" in v["topic_progress"].values())
    )
    not_started_topics = total_topics - completed_topics - in_progress_topics
    avg_pct            = round(sum(_pcts) / total_topics) if total_topics else 0

    week_progress_summary = {
        "total_topics":               total_topics,
        "completed_topics":           completed_topics,
        "in_progress_topics":         in_progress_topics,
        "not_started_topics":         not_started_topics,
        "average_completion_percent": avg_pct,
    }

    return deps.templates.TemplateResponse(
        request=request,
        name="topics.html",
        context={
            "session_id":            session_id,
            "progress":              deps.session_progress(session),
            "topics":                topics,
            "progress_by_topic":     progress_by_topic,
            "week_progress_summary": week_progress_summary,
            "track":                 track,
            "current_week":          current_week,
            "test_mode":             bool(TEST_MODE),
        },
    )


@router.get("/topic/{session_id}/{topic_id}", response_class=HTMLResponse)
async def topic_detail_page(request: Request, session_id: str, topic_id: str):
    data    = deps.get_session_data(session_id, request.state.user_id or "")
    session = data["session"]
    track   = session.track.value
    topic   = get_topic(track, topic_id)
    if topic is None:
        raise HTTPException(status_code=404, detail="Topic not found")

    topic_freshness_label    = classify_topic_freshness(topic.topic_title, topic.description)
    topic_freshness_guidance = freshness_guidance(topic_freshness_label)
    tp_result                = deps.read_topic_progress_with_fallback(
        session,
        session_id=session_id,
        user_id=request.state.user_id,
        legacy_topic_id=topic_id,
    )
    learning_outcome_summary, learning_outcome_unavailable = (
        _topic_detail_learning_outcome_summary(session_id=session_id, topic_id=topic_id)
    )
    modular_topic_context = _topic_detail_modular_context(topic_id=topic_id)

    return deps.templates.TemplateResponse(
        request=request,
        name="topic_detail.html",
        context={
            "session_id":               session_id,
            "topic":                    topic,
            "progress":                 deps.session_progress(session),
            "topic_progress":           tp_result["topic_progress"],
            "completion_percent":       tp_result["completion_percent"],
            "topic_notes":              session.get_topic_notes(topic_id),
            "generated_topic_content":  session.get_generated_topic_content(topic_id),
            "generated_topic_practice": session.get_generated_topic_practice(topic_id),
            "portfolio_submission":     session.get_portfolio_submission(topic_id),
            "quiz_submission":          session.get_quiz_submission(topic_id),
            "interview_submission":     session.get_interview_submission(topic_id),
            "topic_freshness_label":    topic_freshness_label,
            "topic_freshness_guidance": topic_freshness_guidance,
            "modular_topic_context":  modular_topic_context,
            "learning_outcome_summary": learning_outcome_summary,
            "learning_outcome_unavailable": learning_outcome_unavailable,
            "test_mode":                bool(TEST_MODE),
        },
    )


@router.post("/topic/progress")
async def update_topic_progress(request: Request, body: TopicProgressRequest):
    data    = deps.get_session_data(body.session_id, request.state.user_id or "")
    session = data["session"]

    topic = get_topic(session.track.value, body.topic_id)
    if topic is None:
        raise HTTPException(status_code=404, detail="Topic not found")

    try:
        session.mark_topic_step(body.topic_id, body.step, body.status)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

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

    return {
        "topic_id":           body.topic_id,
        "step":               body.step,
        "status":             body.status,
        "topic_progress":     session.get_topic_progress(body.topic_id),
        "completion_percent": session.topic_completion_percent(body.topic_id),
    }


@router.post("/topic/notes")
async def save_topic_notes_endpoint(request: Request, body: TopicNotesRequest):
    data    = deps.get_session_data(body.session_id, request.state.user_id or "")
    session = data["session"]

    topic = get_topic(session.track.value, body.topic_id)
    if topic is None:
        raise HTTPException(status_code=404, detail="Topic not found")

    notes = session.save_topic_notes(
        topic_id         = body.topic_id,
        reflection       = body.reflection,
        confusions       = body.confusions,
        application_idea = body.application_idea,
    )

    if any([notes["reflection"], notes["confusions"], notes["application_idea"]]):
        session.mark_topic_step(body.topic_id, "reflection", "done")

    # Generate mentor response to the reflection (best-effort — notes are already saved).
    reflection_feedback = None
    try:
        quiz_score = session.get_quiz_submission(body.topic_id).get("score")
        quiz_score = quiz_score if isinstance(quiz_score, int) else None

        reflection_feedback = await generate_reflection_response(
            session          = session,
            topic            = topic,
            track_label      = TRACK_DISPLAY_NAMES[session.track],
            reflection       = body.reflection,
            confusions       = body.confusions,
            application_idea = body.application_idea,
            quiz_score       = quiz_score,
            make_client      = deps.make_client,
            run_blocking     = deps.run_blocking,
            test_mode        = TEST_MODE,
            model            = AGENT_MODEL,
            limit_enforcer   = deps.build_limit_enforcer(session),
        )
    except AIActionLimitError:
        pass  # notes saved; reflection response is best-effort
    except Exception as exc:
        _logger.warning(
            "reflection_response generation failed — notes already saved",
            extra={"error": str(exc), "topic_id": body.topic_id},
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
        user_id=request.state.user_id or None,
        legacy_topic_id=body.topic_id,
    )

    response: dict = {
        "topic_id":           body.topic_id,
        "notes":              notes,
        "topic_progress":     session.get_topic_progress(body.topic_id),
        "completion_percent": session.topic_completion_percent(body.topic_id),
    }
    if reflection_feedback is not None:
        response["reflection_feedback"] = {
            "mentor_reply":        reflection_feedback.mentor_reply,
            "lingering_confusion": reflection_feedback.lingering_confusion,
            "is_low_effort":       reflection_feedback.is_low_effort,
        }
    return response


@router.post("/topic/outcome/baseline")
async def submit_topic_outcome_baseline(request: Request):
    body, return_to = await _learning_outcome_request_body(
        request,
        model_class=TopicOutcomeBaselineRequest,
        score_field="baseline_score",
    )
    session = _get_session_for_topic(request, body.session_id, body.topic_id)
    baseline_score = _validated_outcome_score(body.baseline_score, field_name="baseline_score")

    try:
        from database.pool import get_conn
        from repositories.learning_outcomes_repository import (
            get_learning_outcome,
            upsert_baseline_outcome,
        )
        from services.learning_outcome_service import summarize_learning_outcome

        with get_conn() as conn:
            upsert_baseline_outcome(
                conn,
                user_id=request.state.user_id or getattr(session, "user_id", "") or None,
                session_id=body.session_id,
                legacy_topic_id=body.topic_id,
                baseline_prompt=None,
                baseline_answer=body.baseline_answer,
                baseline_score=baseline_score,
            )
            outcome = get_learning_outcome(
                conn,
                session_id=body.session_id,
                legacy_topic_id=body.topic_id,
            )
    except HTTPException:
        raise
    except Exception as exc:
        raise _learning_outcome_db_error(exc, action="save") from exc

    if return_to == "topic_detail":
        return RedirectResponse(
            url=f"/topic/{body.session_id}/{body.topic_id}#learning-outcome",
            status_code=303,
        )

    return {
        "session_id": body.session_id,
        "topic_id": body.topic_id,
        "summary": summarize_learning_outcome(outcome),
    }


@router.post("/topic/outcome/post")
async def submit_topic_outcome_post(request: Request):
    body, return_to = await _learning_outcome_request_body(
        request,
        model_class=TopicOutcomePostRequest,
        score_field="post_score",
    )
    session = _get_session_for_topic(request, body.session_id, body.topic_id)
    post_score = _validated_outcome_score(body.post_score, field_name="post_score")

    try:
        from database.pool import get_conn
        from repositories.learning_outcomes_repository import (
            get_learning_outcome,
            upsert_post_outcome,
        )
        from services.learning_outcome_service import summarize_learning_outcome

        with get_conn() as conn:
            upsert_post_outcome(
                conn,
                user_id=request.state.user_id or getattr(session, "user_id", "") or None,
                session_id=body.session_id,
                legacy_topic_id=body.topic_id,
                post_prompt=None,
                post_answer=body.post_answer,
                post_score=post_score,
            )
            outcome = get_learning_outcome(
                conn,
                session_id=body.session_id,
                legacy_topic_id=body.topic_id,
            )
    except HTTPException:
        raise
    except Exception as exc:
        raise _learning_outcome_db_error(exc, action="save") from exc

    if return_to == "topic_detail":
        return RedirectResponse(
            url=f"/topic/{body.session_id}/{body.topic_id}#learning-outcome",
            status_code=303,
        )

    return {
        "session_id": body.session_id,
        "topic_id": body.topic_id,
        "summary": summarize_learning_outcome(outcome),
    }


@router.get("/topic/outcome/{session_id}/{topic_id}")
async def get_topic_outcome_summary(request: Request, session_id: str, topic_id: str):
    _get_session_for_topic(request, session_id, topic_id)

    try:
        from database.pool import get_conn
        from repositories.learning_outcomes_repository import get_learning_outcome
        from services.learning_outcome_service import summarize_learning_outcome

        with get_conn() as conn:
            outcome = get_learning_outcome(
                conn,
                session_id=session_id,
                legacy_topic_id=topic_id,
            )
    except HTTPException:
        raise
    except Exception as exc:
        raise _learning_outcome_db_error(exc, action="read") from exc

    return {
        "session_id": session_id,
        "topic_id": topic_id,
        "summary": summarize_learning_outcome(outcome),
    }


@router.post("/topic/content/generate")
async def generate_topic_content(request: Request, body: TopicContentGenerateRequest):
    data    = deps.get_session_data(body.session_id, request.state.user_id or "")
    session = data["session"]

    topic = get_topic(session.track.value, body.topic_id)
    if topic is None:
        raise HTTPException(status_code=404, detail="Topic not found")

    freshness_label = classify_topic_freshness(topic.topic_title, topic.description)
    cache_read, cache_write = deps.build_content_cache_fns(
        track_key=session.track.value,
        legacy_topic_id=body.topic_id,
    )
    limit_enforcer = deps.build_limit_enforcer(session)

    try:
        result = await generate_learning_content_for_topic(
            session=session,
            topic=topic,
            track_label=TRACK_DISPLAY_NAMES[session.track],
            make_client=deps.make_client,
            run_blocking=deps.run_blocking,
            test_mode=TEST_MODE,
            model=AGENT_MODEL,
            refresh=body.refresh,
            freshness_label=freshness_label,
            shared_cache_read=cache_read,
            shared_cache_write=cache_write,
            limit_enforcer=limit_enforcer,
        )
    except AIActionLimitError as exc:
        raise HTTPException(status_code=429, detail=exc.user_message) from exc
    except anthropic.APIError as exc:
        raise HTTPException(status_code=500, detail=f"Claude API error: {exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Content generation failed: {exc}") from exc

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

    return {
        "topic_id":                body.topic_id,
        "content":                 result["content"],
        "generated_topic_content": result["generated_topic_content"],
    }


@router.post("/topic/practice/generate")
async def generate_topic_practice(request: Request, body: TopicPracticeGenerateRequest):
    data    = deps.get_session_data(body.session_id, request.state.user_id or "")
    session = data["session"]

    topic = get_topic(session.track.value, body.topic_id)
    if topic is None:
        raise HTTPException(status_code=404, detail="Topic not found")

    if body.practice_type not in VALID_PRACTICE_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid practice_type '{body.practice_type}'. Valid: {sorted(VALID_PRACTICE_TYPES)}",
        )

    freshness_label = classify_topic_freshness(topic.topic_title, topic.description)
    limit_enforcer  = deps.build_limit_enforcer(session)

    try:
        result = await generate_practice_content_for_topic(
            session=session,
            topic=topic,
            track_label=TRACK_DISPLAY_NAMES[session.track],
            practice_type=body.practice_type,
            make_client=deps.make_client,
            run_blocking=deps.run_blocking,
            test_mode=TEST_MODE,
            model=AGENT_MODEL,
            refresh=body.refresh,
            freshness_label=freshness_label,
            limit_enforcer=limit_enforcer,
        )
    except AIActionLimitError as exc:
        raise HTTPException(status_code=429, detail=exc.user_message) from exc
    except anthropic.APIError as exc:
        raise HTTPException(status_code=500, detail=f"Claude API error: {exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Content generation failed: {exc}") from exc

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

    return {
        "topic_id":           body.topic_id,
        "practice_type":      body.practice_type,
        "content":            result["content"],
        "generated_practice": result["generated_practice"],
    }


def _topics_for_listing(*, track: str, current_week: int):
    from services.storage_flags import is_modular_curriculum_reads_enabled

    if not is_modular_curriculum_reads_enabled():
        return get_topics_for_week(track, current_week)

    try:
        return _modular_topics_for_listing(track=track) or get_topics_for_week(track, current_week)
    except Exception:
        return get_topics_for_week(track, current_week)


def _modular_topics_for_listing(*, track: str):
    import database.pool as pool
    from services.modular_curriculum_fallback_service import get_course_structure_with_fallback
    from services.modular_topic_adapter import course_structure_to_topic_cards

    with pool.get_conn() as conn:
        result = get_course_structure_with_fallback(
            conn,
            course_key=_course_key_for_track(track),
            fallback_track_key=track,
        )

    return course_structure_to_topic_cards(
        result.get("course_structure"),
        track_key=track,
    )


def _course_key_for_track(track: str) -> str:
    # Keep this deliberately small while modular curriculum is behind a flag.
    # Runtime still falls back to the static curriculum if the DB course is not ready.
    return {
        "aipm": "aipm-foundations",
        "evals": "evals-foundations",
        "context": "context-engineering-foundations",
        "ai_builder": "ai-builder-foundations",
        "ai_job_ready": "ai-job-ready",
    }.get(track, f"{track}-foundations")


def _topic_detail_modular_context(*, topic_id: str) -> dict:
    from services.storage_flags import is_modular_curriculum_reads_enabled

    if not is_modular_curriculum_reads_enabled():
        return {
            "source": "disabled",
            "topic": None,
            "skills": [],
            "activities": [],
            "error": None,
        }

    try:
        return _load_modular_topic_context(topic_id=topic_id)
    except Exception as exc:
        return {
            "source": "error_fallback",
            "topic": None,
            "skills": [],
            "activities": [],
            "error": _safe_modular_topic_error(exc),
        }


def _load_modular_topic_context(*, topic_id: str) -> dict:
    import database.pool as pool
    from services.modular_curriculum_fallback_service import (
        get_topic_structure_by_legacy_id_with_fallback,
    )

    with pool.get_conn() as conn:
        result = get_topic_structure_by_legacy_id_with_fallback(
            conn,
            legacy_topic_id=topic_id,
        )

    topic = result.get("topic") if isinstance(result, dict) else None
    return {
        "source": result.get("source", "error_fallback") if isinstance(result, dict) else "error_fallback",
        "topic": _safe_modular_topic(topic),
        "skills": _safe_modular_skills(topic.get("skills") if isinstance(topic, dict) else []),
        "activities": _safe_modular_activities(topic.get("activities") if isinstance(topic, dict) else []),
        "error": _safe_modular_topic_error(result.get("error")) if isinstance(result, dict) and result.get("error") else None,
    }


def _safe_modular_topic(topic: dict | None) -> dict | None:
    if not isinstance(topic, dict):
        return None
    return {
        "legacy_topic_id": str(topic.get("legacy_topic_id") or ""),
        "topic_key": str(topic.get("topic_key") or ""),
        "title": str(topic.get("title") or ""),
        "description": str(topic.get("description") or ""),
        "difficulty_level": str(topic.get("difficulty_level") or ""),
        "estimated_minutes": topic.get("estimated_minutes"),
        "status": str(topic.get("status") or ""),
    }


def _safe_modular_skills(skills) -> list[dict]:
    safe: list[dict] = []
    for skill in list(skills or [])[:12]:
        if not isinstance(skill, dict):
            continue
        label = skill.get("name") or skill.get("title") or skill.get("skill_key")
        if not label:
            continue
        safe.append({
            "skill_key": str(skill.get("skill_key") or ""),
            "label": str(label),
        })
    return safe


def _safe_modular_activities(activities) -> list[dict]:
    safe: list[dict] = []
    for activity in list(activities or [])[:12]:
        if not isinstance(activity, dict):
            continue
        title = activity.get("title") or activity.get("activity_type") or activity.get("activity_key")
        if not title:
            continue
        safe.append({
            "activity_key": str(activity.get("activity_key") or ""),
            "activity_type": str(activity.get("activity_type") or ""),
            "title": str(title),
            "is_required": bool(activity.get("is_required", False)),
        })
    return safe


def _safe_modular_topic_error(exc_or_msg) -> str:
    import re

    msg = str(exc_or_msg or "")
    msg = re.sub(r"postgres(?:ql)?://\S+", "[DB_URL_REDACTED]", msg, flags=re.IGNORECASE)
    msg = re.sub(r"(DATABASE_URL|SUPABASE_DATABASE_URL|ANTHROPIC_API_KEY)=\S+", r"\1=[REDACTED]", msg)
    return msg[:200]


def _get_session_for_topic(request: Request, session_id: str, topic_id: str):
    data = deps.get_session_data(session_id, request.state.user_id or "")
    session = data["session"]
    topic = get_topic(session.track.value, topic_id)
    if topic is None:
        raise HTTPException(status_code=404, detail="Topic not found")
    return session


async def _learning_outcome_request_body(
    request: Request,
    *,
    model_class,
    score_field: str,
):
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        payload = await request.json()
        payload = dict(payload or {})
    else:
        form = await request.form()
        payload = dict(form)

    return_to = str(payload.pop("return_to", "") or "")
    if payload.get(score_field) == "":
        payload[score_field] = None

    try:
        return model_class(**payload), return_to
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail="Invalid learning outcome request.") from exc


def _topic_detail_learning_outcome_summary(
    *,
    session_id: str,
    topic_id: str,
) -> tuple[dict, bool]:
    from services.learning_outcome_service import summarize_learning_outcome

    empty_summary = summarize_learning_outcome(None)
    if TEST_MODE:
        return empty_summary, False

    try:
        import database.pool as pool
        from repositories.learning_outcomes_repository import get_learning_outcome

        if not getattr(pool, "DATABASE_URL", ""):
            return empty_summary, False

        with pool.get_conn() as conn:
            outcome = get_learning_outcome(
                conn,
                session_id=session_id,
                legacy_topic_id=topic_id,
            )
        return summarize_learning_outcome(outcome), False
    except Exception as exc:
        from core.logging import get_logger, safe_error_metadata

        get_logger("routes.learning_outcomes").warning(
            "learning outcome summary unavailable: %s",
            safe_error_metadata(exc),
        )
        return empty_summary, True


def _validated_outcome_score(score: int | None, *, field_name: str) -> int | None:
    if score is None:
        return None
    if 0 <= score <= 10:
        return score
    raise HTTPException(status_code=422, detail=f"{field_name} must be between 0 and 10.")


def _learning_outcome_db_error(exc: Exception, *, action: str) -> HTTPException:
    from core.logging import get_logger, safe_error_metadata

    get_logger("routes.learning_outcomes").warning(
        "learning outcome %s failed: %s",
        action,
        safe_error_metadata(exc),
    )
    if action == "read":
        detail = "Learning outcome summary unavailable. Please try again."
    else:
        detail = "Learning outcome save failed. Please try again."
    return HTTPException(status_code=503, detail=detail)
