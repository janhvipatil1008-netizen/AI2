"""
AI² Platform — FastAPI Web Application

Thin web layer over the existing CLI platform, enabling browser-based access
and Playwright-based automated testing.  Runs alongside the Rich CLI — both
share the same orchestrator and sub-agent modules.

Start with:
    uvicorn app:app --reload --port 8000

Test mode (no live Claude calls, mock responses):
    AI2_TEST_MODE=1 uvicorn app:app --port 8765
"""

import asyncio
import functools
import json
import os
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Optional

import anthropic
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from auth import get_current_user_id
from core.security_config import assert_test_mode_off
from routes.deps import debug_access as _debug_access, safe_debug_error_message as _safe_debug_error_message
from database.pool import get_conn
from config import CareerTrack, TRACK_DISPLAY_NAMES, TOTAL_WEEKS
from context.session import SessionContext
from context.learner_profile import (
    LearnerProfile, load_profile, save_profile,
)
from curriculum.syllabus import _WEEK_TO_PHASE, get_phase_by_id
from orchestrator import Orchestrator

load_dotenv()

# ── Config ────────────────────────────────────────────────────────────────────

TEST_MODE = os.getenv("AI2_TEST_MODE") == "1"
assert_test_mode_off()
logger    = logging.getLogger(__name__)

# ── App setup ─────────────────────────────────────────────────────────────────

app = FastAPI(
    title="AI²",
    description="AI for AI — Adaptive Learning Platform",
    version="1.0.0",
)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Rate limiter — high ceiling in TEST_MODE so tests are never throttled
_CHAT_RATE_LIMIT     = "1000/minute" if TEST_MODE else "20/minute"
_PRACTICE_RATE_LIMIT = "1000/minute" if TEST_MODE else "10/minute"
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# In-memory session cache
_sessions: dict[str, dict] = {}
_executor = ThreadPoolExecutor(max_workers=4)


# ── Session persistence (PostgreSQL) ─────────────────────────────────────────


def _save_session(session_id: str, session: SessionContext) -> None:
    """Write-through: persist session to PostgreSQL after every mutation."""
    if TEST_MODE:
        return
    data = json.dumps(session.to_dict())
    now  = datetime.now().isoformat()
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO sessions "
                    "(session_id, session_data, created_at, updated_at, user_id) "
                    "VALUES (%s, %s, %s, %s, %s) "
                    "ON CONFLICT (session_id) DO UPDATE "
                    "SET session_data=%s, updated_at=%s, user_id=%s",
                    (session_id, data, session.start_time, now, session.user_id or None,
                     data, now, session.user_id or None),
                )
    except Exception as exc:
        logger.warning(f"_save_session failed (non-fatal): {exc}")


def _save_exchange_to_history(
    user_id: str, session_id: str,
    user_message: str, assistant_reply: str, agent_used: str,
) -> None:
    """Append a single exchange to the permanent conversation_history table."""
    if TEST_MODE or not user_id:
        return
    now = datetime.now().isoformat()
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO conversation_history "
                    "(user_id, session_id, user_message, assistant_reply, agent_used, timestamp) "
                    "VALUES (%s, %s, %s, %s, %s, %s)",
                    (user_id, session_id, user_message, assistant_reply, agent_used, now),
                )
    except Exception as exc:
        logger.warning(f"_save_exchange_to_history failed (non-fatal): {exc}")


def _save_profile_db(profile: LearnerProfile) -> None:
    """Persist a LearnerProfile to PostgreSQL."""
    if TEST_MODE:
        return
    try:
        with get_conn() as conn:
            save_profile(profile, conn)
    except Exception as exc:
        logger.warning(f"_save_profile_db failed (non-fatal): {exc}")


def _load_profile_db(user_id: str) -> Optional[LearnerProfile]:
    if TEST_MODE or not user_id:
        return None
    try:
        with get_conn() as conn:
            return load_profile(user_id, conn)
    except Exception:
        return None


def _load_session_from_db(session_id: str) -> Optional[SessionContext]:
    """Load a session from PostgreSQL (used on cache miss — e.g. after restart)."""
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT session_data FROM sessions WHERE session_id = %s",
                    (session_id,),
                )
                row = cur.fetchone()
        if row:
            return SessionContext.from_dict(json.loads(row[0]))
    except Exception:
        pass
    return None


def _get_user_sessions(user_id: str, limit: int = 10) -> list[dict]:
    """Return recent sessions for a user, ordered by updated_at desc."""
    if TEST_MODE or not user_id:
        return []
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT session_id, session_data, updated_at FROM sessions "
                    "WHERE user_id = %s ORDER BY updated_at DESC LIMIT %s",
                    (user_id, limit),
                )
                rows = cur.fetchall()
        result = []
        for session_id, data_json, updated_at in rows:
            try:
                data = json.loads(data_json)
                result.append({
                    "session_id":   session_id,
                    "track":        data.get("track", ""),
                    "current_week": data.get("current_week", 1),
                    "updated_at":   updated_at,
                })
            except Exception:
                continue
        return result
    except Exception:
        return []


def _get_user_history(user_id: str, limit: int = 200) -> list[dict]:
    """Return full conversation history for a user from the permanent table."""
    if TEST_MODE or not user_id:
        return []
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT session_id, user_message, assistant_reply, agent_used, timestamp "
                    "FROM conversation_history WHERE user_id = %s ORDER BY timestamp DESC LIMIT %s",
                    (user_id, limit),
                )
                rows = cur.fetchall()
        return [
            {
                "session_id":      r[0],
                "user_message":    r[1],
                "assistant_reply": r[2],
                "agent_used":      r[3],
                "timestamp":       r[4],
            }
            for r in rows
        ]
    except Exception:
        return []


def _startup_db() -> None:
    """Run schema.sql against PostgreSQL if tables don't yet exist. No-op in TEST_MODE."""
    if TEST_MODE:
        return
    schema_path = os.path.join(os.path.dirname(__file__), "database", "schema.sql")
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT EXISTS (SELECT FROM information_schema.tables "
                    "WHERE table_schema = 'public' AND table_name = 'users')"
                )
                tables_exist = cur.fetchone()[0]
                if not tables_exist:
                    with open(schema_path) as f:
                        schema_sql = f.read()
                    for stmt in schema_sql.split(";"):
                        s = stmt.strip()
                        if s:
                            cur.execute(s)
                    logger.info("First-deploy: created schema from database/schema.sql")
    except Exception as exc:
        logger.warning(f"_startup_db skipped: {exc}")

_startup_db()

# ── Authentication middleware ─────────────────────────────────────────────────

_PUBLIC_PATHS = {"/login", "/signup", "/health", "/privacy", "/terms"}


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    """
    Per-user auth: decode ai2_user_token cookie → attach user_id to request.state.
    Unauthenticated access to protected routes → redirect /login (browser) or 401 (API).
    TEST_MODE bypasses all auth so tests are never blocked.
    """
    path = request.url.path

    # Attach user_id to state for all requests (even public ones)
    user_id = None if TEST_MODE else get_current_user_id(request)
    request.state.user_id = user_id

    if TEST_MODE or path in _PUBLIC_PATHS or path.startswith("/static"):
        return await call_next(request)

    if not user_id:
        accept = request.headers.get("accept", "")
        if "text/html" in accept:
            return RedirectResponse(url="/login", status_code=302)
        return JSONResponse({"detail": "Unauthorized — please log in."}, status_code=401)

    return await call_next(request)


# ── Mock responses for TEST_MODE ──────────────────────────────────────────────

_MOCK_RESPONSES = {
    "learning_coach": (
        "Great question! The transformer architecture introduced the self-attention "
        "mechanism, which allows each token to attend to every other token in the "
        "sequence simultaneously. This solved the sequential bottleneck of RNNs.\n\n"
        "📄 **Attention Is All You Need** — Vaswani et al., 2017\n"
        "_Why now:_ This is the paper that started everything — understanding it "
        "makes every LLM concept click into place."
    ),
    "practice_arena_mcq": (
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "📝  QUIZ: RAG Pipelines — AIPM Track\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "🟢 BEGINNER  (Q1–5)\n"
        "─────────────────────────────────────────────────────\n"
        "Q1. What does RAG stand for?\n\n"
        "   A) Random Augmented Generation\n"
        "   B) Retrieval-Augmented Generation\n"
        "   C) Recursive Agentic Grounding\n"
        "   D) Real-time AI Generation\n\n"
        "✅ Answer: B) Retrieval-Augmented Generation\n"
        "💡 Why: RAG combines a retrieval step (fetching relevant documents) with "
        "generation (LLM response), grounding answers in real sources.\n\n"
        "Q2. What problem does RAG primarily solve?\n\n"
        "   A) Model training speed\n"
        "   B) Token cost reduction\n"
        "   C) Hallucination and knowledge cutoffs\n"
        "   D) Prompt formatting\n\n"
        "✅ Answer: C) Hallucination and knowledge cutoffs\n"
        "💡 Why: RAG retrieves fresh, authoritative content at inference time, "
        "preventing the model from fabricating facts or using stale knowledge.\n\n"
        "Q3. Which component converts text into searchable vectors?\n\n"
        "   A) The LLM\n"
        "   B) The embedding model\n"
        "   C) The tokenizer\n"
        "   D) The reranker\n\n"
        "✅ Answer: B) The embedding model\n"
        "💡 Why: Embedding models map text to high-dimensional vectors. Semantic "
        "similarity is then measured by vector distance, not keyword matching.\n\n"
        "Q4. What is a vector store?\n\n"
        "   A) A file system for saving model weights\n"
        "   B) A database optimised for similarity search on embeddings\n"
        "   C) A caching layer for API responses\n"
        "   D) A token vocabulary table\n\n"
        "✅ Answer: B) A database optimised for similarity search on embeddings\n"
        "💡 Why: Vector stores (Chroma, Pinecone, Weaviate) index embeddings and "
        "support fast nearest-neighbour queries — the retrieval backbone of RAG.\n\n"
        "Q5. What is 'chunking' in a RAG pipeline?\n\n"
        "   A) Splitting the model into smaller parts\n"
        "   B) Breaking source documents into smaller text segments\n"
        "   C) Batching API requests together\n"
        "   D) Compressing embeddings\n\n"
        "✅ Answer: B) Breaking source documents into smaller text segments\n"
        "💡 Why: LLMs have finite context windows. Chunking ensures each retrieved "
        "piece fits within the context budget while staying semantically coherent.\n\n"
        "🟡 INTERMEDIATE  (Q6–10)\n"
        "─────────────────────────────────────────────────────\n"
        "Q6. A RAG system returns low-quality answers despite high retrieval recall. "
        "What is the most likely root cause?\n\n"
        "   A) The embedding model is too large\n"
        "   B) Retrieved chunks are relevant but lack sufficient context\n"
        "   C) The LLM temperature is too low\n"
        "   D) The vector store has too many dimensions\n\n"
        "✅ Answer: B) Retrieved chunks are relevant but lack sufficient context\n"
        "💡 Why: High recall means you're finding the right documents, but if chunks "
        "are too small or mid-sentence, the LLM can't synthesise a coherent answer.\n\n"
        "Q7. What does top-k control in retrieval?\n\n"
        "   A) The number of tokens generated\n"
        "   B) The number of candidate documents passed to the LLM\n"
        "   C) The similarity threshold for indexing\n"
        "   D) The LLM sampling strategy\n\n"
        "✅ Answer: B) The number of candidate documents passed to the LLM\n"
        "💡 Why: top-k=5 returns the 5 most similar chunks. Higher k improves recall "
        "but increases token cost and can dilute relevance with noise.\n\n"
        "Q8. Why might hybrid search outperform pure vector search?\n\n"
        "   A) It uses a larger embedding model\n"
        "   B) It combines semantic similarity with keyword matching\n"
        "   C) It stores documents as JSON instead of vectors\n"
        "   D) It reranks results using a second LLM\n\n"
        "✅ Answer: B) It combines semantic similarity with keyword matching\n"
        "💡 Why: Pure vector search misses exact-match queries (product codes, names). "
        "BM25 + vector fusion (Reciprocal Rank Fusion) handles both cases.\n\n"
        "Q9. A product manager notices Agri-Saathi answers questions correctly but "
        "never cites sources. What part of the pipeline needs fixing?\n\n"
        "   A) The embedding model\n"
        "   B) The system prompt and response schema\n"
        "   C) The chunking strategy\n"
        "   D) The vector store index\n\n"
        "✅ Answer: B) The system prompt and response schema\n"
        "💡 Why: Citations require explicit instruction to include source metadata, "
        "and a response schema (JSON/structured output) that returns them reliably.\n\n"
        "Q10. What is retrieval precision@k?\n\n"
        "   A) The percentage of all relevant docs returned in top-k\n"
        "   B) The percentage of top-k results that are actually relevant\n"
        "   C) The accuracy of the embedding model on test data\n"
        "   D) The latency of the retrieval step\n\n"
        "✅ Answer: B) The percentage of top-k results that are actually relevant\n"
        "💡 Why: Precision@5=0.8 means 4 of 5 returned chunks are useful. "
        "Recall@k measures the opposite — how much of the total relevant set was found.\n\n"
        "🔴 ADVANCED  (Q11–15)\n"
        "─────────────────────────────────────────────────────\n"
        "Q11. You need sub-100ms retrieval latency at 10M documents. Which approach "
        "is most appropriate?\n\n"
        "   A) Chroma with cosine similarity, in-memory\n"
        "   B) Pinecone with HNSW indexing and approximate nearest neighbours\n"
        "   C) SQLite full-text search with BM25\n"
        "   D) Re-embedding all documents per query\n\n"
        "✅ Answer: B) Pinecone with HNSW indexing and approximate nearest neighbours\n"
        "💡 Why: HNSW (Hierarchical Navigable Small Worlds) trades tiny accuracy loss "
        "for orders-of-magnitude speed gains at scale — the standard for production RAG.\n\n"
        "Q12. Context window budget is 8K tokens. Your retrieval returns 12K tokens "
        "of relevant chunks. What is the best strategy?\n\n"
        "   A) Increase max_tokens to 16K\n"
        "   B) Truncate all chunks to 500 tokens each\n"
        "   C) Rerank and compress: keep top-3, summarise others\n"
        "   D) Skip retrieval and rely on model parametric knowledge\n\n"
        "✅ Answer: C) Rerank and compress: keep top-3, summarise others\n"
        "💡 Why: A cross-encoder reranker picks the most relevant chunks, then "
        "compression (LLM summarisation) fits the rest — preserving signal while "
        "respecting the budget.\n\n"
        "Q13. Faithfulness score drops from 0.92 to 0.71 after adding a weather tool "
        "to Agri-Saathi. What is the most likely cause?\n\n"
        "   A) The embedding model changed\n"
        "   B) Tool outputs are injected into context without citation metadata\n"
        "   C) Temperature was increased for the tool-use call\n"
        "   D) The vector store was re-indexed\n\n"
        "✅ Answer: B) Tool outputs are injected into context without citation metadata\n"
        "💡 Why: The LLM now blends RAG-retrieved text with live tool data. Without "
        "clear source labels, it conflates the two — reducing groundedness scores.\n\n"
        "Q14. You need to evaluate whether adding a reranker improves Agri-Saathi "
        "quality. What is the correct experimental design?\n\n"
        "   A) Deploy reranker, observe user satisfaction over 2 weeks\n"
        "   B) Run golden_set.csv through pipeline A (no reranker) and B (reranker), "
        "compare faithfulness + precision@5 on identical queries\n"
        "   C) Ask the LLM to rate its own outputs before and after\n"
        "   D) Check retrieval latency only — quality is subjective\n\n"
        "✅ Answer: B) Run golden_set.csv through pipeline A and B, compare metrics\n"
        "💡 Why: Controlled ablation on a held-out golden set with objective metrics "
        "isolates the reranker's contribution — the only rigorous way to attribute change.\n\n"
        "Q15. A context engineer notices 'lost-in-the-middle' failures: the LLM "
        "ignores chunks placed in positions 3–7 of a 10-chunk context. Best fix?\n\n"
        "   A) Increase chunk size\n"
        "   B) Place the most critical chunks at positions 1 and 10 (primacy + recency)\n"
        "   C) Use a different embedding model\n"
        "   D) Reduce top-k to 3\n\n"
        "✅ Answer: B) Place the most critical chunks at positions 1 and 10\n"
        "💡 Why: LLMs attend most strongly to the start and end of context (U-shaped "
        "attention). Placing high-relevance chunks at these positions exploits this bias.\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "📊  QUIZ COMPLETE\n"
        "  15 questions · Beginner: Q1–5 · Intermediate: Q6–10 · Advanced: Q11–15\n"
        "  Tip: Review the 'lost-in-the-middle' paper and try implementing a reranker "
        "on your Agri-Saathi pipeline.\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    ),
    "practice_arena_interview": (
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🎯  INTERVIEW PREP: RAG Pipelines — AIPM Track\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "💬 CONCEPTUAL  (Q1–5)  |  Phone screen · Entry–Mid level\n"
        "─────────────────────────────────────────────────────\n"
        "Q1. What is Retrieval-Augmented Generation and why does it matter for AI products?\n\n"
        "   🎯 What a strong answer covers:\n"
        "      • Core definition: retrieve relevant docs, inject into LLM context\n"
        "      • Why it matters: solves hallucination + knowledge cutoff problems\n"
        "      • Product angle: enables trustworthy, citable AI responses at scale\n\n"
        "   ✨ Model answer:\n"
        "      RAG is an architecture that grounds LLM responses in retrieved "
        "      documents rather than parametric memory alone. At query time, the "
        "      system embeds the question, retrieves top-k relevant chunks from a "
        "      vector store, and injects them into the prompt before generation. "
        "      For AI PMs, RAG is the go-to pattern when you need factual accuracy, "
        "      source attribution, or fresh data that wasn't in the training set.\n\n"
        "⚙️  TECHNICAL  (Q6–10)  |  Technical round · Mid–Senior level\n"
        "─────────────────────────────────────────────────────\n"
        "Q6. Walk me through how you'd design a RAG pipeline for a customer support bot.\n\n"
        "   🎯 What a strong answer covers:\n"
        "      • Document ingestion, chunking strategy, embedding model choice\n"
        "      • Retrieval design: top-k, threshold, hybrid search consideration\n"
        "      • Context assembly and citation passing to the LLM\n\n"
        "   ✨ Model answer:\n"
        "      I'd start with document ingestion — scraping the KB, cleaning HTML, "
        "      then chunking at ~512 tokens with 10% overlap to preserve sentence "
        "      boundaries. I'd use a bi-encoder like text-embedding-3-small for "
        "      speed, storing in Chroma for prototyping. At query time: embed the "
        "      question, retrieve top-5, rerank with a cross-encoder, then assemble "
        "      context with source metadata so the LLM can cite directly.\n\n"
        "🏗️  SCENARIO / DESIGN  (Q11–15)  |  Design round · Senior–Lead level\n"
        "─────────────────────────────────────────────────────\n"
        "Q11. Agri-Saathi's faithfulness score has dropped from 0.92 to 0.71 after "
        "the last sprint. You have 48 hours before the demo. Walk me through your "
        "debugging and recovery plan.\n\n"
        "   🎯 What a strong answer covers:\n"
        "      • Systematic diagnosis (what changed in the last sprint?)\n"
        "      • Golden set regression to isolate failure category\n"
        "      • Prioritised fix with rollback option\n\n"
        "   ✨ Model answer:\n"
        "      First I'd run our golden_set.csv immediately to identify which failure "
        "      category increased — hallucination, wrong citation, or refusal. Then "
        "      I'd diff the last sprint: was it a prompt change, new tool, or "
        "      re-chunking? With 48 hours I'd prioritise a targeted prompt fix or "
        "      rollback the riskiest change, retest on the golden set, and only ship "
        "      if faithfulness is back above 0.88. I'd document the incident for the "
        "      post-mortem regardless of outcome.\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🏁  INTERVIEW PREP COMPLETE — 15 questions across 3 levels\n"
        "   To practice answering: reply with your answer to any question above.\n"
        "   I'll evaluate it and give you specific coaching feedback.\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    ),
    "idea_generator": (
        "Here are three portfolio-worthy project ideas tailored to your current phase:\n\n"
        "**1. Agri-Saathi Context Dashboard**\n"
        "Build a real-time panel showing exactly what context your RAG system is "
        "injecting per query — chunk scores, token counts, source trust levels. "
        "Skills: context engineering, visualisation, debugging tools.\n\n"
        "**2. Eval Harness CLI**\n"
        "A command-line tool that runs your golden set against any LLM endpoint and "
        "outputs a colour-coded scorecard. Portable, reusable across projects.\n\n"
        "**3. Prompt Version Manager**\n"
        "Git-like versioning for system prompts — diff two versions, replay against "
        "golden set, see which version wins on faithfulness. Strong PM portfolio signal."
    ),
}


def _mock_orchestrator_response(message: str, session: SessionContext) -> tuple[str, str]:
    """Return (response_text, agent_name) without hitting the Claude API."""
    msg_lower = message.lower()
    if any(w in msg_lower for w in ("quiz", "test me", "question", "mcq")):
        return _MOCK_RESPONSES["practice_arena_mcq"], "practice_arena"
    if any(w in msg_lower for w in ("interview", "prep", "mock")):
        return _MOCK_RESPONSES["practice_arena_interview"], "practice_arena"
    if any(w in msg_lower for w in ("idea", "project", "build", "inspire")):
        return _MOCK_RESPONSES["idea_generator"], "idea_generator"
    return _MOCK_RESPONSES["learning_coach"], "learning_coach"


# ── Request / response models ─────────────────────────────────────────────────

# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_client() -> anthropic.Anthropic:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY not configured")
    return anthropic.Anthropic(api_key=api_key)


def _get_session_data(session_id: str, user_id: str = "") -> dict:
    # ── In-memory cache hit ───────────────────────────────────────────────────
    if session_id in _sessions:
        data = _sessions[session_id]
        if not TEST_MODE and user_id:
            owner = data["session"].user_id
            if owner and owner != user_id:
                raise HTTPException(status_code=403, detail="Access denied.")
        return data

    # ── DB restore (cache miss after restart / multi-worker) ─────────────────
    if not TEST_MODE:
        try:
            with get_conn() as conn:
                with conn.cursor() as cur:
                    if user_id:
                        cur.execute(
                            "SELECT session_data FROM sessions "
                            "WHERE session_id = %s AND user_id = %s",
                            (session_id, user_id),
                        )
                        row = cur.fetchone()
                        if row is None:
                            # Distinguish 404 (doesn't exist) from 403 (exists, wrong user)
                            cur.execute(
                                "SELECT user_id FROM sessions WHERE session_id = %s",
                                (session_id,),
                            )
                            exists = cur.fetchone()
                            if exists is None:
                                raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
                            raise HTTPException(status_code=403, detail="Access denied.")
                    else:
                        cur.execute(
                            "SELECT session_data FROM sessions WHERE session_id = %s",
                            (session_id,),
                        )
                        row = cur.fetchone()
                        if row is None:
                            raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")

            session = SessionContext.from_dict(json.loads(row[0]))
            client  = _make_client()
            profile = _load_profile_db(session.user_id) if session.user_id else None
            orch    = Orchestrator(client=client, session=session, profile=profile)
            _sessions[session_id] = {"session": session, "orch": orch, "client": client, "profile": profile}
            return _sessions[session_id]
        except HTTPException:
            raise
        except Exception:
            pass

    raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")


def _track_from_str(track_str: str) -> CareerTrack:
    mapping = {t.value: t for t in CareerTrack}
    if track_str not in mapping:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid track '{track_str}'. Choose from: {list(mapping.keys())}",
        )
    return mapping[track_str]


def _session_progress(session: SessionContext) -> dict:
    phase_id = _WEEK_TO_PHASE.get(session.current_week, "portfolio")
    phase    = get_phase_by_id(phase_id) or {}
    return {
        "track":          str(session.track.value),
        "track_label":    str(TRACK_DISPLAY_NAMES[session.track]),
        "current_week":   int(session.current_week),
        "total_weeks":    int(TOTAL_WEEKS),
        "phase_id":       str(phase_id),
        "phase_title":    str(phase.get("title", "")),
        "phase_desc":     str(phase.get("theme", "")),
        "exchanges":      int(len(session.history)),
        "exercises_done": int(session.exercises_done),
        "tasks_done":     int(session.tasks_done_count()),
        "topics_count":   int(len(session.topics_explored)),
        "quizzes_taken":  int(len(session.quiz_scores)),
        "goals":          list(session.goals),
    }


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/admin/beta-metrics", response_class=HTMLResponse)
async def admin_beta_metrics(
    request: Request,
    _: None = Depends(_debug_access),
):
    """Simple protected internal view for private beta aggregate metrics."""
    from services.beta_metrics_service import build_beta_metrics_payload

    db_available = False
    db_metrics = None
    try:
        from repositories.beta_metrics_repository import collect_beta_metrics

        with get_conn() as conn:
            db_metrics = collect_beta_metrics(conn)
        db_available = True
    except Exception as exc:
        logger.warning("beta metrics unavailable: %s", _safe_debug_error_message(exc))

    metrics = build_beta_metrics_payload(
        db_available=db_available,
        db_metrics=db_metrics,
    )
    return templates.TemplateResponse(
        request=request,
        name="beta_metrics.html",
        context={
            "metrics": metrics,
            "test_mode": bool(TEST_MODE),
        },
    )

# ── Async helper ──────────────────────────────────────────────────────────────

async def _run_blocking(fn, *args, **kwargs):
    """Run a synchronous function in a thread pool to avoid blocking the event loop."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, functools.partial(fn, *args, **kwargs))


# ── Route dependency injection ────────────────────────────────────────────────

import routes.deps as _rdeps  # noqa: E402
_rdeps.templates        = templates
_rdeps.get_session_data = _get_session_data
_rdeps.get_user_history = _get_user_history
_rdeps.get_user_sessions = _get_user_sessions
_rdeps.load_profile_db  = _load_profile_db
_rdeps.save_exchange_to_history = _save_exchange_to_history
_rdeps.save_profile_db = _save_profile_db
_rdeps.save_session     = _save_session
_rdeps.session_progress = _session_progress
_rdeps.make_client      = _make_client
_rdeps.run_blocking     = _run_blocking
_rdeps.track_from_str   = _track_from_str
_rdeps.mock_orchestrator_response = _mock_orchestrator_response
_rdeps.mock_responses   = _MOCK_RESPONSES
_rdeps.limiter          = limiter
_rdeps.CHAT_RATE_LIMIT  = _CHAT_RATE_LIMIT
_rdeps.PRACTICE_RATE_LIMIT = _PRACTICE_RATE_LIMIT
_rdeps.session_cache    = _sessions
_rdeps.TEST_MODE        = TEST_MODE

from routes.public import router as public_router  # noqa: E402
app.include_router(public_router)

from routes.onboarding import router as onboarding_router  # noqa: E402
app.include_router(onboarding_router)

from routes.dashboard import router as dashboard_router  # noqa: E402
app.include_router(dashboard_router)

from routes.auth_routes import router as auth_router  # noqa: E402
app.include_router(auth_router)

from routes.syllabus import router as syllabus_router  # noqa: E402
app.include_router(syllabus_router)

from routes.jobs import router as jobs_router  # noqa: E402
app.include_router(jobs_router)

from routes.chat import router as chat_router  # noqa: E402
app.include_router(chat_router)

from routes.topics import router as topics_router, get_next_topic_step  # noqa: E402,F401
app.include_router(topics_router)

from routes.todos import router as todos_router  # noqa: E402
app.include_router(todos_router)

from routes.submissions import router as submissions_router  # noqa: E402
app.include_router(submissions_router)

from routes.debug import router as debug_router  # noqa: E402
app.include_router(debug_router)
