# AI² Backend Stability Checkpoint Before UI Polish

## 1. Current Backend Status

The following backend work is complete and stable on `main`:

| area | what was done |
|---|---|
| **Route splitting** | All routes extracted from `app.py` into `routes/public.py`, `routes/auth_routes.py`, `routes/dashboard.py`, `routes/onboarding.py`, `routes/syllabus.py`, `routes/jobs.py`, `routes/chat.py`, `routes/topics.py`, `routes/submissions.py`, `routes/todos.py` |
| **Debug/admin splitting** | All `/debug/*` routes extracted to `routes/debug.py`; all `/admin/*` routes extracted to `routes/admin.py`; debug token protection verified |
| **Session persistence extraction** | `get_session_data`, `save_session`, `get_user_history`, `load_profile_db`, `save_profile_db` extracted from `app.py` into `services/session_persistence.py`; `app.py` wrappers delegate cleanly |
| **Session cache eviction** | `_sessions_last_accessed` dict added; TTL (30 min), LRU cap (500 entries), sweep (10 min) implemented; background asyncio task wired to `@app.on_event("startup")` |
| **Exception logging improvement** | Full audit in `docs/ai2-exception-logging-audit.md`; first slice implemented: `services/content_service.py:205` silent `except Exception: pass` replaced with `logger.warning` + `safe_error_metadata` for shared content cache write failures |
| **GitHub Actions** | `.github/workflows/test.yml` runs focused stable pytest suite on every push and pull request using Python 3.11 with safe placeholder env vars |
| **LangSmith observability plan** | Full AI call inventory (15 call sites), safe metadata policy, env var design, and 6-slice implementation plan in `docs/ai2-langsmith-observability-plan.md` |
| **LangSmith env flags** | `LANGSMITH_TRACING`, `LANGSMITH_API_KEY`, `LANGSMITH_PROJECT`, `LANGSMITH_ENDPOINT` documented in `.env.example`; `services/observability_flags.py` provides read-only helpers; tracing off by default |
| **No-op observability wrapper** | `services/llm_observability.py` provides `trace_llm_call` context manager, `build_safe_trace_metadata`, and `sanitize_trace_metadata`; no LangSmith SDK import, no network calls |
| **Observability wired — structured content** | `generate_learning_content_for_topic` and `generate_practice_content_for_topic` in `services/content_service.py` wrapped with `trace_llm_call("structured.generate_lesson/practice")` |
| **Observability wired — structured feedback** | `evaluate_quiz_answers`, `generate_portfolio_feedback`, `generate_interview_feedback` in `services/submission_service.py` wrapped with `trace_llm_call("structured.*_feedback")` |
| **Observability wired — chat/orchestrator** | `Orchestrator.process` call in `routes/chat.py` `POST /chat` wrapped with `trace_llm_call("chat.orchestrator_process")` |

---

## 2. Tests Run

**Command:**
```
python -m pytest \
  tests/test_public_routes_split.py \
  tests/test_auth_routes_split.py \
  tests/test_dashboard_routes_split.py \
  tests/test_onboarding_routes_split.py \
  tests/test_syllabus_routes_split.py \
  tests/test_jobs_routes_split.py \
  tests/test_chat_routes_split.py \
  tests/test_debug_endpoint_protection.py \
  tests/test_admin_beta_metrics_route_split.py \
  tests/test_core_session_persistence_split.py \
  tests/test_session_cache_eviction.py \
  tests/test_llm_observability_noop.py \
  tests/test_content_service_observability_noop.py \
  tests/test_submission_service_observability_noop.py \
  tests/test_chat_observability_noop.py \
  tests/test_topic_content.py \
  tests/test_topic_practice.py \
  tests/test_quiz_submission.py \
  tests/test_portfolio.py \
  tests/test_interview_submission.py
```

**Result: 408 passed, 0 failures, 7 warnings**

The two previously stale assertions in `test_public_routes_split.py` and `test_jobs_routes_split.py` (which checked `@app.get("/debug/storage-status")` was still in `app.py`) have been updated to assert the correct post-debug-split architecture: `routes/debug.py` defines `@router.get("/debug/storage-status")` and `app.py` includes it via `app.include_router(debug_router)`.

---

## 3. What Is Stable Now

- **Route URLs preserved.** All `/chat`, `/session/start`, `/topics/*`, `/submissions/*`, `/quiz/*`, `/portfolio/*`, `/interview/*`, `/debug/*`, `/admin/*`, `/onboarding/*`, `/dashboard`, `/syllabus`, `/jobs`, `/todos`, and public routes remain at their original paths.
- **Debug protection preserved.** `/debug/*` endpoints require `AI2_DEBUG_TOKEN` in production; token check verified by `test_debug_endpoint_protection.py` (23/23).
- **Session ownership preserved.** Session cache keyed by UUID; ownership checks in place; eviction operates on TTL and LRU without touching DB data.
- **TEST_MODE preserved.** `AI2_TEST_MODE=1` bypasses all DB calls, Claude API calls, and LangSmith network calls. All test suites run cleanly in TEST_MODE.
- **No LangSmith SDK or network calls.** `services/llm_observability.py` imports only stdlib (`contextlib`, `typing`) and `services/observability_flags`. No `langsmith` package imported anywhere. Verified by source-level assertions in `test_llm_observability_noop.py`, `test_content_service_observability_noop.py`, `test_submission_service_observability_noop.py`, and `test_chat_observability_noop.py`.
- **Structured AI paths work.** `generate_learning_content_for_topic`, `generate_practice_content_for_topic`, `evaluate_quiz_answers`, `generate_portfolio_feedback`, and `generate_interview_feedback` all return correct shapes and content in TEST_MODE and with mock Claude clients.
- **Chat/orchestrator path works.** `POST /chat` returns `{response, agent_used, progress}` correctly in TEST_MODE; `Orchestrator.process` call is wrapped but behavior is identical when tracing is disabled.
- **Safe metadata enforced.** `sanitize_trace_metadata` blocks API keys, DB URLs, generated content text, learner submissions, notes, chat history, and profile details before any value reaches the observability layer.

---

## 4. Remaining Backend Work Later

The following items are documented and planned but not yet implemented:

- **Real LangSmith SDK integration.** Slices 2–5 from `docs/ai2-langsmith-observability-plan.md` — activating `trace_llm_call` with a real `langsmith.RunTree` when `LANGSMITH_TRACING=true` and `LANGSMITH_API_KEY` is set.
- **More exception logging slices.** Second slice: `routes/dashboard.py:98–99` display_name fetch silent pass → `logger.warning`. Further slices from `docs/ai2-exception-logging-audit.md` §2b.
- **DB modular reads activation.** `AI2_MODULAR_CURRICULUM_READS_ENABLED`, `AI2_PROGRESS_DB_READS_ENABLED`, `AI2_TODOS_DB_READS_ENABLED` flags exist; activation requires migration smoke tests.
- **Production monitoring improvements.** Structured log aggregation, alert thresholds on `logger.error` events, latency SLOs for structured content generation.
- **Stale test cleanup.** Done — the two stale `@app.get("/debug/storage-status")` assertions in `test_public_routes_split.py` and `test_jobs_routes_split.py` were updated to assert the correct post-debug-split architecture. Full regression now 408/408.

---

## 5. Next Product Step

**Step 37 — UI polish using Lovable AI.**

The backend is stable, all route URLs are locked, and TEST_MODE is preserved end-to-end. This is the correct moment to begin UI polish before beta. Lovable AI can safely edit the templated frontend files listed below without risking backend regressions.

---

## 6. Lovable UI Scope

### Allowed — Lovable may edit these files

| file | purpose |
|---|---|
| `templates/topics.html` | Topic listing and weekly view |
| `templates/topic_detail.html` | Individual topic learning, quiz, portfolio, interview tabs |
| `templates/todos.html` | Learner to-do list |
| `templates/syllabus.html` | Course syllabus overview |
| `static/style.css` | All visual styling |

Lovable should treat these as pure HTML/CSS/Jinja2 template changes. Do not alter any `{% url %}` references, form `action` attributes, or `fetch()`/`axios()` endpoint paths — those are hardcoded to live route URLs.

### Not allowed — Lovable must not touch these files

| file / directory | reason |
|---|---|
| `app.py` | FastAPI app instance, startup events, session cache |
| `routes/` | All route handlers — URLs and response shapes are locked |
| `services/` | Business logic, session persistence, observability |
| `repositories/` | DB query layer |
| `database/schema.sql` | PostgreSQL schema — changes require migration |
| `auth.py` | Authentication and cookie logic |
| `config.py` | Model IDs, track definitions, feature constants |
| `orchestrator.py` | Chat routing and synthesis logic |
| `agents/` | Learning Coach, Practice Arena, Idea Generator, Job Search Agent |
| `harness/` | Prompt templates, context builders, guardrails |
| `.env` | Environment secrets — never edit or commit |
| `tests/` | Test files — changes here must be reviewed separately |
