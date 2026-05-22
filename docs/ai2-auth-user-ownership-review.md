# AI² Auth and User Ownership Review

---

## 1. Current Auth Status

| Capability                          | Status               | Notes                                                              |
|-------------------------------------|----------------------|--------------------------------------------------------------------|
| Signup (email + password)           | Exists               | `POST /signup` in `app.py:1820`                                    |
| Login (email + password)            | Exists               | `POST /login` in `app.py:1778`                                     |
| Logout                              | Exists               | `GET /logout` in `app.py:1872` — deletes cookie server-side        |
| Password hashing                    | Exists               | bcrypt via `auth.py:21`                                            |
| Signed cookie tokens                | Exists               | itsdangerous `URLSafeTimedSerializer` via `auth.py:47`             |
| `get_current_user_id` helper        | Exists               | `auth.py:61` — decodes and validates the signed cookie             |
| Auth middleware                     | Exists               | `app.py:319` — attaches `user_id` to all requests via `request.state` |
| Redirect unauthenticated browsers   | Exists               | `app.py:338` — HTML requests redirect to `/login`                  |
| Reject unauthenticated API calls    | Exists               | `app.py:339` — non-HTML requests get `401 Unauthorized`            |
| `users` table in DB schema          | Exists               | `database/schema.sql:4`                                            |
| `sessions` table with `user_id` FK  | Exists               | `database/schema.sql:13`                                           |
| Session ownership enforcement       | Exists               | `app.py:624` — `_get_session_data()` checks `user_id` at both cache and DB level |
| Password reset / magic link         | Missing              | Not implemented                                                    |
| Email verification                  | Missing              | Not implemented                                                    |
| Secure cookie flag (HTTPS only)     | Needs Verification   | Cookie is `httponly=True, samesite="lax"` but `secure=True` is not set — must confirm TLS in production |
| `AUTH_SECRET` env var set           | Needs Verification   | Falls back to a random secret on restart if not set (`auth.py:38`) |
| Debug endpoints require auth        | Needs Work           | `/debug/storage-status`, `/debug/storage-health` have no ownership check |

**Summary:** Auth is substantially implemented. Signup, login, logout, signed cookies, auth middleware, and session ownership checks all exist and are tested. The remaining gaps are `secure=True` on the cookie, confirming `AUTH_SECRET` is set in production, protecting debug endpoints, and missing password reset.

---

## 2. Current User and Session Model

### How `user_id` appears in the app

- A `user_id` (UUID string) is generated at signup (`app.py:1847`) and stored in the `users` table.
- On login, the `user_id` is signed into an `ai2_user_token` cookie using `itsdangerous` (`auth.py:50`).
- The auth middleware decodes this cookie on every request and writes the result to `request.state.user_id` (`app.py:329–330`).
- All routes that access learner data read `request.state.user_id` to identify the current user.

### How `session_id` appears in the app

- A `session_id` is a separate UUID generated when a learner starts a session (`/session/start`).
- It is passed into learner-facing routes as a request body field or query parameter.
- The `sessions` table stores `session_id` with a `user_id` foreign key (`schema.sql:13–18`), linking sessions to their owner.

### How `SessionContext` is loaded

1. A route receives `session_id` from the request.
2. The route calls `_get_session_data(session_id, request.state.user_id or "")` (`app.py:624`).
3. This function first checks the in-process `_sessions` dict (cache hit path). If the session is found and the stored `session.user_id` does not match the caller's `user_id`, it raises `403 Access denied` (`app.py:628–631`).
4. On a cache miss (restart, new worker), it queries the DB with `WHERE session_id = %s AND user_id = %s` (`app.py:641–643`). If the row exists but belongs to a different user, it raises `403` (`app.py:655`). If it does not exist at all, it raises `404` (`app.py:654`).
5. On success, the session is deserialized from `session_data` JSON and stored back into the in-process cache.

### How session data is saved

- After every mutation, `_save_session(session_id, session)` is called (`app.py:89`).
- This upserts the full `SessionContext.to_dict()` JSON blob into `sessions.session_data`, and also writes `session.user_id` to the `user_id` column (`app.py:103–105`).
- In `TEST_MODE`, `_save_session` is a no-op.

### How sessions connect to users

- `sessions.user_id` is a nullable foreign key referencing `users.user_id`.
- All learner data tables (`topic_progress`, `todos`, `generated_topic_content`, etc.) include both `user_id` and `session_id` columns.
- The `_save_session` path writes `session.user_id` to the `sessions` row, maintaining the link.

---

## 3. Current Learner Data Ownership Coverage

| Data Category                         | Tied to `user_id` | Tied to `session_id` | DB Mirror Exists | Ownership Risk                                       |
|---------------------------------------|-------------------|----------------------|------------------|------------------------------------------------------|
| Topic progress                        | Yes               | Yes                  | Yes              | Low — both IDs stored and checked via session gate   |
| Todos                                 | Yes               | Yes                  | Yes              | Low — same pattern                                   |
| Topic notes / reflections             | Yes               | Yes                  | Yes              | Low — same pattern                                   |
| Generated lesson content              | Yes               | Yes                  | Yes              | Low — session gate enforces ownership before access  |
| Generated practice content            | Yes               | Yes                  | Yes              | Low — same pattern                                   |
| Quiz submissions / evaluations        | Yes               | Yes                  | Yes              | Low — same pattern                                   |
| Portfolio submissions / feedback      | Yes               | Yes                  | Yes              | Low — same pattern                                   |
| Interview submissions / feedback      | Yes               | Yes                  | Yes              | Low — same pattern                                   |
| Usage events                          | Yes               | Yes                  | Yes (DB-primary) | Low — already DB-backed with both IDs                |
| Conversation history                  | Yes               | Yes                  | Yes              | Low — queried by `user_id` only (`app.py:209`)       |

**Summary:** All learner data categories include `user_id` and `session_id` in their DB schema. Ownership is enforced at the session-loading gate (`_get_session_data`), so any route that correctly calls this helper is covered.

---

## 4. Ownership Risks

### Risk 1 — `session_id` accepted from request body without strong client-side secret

`session_id` is passed as a plain string in request bodies and query parameters (e.g., `ChatRequest.session_id`, `TodoCreateRequest.session_id`). The caller supplies the `session_id` they want to access. The ownership check in `_get_session_data` prevents a user from accessing another user's session, but the `session_id` namespace is flat — any user who guesses or obtains another user's `session_id` will hit a correct `403`, but the existence of the session is revealed by the different 403 vs 404 response codes (`app.py:653–655`).

**Severity:** Low — 403 is the correct response. The side-channel (existence disclosure) is a minor information leak, not a data breach.

---

### Risk 2 — `TEST_MODE` completely bypasses auth

When `AI2_TEST_MODE=1` is set, all auth checks are skipped (`app.py:332`), ownership checks are skipped (`app.py:628`), and `_save_session` is a no-op (`app.py:91`). This is correct for CI, but the environment variable must never be set in production.

**Severity:** Critical if `TEST_MODE` is inadvertently enabled in production. Should be confirmed off by deployment config or an explicit startup assertion.

---

### Risk 3 — Debug endpoints have no ownership or auth check

`/debug/storage-status` (`app.py:716`) and `/debug/storage-health` (`app.py:767`) are reachable by any authenticated user. They do not expose raw user data or secrets, but they reveal internal architecture details: which DB flags are enabled, storage mode, and session-level counts. Before public launch, these should require an admin/internal role or be restricted by IP.

**Severity:** Medium — no data leakage, but internal architecture is visible to all authenticated users.

---

### Risk 4 — `AUTH_SECRET` falls back to a random value on restart

If `AUTH_SECRET` is not set in the environment, `auth.py:39` generates a random secret using `secrets.token_hex(32)`. This means every server restart invalidates all existing sessions. In production this would silently log out all users.

**Severity:** Medium — data is not lost, but all sessions are invalidated. The warning is emitted at startup, but it is easy to miss in production logs.

---

### Risk 5 — Cookie does not set `Secure=True`

The `ai2_user_token` cookie is set with `httponly=True, samesite="lax"` but without `secure=True` (`app.py:1807, 1868`). Without `Secure`, the cookie can be transmitted over plain HTTP, allowing interception in a man-in-the-middle scenario.

**Severity:** Low on HTTPS-only deployments, but must be confirmed. If the app is ever served over HTTP in production, this becomes a session hijacking vector.

---

### Risk 6 — `_load_session_from_db` does not filter by `user_id`

The internal helper `_load_session_from_db(session_id)` at `app.py:153` queries `WHERE session_id = %s` without a `user_id` check. This function is called only from `_get_session_data` after the ownership check has already been applied. It is not directly callable from routes. However, if a future developer calls it directly, the ownership layer is bypassed.

**Severity:** Low — currently internal-only and gated by the calling function. Document as a code-review concern.

---

### Risk 7 — Repositories' read queries filter by `session_id` only, not `user_id`

Several repository read functions (e.g., `progress_repository.get_topic_progress_by_legacy_id`) query by `session_id` alone, not `user_id + session_id`. Since `session_id` is a UUID and ownership is enforced at the route level before repositories are called, this is currently safe. But if a repository read is ever called with an unvalidated `session_id`, there is no secondary defense.

**Severity:** Low — defense-in-depth concern, not an active vulnerability.

---

## 5. Private Beta Minimum Auth Requirements

| Requirement                                              | Current Status       |
|----------------------------------------------------------|----------------------|
| Every learner has a `user_id`                            | Met — signup creates UUID                          |
| Every session belongs to a `user_id`                     | Met — `sessions.user_id` FK, ownership enforced   |
| Learner routes load session only for current user        | Met — `_get_session_data` enforces 403             |
| DB reads/writes filter by `user_id` + `session_id`       | Partially met — writes include both; some reads use `session_id` only |
| `AUTH_SECRET` set in production environment              | Needs Verification — fallback to random secret must be confirmed off |
| Cookie has `Secure=True` on HTTPS deployment             | Needs Verification — not set in code; must be confirmed at deploy     |
| Debug endpoints protected or disabled in production      | Needs Work — no access control on `/debug/*`       |
| Logout flow                                              | Met — `GET /logout` deletes cookie                 |
| Password reset or magic link                             | Missing — not implemented; can be deferred for closed beta            |
| Email verification                                       | Missing — not implemented; can be deferred for closed beta            |
| Session isolation tests pass against real DB             | Met — `tests/test_session_ownership.py` covers 403 cross-user case   |

---

## 6. Recommended Auth Approach

**Recommendation: Keep the current custom auth implementation.** Do not switch to Supabase Auth or Clerk.

**Why:** The existing auth is more complete than it might appear from a surface-level audit. It has:
- bcrypt password hashing
- Signed, time-limited cookies via itsdangerous
- Auth middleware with per-request `user_id` attachment
- Session ownership enforcement at both cache and DB level
- Tested cross-user 403 behavior
- Full signup, login, logout flows

Replacing this with an external provider at this stage would require rewriting the session ownership model, the middleware, the cookie handling, the DB user/session link, and all tests — for a system that is fundamentally sound. The effort is not justified.

**What to do instead:** Close the three gaps that remain:
1. Set `AUTH_SECRET` in the production environment and add a hard startup check.
2. Add `secure=True` to the cookie on production (conditionally, based on an env flag).
3. Add an admin/internal-only guard to the `/debug/*` endpoints.

These are small, targeted changes that do not require architectural rework.

---

## 7. Exact Build Order

Execute in this order before moving to DB-primary reads.

1. **Confirm `AUTH_SECRET` is set in production** — add a startup assertion that raises if `AUTH_SECRET` is not set and `TEST_MODE` is off. The current warning is too easy to miss.

2. **Add `Secure=True` to cookie on HTTPS** — add an `AI2_SECURE_COOKIES` env flag (default off for local dev, on for production). Pass `secure=True` to `set_cookie` when the flag is on.

3. **Protect debug endpoints** — add a simple admin check to `/debug/storage-status`, `/debug/storage-health`, and `/debug/storage-health-view`. Options: require a static admin token header, restrict to internal IPs, or gated by an `AI2_DEBUG_ENABLED` env flag that defaults off in production.

4. **Add `user_id` to repository read queries as a secondary filter** — defense-in-depth. Update `get_topic_progress_by_legacy_id` and similar read functions to also accept and filter by `user_id`.

5. **Add route-level ownership tests for each route family** — extend `test_session_ownership.py` to cover todos, notes, and submission routes in addition to the chat page.

6. **Verify `TEST_MODE` cannot be enabled in production** — add a deployment check or document clearly in runbooks.

7. **Only after the above: begin moving DB reads to primary** — the session gate is solid. Once the three cookie/secret/debug gaps are closed and tests cover all route families, it is safe to flip DB-primary reads behind flags.

---

## 8. Files Inspected

| File                                          | What It Contains                                                                 |
|-----------------------------------------------|---------------------------------------------------------------------------------|
| [auth.py](../auth.py)                         | bcrypt hashing, signed cookie creation/decoding, `get_current_user_id` helper   |
| [app.py](../app.py) (lines 314–341)           | `auth_middleware` — attaches `user_id` to all requests, redirects unauthenticated |
| [app.py](../app.py) (lines 624–676)           | `_get_session_data` — core session ownership enforcement at cache and DB level   |
| [app.py](../app.py) (lines 89–108)            | `_save_session` — upserts session blob + `user_id` to `sessions` table          |
| [app.py](../app.py) (lines 1769–1876)         | `/login`, `/signup`, `/logout` route handlers                                    |
| [app.py](../app.py) (lines 716–800)           | `/debug/storage-status`, `/debug/storage-health` — no access guard              |
| [database/schema.sql](../database/schema.sql) | `users`, `sessions`, and all learner data tables with `user_id` + `session_id`  |
| [context/session.py](../context/session.py) (lines 34–81) | `SessionContext` dataclass — includes `user_id: str` field          |
| [routes/todos.py](../routes/todos.py)         | Uses `deps.get_session_data(session_id, request.state.user_id or "")`            |
| [routes/submissions.py](../routes/submissions.py) | Same pattern — `_get_session()` helper passes `user_id` through          |
| [routes/topics.py](../routes/topics.py)       | Same pattern                                                                     |
| [routes/deps.py](../routes/deps.py)           | Write-through helpers — all pass `user_id` and `session_id` to repositories     |
| [repositories/progress_repository.py](../repositories/progress_repository.py) | Read queries filter by `session_id` only — `user_id` in writes |
| [tests/test_session_ownership.py](../tests/test_session_ownership.py) | Integration tests: cross-user 403, own-session 200; requires real DB |

---

## 9. Final Recommendation

### Is auth ready?

**Mostly yes — with three gaps to close before private beta.**

The auth implementation is substantially complete and covers the most critical requirements: users exist, sessions belong to users, the session ownership check is enforced at both the in-memory and DB layer, and cross-user access returns 403 with test coverage. This is a stronger foundation than many early-stage apps.

The three gaps that must be closed before private beta are:
1. `AUTH_SECRET` must be confirmed set in production (currently falls back to random — all sessions invalidated on restart).
2. Cookie `Secure=True` must be verified for HTTPS deployments.
3. Debug endpoints must be protected before the app is publicly accessible.

### Should DB-primary reads start now?

**Not yet — close the auth gaps first.**

The session ownership gate (`_get_session_data`) is the foundation for safe DB-primary reads. Once that gate is fully hardened (secret confirmed, debug endpoints protected, ownership tests cover all route families), flipping DB-primary reads behind flags is low-risk.

### Next coding step

Set `AUTH_SECRET` production enforcement, add the `Secure` cookie flag, and guard the `/debug/*` endpoints. These are three small, targeted changes. They unblock the DB-primary migration that follows.
