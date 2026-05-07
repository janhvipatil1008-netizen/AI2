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
import sqlite3
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Optional

import anthropic
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from auth import (
    AUTH_COOKIE, hash_password, verify_password,
    create_auth_token, get_current_user_id,
)
from config import CareerTrack, TRACK_DISPLAY_NAMES, TRACK_TAGLINES, TOTAL_WEEKS
from context.session import SessionContext
from context.learner_profile import (
    LearnerProfile, load_profile, save_profile,
)
from curriculum.syllabus import (
    format_week_context, _WEEK_TO_PHASE, get_phase_by_id,
    PHASES, get_task_key, ROLE_TRACKS, WEEKS,
    get_progress as syllabus_get_progress,
)
from orchestrator import Orchestrator
import agents.practice_arena as practice_arena

load_dotenv()

# ── Config ────────────────────────────────────────────────────────────────────

TEST_MODE       = os.getenv("AI2_TEST_MODE") == "1"
SESSION_DB_PATH = os.getenv("AI2_SESSION_DB", "sessions.db")

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

# Thread lock for SQLite writes
_db_lock = threading.Lock()


# ── Session persistence (SQLite) ──────────────────────────────────────────────

def _init_db() -> None:
    if TEST_MODE:
        return
    with _db_lock:
        with sqlite3.connect(SESSION_DB_PATH) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id       TEXT PRIMARY KEY,
                    email         TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    display_name  TEXT,
                    created_at    TEXT NOT NULL,
                    updated_at    TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id   TEXT PRIMARY KEY,
                    session_data TEXT NOT NULL,
                    created_at   TEXT NOT NULL,
                    updated_at   TEXT NOT NULL,
                    user_id      TEXT REFERENCES users(user_id)
                )
            """)
            # Add user_id column to existing sessions table if upgrading
            try:
                conn.execute("ALTER TABLE sessions ADD COLUMN user_id TEXT REFERENCES users(user_id)")
            except sqlite3.OperationalError:
                pass  # column already exists
            conn.execute("""
                CREATE TABLE IF NOT EXISTS conversation_history (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id         TEXT NOT NULL REFERENCES users(user_id),
                    session_id      TEXT NOT NULL,
                    user_message    TEXT NOT NULL,
                    assistant_reply TEXT NOT NULL,
                    agent_used      TEXT NOT NULL,
                    timestamp       TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS learner_profiles (
                    user_id      TEXT PRIMARY KEY REFERENCES users(user_id),
                    profile_data TEXT NOT NULL,
                    updated_at   TEXT NOT NULL
                )
            """)
            conn.commit()


def _save_session(session_id: str, session: SessionContext) -> None:
    """Write-through: persist session to SQLite after every mutation."""
    if TEST_MODE:
        return
    data = json.dumps(session.to_dict())
    now  = datetime.now().isoformat()
    with _db_lock:
        with sqlite3.connect(SESSION_DB_PATH) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute(
                "INSERT OR REPLACE INTO sessions "
                "(session_id, session_data, created_at, updated_at, user_id) "
                "VALUES (?, ?, ?, ?, ?)",
                (session_id, data, session.start_time, now, session.user_id or None),
            )
            conn.commit()


def _save_exchange_to_history(
    user_id: str, session_id: str,
    user_message: str, assistant_reply: str, agent_used: str,
) -> None:
    """Append a single exchange to the permanent conversation_history table."""
    if TEST_MODE or not user_id:
        return
    now = datetime.now().isoformat()
    with _db_lock:
        with sqlite3.connect(SESSION_DB_PATH) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute(
                "INSERT INTO conversation_history "
                "(user_id, session_id, user_message, assistant_reply, agent_used, timestamp) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (user_id, session_id, user_message, assistant_reply, agent_used, now),
            )
            conn.commit()


def _save_profile_db(profile: LearnerProfile) -> None:
    """Persist a LearnerProfile to SQLite."""
    if TEST_MODE:
        return
    with _db_lock:
        with sqlite3.connect(SESSION_DB_PATH) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            save_profile(profile, conn)


def _load_profile_db(user_id: str) -> Optional[LearnerProfile]:
    if TEST_MODE or not user_id:
        return None
    try:
        with sqlite3.connect(SESSION_DB_PATH) as conn:
            return load_profile(user_id, conn)
    except Exception:
        return None


def _load_session_from_db(session_id: str) -> Optional[SessionContext]:
    """Load a session from SQLite (used on cache miss — e.g. after restart)."""
    try:
        with sqlite3.connect(SESSION_DB_PATH) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            row = conn.execute(
                "SELECT session_data FROM sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
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
        with sqlite3.connect(SESSION_DB_PATH) as conn:
            rows = conn.execute(
                "SELECT session_id, session_data, updated_at FROM sessions "
                "WHERE user_id = ? ORDER BY updated_at DESC LIMIT ?",
                (user_id, limit),
            ).fetchall()
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
        with sqlite3.connect(SESSION_DB_PATH) as conn:
            rows = conn.execute(
                "SELECT session_id, user_message, assistant_reply, agent_used, timestamp "
                "FROM conversation_history WHERE user_id = ? ORDER BY timestamp DESC LIMIT ?",
                (user_id, limit),
            ).fetchall()
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


# Initialise the DB at module load time (no-op in TEST_MODE)
_init_db()

# Initialise jobs.db (always — no TEST_MODE guard, jobs.db is read-only safe)
try:
    from jobs.database import (
        init_db as _init_jobs_db,
        get_jobs as _get_jobs,
        get_job_with_enrichment as _get_job_detail,
        get_stats as _get_jobs_stats,
    )
    _init_jobs_db()
except Exception as _jobs_db_err:
    import logging as _log
    _log.getLogger(__name__).warning(f"jobs.db init skipped: {_jobs_db_err}")


# ── Authentication middleware ─────────────────────────────────────────────────

_PUBLIC_PATHS = {"/login", "/signup", "/health"}


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

class TaskToggleRequest(BaseModel):
    session_id: str
    task_key:   str
    status:     str = "done"   # "done" | "in_progress" | "todo"


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
            with sqlite3.connect(SESSION_DB_PATH) as conn:
                conn.execute("PRAGMA journal_mode=WAL")
                if user_id:
                    # Fetch only if session belongs to this user
                    row = conn.execute(
                        "SELECT session_data FROM sessions WHERE session_id = ? AND user_id = ?",
                        (session_id, user_id),
                    ).fetchone()
                    if row is None:
                        # Distinguish 404 (doesn't exist) from 403 (exists, wrong user)
                        exists = conn.execute(
                            "SELECT user_id FROM sessions WHERE session_id = ?",
                            (session_id,),
                        ).fetchone()
                        if exists is None:
                            raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
                        raise HTTPException(status_code=403, detail="Access denied.")
                else:
                    row = conn.execute(
                        "SELECT session_data FROM sessions WHERE session_id = ?",
                        (session_id,),
                    ).fetchone()
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

@app.get("/health")
async def health():
    return {"status": "ok", "test_mode": TEST_MODE}


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    if request.state.user_id:
        return RedirectResponse(url="/dashboard", status_code=302)
    return templates.TemplateResponse(
        request=request, name="login.html", context={"error": ""},
    )


@app.post("/login")
async def login_submit(request: Request):
    form     = await request.form()
    email    = str(form.get("email", "")).strip().lower()
    password = str(form.get("password", ""))

    if not TEST_MODE:
        try:
            with sqlite3.connect(SESSION_DB_PATH) as conn:
                row = conn.execute(
                    "SELECT user_id, password_hash FROM users WHERE email = ?", (email,)
                ).fetchone()
        except Exception:
            row = None

        if not row or not verify_password(password, row[1]):
            return templates.TemplateResponse(
                request=request, name="login.html",
                context={"error": "Incorrect email or password — please try again."},
                status_code=401,
            )
        user_id = row[0]
    else:
        user_id = "test-user"

    token = create_auth_token(user_id)
    resp  = RedirectResponse(url="/dashboard", status_code=302)
    resp.set_cookie(AUTH_COOKIE, token, httponly=True, samesite="lax", max_age=30 * 24 * 3600)
    return resp


@app.get("/signup", response_class=HTMLResponse)
async def signup_page(request: Request):
    if request.state.user_id:
        return RedirectResponse(url="/dashboard", status_code=302)
    return templates.TemplateResponse(
        request=request, name="signup.html", context={"error": ""},
    )


@app.post("/signup")
async def signup_submit(request: Request):
    form         = await request.form()
    email        = str(form.get("email", "")).strip().lower()
    display_name = str(form.get("display_name", "")).strip()
    password     = str(form.get("password", ""))
    confirm      = str(form.get("confirm_password", ""))

    if not email or not password:
        return templates.TemplateResponse(
            request=request, name="signup.html",
            context={"error": "Email and password are required."},
            status_code=422,
        )
    if password != confirm:
        return templates.TemplateResponse(
            request=request, name="signup.html",
            context={"error": "Passwords do not match."},
            status_code=422,
        )
    if len(password) < 8:
        return templates.TemplateResponse(
            request=request, name="signup.html",
            context={"error": "Password must be at least 8 characters."},
            status_code=422,
        )

    user_id      = str(uuid.uuid4())
    password_hash = hash_password(password)
    now          = datetime.now().isoformat()

    try:
        with _db_lock:
            with sqlite3.connect(SESSION_DB_PATH) as conn:
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute(
                    "INSERT INTO users (user_id, email, password_hash, display_name, created_at, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (user_id, email, password_hash, display_name or email.split("@")[0], now, now),
                )
                conn.commit()
    except sqlite3.IntegrityError:
        return templates.TemplateResponse(
            request=request, name="signup.html",
            context={"error": "An account with that email already exists."},
            status_code=409,
        )

    token = create_auth_token(user_id)
    resp  = RedirectResponse(url="/dashboard", status_code=302)
    resp.set_cookie(AUTH_COOKIE, token, httponly=True, samesite="lax", max_age=30 * 24 * 3600)
    return resp


@app.get("/logout")
async def logout():
    resp = RedirectResponse(url="/login", status_code=302)
    resp.delete_cookie(AUTH_COOKIE)
    return resp


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    user_id = request.state.user_id or "test-user"

    display_name = "Learner"
    if not TEST_MODE:
        try:
            with sqlite3.connect(SESSION_DB_PATH) as conn:
                row = conn.execute(
                    "SELECT display_name FROM users WHERE user_id = ?", (user_id,)
                ).fetchone()
            if row:
                display_name = row[0] or display_name
        except Exception:
            pass

    recent_sessions = _get_user_sessions(user_id, limit=5)
    profile         = _load_profile_db(user_id)

    tracks = [
        {
            "value":   str(t.value),
            "label":   str(TRACK_DISPLAY_NAMES[t]),
            "tagline": str(TRACK_TAGLINES[t]),
        }
        for t in CareerTrack
    ]

    stats = {
        "session_count":   profile.session_count   if profile else 0,
        "total_quizzes":   profile.total_quizzes    if profile else 0,
        "topics_mastered": len(profile.topics_mastered) if profile else 0,
        "total_exchanges": profile.total_exchanges  if profile else 0,
    }

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "display_name":    display_name,
            "recent_sessions": recent_sessions,
            "tracks":          tracks,
            "stats":           stats,
            "test_mode":       bool(TEST_MODE),
        },
    )


@app.get("/history", response_class=HTMLResponse)
async def history_page(request: Request):
    user_id = request.state.user_id or "test-user"
    entries = _get_user_history(user_id, limit=200)
    return templates.TemplateResponse(
        request=request,
        name="history.html",
        context={
            "entries":   entries,
            "test_mode": bool(TEST_MODE),
        },
    )


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    if TEST_MODE or request.state.user_id:
        return RedirectResponse(url="/dashboard", status_code=302)
    return RedirectResponse(url="/login", status_code=302)


@app.post("/session/start")
@limiter.limit(_CHAT_RATE_LIMIT)
async def start_session(request: Request, body: StartSessionRequest):
    user_id = getattr(request.state, "user_id", None) or ""
    track   = _track_from_str(body.track)
    session = SessionContext(track=track, user_id=user_id, current_week=max(1, min(body.week, TOTAL_WEEKS)))
    client  = None if TEST_MODE else _make_client()

    # Load or create learner profile
    profile = _load_profile_db(user_id) if user_id else None
    if profile is None and user_id:
        profile = LearnerProfile.new_for_user(user_id, track)

    orch = None if TEST_MODE else Orchestrator(client=client, session=session, profile=profile)

    session_id = str(uuid.uuid4())
    _sessions[session_id] = {"session": session, "orch": orch, "client": client, "profile": profile}
    _save_session(session_id, session)

    return {
        "session_id": session_id,
        "progress":   _session_progress(session),
    }


@app.post("/chat")
@limiter.limit(_CHAT_RATE_LIMIT)
async def chat(request: Request, body: ChatRequest):
    data    = _get_session_data(body.session_id, request.state.user_id or "")
    session: SessionContext = data["session"]

    if not body.message.strip():
        raise HTTPException(status_code=422, detail="Message cannot be empty")

    # ── Interactive quiz intercept ─────────────────────────────────────────────
    # If the learner is mid-quiz and types A/B/C/D, handle it directly without
    # going to the orchestrator. This makes quiz answers instant (no API call).
    if session.quiz_state and session.quiz_state.get("questions"):
        cleaned = body.message.strip().rstrip(".!?,").upper()
        if cleaned in ("A", "B", "C", "D"):
            response_text = practice_arena.handle_quiz_answer(session, cleaned)
            agent_used    = "practice_arena"
            session.add_exchange(body.message, response_text[:500], agent_used)
            _save_session(body.session_id, session)
            return {
                "response":   response_text,
                "agent_used": agent_used,
                "progress":   _session_progress(session),
            }

    if TEST_MODE:
        response_text, agent_used = _mock_orchestrator_response(body.message, session)
        session.add_exchange(body.message, response_text[:500], agent_used)
        session.note_topic(body.message[:60])
    else:
        orch: Orchestrator = data["orch"]
        try:
            response_text = await _run_blocking(orch.process, body.message)
            agent_used = session.history[-1].agent_used if session.history else "orchestrator"
        except anthropic.APIError as exc:
            raise HTTPException(status_code=502, detail=f"Claude API error: {exc}") from exc

    _save_session(body.session_id, session)

    # Persist this exchange to the permanent history table
    _save_exchange_to_history(
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
        _save_profile_db(profile)

    return {
        "response":   response_text,
        "agent_used": agent_used,
        "progress":   _session_progress(session),
    }


@app.get("/progress/{session_id}")
async def get_progress(request: Request, session_id: str):
    data    = _get_session_data(session_id, request.state.user_id or "")
    session = data["session"]
    return _session_progress(session)


@app.post("/quiz")
@limiter.limit(_PRACTICE_RATE_LIMIT)
async def quiz(request: Request, body: QuizRequest):
    data    = _get_session_data(body.session_id, request.state.user_id or "")
    session = data["session"]

    if TEST_MODE:
        response_text = _MOCK_RESPONSES["practice_arena_mcq"]
        session.note_topic(body.topic)
        session.mark_exercise_done()
    else:
        client = data["client"]
        response_text = await _run_blocking(
            practice_arena.generate_mcq_quiz,
            client, body.topic, session, body.difficulty,
        )

    _save_session(body.session_id, session)
    return {"response": response_text, "progress": _session_progress(session)}


@app.post("/interview")
@limiter.limit(_PRACTICE_RATE_LIMIT)
async def interview(request: Request, body: InterviewRequest):
    data    = _get_session_data(body.session_id, request.state.user_id or "")
    session = data["session"]

    if TEST_MODE:
        response_text = _MOCK_RESPONSES["practice_arena_interview"]
        session.note_topic(body.topic)
        session.mark_exercise_done()
    else:
        client = data["client"]
        response_text = await _run_blocking(
            practice_arena.generate_interview_questions,
            client, body.topic, session, body.difficulty,
        )

    _save_session(body.session_id, session)
    return {"response": response_text, "progress": _session_progress(session)}


@app.post("/evaluate")
@limiter.limit(_PRACTICE_RATE_LIMIT)
async def evaluate(request: Request, body: EvaluateRequest):
    data    = _get_session_data(body.session_id, request.state.user_id or "")
    session = data["session"]

    if TEST_MODE:
        response_text = (
            "📋  ANSWER EVALUATION\n"
            "─────────────────────────────────────────────────────\n"
            f"Question: {body.question}\n\n"
            f"Your answer: {body.answer}\n\n"
            "─────────────────────────────────────────────────────\n"
            "SCORECARD\n"
            "  Clarity    : 8/10 — Well-structured and easy to follow\n"
            "  Accuracy   : 7/10 — Core concepts correct; minor gaps\n"
            "  Depth      : 6/10 — Good surface coverage; could go deeper on tradeoffs\n"
            "  Relevance  : 9/10 — Directly addresses the question\n"
            "  ─────────────────────────\n"
            "  TOTAL      : 30/40  (75%)  ⭐⭐⭐\n\n"
            "✅  WHAT YOU GOT RIGHT\n"
            "  • Correctly identified the core mechanism\n"
            "  • Good use of concrete example\n\n"
            "🔧  WHERE TO IMPROVE\n"
            "  • Add tradeoff discussion (latency vs accuracy)\n"
            "  • Mention a specific tool or metric\n\n"
            "✨  MODEL ANSWER\n"
            "  [A stronger version would be here in production mode]\n\n"
            "💡  ONE DRILL\n"
            "  Practice the STAR format: Situation → Task → Action → Result"
        )
    else:
        client = data["client"]
        response_text = await _run_blocking(
            practice_arena.evaluate_answer,
            client, body.question, body.answer, session, body.topic,
        )

    return {"response": response_text, "progress": _session_progress(session)}


@app.get("/syllabus/{session_id}", response_class=HTMLResponse)
async def syllabus_page(request: Request, session_id: str):
    data    = _get_session_data(session_id, request.state.user_id or "")
    session = data["session"]
    role    = session.track.value

    phases_data = []
    for week in WEEKS:
        wn        = week["num"]
        all_tasks = []
        role_done = role_total = 0
        for day in week["days"]:
            for ti, task_text in enumerate(day["all_tracks"]):
                key    = get_task_key(wn, day["day_idx"], "all", ti)
                status = session.syllabus_progress.get(key, "todo")
                all_tasks.append({
                    "key":        key,
                    "text":       task_text,
                    "track_name": "All Tracks",
                    "status":     status,
                    "roles":      list(ROLE_TRACKS.keys()),
                    "is_my_role": True,
                })
                role_total += 1
                if status == "done":
                    role_done += 1
            role_tasks = day["tracks"].get(role, [])
            task_list  = role_tasks if isinstance(role_tasks, list) else [role_tasks]
            for ti, task_text in enumerate(task_list):
                if not task_text:
                    continue
                key    = get_task_key(wn, day["day_idx"], role, ti)
                status = session.syllabus_progress.get(key, "todo")
                all_tasks.append({
                    "key":        key,
                    "text":       task_text,
                    "track_name": ROLE_TRACKS[role]["label"],
                    "status":     status,
                    "roles":      [role],
                    "is_my_role": True,
                })
                role_total += 1
                if status == "done":
                    role_done += 1
        if all_tasks:
            phases_data.append({
                "id":          f"week-{wn}",
                "icon":        "📅",
                "phase":       f"Week {wn}",
                "weeks":       week["week_hours"],
                "title":       week["title"],
                "description": week["theme"],
                "tasks":       all_tasks,
                "done":        role_done,
                "total":       role_total,
                "pct":         round(role_done / role_total * 100) if role_total > 0 else 0,
            })

    overall = syllabus_get_progress(session.syllabus_progress, [role])

    return templates.TemplateResponse(
        request=request,
        name="syllabus.html",
        context={
            "session_id":  session_id,
            "progress":    _session_progress(session),
            "phases":      phases_data,
            "overall":     overall,
            "test_mode":   bool(TEST_MODE),
            "user_role":   role,
            "role_tracks": ROLE_TRACKS,
        },
    )


@app.post("/task/toggle")
async def task_toggle(request: Request, body: TaskToggleRequest):
    valid_statuses = {"done", "in_progress", "todo"}
    if body.status not in valid_statuses:
        raise HTTPException(status_code=422, detail=f"status must be one of {valid_statuses}")

    data    = _get_session_data(body.session_id, request.state.user_id or "")
    session = data["session"]
    session.mark_task(body.task_key, body.status)
    _save_session(body.session_id, session)

    role    = session.track.value
    overall = syllabus_get_progress(session.syllabus_progress, [role])
    return {
        "task_key": body.task_key,
        "status":   body.status,
        "overall":  overall,
        "tasks_done": session.tasks_done_count(),
    }


@app.get("/chat/{session_id}", response_class=HTMLResponse)
async def chat_page(request: Request, session_id: str):
    data    = _get_session_data(session_id, request.state.user_id or "")
    session = data["session"]
    return templates.TemplateResponse(
        request=request,
        name="chat.html",
        context={
            "session_id": session_id,
            "progress":   _session_progress(session),
            "test_mode":  bool(TEST_MODE),
        },
    )


# ── Job Search routes ─────────────────────────────────────────────────────────

@app.get("/jobs", response_class=HTMLResponse)
async def jobs_page(request: Request):
    """Job list page — shows all fetched jobs with match scores."""
    user_id = request.state.user_id or "test-user"
    try:
        jobs = _get_jobs(limit=50)
    except Exception:
        jobs = []
    try:
        stats = _get_jobs_stats()
    except Exception:
        stats = {"total": 0, "enriched": 0, "pending": 0, "last_fetch": None}
    return templates.TemplateResponse(
        request=request,
        name="jobs.html",
        context={
            "jobs":      jobs,
            "stats":     stats,
            "test_mode": bool(TEST_MODE),
        },
    )


@app.get("/jobs/{job_id}", response_class=HTMLResponse)
async def job_detail_page(request: Request, job_id: str):
    """Job detail page — shows enriched JD analysis or triggers enrichment."""
    try:
        job = _get_job_detail(job_id)
    except Exception:
        job = None
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return templates.TemplateResponse(
        request=request,
        name="job_detail.html",
        context={
            "job":       job,
            "test_mode": bool(TEST_MODE),
        },
    )


@app.get("/api/jobs/health")
async def jobs_health():
    """Returns job DB stats — no auth required."""
    try:
        return {"status": "ok", **_get_jobs_stats()}
    except Exception as exc:
        return {"status": "error", "detail": str(exc)}


@app.post("/api/jobs/enrich/{job_id}")
async def enrich_job_endpoint(job_id: str, request: Request):
    """Trigger on-demand enrichment for a single job. Returns enrichment data."""
    # Resolve session for personalised context (optional)
    session_id = request.query_params.get("session_id")
    session = None
    if session_id and not TEST_MODE:
        try:
            session = _get_session_data(session_id)["session"]
        except Exception:
            pass

    from jobs.enricher import enrich_job
    try:
        data = await _run_blocking(enrich_job, job_id, session)
        return {"status": "ok", "job_id": job_id, "match_score": data.get("match_score"), "data": data}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/jobs/refresh")
async def refresh_jobs(category: str = "all"):
    """Trigger a job fetch run in the background. Returns immediately."""
    from jobs.fetcher import fetch_and_store

    async def _bg():
        try:
            result = await _run_blocking(fetch_and_store, category)
            logger.info(f"Background job fetch: {result}")
        except Exception as exc:
            logger.error(f"Background job fetch failed: {exc}")

    asyncio.create_task(_bg())
    return {"status": "queued", "message": f"Fetching '{category}' jobs in background"}


# ── Async helper ──────────────────────────────────────────────────────────────

async def _run_blocking(fn, *args, **kwargs):
    """Run a synchronous function in a thread pool to avoid blocking the event loop."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, functools.partial(fn, *args, **kwargs))
