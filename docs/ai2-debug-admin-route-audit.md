# AI² Debug and Admin Route Audit

Audit of all debug and admin routes currently in `app.py`, prepared before splitting them to `routes/debug.py` and `routes/admin.py`.

---

## 1. Current Debug/Admin Routes In app.py

All routes use `_debug_access` as a FastAPI dependency (see Section 2).

| Method | Path | Function | DB Connection | Responsibility |
|--------|------|----------|--------------|----------------|
| GET | `/debug/storage-status` | `debug_storage_status` | No | Returns boolean storage-flag summary. Reads only env-gated feature flags; never opens a DB connection. |
| GET | `/debug/storage-health` | `debug_storage_health` | Conditional | Delegates to `_build_storage_health_payload`. Opens DB only if `session_id` is supplied (via `_get_session_data`). |
| GET | `/debug/storage-health-view` | `debug_storage_health_view` | Conditional | HTMLResponse version of `/debug/storage-health`. Same DB behaviour; renders `storage_health.html`. |
| GET | `/admin/beta-metrics` | `admin_beta_metrics` | Yes (always) | HTMLResponse; opens one `get_conn()` to collect aggregate beta metrics via `collect_beta_metrics`. Falls back gracefully on DB error. |
| GET | `/debug/curriculum-db-check` | `debug_curriculum_db_check` | Conditional | Opens DB only when `AI2_CURRICULUM_DB_READS_ENABLED=1`. Reports track/topic DB read readiness. |
| GET | `/debug/curriculum-fallback-check` | `debug_curriculum_fallback_check` | Conditional | Opens DB only when `AI2_CURRICULUM_DB_READS_ENABLED=1`. Shows whether results come from DB or static fallback. |
| GET | `/debug/learner-state-db-check` | `debug_learner_state_db_check` | Conditional | Opens DB only when `AI2_PROGRESS_DB_READS_ENABLED=1` or `AI2_TODOS_DB_READS_ENABLED=1`. Reports topic-progress and todos mirror state. |
| GET | `/debug/generated-learning-db-check` | `debug_generated_learning_db_check` | Yes (always) | Always opens DB. Reads generated-learning mirror state for a session/topic. |
| GET | `/debug/usage-events-db-check` | `debug_usage_events_db_check` | Yes (always) | Always opens DB. Lists usage-events mirror rows and aggregate summary for a session. |
| GET | `/debug/usage-events-mismatch-check` | `debug_usage_events_mismatch_check` | Yes (always) | Loads session via `_get_session_data`, opens DB, compares usage-events mirror against SessionContext. |
| GET | `/debug/generated-learning-mismatch-check` | `debug_generated_learning_mismatch_check` | Yes (always) | Loads session, opens DB, compares generated-learning mirror against SessionContext. |
| GET | `/debug/learner-state-mismatch-check` | `debug_learner_state_mismatch_check` | Conditional | Loads session. Opens DB only when at least one of the progress/todos flags is enabled. Compares DB mirrors against SessionContext. |
| GET | `/debug/learner-state-fallback-check` | `debug_learner_state_fallback_check` | Conditional | Loads session. Opens DB only when at least one flag is enabled. Shows whether learner-state comes from DB or SessionContext fallback. |
| GET | `/debug/modular-curriculum` | `debug_modular_curriculum` | Yes (attempts) | Always attempts a DB connection; gracefully falls back to static curriculum if DB is unavailable. Inspection-only; never modifies data. |

### Helper functions (debug/admin-specific, also in app.py)

| Function | Type | Responsibility |
|----------|------|----------------|
| `_debug_access(request)` | FastAPI dependency | Blocks debug/admin endpoints in production unless `X-AI2-Debug-Token` header matches `AI2_DEBUG_TOKEN`. |
| `_build_storage_health_payload(request, session_id, legacy_topic_id)` | Builder | Assembles the storage-health JSON dict. Opens DB indirectly via `_get_session_data` when `session_id` is provided. |
| `_storage_health_overall_status(...)` | Pure helper | Derives `"healthy"` / `"partial"` / `"not_configured"` from flag booleans. |
| `_storage_health_session_status(session)` | Pure helper | Returns safe session counts (no generated content). |
| `_storage_health_completed_topics_count(session, topic_progress)` | Pure helper | Counts completed topics from `topic_progress` dict. |
| `_storage_health_topic_status(session, legacy_topic_id)` | Pure helper | Returns presence-only booleans for a topic (no generated text). |
| `_empty_generated_learning_state_found()` | Pure helper | Returns zero-state dict for generated-learning found flags. |
| `_generated_learning_state_found(state)` | Pure helper | Maps a DB state dict to presence-only boolean flags. |
| `_flatten_generated_learning_found(found)` | Pure helper | Flattens the found-flags dict to a flat `list[bool]`. |
| `_safe_debug_error_message(exc)` | Security helper | Redacts DB URLs, API keys, and env var values from exception messages before returning them in debug responses. |
| `_safe_debug_limit(value, ...)` | Input sanitizer | Clamps a user-supplied `limit` query parameter to a safe integer range. |

---

## 2. Security Dependencies

### `AI2_DEBUG_TOKEN`
A server-side secret set via the `AI2_DEBUG_TOKEN` environment variable. It is never returned in any response and is only read at request time inside `is_debug_access_allowed`.

### Production 404 behavior without token
`_debug_access` calls `is_debug_access_allowed(request)` from `core/security_config.py`. In production (`AI2_ENV=production`), if the `X-AI2-Debug-Token` request header is absent or does not match the configured token, the dependency raises `HTTPException(status_code=404)` — returning "Not found" rather than 401/403. This avoids confirming that a debug endpoint exists at all.

If `AI2_DEBUG_TOKEN` is not configured in production, `is_debug_access_allowed` returns `False` unconditionally, so all debug/admin endpoints return 404 even with a header.

### `_debug_access` dependency
Defined at line 610 of `app.py`. Applied via `Depends(_debug_access)` on every debug and admin route. It is the sole gating mechanism for this entire group of routes. In non-production (`AI2_ENV` not `"production"`), it always returns `True`.

### Error sanitization
`_safe_debug_error_message(exc)` is called before any exception detail reaches a response. It:
- Redacts known env var names and their live values (`SUPABASE_DATABASE_URL`, `DATABASE_URL`, `ANTHROPIC_API_KEY`)
- Redacts any `postgres://` or `postgresql://` URL patterns
- Redacts any other `scheme://` URLs
- Redacts the word "traceback" (to avoid leaking stack trace fragments)
- Truncates the message to 300 characters

### No private content exposure
All debug endpoints return only:
- Boolean flags
- Integer counts
- Normalised row dicts from dedicated read services
- Safe error summaries via `_safe_debug_error_message`

None of the debug endpoints return raw `session_data`, generated content text, quiz answers, portfolio submissions, interview feedback, or API keys.

---

## 3. DB Dependencies

| Route | Opens DB Connection |
|-------|---------------------|
| `/debug/storage-status` | **No** — reads env flags only |
| `/debug/storage-health` | **Conditional** — only if `session_id` query param provided |
| `/debug/storage-health-view` | **Conditional** — only if `session_id` query param provided |
| `/admin/beta-metrics` | **Yes** — always opens one connection |
| `/debug/curriculum-db-check` | **Conditional** — only when `AI2_CURRICULUM_DB_READS_ENABLED=1` |
| `/debug/curriculum-fallback-check` | **Conditional** — only when `AI2_CURRICULUM_DB_READS_ENABLED=1` |
| `/debug/learner-state-db-check` | **Conditional** — only when progress or todos flag enabled |
| `/debug/generated-learning-db-check` | **Yes** — always |
| `/debug/usage-events-db-check` | **Yes** — always |
| `/debug/usage-events-mismatch-check` | **Yes** — always (also loads session) |
| `/debug/generated-learning-mismatch-check` | **Yes** — always (also loads session) |
| `/debug/learner-state-mismatch-check` | **Conditional** — only when at least one flag enabled (always loads session) |
| `/debug/learner-state-fallback-check` | **Conditional** — only when at least one flag enabled (always loads session) |
| `/debug/modular-curriculum` | **Yes** — always attempts; graceful fallback on failure |

---

## 4. Recommended Split Destination

### `routes/debug.py`
All `/debug/*` routes and their supporting helper functions:
- All 13 `/debug/*` route handlers
- `_build_storage_health_payload`
- `_storage_health_overall_status`
- `_storage_health_session_status`
- `_storage_health_completed_topics_count`
- `_storage_health_topic_status`
- `_empty_generated_learning_state_found`
- `_generated_learning_state_found`
- `_flatten_generated_learning_found`
- `_safe_debug_error_message`
- `_safe_debug_limit`

### `routes/admin.py`
The single `/admin/*` route:
- `admin_beta_metrics`

### Protection dependency (`_debug_access`)
Keep `_debug_access` in `routes/deps.py` (already the shared dependency hub) or in a small `routes/_debug_guard.py` helper. Both `routes/debug.py` and `routes/admin.py` import and apply it. This keeps the token-checking logic in one place and avoids duplicating it.

### Response sanitization helpers
`_safe_debug_error_message` and `_safe_debug_limit` are used exclusively by debug routes. Move them into `routes/debug.py` alongside the routes that call them, unless they are later needed elsewhere.

---

## 5. Risk Areas

1. **Accidentally exposing debug endpoints in production** — `_debug_access` must be applied to every route in the new modules, including any routes added in the future. Missing the dependency on even one route would silently expose it. A module-level note and a test that hits the endpoint without a token both help guard against this.

2. **Leaking DB URLs / env vars / API keys** — `_safe_debug_error_message` must be carried over intact to `routes/debug.py`. If it is accidentally omitted from a new route, raw exception messages could leak `DATABASE_URL` or `ANTHROPIC_API_KEY` values in error responses.

3. **Opening DB connections for unauthorized requests** — `_debug_access` must run before any DB-opening code path. FastAPI executes `Depends` before the route body, so the current approach is safe, but this ordering must be preserved in the split modules.

4. **Changing response shapes used by tests** — `tests/test_debug_admin_route_audit.py` and any future debug-specific tests rely on the response JSON structure. The split must be a pure move; no field names or HTTP status codes should change.

5. **Breaking `/admin/beta-metrics`** — This is the only `admin` route and renders an HTML template (`beta_metrics.html`). It also depends on `build_beta_metrics_payload` and `collect_beta_metrics` from separate service/repository modules. The split should verify that the template path and service imports all resolve from `routes/admin.py`.

6. **`_debug_access` is currently a plain function, not a `routes.deps` attribute** — Unlike the session/profile helpers (which are injected via `routes.deps`), `_debug_access` is defined directly in `app.py` and referenced locally by each route via `Depends(_debug_access)`. During the split it must be imported from its new home consistently across both new modules.

---

## 6. Safe Split Plan

Recommended one slice at a time, each with its own commit and test run:

1. **Move `_debug_access` to `routes/deps.py`** (or `routes/_debug_guard.py`). Update all existing debug/admin `Depends(...)` calls in `app.py` to use the new import. Run full test suite. Commit.

2. **Move config-only debug endpoints** — `/debug/storage-status`, the `_storage_health_overall_status` helper, and related pure helpers. These never open a DB connection and are the lowest-risk slice. Create `routes/debug.py` with an `APIRouter`. Run tests. Commit.

3. **Move DB-check debug endpoints** — `/debug/curriculum-db-check`, `/debug/curriculum-fallback-check`, `/debug/learner-state-db-check`. These open DB only when flags are enabled. Move `_safe_debug_error_message` and `_safe_debug_limit` at this step. Run tests. Commit.

4. **Move mismatch endpoints** — `/debug/usage-events-db-check`, `/debug/usage-events-mismatch-check`, `/debug/generated-learning-db-check`, `/debug/generated-learning-mismatch-check`, `/debug/learner-state-mismatch-check`, `/debug/learner-state-fallback-check`. Move remaining helpers (`_build_storage_health_payload`, `_storage_health_session_status`, etc.). Run tests. Commit.

5. **Move storage-health and modular-curriculum endpoints** — `/debug/storage-health`, `/debug/storage-health-view`, `/debug/modular-curriculum`. Complete `routes/debug.py`. Run tests. Commit.

6. **Move `/admin/beta-metrics` last** — Create `routes/admin.py`. This is the most isolated route (single endpoint, own service/repository imports, HTML template). Moving it last means `routes/debug.py` is already proven before touching admin. Run tests. Commit.

---

## 7. Test Plan

Tests for the split should cover:

- `GET /debug/storage-status` without `X-AI2-Debug-Token` in production returns `404` (not 401/403/200)
- `GET /debug/storage-status` with correct `X-AI2-Debug-Token` in production returns `200`
- `GET /debug/storage-status` in non-production always returns `200` (no token required)
- Unauthorized requests to any `/debug/*` endpoint do not open a DB connection
- `GET /debug/storage-health` without `session_id` does not open a DB connection (config-only path)
- `_safe_debug_error_message` redacts DB URL, API key, and traceback from error strings
- Response sanitization: no response from any `/debug/*` route contains a raw `postgres://` URL or `ANTHROPIC_API_KEY` value
- `GET /admin/beta-metrics` without token in production returns `404`
- `GET /admin/beta-metrics` with correct token returns `200` HTML response
- Route URLs are unchanged after split (no 404 regressions on correct paths)
- Response JSON shapes for all `/debug/*` endpoints are unchanged after split
