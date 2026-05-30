# AI² Exception Logging Audit

## 1. Purpose

This audit surveys every broad `except` block in the AI² codebase to identify which failures are currently silent, which already log safely, and what the next minimal logging improvement should be.

The goal is to make failures observable during beta without changing any learner-facing behavior, without leaking secrets or DB URLs to log output, and without introducing any new dependencies. No code changes are made in this document; it is a pre-implementation record for reviewers and future implementation PRs.

---

## 2. Findings Summary

### 2a. Safe intentional fallbacks — no change needed

These blocks fail closed, re-raise appropriately, or already log with safe structured metadata. No action required.

| file | line(s) | pattern | verdict |
|---|---|---|---|
| `database/pool.py` | 60 | `except Exception: conn.rollback(); raise` | Correct — re-raises after rollback. |
| `auth.py` | 30 | `except Exception: return False` | Safe — bcrypt failure, silent by design (timing attack mitigation). |
| `services/generated_learning_read_service.py` | 28 | `except Exception: return {}` | Safe — JSON parse failure on cached metadata, empty dict is correct fallback. |
| `services/learner_state_read_service.py` | 43 | `except Exception: metadata = {}` | Safe — JSON parse failure, empty dict fallback. |
| `jobs/database.py` | 58, 85 | `except Exception: d["summary"] = {} / pass` | Safe — JSON deserialization of enrichment data; broken row is skipped. |
| `routes/deps.py` | 84, 123, 154, 190, 228, 277, 325, 344, 387, 433 | All write-through functions | Already log with `get_logger("routes.write_through").warning(...)` and `safe_error_metadata`. |
| `routes/admin.py` | 35–36 | `except Exception as exc: logger.warning(safe_debug_error_message(exc))` | Already logged safely. |
| `routes/jobs.py` | 22–23 | `except Exception as _jobs_db_err: logger.warning(...)` | Already logged on import failure. |
| `routes/jobs.py` | 113–114 | `except Exception as exc: logger.error(...)` | Already logged for background fetch failure. |
| `routes/onboarding.py` | 68–69 | `except Exception: logger.warning("onboarding course enrollment failed...")` | Already logged. Does not include `exc` details — minor gap noted in §3. |
| `services/content_service.py` | 156, 176, 369, 391 | `except Exception as exc: logger.error(...)` with `safe_error_metadata` | Claude API failures already logged with structured metadata. |
| `services/session_persistence.py` | 47–48, 136–137, 184–185 | `(logger or _logger).warning(f"... failed (non-fatal): {exc}")` | Already logged for session/history/profile write failures. |
| `jobs/fetcher.py` | 51–52 | `except Exception as exc: logger.warning(f"... failed: {exc}")` | Already logged for job scraping failure. |
| `app.py` | 205–206 | `except Exception as exc: logger.warning(f"_startup_db skipped: {exc}")` | Already logged for schema bootstrap. |
| `services/modular_progress_snapshot_service.py` | 114 | `except Exception as exc: return {"error": sanitize_modular_snapshot_error(exc)}` | Returns sanitized error dict; callers in `routes/deps.py` log via `safe_error_metadata`. |
| `services/learner_course_enrollment_service.py` | 136, 165, 196 | `except Exception as exc: return {"error": sanitize_enrollment_error(exc)}` | Returns sanitized error dict; callers log or surface gracefully. |
| `routes/dashboard.py` | 238, 304 | `except Exception: pass` inside `conn.close()` | Intentional cleanup-block silent swallow. `close()` errors should not propagate. |

### 2b. Should log warning — currently silent

These blocks swallow errors with no log output. A `logger.warning(...)` with safe metadata should be added.

| file | line(s) | current pattern | recommended change |
|---|---|---|---|
| `routes/dashboard.py` | 98–99 | `except Exception: pass` — display_name DB fetch silently falls back to `"Learner"`. | Add `logger.warning("dashboard display_name fetch failed")` with safe metadata. |
| `routes/dashboard.py` | 111–112 | `except Exception: recent_session = None` — recent session load fails silently. | Add `logger.warning("dashboard recent_session load failed")` with safe metadata. |
| `routes/dashboard.py` | 229–230 | `except Exception: return {...disabled}` — enrollment summary fetch fails silently. | Add `logger.warning("dashboard enrollment_summary failed")`. |
| `routes/dashboard.py` | 295–296 | `except Exception: modular_summary = {...}` — modular progress fetch fails silently. | Add `logger.warning("dashboard modular_progress failed")`. |
| `services/session_persistence.py` | 107–108 | `except Exception: pass` — DB restore in `get_session_data` fails silently; caller raises 404. | Add `logger.warning("get_session_data DB restore failed")` with `session_id` (safe). |
| `services/session_persistence.py` | 168–169 | `except Exception: return []` — `get_user_history` DB failure returns empty list silently. | Add `logger.warning("get_user_history failed")`. |
| `services/session_persistence.py` | 198–199 | `except Exception: return None` — `load_profile_db` failure returns None silently. | Add `logger.warning("load_profile_db failed")`. |
| `services/session_persistence.py` | 233 | `except Exception: return []` — `get_user_sessions` outer failure returns empty list silently. | Add `logger.warning("get_user_sessions failed")`. |
| `services/content_service.py` | 62–63 | `except Exception: shared_row = None` — shared cache read fails silently; every request falls through to Claude. | Add `logger.warning("shared content_cache read failed")` with topic/track metadata. |
| `services/content_service.py` | 205–206 | `except Exception: pass` — shared cache write fails silently; generated content is not persisted. | **First implementation slice — see §5.** Add `logger.warning("shared content_cache write failed")` with topic/track metadata. |
| `services/dashboard_modular_progress_service.py` | 106 | `except Exception: return _empty_summary("error_fallback")` — modular progress query fails silently. | Add `logger.warning("build_dashboard_modular_progress_summary failed")`. |
| `services/learner_state_fallback_service.py` | 71, 121 | `except Exception as exc: notes.append("DB read failed; using session fallback.")` — appends to a debug notes list but never calls `logger`. | Add `logger.warning(...)` alongside the notes append. |
| `routes/jobs.py` | 32–33, 36–37, 54–55 | `except Exception: jobs = [] / stats = {...} / job = None` — job listing/stats/detail DB failures are silent. | Add `logger.warning(...)` for each. |
| `routes/jobs.py` | 93–94 | `except Exception: pass` — learner context extraction for job enrichment fails silently. | Add `logger.debug(...)` (low-signal, not worth warning). |
| `routes/topics.py` | 557–558 | `except Exception: return get_topics_for_week(...)` — modular topic listing falls back silently. | Add `logger.warning("modular topic listing failed, using week fallback")`. |

### 2c. Should log exception — unexpected errors being swallowed or leaking

These blocks either leak raw exception text to the learner-facing HTTP response, or suppress unexpected errors without any instrumentation.

| file | line(s) | current pattern | recommended change |
|---|---|---|---|
| `routes/topics.py` | 442–443, 513–514 | `except Exception as exc: raise HTTPException(status_code=500, detail=f"Content generation failed: {exc}")` | Raw `exc` in learner-facing 500 detail leaks internal error strings. Add `logger.exception(...)` before raising; scrub detail to a generic message. |
| `routes/jobs.py` | 100–101 | `except Exception as exc: raise HTTPException(status_code=500, detail=str(exc))` | Same — raw `str(exc)` in 500 detail. Add `logger.exception(...)`, use safe generic detail. |
| `routes/debug.py` | 268–269 | `except Exception: steps = topic_progress.get(topic_id) or {}` — completion percent calculation fails silently in a loop. | Add `logger.warning(...)` with topic_id. Debug route, low urgency. |
| `routes/topics.py` | 605–607 | `except Exception as exc: return {"source": "error_fallback", ...}` — topic context load fails, returns error dict without logging. | Add `logger.warning(...)` with topic_id. |
| `routes/topics.py` | 750–751 | `except Exception as exc: from core.logging import ...` — lazy import inside except block; no log call visible at line 750. Verify logging actually fires. | Confirm `logger.warning` call exists after the lazy import; if not, add it. |

### 2d. Should remain silent — intentional and tested

These blocks are known to be correct silent swallows. They should stay as-is.

| file | line(s) | reason |
|---|---|---|
| `database/pool.py` | 60 | Rollback + re-raise is the correct pattern; outer callers handle the exception. |
| `auth.py` | 30 | Silent `return False` on bcrypt failure prevents timing-based side channels. |
| `routes/dashboard.py` | 238, 304 | `conn.close()` in cleanup blocks — errors here must not propagate. |
| `jobs/database.py` | 58, 85 | JSON decode of enrichment data — broken rows are silently skipped to keep the list rendering. |
| `services/session_persistence.py` | 230–231 | Per-row JSON parse failure in `get_user_sessions` inner loop — `continue` skips broken rows cleanly. |

---

## 3. High-Priority Areas

### DB write-through failures

`routes/deps.py` write-through functions (`write_through_topic_progress`, `write_through_modular_progress_snapshot`, `write_through_todos`, `write_through_generated_learning_state`, `write_through_usage_events`) all already log with `get_logger("routes.write_through").warning(...)` and `safe_error_metadata`. **No action needed.**

### Content cache read/write failures

`services/content_service.py:62-63` (cache read) and `205-206` (cache write) are both silent. A cache read failure means every subsequent request for that topic/track content hits Claude directly, silently burning API quota. A cache write failure means newly generated content is not persisted for reuse. Both should emit `logger.warning`. The write failure is the first implementation slice (§5).

### Modular progress snapshot failures

`services/modular_progress_snapshot_service.py:114` catches all exceptions and returns a dict with a sanitized `error` field. The function itself does not log. The caller `write_through_modular_progress_snapshot` in `routes/deps.py` raises a `RuntimeError` on failure and then logs it with `safe_error_metadata`. **The failure IS logged, but only one level up.** Adding a `logger.warning` inside the service itself would make failures observable without a call stack trace, which is useful for beta monitoring.

### Onboarding enrollment failures

`routes/onboarding.py:68-69` already logs `logger.warning("onboarding course enrollment failed; continuing without DB enrollment")`. The message does not include the exception type or safe metadata, so the log line is observable but not diagnosable. When the slice for `learner_course_enrollment_service` logging is implemented, this warning should also include `safe_error_metadata(exc)`.

### Beta feedback save failures

`services/beta_feedback_service.py` is a pure validation module with no DB calls and no exception swallowing. DB persistence of feedback is handled by callers; no silent swallows found in this service.

### Debug/admin DB failures

`routes/debug.py` already uses `safe_error_metadata` consistently for all DB-related exception blocks (lines 669–671, 769–771, 860–862, 968–970, 1061–1063, 1125–1127). Admin routes use `safe_debug_error_message`. **No action needed here.**

### Job refresh/enrichment failures

`routes/jobs.py:32-37,54` are silent on DB failure (jobs list/stats/detail return empty). These should emit `logger.warning` so beta monitoring can detect when the jobs DB is unreachable. `routes/jobs.py:93-94` (learner context extraction) can be `logger.debug` since it is best-effort context enrichment.

### Claude/AI provider failures

`services/content_service.py` (lines 156/176, 369/391) and `services/submission_service.py` (lines 134, 261, 388) already log `logger.error(...)` with `safe_error_metadata` for all Claude API failures. **No action needed.**

---

## 4. Recommended Logging Rules

All logging improvements in AI² must follow these rules:

1. **Learner-facing behavior must remain unchanged.** Adding a log line never changes a return value, HTTP status code, redirect, or template rendering. If the existing fallback is `return []`, `return None`, or a disabled-summary dict, that fallback is preserved exactly.

2. **Never expose secrets, DB URLs, or API keys in log output.** Use `core.logging.safe_error_metadata(exc)` for structured safe metadata. Use `routes.deps.safe_debug_error_message(exc)` for human-readable safe summaries. Never log `str(exc)` directly unless its source is known-safe (e.g., a locally constructed `RuntimeError` with a fixed message).

3. **Include only safe contextual fields.** `session_id` (a UUID) is safe to log. `user_id` (a UUID) is safe to log at warning level. `topic_id` and `track_key` are safe. `user_message` content, `assistant_reply` text, email addresses, and display names are **never** logged.

4. **Use `logger.warning` for expected fallback failures.** DB read/write failures that degrade gracefully to an in-memory fallback or empty-list response are `warning` severity. They are expected in unhealthy environments and must not trigger alerts on their own.

5. **Use `logger.exception` for unexpected errors.** Code paths that should never fail in normal operation (e.g., orchestrator errors, un-caught Claude client errors before they are caught by the typed exception handlers) should use `logger.exception(...)` so the full traceback is captured.

6. **Keep existing safe user-facing messages.** Where a route already returns a helpful generic 500 message to the user, preserve it. Only scrub messages that currently include raw `str(exc)` output (see §2c).

7. **Use the module-level `logger = logging.getLogger(__name__)` pattern.** Do not use `print()`. Do not create new loggers inside except blocks. Do not import loggers lazily inside except blocks when a module-level logger suffices.

---

## 5. First Implementation Slice

**Recommended: shared content cache write failure in `services/content_service.py:205-206`.**

```python
# current
try:
    shared_cache_write(content, model)
except Exception:
    pass

# recommended
try:
    shared_cache_write(content, model)
except Exception as exc:
    logger.warning(
        "shared content_cache write failed: %s",
        safe_error_metadata(exc, topic_id=..., track_key=...),
    )
```

**Why this slice:**
- The failure is currently completely invisible. A broken content cache silently causes every identical topic/track request to regenerate content from Claude, burning API quota and increasing latency.
- The fix is a 3-line change: `except Exception:` → `except Exception as exc:`, remove `pass`, add `logger.warning(...)`.
- `content_service.py` already has a module-level `logger` and already uses `safe_error_metadata` for Claude errors — no new imports needed.
- The `topic_id` and `track_key` context variables are already in scope at the call site.
- Zero behavior change: the function returns the generated content dict whether or not the cache write succeeds.
- Low blast radius: only the logging line changes, not the control flow.

**Second slice (after first is merged and verified):** `routes/dashboard.py:98-99` — display_name DB fetch silent pass → `logger.warning`. Low-risk, one line, improves visibility of DB connectivity issues on the dashboard.

---

## 6. Test Plan

Before implementing any logging change:

1. **Behavior unchanged.** The existing test suite (`tests/test_chat_routes_split.py`, `tests/test_topics_routes.py`, `tests/test_dashboard_summary.py`, `tests/test_onboarding_flow.py`, `tests/test_todo_routes.py`) must pass without modification after adding any log line. No route response, status code, or redirect may change.

2. **Log emitted on failure.** For each added `logger.warning` or `logger.exception`, write a focused test that monkeypatches the failing call (e.g., `shared_cache_write` raises `RuntimeError`), captures log output via `caplog`, and asserts the expected log message key is present (e.g., `"shared content_cache write failed"` or `"content_cache"` in the log record message).

3. **No secrets in logs.** Each logging test must assert that `caplog` records do not contain:
   - Any value matching a DB URL pattern (`postgres://`, `SUPABASE_DATABASE_URL`)
   - Any value matching an API key pattern (`sk-ant-`, `ANTHROPIC_API_KEY`)
   - Raw user message content or assistant reply text
   - Email addresses

4. **Existing route tests still pass.** Run the full regression suite defined in `tests/test_session_cache_eviction.py`, `tests/test_core_session_persistence_split.py`, and all route split tests after each logging change.

5. **TEST_MODE not affected.** In `TEST_MODE=1`, DB calls that trigger the new warnings are already no-ops or return empty — the warning paths will not fire. Tests should confirm this by running in TEST_MODE and asserting the relevant `caplog` records are absent.
