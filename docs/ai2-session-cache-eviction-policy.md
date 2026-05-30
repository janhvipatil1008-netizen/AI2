# AI² Session Cache Eviction Policy

## 1. Current State

`_sessions` is a plain Python `dict[str, dict]` declared at `app.py:90`:

```python
_sessions: dict[str, dict] = {}
```

It is the in-memory runtime cache owned by `app.py` for the lifetime of the server process. Each entry is keyed by `session_id` (a UUID string) and contains four objects:

| key | type | description |
|---|---|---|
| `"session"` | `SessionContext` | Full learner state: history, topic progress, generated content, submissions, usage events, todos, onboarding profile. |
| `"orch"` | `Orchestrator` | Agent router. Holds references to `session` and `client`. |
| `"client"` | `anthropic.Anthropic` | Stateless Anthropic HTTP client. Small. |
| `"profile"` | `LearnerProfile \| None` | Learner profile loaded from PostgreSQL at session restore time. |

The cache is written to `routes.deps.session_cache` at startup (`app.py:493`) so route modules can read it directly. Reads go through `services/session_persistence.py::get_session_data`, which checks the cache first and falls back to PostgreSQL on a miss.

There is no TTL, no max-size cap, no LRU eviction, and no background cleanup. Entries accumulate indefinitely for the lifetime of the process.

---

## 2. Problem

Without eviction, `_sessions` grows monotonically as users start sessions. During beta each new session adds one entry and nothing removes it.

The dominant memory cost per entry is the `SessionContext` object, which contains:

- **`history`**: an unbounded list of `ExchangeRecord` objects. Each exchange stores the full user message and assistant reply. Replies from learning-coach and practice-arena agents can be 500–3 000 characters each. A learner doing 50 exchanges accumulates roughly 50–150 KB in this field alone.
- **`generated_topic_content`**: a dict keyed by `topic_id`, each value holding AI-generated lesson text (~2–5 KB per topic). A learner who explores 10 topics stores 20–50 KB here.
- **`generated_topic_practice`**: similar to above; three practice types per topic (quiz, portfolio_task, interview_practice) at ~3–6 KB each adds another 30–180 KB for an active learner.
- **`portfolio_submissions`, `quiz_submissions`, `interview_submissions`**: smaller but grow with engagement.
- **`usage_events`**: a list of lightweight dicts; grows linearly with AI calls.

Rough per-entry size estimate: **100 KB – 1 MB** depending on session depth.

At beta scale the absolute numbers are manageable today (10–50 concurrent users × 500 KB ≈ 5–25 MB). The risk is that sessions from inactive users, abandoned sessions, and test runs are never freed. A single-worker Render instance running for several weeks of beta can accumulate hundreds of stale entries, pushing resident memory up silently until the process is OOM-killed or recycled.

A second problem is predictability: no cap means there is no upper bound on memory that can be stated, monitored, or tested.

---

## 3. Eviction Policy Goals

Any eviction policy for `_sessions` must satisfy the following goals, in priority order:

1. **No cross-user data leakage.** Evicting a session must only remove the in-memory entry. It must never delete or corrupt the corresponding PostgreSQL row. After eviction, the next request for that session must restore from DB and re-validate ownership via the existing ownership-check path in `get_session_data`.

2. **No route changes and no URL changes.** The `_sessions` dict is exposed to route modules as `deps.session_cache`. The eviction mechanism must remain dict-compatible so routes that do `deps.session_cache[session_id]` or `session_id in deps.session_cache` continue to work without modification.

3. **No data loss for active users.** A session that is actively used must not be evicted mid-flight. Eviction must only target entries that are idle (not recently accessed).

4. **DB-restorable.** Every evicted session must be retrievable from PostgreSQL because `save_session` writes through on every mutation. Eviction is purely a memory-management operation.

5. **Observable.** The policy must be log-friendly: it should be possible to emit a structured log line when an entry is evicted so memory behaviour can be monitored during beta.

---

## 4. Policy Options

### Option A — LRU cap only (`cachetools.LRUCache`)

Evict the least-recently-used entry when the count reaches a configured maximum.

- **Pros**: simple, bounded memory, deterministic worst-case count.
- **Cons**: no time-based cleanup; a long-running but low-traffic server with fewer than `maxsize` sessions never frees any memory. Requires adding `cachetools` to `requirements.txt` (not currently listed).

### Option B — Fixed TTL from insertion (`cachetools.TTLCache`)

Evict any entry whose age since insertion exceeds a fixed TTL, also enforcing a max-size cap.

- **Pros**: simple drop-in replacement for `dict`; TTLCache is a dict subclass. Provides both time-based and count-based eviction.
- **Cons**: TTL is measured from insertion, not last access. A user who starts a session, works for 2 hours, and then the TTL (say 1 hour) fires will be silently evicted and pay one DB restore round-trip on their next message. This is non-fatal but surprising. Requires `cachetools`.

### Option C — Background sweep with last-accessed tracking

Keep `_sessions` as a plain `dict`. Add a parallel `dict[str, float]` (`_sessions_last_accessed`) that records `time.monotonic()` on every read and write. A FastAPI `startup` background task runs periodically (e.g., every 10 minutes) and removes entries where `time.monotonic() - last_accessed[id] > TTL`.

- **Pros**: correct inactivity semantics; no new dependencies; works with existing dict interface; transparent to routes.
- **Cons**: more code than a drop-in replacement; sweep interval introduces latency between a session going idle and being freed; requires a background thread or asyncio task.

### Option D — Stdlib `functools.lru_cache` / `OrderedDict` LRU

Implement LRU manually using `collections.OrderedDict`.

- **Pros**: no new dependencies; full control.
- **Cons**: requires implementing dict protocol correctly; more error-prone; no TTL unless combined with background sweep.

---

## 5. Recommended Policy

**Hybrid: LRU cap + inactivity TTL via background sweep (Option C combined with an LRU cap).**

Specifically:

| parameter | recommended value | rationale |
|---|---|---|
| Max entries | **500** | Generous for beta (hundreds of learners). At 500 KB per entry, worst case is 250 MB, well within a 512 MB Render instance. |
| Inactivity TTL | **1 800 seconds (30 minutes)** | A learner who closes the browser or is inactive for 30 minutes is unlikely to be mid-exchange. DB restore on return is fast. |
| Sweep interval | **600 seconds (10 minutes)** | Balances cleanup frequency against background overhead. |

The background sweep approach is preferred over `cachetools` because:
1. `cachetools` is not currently in `requirements.txt` — adding a dependency for a single dict is a larger change than the eviction logic itself.
2. Inactivity semantics (TTL from last access) are correct for a session cache; TTL from insertion would evict active users.
3. The background sweep is independently testable and produces clear log output.

The LRU cap (max 500 entries) acts as a hard safety ceiling independent of TTL, protecting against abnormal traffic patterns during beta.

---

## 6. Implementation Approach

This section describes the planned implementation. **Do not implement until the policy is approved and a dedicated implementation PR is opened.**

### 6.1 Data structures to add to `app.py`

```python
import time

_sessions: dict[str, dict] = {}          # existing — no change
_sessions_last_accessed: dict[str, float] = {}  # new: session_id → monotonic timestamp
_SESSION_MAX_ENTRIES = 500
_SESSION_TTL_SECONDS = 1800              # 30 minutes inactivity
_SESSION_SWEEP_INTERVAL_SECONDS = 600   # 10 minutes
```

### 6.2 `_session_touch` helper

A single helper updates `_sessions_last_accessed` on every read and write to `_sessions`. It is called by:
- `get_session_data` after a cache hit and after a DB-restore write.
- `_save_session` after writing the updated entry.

```python
def _session_touch(session_id: str) -> None:
    _sessions_last_accessed[session_id] = time.monotonic()
```

### 6.3 LRU cap enforcement

When `get_session_data` adds a new entry to `_sessions`, check the count:

```python
if len(_sessions) >= _SESSION_MAX_ENTRIES:
    oldest_id = min(_sessions_last_accessed, key=_sessions_last_accessed.get)
    _sessions.pop(oldest_id, None)
    _sessions_last_accessed.pop(oldest_id, None)
    logger.info("session_cache_evict_lru session_id=%s", oldest_id)
```

This is called inside `get_session_data` in `services/session_persistence.py`, which already receives `session_cache` as a parameter. The LRU cap logic can be encapsulated in a small helper passed in alongside `session_cache`, keeping persistence logic in the service layer and cache-management logic in `app.py`.

### 6.4 Background sweep

Register a FastAPI `lifespan` or `startup` event that starts an asyncio background task:

```python
async def _session_cache_sweep():
    while True:
        await asyncio.sleep(_SESSION_SWEEP_INTERVAL_SECONDS)
        now = time.monotonic()
        expired = [
            sid for sid, last in list(_sessions_last_accessed.items())
            if now - last > _SESSION_TTL_SECONDS
        ]
        for sid in expired:
            _sessions.pop(sid, None)
            _sessions_last_accessed.pop(sid, None)
            logger.info("session_cache_evict_ttl session_id=%s", sid)
        if expired:
            logger.info("session_cache_sweep evicted=%d remaining=%d", len(expired), len(_sessions))
```

In `TEST_MODE`, the sweep should be registered but the TTL should be very large (or the sweep skipped entirely) so tests are not affected by eviction timing.

### 6.5 No changes needed in route modules

Because `_sessions` remains a plain dict and all dict operations (`in`, `[]`, `=`, `.get`) behave identically, route modules do not need changes. `deps.session_cache = _sessions` continues to pass the same dict reference.

---

## 7. Safety Requirements

The following invariants must be verified before implementation merges:

1. **Eviction never deletes from PostgreSQL.** `_sessions.pop(sid)` removes only the in-memory entry. The `sessions` table row must remain intact. Verify with an integration test that evicts a session and then verifies the row still exists in DB.

2. **Ownership check survives eviction.** After eviction, a request from `user-b` for a session owned by `user-a` must still raise HTTP 403. The ownership check in `get_session_data` runs on every DB restore path. Verify with a test: create session as user-a, evict from cache, request as user-b, expect 403.

3. **Active sessions are not evicted mid-request.** FastAPI request handlers are async. The sweep task runs in the same event loop. Because Python's asyncio cooperative scheduler will not preempt a handler mid-await, the sweep can only run between awaits. The LRU cap eviction runs synchronously inside `get_session_data` before the entry is added, so it cannot evict the entry being added. These properties mean mid-request eviction is not possible without a race between threads. Confirm `_executor` thread pool does not mutate `_sessions` directly outside of `get_session_data`.

4. **`_sessions_last_accessed` stays in sync.** Every path that writes to `_sessions` must call `_session_touch`. Every path that pops from `_sessions` must also pop from `_sessions_last_accessed`. A test that patches `time.monotonic` can verify this.

5. **TEST_MODE sweep does not interfere with tests.** Set `_SESSION_TTL_SECONDS = 86400` (24 hours) in TEST_MODE, or register the sweep but check `TEST_MODE` at the top of the loop and skip eviction.

6. **No eviction during `_startup_db`.** The cache is empty at startup so no eviction fires during schema initialization.

---

## 8. Test Plan

New tests to write in `tests/test_session_cache_eviction.py` before implementing:

| test | what it verifies |
|---|---|
| `test_lru_cap_evicts_oldest_entry` | When `_SESSION_MAX_ENTRIES` is reached, the entry with the oldest `last_accessed` is removed from both `_sessions` and `_sessions_last_accessed`. |
| `test_lru_cap_does_not_delete_from_db` | After LRU eviction, the evicted `session_id` is absent from the cache but present in the DB. |
| `test_ttl_sweep_removes_idle_session` | After `_SESSION_TTL_SECONDS` elapses (mocked with `monkeypatch` on `time.monotonic`), the sweep removes the idle entry. |
| `test_ttl_sweep_keeps_recently_accessed_session` | A session touched within the TTL window is not removed by the sweep. |
| `test_ownership_check_survives_eviction` | A session evicted from cache, then requested by a different `user_id`, raises HTTP 403 on DB restore. |
| `test_session_touch_called_on_cache_hit` | `_sessions_last_accessed[sid]` is updated after a cache-hit read. |
| `test_session_touch_called_on_db_restore` | `_sessions_last_accessed[sid]` is set after a DB-restore write. |
| `test_test_mode_sweep_does_not_evict` | In TEST_MODE, no entries are evicted regardless of `last_accessed` age. |
| `test_eviction_log_lines_emitted` | A structured log line is emitted at `INFO` level for each evicted entry. |

Existing tests to confirm still pass after implementation:

- `tests/test_core_session_persistence_split.py` — all 8 tests must pass unchanged.
- `tests/test_session_ownership.py` — all ownership/403 tests must pass.
- `tests/test_chat_routes_split.py` — cache hit and DB-restore paths must pass.
- `tests/test_dashboard_routes_split.py` — TEST_MODE session-cache reads must pass.

---

## 9. Relationship to `ai2-session-persistence-audit.md`

This document fulfils the prerequisite named in the persistence audit (Section 5 and Section 6): "In-memory `_sessions` scaling risk" and "After moving persistence helpers, add TTL or LRU eviction for `_sessions`."

The migration order from that audit remains in effect:

1. ✅ History helpers moved to `services/session_persistence.py`.
2. ✅ `get_user_sessions`, `load_profile_db`, `save_profile_db` moved.
3. ✅ `get_session_data`, `save_session` moved.
4. **Next**: Implement eviction using this policy (this document is the prerequisite).
5. **After eviction is implemented and tested**: `_sessions` may optionally be moved to `services/session_persistence.py` as a module-level cache, or wrapped in a dedicated `SessionCache` class.

Do not move `_sessions` out of `app.py` until the eviction implementation is complete and the test suite in Section 8 passes.

---

## 10. Open Questions

These should be resolved before implementation begins:

1. **Single worker vs. multi-worker**: Render free/starter tier typically runs a single Uvicorn worker. If horizontal scaling is added, each worker will have its own `_sessions` dict; a user routed to a different worker will always pay a DB restore round-trip. This is acceptable for beta but should inform whether a shared Redis-backed cache is planned post-beta.

2. **`_SESSION_MAX_ENTRIES` tuning**: 500 is a conservative starting estimate. Beta traffic metrics (from Render's memory graph) should be used to calibrate this value before the first production deploy with eviction enabled.

3. **`_load_session_from_db` in `app.py`**: The persistence audit identifies this function as a dormant duplicate of the DB-restore path in `get_session_data`. It should be removed before implementing eviction to avoid creating a second code path that bypasses `_session_touch`.
