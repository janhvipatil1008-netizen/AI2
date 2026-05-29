# AI² app.py Post Route-Split Checkpoint

## 1. Routes Already Moved

The post route-split checkpoint confirms these route modules now exist:

- `routes/public.py`
- `routes/onboarding.py`
- `routes/dashboard.py`
- `routes/auth_routes.py`
- `routes/syllabus.py`
- `routes/jobs.py`
- `routes/chat.py`
- `routes/debug.py`
- `routes/admin.py`

## 2. What Still Remains In app.py

### FastAPI app construction

- `FastAPI(...)` application construction with title, description, and version.
- Shared `TEST_MODE` initialization and production test-mode assertion.

### Middleware

- Authentication middleware still attaches `request.state.user_id`.
- Public path handling still lives in `app.py`, including login, signup, health, privacy, terms, and static bypass behavior.

### Static/templates setup

- Static file mounting for `/static`.
- Shared `Jinja2Templates(directory="templates")` setup.

### Limiter setup

- SlowAPI limiter construction.
- Rate-limit exception handler registration.
- Chat and practice rate-limit constants, including TEST_MODE high ceilings.

### Session persistence helpers

- `_get_session_data`
- `_save_session`
- `_get_user_sessions`
- `_get_user_history`
- `_save_exchange_to_history`
- `_load_session_from_db`
- `_load_profile_db`
- `_save_profile_db`
- `_make_client`
- `_track_from_str`
- `_session_progress`
- `_run_blocking`

### In-memory _sessions cache

- `_sessions` remains in `app.py` as the shared in-memory session cache.
- The cache is still wired into split route modules through `routes.deps.session_cache`.

### TEST_MODE mock responses

- `_MOCK_RESPONSES` is still present.
- `_mock_orchestrator_response` is still present and wired into `routes.deps`.

### Dependency wiring into routes.deps

- `app.py` still populates shared route dependencies in `routes.deps`, including templates, session helpers, profile helpers, mock responses, limiter settings, session cache, and `TEST_MODE`.
- This route dependency wiring remains a central runtime contract for the split routers.

### Router includes

- `app.py` imports and includes the public, onboarding, dashboard, auth, syllabus, jobs, chat, topics, todos, submissions, debug, and admin routers.

### Startup logic

- `_startup_db` remains in `app.py`.
- Startup schema initialization still runs during module import outside TEST_MODE.

## 3. What Should Move Next

Recommended next target: `services/session_persistence.py`.

Functions likely to move:

- `_get_session_data`
- `_save_session`
- `_get_user_sessions`
- `_get_user_history`
- `_save_exchange_to_history`
- session DB helpers such as `_load_session_from_db`, `_load_profile_db`, and `_save_profile_db`

Keep `_sessions` in `app.py` until an eviction policy is planned. Moving the in-memory cache too early could blur session lifetime, ownership checks, and multi-worker behavior.

## 4. Risk Notes

- Session ownership: `_get_session_data` enforces user/session ownership on cache hits and DB restores. Moving it must preserve 403 versus 404 behavior.
- Cookie/user_id/session_id behavior: auth middleware, route handlers, and session persistence share assumptions about cookie-derived `user_id` and request-provided `session_id`.
- DB fallback behavior: cache miss restore and non-fatal DB write failures are part of the current runtime behavior.
- TEST_MODE behavior: TEST_MODE bypasses persistence, auth enforcement, and live model calls in several places.
- Route dependency wiring: split route modules depend on `routes.deps` being populated before the routers execute request logic.
- Render smoke stability: startup DB initialization, health routes, auth redirects, and debug/admin protection should stay stable for Render smoke checks.

## 5. Recommended Next Step

Audit session persistence helpers before moving them.

The audit should map every caller, confirm ownership and DB fallback semantics, and decide whether `_sessions` stays app-owned until cache eviction and multi-worker behavior are explicitly designed.
