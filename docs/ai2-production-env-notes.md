# AI² Production Environment Notes

Quick reference for deploying AI² in production. See `docs/ai2-production-readiness-audit.md` for the full audit.

---

## Required environment variables in production

| Variable               | Required in production | Notes                                                             |
|------------------------|------------------------|-------------------------------------------------------------------|
| `AI2_ENV`              | Yes                    | Set to `production` to enable production-mode safety checks       |
| `AUTH_SECRET`          | Yes                    | 64-char hex string. Generate: `python -c "import secrets; print(secrets.token_hex(32))"` |
| `ANTHROPIC_API_KEY`    | Yes                    | Your Anthropic API key                                            |
| `SUPABASE_DATABASE_URL`| Yes                    | Supabase PostgreSQL connection string                             |
| `AI2_TEST_MODE`        | Must NOT be set to `1` | Setting `AI2_TEST_MODE=1` in production will crash the app at startup |
| `AI2_DEBUG_TOKEN`      | Required to use `/debug/*` | Long random token. Without it, all debug endpoints return 404 in production |

---

## Production safety checks

When `AI2_ENV=production`, the app enforces three safety rules at startup:

### 1. AUTH_SECRET must be set

`core/security_config.py` raises `RuntimeError("AUTH_SECRET must be set in production.")` at startup if `AUTH_SECRET` is missing or empty.

**Why:** Without a stable `AUTH_SECRET`, every server restart invalidates all user sessions. Users are silently logged out.

**Fix:** Set `AUTH_SECRET` to a stable 64-char hex string in your production environment. Do not commit the real value to version control.

---

### 2. TEST_MODE must not be enabled in production

`core/security_config.py` raises `RuntimeError("TEST_MODE cannot be enabled in production.")` at startup if `AI2_TEST_MODE=1` and `AI2_ENV=production`.

**Why:** `TEST_MODE` bypasses all authentication and session ownership checks. It is designed only for automated testing and must never run on a live server.

**Fix:** Do not set `AI2_TEST_MODE=1` in production. If the app crashes with this error, remove the variable from your deployment config immediately.

---

### 3. Cookies use Secure=True in production

When `AI2_ENV=production`, `get_cookie_secure()` returns `True` and the `ai2_user_token` cookie is set with `Secure=True`. This ensures the cookie is only transmitted over HTTPS.

**Why:** Without `Secure=True`, the session cookie can be sent over plain HTTP, enabling session hijacking on any non-HTTPS connection.

**Fix:** Ensure your production server is behind HTTPS. Set `AI2_ENV=production` in your deployment environment.

---

## Local development behavior

When `AI2_ENV` is unset or set to anything other than `production`:

- Missing `AUTH_SECRET` is allowed. A random secret is generated and a warning is logged. Sessions will be invalidated on restart (acceptable in dev).
- `AI2_TEST_MODE=1` is allowed. Auth is bypassed for automated tests.
- Cookies do not use `Secure=True`. HTTP is usable for local dev.

No changes to local dev or test behavior are required.

---

## Feature flags

```env
AI2_DB_WRITE_THROUGH_ENABLED=false
AI2_TODOS_DB_READS_ENABLED=false
AI2_PROGRESS_DB_READS_ENABLED=false
AI2_USAGE_LIMITS_ENABLED=true
AI2_MODULAR_CURRICULUM_READS_ENABLED=false
```

`AI2_MODULAR_CURRICULUM_READS_ENABLED` is disabled by default. When false, the old/static curriculum runtime remains active. When true, later runtime code may read the DB-backed modular curriculum.

Do not enable this flag in production until the modular curriculum seed process and `/debug/modular-curriculum` endpoint have been verified with migration smoke tests.

For the first Render/Azure smoke test, keep DB-primary reads conservative:

- `AI2_DB_WRITE_THROUGH_ENABLED=true` only after `database/schema.sql` has been applied to the production database.
- `AI2_TODOS_DB_READS_ENABLED=false` initially; enable after write-through and fallback checks pass.
- `AI2_PROGRESS_DB_READS_ENABLED=false` initially; enable after write-through and fallback checks pass.
- `AI2_USAGE_LIMITS_ENABLED=true` for private beta cost control.
- `AI2_MODULAR_CURRICULUM_READS_ENABLED=false` initially; enable only after schema, manual modular seed, and `/debug/modular-curriculum` verification pass.

---

---

## Debug endpoint protection (AI2_DEBUG_TOKEN)

All `/debug/*` endpoints are protected in production by a token check.

**How it works:**
- When `AI2_ENV=production`, every `/debug/*` request must include the header `X-AI2-Debug-Token: <value>`.
- The value is compared to `AI2_DEBUG_TOKEN` using constant-time comparison (`hmac.compare_digest`) to avoid timing side-channels.
- If `AI2_DEBUG_TOKEN` is not set in production, all debug endpoints return `404 Not found` — they behave as if they do not exist.
- If the token does not match, the response is `404 Not found` — no hint that a token is required or exists.
- In local dev / test mode (`AI2_ENV` unset or not `production`), debug endpoints remain accessible without any token.

**Never:**
- Commit the real `AI2_DEBUG_TOKEN` value to version control.
- Log the token value.
- Share the token in error messages or response bodies.
- Use a short or predictable token. Generate with: `python -c "import secrets; print(secrets.token_hex(32))"`

---

## Remaining production hardening (still needed)

These items are NOT yet addressed and should be completed before public launch:

1. ~~**Debug endpoints**~~ — Resolved. All `/debug/*` endpoints are protected by `AI2_DEBUG_TOKEN` in production.

2. **Password reset** — No password reset or magic link flow exists. Required before opening signups to the public.

3. **Email verification** — No email verification on signup. Can be deferred for closed/invite-only beta.

See `docs/ai2-production-readiness-audit.md` Section 7 (Security and Privacy Audit) for the full list.
