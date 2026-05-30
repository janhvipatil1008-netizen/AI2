"""Chat and session routes."""

import uuid
from typing import Optional

import anthropic
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

import agents.practice_arena as practice_arena
import routes.deps as deps
from config import TOTAL_WEEKS
from context.learner_profile import LearnerProfile
from context.session import SessionContext
from orchestrator import Orchestrator
from services.llm_observability import build_safe_trace_metadata, trace_llm_call

router = APIRouter()


class StartSessionRequest(BaseModel):
    track: str          # "aipm" | "evals" | "context"
    week:  int = 1


class ChatRequest(BaseModel):
    session_id: str
    message:    str


class QuizRequest(BaseModel):
    session_id: str
    topic:      str
    difficulty: str = "all"


class InterviewRequest(BaseModel):
    session_id: str
    topic:      str
    difficulty: str = "all"


class EvaluateRequest(BaseModel):
    session_id: str
    question:   str
    answer:     str
    topic:      str = ""


@router.get("/history", response_class=HTMLResponse)
async def history_page(request: Request):
    user_id = request.state.user_id or "test-user"
    entries = deps.get_user_history(user_id, limit=200)
    return deps.templates.TemplateResponse(
        request=request,
        name="history.html",
        context={
            "entries":   entries,
            "test_mode": bool(deps.TEST_MODE),
        },
    )


@router.post("/session/start")
@deps.limiter.limit(deps.CHAT_RATE_LIMIT)
async def start_session(request: Request, body: StartSessionRequest):
    user_id = getattr(request.state, "user_id", None) or ""
    track   = deps.track_from_str(body.track)
    session = SessionContext(track=track, user_id=user_id, current_week=max(1, min(body.week, TOTAL_WEEKS)))
    client  = None if deps.TEST_MODE else deps.make_client()

    # Load or create learner profile
    profile = deps.load_profile_db(user_id) if user_id else None
    if profile is None and user_id:
        profile = LearnerProfile.new_for_user(user_id, track)

    orch = None if deps.TEST_MODE else Orchestrator(client=client, session=session, profile=profile)

    session_id = str(uuid.uuid4())
    deps.session_cache[session_id] = {"session": session, "orch": orch, "client": client, "profile": profile}
    deps.save_session(session_id, session)

    return {
        "session_id": session_id,
        "progress":   deps.session_progress(session),
    }


@router.post("/chat")
@deps.limiter.limit(deps.CHAT_RATE_LIMIT)
async def chat(request: Request, body: ChatRequest):
    data    = deps.get_session_data(body.session_id, request.state.user_id or "")
    session: SessionContext = data["session"]

    if not body.message.strip():
        raise HTTPException(status_code=422, detail="Message cannot be empty")

    # Interactive quiz intercept: answer active A/B/C/D quiz turns without a Claude call.
    if session.quiz_state and session.quiz_state.get("questions"):
        cleaned = body.message.strip().rstrip(".!?,").upper()
        if cleaned in ("A", "B", "C", "D"):
            response_text = practice_arena.handle_quiz_answer(session, cleaned)
            agent_used    = "practice_arena"
            session.add_exchange(body.message, response_text[:500], agent_used)
            deps.save_session(body.session_id, session)
            return {
                "response":   response_text,
                "agent_used": agent_used,
                "progress":   deps.session_progress(session),
            }

    if deps.TEST_MODE:
        response_text, agent_used = deps.mock_orchestrator_response(body.message, session)
        session.add_exchange(body.message, response_text[:500], agent_used)
        session.note_topic(body.message[:60])
    else:
        orch: Orchestrator = data["orch"]
        with trace_llm_call(
            "chat.orchestrator_process",
            metadata=build_safe_trace_metadata(
                session_id=body.session_id,
                route_type="chat",
                turn_count=len(session.history),
            ),
        ):
            try:
                response_text = await deps.run_blocking(orch.process, body.message)
                agent_used = session.history[-1].agent_used if session.history else "orchestrator"
            except anthropic.APIError as exc:
                raise HTTPException(status_code=502, detail=f"Claude API error: {exc}") from exc

    deps.save_session(body.session_id, session)

    # Persist this exchange to the permanent history table
    deps.save_exchange_to_history(
        user_id=session.user_id,
        session_id=body.session_id,
        user_message=body.message,
        assistant_reply=response_text[:2000],
        agent_used=agent_used,
    )

    # Update learner profile after each exchange
    profile: Optional[LearnerProfile] = data.get("profile")
    if profile and session.user_id:
        profile.total_exchanges = sum(
            1 for _ in session.history
        )
        deps.save_profile_db(profile)

    return {
        "response":   response_text,
        "agent_used": agent_used,
        "progress":   deps.session_progress(session),
    }


@router.get("/progress/{session_id}")
async def get_progress(request: Request, session_id: str):
    data    = deps.get_session_data(session_id, request.state.user_id or "")
    session = data["session"]
    return deps.session_progress(session)


@router.post("/quiz")
@deps.limiter.limit(deps.PRACTICE_RATE_LIMIT)
async def quiz(request: Request, body: QuizRequest):
    data    = deps.get_session_data(body.session_id, request.state.user_id or "")
    session = data["session"]

    if deps.TEST_MODE:
        response_text = deps.mock_responses["practice_arena_mcq"]
        session.note_topic(body.topic)
        session.mark_exercise_done()
    else:
        client = data["client"]
        response_text = await deps.run_blocking(
            practice_arena.generate_mcq_quiz,
            client, body.topic, session, body.difficulty,
        )

    deps.save_session(body.session_id, session)
    return {"response": response_text, "progress": deps.session_progress(session)}


@router.post("/interview")
@deps.limiter.limit(deps.PRACTICE_RATE_LIMIT)
async def interview(request: Request, body: InterviewRequest):
    data    = deps.get_session_data(body.session_id, request.state.user_id or "")
    session = data["session"]

    if deps.TEST_MODE:
        response_text = deps.mock_responses["practice_arena_interview"]
        session.note_topic(body.topic)
        session.mark_exercise_done()
    else:
        client = data["client"]
        response_text = await deps.run_blocking(
            practice_arena.generate_interview_questions,
            client, body.topic, session, body.difficulty,
        )

    deps.save_session(body.session_id, session)
    return {"response": response_text, "progress": deps.session_progress(session)}


@router.post("/evaluate")
@deps.limiter.limit(deps.PRACTICE_RATE_LIMIT)
async def evaluate(request: Request, body: EvaluateRequest):
    data    = deps.get_session_data(body.session_id, request.state.user_id or "")
    session = data["session"]

    if deps.TEST_MODE:
        response_text = (
            "ðŸ“‹  ANSWER EVALUATION\n"
            "â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€\n"
            f"Question: {body.question}\n\n"
            f"Your answer: {body.answer}\n\n"
            "â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€\n"
            "SCORECARD\n"
            "  Clarity    : 8/10 â€” Well-structured and easy to follow\n"
            "  Accuracy   : 7/10 â€” Core concepts correct; minor gaps\n"
            "  Depth      : 6/10 â€” Good surface coverage; could go deeper on tradeoffs\n"
            "  Relevance  : 9/10 â€” Directly addresses the question\n"
            "  â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€\n"
            "  TOTAL      : 30/40  (75%)  â­â­â­\n\n"
            "âœ…  WHAT YOU GOT RIGHT\n"
            "  â€¢ Correctly identified the core mechanism\n"
            "  â€¢ Good use of concrete example\n\n"
            "ðŸ”§  WHERE TO IMPROVE\n"
            "  â€¢ Add tradeoff discussion (latency vs accuracy)\n"
            "  â€¢ Mention a specific tool or metric\n\n"
            "âœ¨  MODEL ANSWER\n"
            "  [A stronger version would be here in production mode]\n\n"
            "ðŸ’¡  ONE DRILL\n"
            "  Practice the STAR format: Situation â†’ Task â†’ Action â†’ Result"
        )
    else:
        client = data["client"]
        response_text = await deps.run_blocking(
            practice_arena.evaluate_answer,
            client, body.question, body.answer, session, body.topic,
        )

    return {"response": response_text, "progress": deps.session_progress(session)}


@router.get("/chat/{session_id}", response_class=HTMLResponse)
async def chat_page(request: Request, session_id: str):
    data    = deps.get_session_data(session_id, request.state.user_id or "")
    session = data["session"]
    return deps.templates.TemplateResponse(
        request=request,
        name="chat.html",
        context={
            "session_id": session_id,
            "progress":   deps.session_progress(session),
            "test_mode":  bool(deps.TEST_MODE),
        },
    )
