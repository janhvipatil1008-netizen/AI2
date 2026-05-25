# AI² app.py Refactor Audit

**Date:** 2026-05-25
**File audited:** `app.py` — 2,800 lines
**Purpose:** Document all sections and functions in app.py and produce a safe, incremental split plan.

---

## 1. Current app.py Responsibilities

`app.py` currently does all of the following in a single file:

1. **App construction** — `FastAPI()` instance, `StaticFiles` mount, `Jinja2Templates`, rate limiter setup
2. **In-memory session cache** — `_sessions` dict, `_executor` thread pool
3. **Session persistence** — 8 functions: save/load session to PostgreSQL, save/load user profiles, load conversation history, load user sessions list, build dashboard learning summary
4. **Startup hook** — `_startup_db()` runs DB connectivity check on startup
5. **Authentication middleware** — `auth_middleware` HTTP middleware with `_PUBLIC_PATHS` allowlist
6. **TEST_MODE mock responses** — large `_MOCK_RESPONSES` dict + `_mock_orchestrator_response()` (~250 lines)
7. **Request/response Pydantic models** — `StartSessionRequest`, `ChatRequest`, `QuizRequest`, `InterviewRequest`, `EvaluateRequest`, `TaskToggleRequest`
8. **Helper functions** — `_make_client()`, `_get_session_data()` (with ownership check), `_track_from_str()`, `_session_progress()`
9. **Health route** — `GET /health`
10. **Debug routes** — 10 debug GET endpoints + 7 private debug helper functions + `_debug_access` dependency
11. **Admin route** — `GET /admin/beta-metrics`
12. **Auth routes** — `GET/POST /login`, `GET/POST /signup`, `GET /logout`
13. **Public static routes** — `GET /privacy`, `GET /terms`, `GET /` (index)
14. **Dashboard route + helpers** — `GET /dashboard` + 6 private dashboard helper functions
15. **Onboarding routes** — `GET/POST /onboarding/{session_id}`, `POST /onboarding/save`
16. **History route** — `GET /history`
17. **Chat routes** — `POST /session/start`, `POST /chat`, `GET /chat/{session_id}`, `GET /progress/{session_id}`
18. **Syllabus route** — `GET /syllabus/{session_id}`
19. **Task toggle route** — `POST /task/toggle`
20. **Legacy practice routes** — `POST /quiz`, `POST /interview`, `POST /evaluate`
21. **Jobs routes** — `GET /jobs`, `GET /jobs/{job_id}`, `GET /api/jobs/health`, `POST /api/jobs/enrich/{job_id}`, `POST /api/jobs/refresh`
22. **Async helper** — `_run_blocking()` wraps sync functions in thread pool
23. **Route dependency injection** — wires `routes/deps.py` shared state at the bottom before including routers
24. **Router inclusion** — `app.include_router` for topics, todos, submissions

---

## 2. Functions and Routes Found

### Session Persistence (lines 101–291)

| Name | Current location | Responsibility | Recommended destination | Risk |
|---|---|---|---|---|
| `_save_session` | app.py:104 | Write SessionContext to PostgreSQL | `services/session_persistence.py` | Medium |
| `_save_exchange_to_history` | app.py:126 | Write conversation exchange to DB | `services/session_persistence.py` | Medium |
| `_save_profile_db` | app.py:147 | Write LearnerProfile to DB | `services/session_persistence.py` | Medium |
| `_load_profile_db` | app.py:158 | Read LearnerProfile from DB | `services/session_persistence.py` | Medium |
| `_load_session_from_db` | app.py:168 | Read SessionContext from DB | `services/session_persistence.py` | Medium |
| `_get_user_sessions` | app.py:185 | List user's session records | `services/session_persistence.py` | Medium |
| `_get_user_history` | app.py:215 | Load conversation history for user | `services/session_persistence.py` | Medium |
| `build_dashboard_learning_summary` | app.py:242 | Build learning summary dict for dashboard | `services/session_persistence.py` or dashboard service | Medium |
| `_startup_db` | app.py:292 | DB ping on startup | `app.py` (keep for now) | Low |

### Authentication (lines 329–356)

| Name | Current location | Responsibility | Recommended destination | Risk |
|---|---|---|---|---|
| `_PUBLIC_PATHS` | app.py:331 | Allowlist of unauthenticated routes | `app.py` middleware block | **High** |
| `auth_middleware` | app.py:334 | HTTP middleware — cookie decode, 302/401 | `app.py` (keep) or `middleware/auth.py` | **High** |

### Mock/Test block (lines 359–598)

| Name | Current location | Responsibility | Recommended destination | Risk |
|---|---|---|---|---|
| `_MOCK_RESPONSES` | app.py:361 | Dict of static test responses | `tests/fixtures.py` or `app.py` (keep) | Low |
| `_mock_orchestrator_response` | app.py:587 | Return mock response in TEST_MODE | Same as above | Low |

### Pydantic models (lines 599–629)

| Name | Current location | Responsibility | Recommended destination | Risk |
|---|---|---|---|---|
| `StartSessionRequest` | app.py:~600 | Request body model | `models/requests.py` | Low |
| `ChatRequest` | app.py:~606 | Request body model | `models/requests.py` | Low |
| `QuizRequest` | app.py:~612 | Request body model | `models/requests.py` | Low |
| `InterviewRequest` | app.py:~616 | Request body model | `models/requests.py` | Low |
| `EvaluateRequest` | app.py:~620 | Request body model | `models/requests.py` | Low |
| `TaskToggleRequest` | app.py:~626 | Request body model | `models/requests.py` | Low |

### Helpers (lines 630–723)

| Name | Current location | Responsibility | Recommended destination | Risk |
|---|---|---|---|---|
| `_make_client` | app.py:632 | Create `anthropic.Anthropic` client | `app.py` or `core/anthropic_client.py` | Low |
| `_get_session_data` | app.py:639 | Cache hit + DB restore + ownership check | `services/session_persistence.py` | **High** |
| `_track_from_str` | app.py:694 | Parse track string to CareerTrack enum | `app.py` or `config.py` | Low |
| `_session_progress` | app.py:704 | Build progress dict for templates | `services/session_persistence.py` or keep | Medium |
| `_run_blocking` | app.py:2776 | Run sync fn in thread pool | `app.py` (keep) | Low |

### Routes — Public / Static (lines 726–2039)

| Route | Method | Current location | Responsibility | Recommended destination | Risk |
|---|---|---|---|---|---|
| `/health` | GET | app.py:726 | Health check JSON | `routes/public.py` | **Low** |
| `/privacy` | GET | app.py:2021 | Static page | `routes/public.py` | **Low** |
| `/terms` | GET | app.py:2030 | Static page | `routes/public.py` | **Low** |
| `/` | GET | app.py:2382 | Index/landing page | `routes/public.py` | **Low** |

### Routes — Auth (lines 1911–2020)

| Route | Method | Current location | Responsibility | Recommended destination | Risk |
|---|---|---|---|---|---|
| `/login` | GET | app.py:1911 | Login form | `routes/auth.py` | Medium |
| `/login` | POST | app.py:1920 | Authenticate, set cookie | `routes/auth.py` | Medium |
| `/signup` | GET | app.py:1953 | Signup form | `routes/auth.py` | Medium |
| `/signup` | POST | app.py:1962 | Create user, set cookie | `routes/auth.py` | Medium |
| `/logout` | GET | app.py:2014 | Clear cookie, redirect | `routes/auth.py` | Medium |

### Routes — Dashboard and Onboarding (lines 2039–2367)

| Route / Helper | Method | Current location | Responsibility | Recommended destination | Risk |
|---|---|---|---|---|---|
| `/dashboard` | GET | app.py:2039 | Dashboard HTML | `routes/dashboard.py` | Medium |
| `_onboarding_template_context` | helper | app.py:2145 | Build onboarding template dict | `routes/dashboard.py` | Medium |
| `_dashboard_enrollment_summary` | helper | app.py:2175 | Enrollment summary for dashboard | `routes/dashboard.py` | Medium |
| `_disabled_dashboard_enrollment_summary` | helper | app.py:2222 | Fallback summary | `routes/dashboard.py` | Medium |
| `_disabled_dashboard_modular_progress_summary` | helper | app.py:2237 | Fallback progress | `routes/dashboard.py` | Medium |
| `_dashboard_db_summaries` | helper | app.py:2248 | DB summary fetching | `routes/dashboard.py` | Medium |
| `_ensure_onboarding_course_enrollment` | helper | app.py:2290 | Enroll if missing | `routes/dashboard.py` or `services/` | Medium |
| `/onboarding/{session_id}` | GET | app.py:2316 | Onboarding form | `routes/onboarding.py` | Medium |
| `/onboarding/save` | POST | app.py:2330 | Save onboarding answers | `routes/onboarding.py` | Medium |
| `/history` | GET | app.py:2368 | History page | `routes/dashboard.py` | Low |

### Routes — Chat and Session (lines 2382–2566)

| Route | Method | Current location | Responsibility | Recommended destination | Risk |
|---|---|---|---|---|---|
| `/session/start` | POST | app.py:2389 | Create new session, redirect to chat | `routes/chat.py` | Medium |
| `/chat` | POST | app.py:2414 | AI chat message handler | `routes/chat.py` | Medium |
| `/progress/{session_id}` | GET | app.py:2477 | Session progress JSON | `routes/chat.py` | Low |
| `/quiz` | POST | app.py:2484 | Legacy quiz endpoint | `routes/chat.py` | Medium |
| `/interview` | POST | app.py:2505 | Legacy interview endpoint | `routes/chat.py` | Medium |
| `/evaluate` | POST | app.py:2526 | Legacy evaluate endpoint | `routes/chat.py` | Medium |
| `/chat/{session_id}` | GET | app.py:2663 | Chat HTML page | `routes/chat.py` | Medium |

### Routes — Syllabus and Task (lines 2567–2677)

| Route | Method | Current location | Responsibility | Recommended destination | Risk |
|---|---|---|---|---|---|
| `/syllabus/{session_id}` | GET | app.py:2567 | Syllabus tracker HTML | `routes/syllabus.py` | Medium |
| `/task/toggle` | POST | app.py:2642 | Toggle task completion | `routes/syllabus.py` | Medium |

### Routes — Debug (lines 731–1910)

| Route | Method | Current location | Responsibility | Recommended destination | Risk |
|---|---|---|---|---|---|
| `_debug_access` | Depends | app.py:731 | Token guard for debug routes | `routes/debug.py` | Medium |
| `/debug/storage-status` | GET | app.py:737 | Storage status JSON | `routes/debug.py` | Medium |
| `/debug/storage-health` | GET | app.py:788 | Storage health JSON | `routes/debug.py` | Medium |
| `/debug/storage-health-view` | GET | app.py:804 | Storage health HTML | `routes/debug.py` | Medium |
| `/debug/curriculum-db-check` | GET | app.py:1042 | Curriculum DB check | `routes/debug.py` | Medium |
| `/debug/curriculum-fallback-check` | GET | app.py:1127 | Curriculum fallback check | `routes/debug.py` | Medium |
| `/debug/learner-state-db-check` | GET | app.py:1218 | Learner state DB check | `routes/debug.py` | Medium |
| `/debug/generated-learning-db-check` | GET | app.py:1398 | Generated learning DB check | `routes/debug.py` | Medium |
| `/debug/usage-events-db-check` | GET | app.py:1447 | Usage events DB check | `routes/debug.py` | Medium |
| `/debug/usage-events-mismatch-check` | GET | app.py:1507 | Usage events mismatch | `routes/debug.py` | Medium |
| `/debug/generated-learning-mismatch-check` | GET | app.py:1570 | Generated learning mismatch | `routes/debug.py` | Medium |
| `/debug/learner-state-mismatch-check` | GET | app.py:1640 | Learner state mismatch | `routes/debug.py` | Medium |
| `/debug/learner-state-fallback-check` | GET | app.py:1745 | Learner state fallback | `routes/debug.py` | Medium |
| `/debug/modular-curriculum` | GET | app.py:1834 | Modular curriculum check | `routes/debug.py` | Medium |
| `_build_storage_health_payload` | helper | app.py:858 | Build health payload dict | `routes/debug.py` or `services/debug_response_utils.py` | Low |
| `_storage_health_*` (4 helpers) | helpers | app.py:989–1041 | Health payload sub-builders | `services/debug_response_utils.py` | Low |
| `_empty_generated_learning_state_found` | helper | app.py:1322 | Safe fallback dict | `services/debug_response_utils.py` | Low |
| `_generated_learning_state_found` | helper | app.py:1337 | State found dict | `services/debug_response_utils.py` | Low |
| `_safe_debug_error_message` | helper | app.py:1356 | Sanitize error for debug | `services/debug_response_utils.py` | Low |
| `_safe_debug_limit` | helper | app.py:1390 | Clamp integer query params | `services/debug_response_utils.py` | Low |
| `_flatten_generated_learning_found` | helper | app.py:1626 | Flatten nested found dict | `services/debug_response_utils.py` | Low |

### Routes — Admin (line 825)

| Route | Method | Current location | Responsibility | Recommended destination | Risk |
|---|---|---|---|---|---|
| `/admin/beta-metrics` | GET | app.py:825 | Beta metrics admin HTML | `routes/admin.py` | Medium |

### Routes — Jobs (lines 2678–2773)

| Route | Method | Current location | Responsibility | Recommended destination | Risk |
|---|---|---|---|---|---|
| `/jobs` | GET | app.py:2680 | Jobs list HTML | `routes/jobs.py` | Low |
| `/jobs/{job_id}` | GET | app.py:2703 | Job detail HTML | `routes/jobs.py` | Low |
| `/api/jobs/health` | GET | app.py:2722 | Jobs health JSON | `routes/jobs.py` | Low |
| `/api/jobs/enrich/{job_id}` | POST | app.py:2731 | Enrich single job | `routes/jobs.py` | Low |
| `/api/jobs/refresh` | POST | app.py:2758 | Refresh all jobs | `routes/jobs.py` | Low |

---

## 3. Recommended Target Structure

```
app.py                              ← app creation, middleware, router includes ONLY (~80 lines)
routes/
  public.py                         ← /, /health, /privacy, /terms
  auth.py                           ← /login, /signup, /logout
  dashboard.py                      ← /dashboard, /history + 6 dashboard helpers
  onboarding.py                     ← /onboarding/{session_id}, /onboarding/save
  chat.py                           ← /session/start, /chat, /chat/{session_id}, /progress, /quiz, /interview, /evaluate
  syllabus.py                       ← /syllabus/{session_id}, /task/toggle
  debug.py                          ← all /debug/* + _debug_access + debug helpers
  admin.py                          ← /admin/beta-metrics
  jobs.py                           ← /jobs, /jobs/{job_id}, /api/jobs/*
  topics.py                         ← (already exists)
  todos.py                          ← (already exists)
  submissions.py                    ← (already exists)
  deps.py                           ← (already exists — shared runtime state injection)
services/
  session_persistence.py            ← _save_session, _load_session_from_db, _get_session_data, _save_profile_db, _load_profile_db, _get_user_sessions, _get_user_history, build_dashboard_learning_summary
  debug_response_utils.py           ← _build_storage_health_payload, _storage_health_* helpers, _safe_debug_error_message, _safe_debug_limit, _flatten_generated_learning_found
models/
  requests.py                       ← StartSessionRequest, ChatRequest, QuizRequest, InterviewRequest, EvaluateRequest, TaskToggleRequest
```

### What stays in app.py after all splits
- `FastAPI()` app creation
- `app.mount("/static", ...)` 
- `Jinja2Templates(...)` 
- Rate limiter setup
- `_sessions` dict and `_executor` (until a proper session store is introduced)
- `auth_middleware` HTTP middleware + `_PUBLIC_PATHS`
- `TEST_MODE` config and `assert_test_mode_off()`
- `_startup_db()` startup hook
- `_make_client()` (or move to `core/`)
- `_mock_orchestrator_response()` + `_MOCK_RESPONSES` (TEST_MODE only)
- `deps.py` wiring block (already at bottom)
- All `app.include_router(...)` calls

---

## 4. Split Order

Each slice should be done in a separate commit, with tests run after each:

| Step | What to move | Target file | Risk |
|---|---|---|---|
| 1 | `/`, `/health`, `/privacy`, `/terms` | `routes/public.py` | **Low** — no session, no DB, no auth |
| 2 | `/onboarding/{session_id}`, `/onboarding/save` | `routes/onboarding.py` | Low-Medium — uses `_get_session_data`, `_save_session` |
| 3 | `/dashboard`, `/history` + 6 helpers | `routes/dashboard.py` | Medium — large template context, uses many services |
| 4 | All `/debug/*` + `_debug_access` + helpers | `routes/debug.py` | Medium — `_debug_access` must move with routes |
| 5 | `/admin/beta-metrics` | `routes/admin.py` | Medium — uses `_debug_access` pattern |
| 6 | `/login`, `/signup`, `/logout` | `routes/auth.py` | Medium — sets/clears cookies, creates sessions |
| 7 | `/syllabus/{session_id}`, `/task/toggle` | `routes/syllabus.py` | Medium — uses session helpers |
| 8 | `/session/start`, `/chat`, `/chat/{session_id}`, `/quiz`, `/interview`, `/evaluate`, `/progress/{session_id}` | `routes/chat.py` | **High** — core learner flow, orchestrator, rate limiter |
| 9 | `/jobs`, `/api/jobs/*` | `routes/jobs.py` | Low — self-contained, no SessionContext |
| 10 | Pydantic models | `models/requests.py` | Low — pure data classes |
| 11 | Session persistence functions | `services/session_persistence.py` | **High** — called from many routes; do last |
| 12 | Debug helper functions | `services/debug_response_utils.py` | Low — pure formatting, no DB calls |

---

## 5. Highest-Risk Areas

### Auth middleware allowlist — `_PUBLIC_PATHS` (app.py:331)
The set `{"/login", "/signup", "/health", "/privacy", "/terms"}` is checked in `auth_middleware`. If any new route module adds a public route and fails to update `_PUBLIC_PATHS`, that route will incorrectly redirect unauthenticated users to `/login`. Every route extraction must audit whether new routes need to be added to this set.

### Session ownership check — `_get_session_data` (app.py:639)
This function combines three concerns: in-memory cache lookup, DB restore on cache miss, and 403 ownership enforcement. It is called by virtually every protected route. Moving it without an exact behavioral match will break session security. Must be extracted as a single atomic unit with its own focused tests.

### Debug token protection — `_debug_access` (app.py:731)
This `Depends()` function checks `is_debug_access_allowed()` from `core.security_config`. It must be imported into `routes/debug.py` and `routes/admin.py` — if it is accidentally removed or the import is wrong, debug endpoints become unauthenticated in production.

### DB `get_conn` usage (multiple locations)
`get_conn()` from `database.pool` is called in `_save_session`, `_get_session_data`, `_load_session_from_db`, and many session persistence functions. These are synchronous calls executed in an async FastAPI context via `_run_blocking`. The threading model must be preserved when these functions are moved.

### Route URL stability
All existing route URLs must remain exactly unchanged. Templates reference URLs like `/chat/{session_id}`, `/onboarding/{session_id}`, `/syllabus/{session_id}` directly. Any URL change will break navigation without a template update.

### Template context variables
Each route renders a template with a specific context dict. Moving a route to a new file without moving all helper functions that build that context will cause `TemplateNotFound` or `KeyError` at render time. Dashboard is the most complex — it calls 4 different context-building helpers.

---

## 6. Test Strategy

For each split slice, run the following tests immediately after moving routes:

| Slice | Tests to run |
|---|---|
| Public routes (/, /health, /privacy, /terms) | `test_navigation.py`, `test_privacy_terms_pages.py`, `test_render_smoke_verification_report.py` |
| Onboarding routes | `test_navigation.py` |
| Dashboard route | `test_navigation.py` |
| Debug routes | `test_debug_endpoint_protection.py`, `test_storage_health_endpoint.py` |
| Admin route | `test_debug_endpoint_protection.py` |
| Auth routes | `test_production_auth_config.py` |
| Syllabus routes | `test_navigation.py` |
| Chat routes | `test_topic_practice.py`, `test_topic_content.py` |
| Session persistence | Full suite: `python -m pytest` |

---

## 7. Next Implementation Step

**Move public/static-safe routes only:**

Target routes (all in `app.py`, lines ~726–2039):
- `GET /health` — no auth, no session, no DB
- `GET /privacy` — no auth, no session, no DB
- `GET /terms` — no auth, no session, no DB
- `GET /` (index) — no auth, reads `request.state.user_id` only for redirect check

**Why this is the safest first slice:**
- None of these routes use `_get_session_data`, `_save_session`, or any session helper
- None use `get_conn` or any DB call
- All are already in `_PUBLIC_PATHS` — no middleware changes needed
- Templates rendered: `index.html`, `privacy.html`, `terms.html` — simple, no complex context
- Proves the `app.include_router()` extraction pattern works end-to-end before touching higher-risk routes

**Implementation preview:**
```python
# routes/public.py
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
import routes.deps as deps

router = APIRouter()

@router.get("/health")
async def health():
    return {"status": "ok", "test_mode": deps.TEST_MODE}

@router.get("/privacy", response_class=HTMLResponse)
async def privacy_page(request: Request):
    return deps.templates.TemplateResponse("privacy.html", {"request": request})

@router.get("/terms", response_class=HTMLResponse)
async def terms_page(request: Request):
    return deps.templates.TemplateResponse("terms.html", {"request": request})

@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    user_id = request.state.user_id
    if user_id:
        return RedirectResponse(url="/dashboard", status_code=302)
    return deps.templates.TemplateResponse("index.html", {"request": request})
```

After adding to app.py: `app.include_router(public_router)`

**Tests to run after this slice:** `test_navigation.py`, `test_privacy_terms_pages.py`

---

*This document is an audit and planning artifact only. No runtime behavior, routes, templates, static files, schema, feature flags, or data were modified to produce it.*
