# AI² Production Readiness Audit

---

## 1. Current Production Readiness Summary

AI² has a strong production-style architecture foundation. The codebase has layered services, structured AI evaluation via rubrics, safe logging, write-through DB mirrors, fallback services, mismatch checks, and observability endpoints. It reflects real engineering discipline.

However, AI² is **not yet fully public-launch ready**. Several critical risks remain: learner state can be lost on server restart, there is no enforced usage limiting, and auth/user ownership has not been fully verified for multi-user isolation.

AI² is close to **private beta readiness** once the blockers below are addressed. A focused 4–6 week sprint should close the gap.

### Status Summary

| Area                          | Status       |
|-------------------------------|--------------|
| AI generation / rubric eval   | Ready        |
| Harness / prompt engineering  | Ready        |
| DB schema and repositories    | Ready        |
| Write-through DB mirrors      | Ready        |
| Storage health / mismatch     | Ready        |
| Safe logging / usage events   | Ready        |
| SessionContext as source of truth | Blocker  |
| DB-primary reads for learner state | Blocker |
| Content caching               | Blocker      |
| Multi-server / stateless design | Blocker    |
| Auth / user ownership         | Blocker      |
| Usage limit enforcement       | Blocker      |
| Sentry / uptime monitoring    | Needs Work   |
| DB backups / migration plan   | Needs Work   |
| Privacy policy / terms        | Needs Work   |
| Payments                      | Can Wait     |
| Certificates / gamification   | Can Wait     |

---

## 2. Critical Launch Blockers

### Blocker 1 — SessionContext is still the runtime source of truth

**Why it matters:** SessionContext is an in-memory Python object. It exists only for the lifetime of the server process. A server restart, crash, or redeploy wipes all active learner state. In development this is fine. In production it causes silent data loss.

**Production risk:** Learners lose progress, quiz results, todos, and notes after any server restart. This is a trust-destroying event for a real user.

**Recommended fix:** Move each learner state category to DB-primary reads, one category at a time, behind a feature flag. Start with todos and topic progress as the lowest-risk items.

**Priority:** P0 — must fix before private beta.

---

### Blocker 2 — Learner-critical state must become durable in DB

**Why it matters:** The DB write-through mirrors exist but are optional. Learner-facing routes still read from SessionContext. If write-through is off, or if a write fails silently, DB may diverge from in-memory state without anyone noticing.

**Production risk:** Inconsistent state across restarts. Potential for silent data loss even when write-through is enabled, if a write fails and the error is swallowed.

**Recommended fix:** Enable write-through by default. Add write failure alerts. Move learner-facing reads to DB-primary behind a flag and validate with the existing mismatch check endpoints before promoting.

**Priority:** P0 — must fix before private beta.

---

### Blocker 3 — No shared content caching yet

**Why it matters:** AI² currently calls Claude for base lesson content on every request for the same topic. The same lesson for the same topic, level, and language should not trigger a fresh LLM call every time.

**Production risk:** Unnecessary API cost, higher latency, and inconsistent content across learners for what should be a stable base lesson.

**Recommended fix:** Implement a content cache table (topic + level + language + content_type + version) with a cache-first lookup in the lesson generation service. See Section 5 for full scope.

**Priority:** P0 — must fix before private beta.

---

### Blocker 4 — Single-server assumption must be removed

**Why it matters:** SessionContext is per-process. If the app runs behind a load balancer with two FastAPI workers, two different users may be assigned to different workers, and one worker will have no knowledge of state written to the other.

**Production risk:** Intermittent data loss, 404-style behavior, or silently stale state on horizontally scaled deployments. Even a single-server setup with Gunicorn workers has this risk.

**Recommended fix:** Move to DB-primary reads. Once learner state is read from PostgreSQL instead of in-process memory, the app becomes stateless and safe to run with multiple workers or instances.

**Priority:** P0 — must fix before private beta.

---

### Blocker 5 — Real auth and user ownership must be verified

**Why it matters:** Learner data must be scoped per authenticated user. Without verified auth and row-level ownership checks, one learner could accidentally or intentionally read or modify another learner's data.

**Production risk:** Data leakage between users. Loss of user trust. Potential compliance issues.

**Recommended fix:** Audit all learner-facing routes to confirm they scope DB queries and SessionContext lookups by authenticated user ID. Confirm session tokens are signed and not guessable. Confirm logout clears state correctly.

**Priority:** P0 — must fix before private beta.

---

### Blocker 6 — Usage limits are not enforced yet

**Why it matters:** The usage policy layer exists and tracks events, but hard limits are not enforced. A single learner could trigger unlimited Claude API calls, driving up cost with no cap.

**Production risk:** Runaway API spend. A single misbehaving or malicious session could cost hundreds of dollars.

**Recommended fix:** Implement soft usage-limit enforcement behind a feature flag. Check the usage event count per user per day before allowing an AI generation request. Return a friendly limit-reached message when the cap is hit.

**Priority:** P0 — must fix before private beta.

---

## 3. Data Durability Audit

| Data Category                 | Currently in SessionContext | DB Mirror Exists | Should Be DB-Primary Before Launch |
|-------------------------------|-----------------------------|------------------|------------------------------------|
| Topic progress                | Yes                         | Yes              | Yes — P0                           |
| Todos                         | Yes                         | Yes              | Yes — P0                           |
| Topic notes / reflections     | Yes                         | Yes              | Yes — P0                           |
| Generated lesson content      | Yes (per request)           | Yes              | Yes — cache-first before launch    |
| Generated practice content    | Yes (per request)           | Yes              | Yes — cache-first before launch    |
| Quiz submissions / evaluations | Yes                        | Yes              | Yes — P0                           |
| Portfolio submissions / feedback | Yes                      | Yes              | Yes — before public launch         |
| Interview submissions / feedback | Yes                      | Yes              | Yes — before public launch         |
| Usage events                  | DB write-through only        | Yes              | Already DB-backed — maintain       |

**Summary:** DB mirrors exist for all critical categories. The remaining work is flipping learner-facing reads from SessionContext to DB-primary, one category at a time, behind flags.

---

## 4. Scalability Audit

### Current state

AI² runs as a single FastAPI process. SessionContext holds per-learner runtime state in memory. This works for development and a single-user demo but is not safe for production scale.

### Risks to address

**In-memory state:** Any in-process state (SessionContext) is invisible to other workers or instances. Horizontal scaling without removing this state breaks the product.

**Single-server assumption:** The current architecture assumes one process owns all active learner sessions. This prevents running multiple Gunicorn workers, deploying to a cloud platform with autoscaling, or running a redundant instance for uptime.

### Path to stateless design

1. Move all mutable learner state from SessionContext to PostgreSQL.
2. Each request reads its required state from the DB, not from an in-process object.
3. The app becomes stateless — any worker can handle any request.
4. No shared in-process cache is needed because state lives in the DB.

### After stateless design is complete

- Multiple FastAPI/Gunicorn workers are safe.
- A load balancer can route to any instance.
- PostgreSQL is the durable single source of truth.
- A Redis or shared cache can be added later for hot content (base lessons) to reduce DB reads.

### What can wait

Kubernetes, microservices, and distributed caching are not needed for private beta or early free trial. PostgreSQL as a primary with a standard cloud deployment is enough for the first 1,000 learners.

---

## 5. AI Cost and Content Caching Audit

### The problem

Base lesson content for a given topic, level, and language is largely stable. Calling Claude on every page load for the same lesson wastes money and introduces latency.

### What should be cached

- Base lesson text for a topic + level + language + content_type + version combination.
- Practice task templates for stable topic/level combinations.

Cache key structure: `topic_slug | level | language | content_type | schema_version`

### What should not be fully cached

- Personalized feedback on quiz, portfolio, and interview submissions. These depend on the learner's specific answer and should always call the model.
- Adaptive or tailored lesson variations that depend on learner history.

### Benefits of caching

- **Cost:** Reduces Claude API calls for repeated base content by a large fraction once learners overlap on the same topics.
- **Consistency:** All learners on the same topic get the same stable base lesson. Feedback quality drift is contained to evaluation calls.
- **Latency:** Cached content returns in milliseconds instead of seconds.

### Recommended implementation

1. Add a `content_cache` table: `(cache_key, topic_slug, level, language, content_type, version, content_json, created_at, hit_count)`.
2. Add a cache lookup service: check DB before calling Claude.
3. On cache miss: call Claude, store result, return to learner.
4. Add a cache hit counter to track effectiveness.
5. Add a `cache_version` field to allow invalidation when prompt templates change.

---

## 6. Learning Effectiveness Audit

### Current strengths

- Rubric-based feedback for quiz, portfolio, and interview submissions provides structured, consistent evaluation.
- Practice tasks are generated contextually.
- Topic notes and reflections are persisted.

### What is missing for a real learning product

**Baseline and post-topic checks:** There is currently no measurement of what a learner knew before starting a topic versus after completing it. Without this, it is impossible to claim the product improves learning outcomes.

- Add a short pre-topic knowledge check before the first lesson.
- Add a post-topic knowledge check after the final quiz.
- Compare scores to show visible improvement.

**Longitudinal quiz score improvement:** Track quiz score across attempts on the same topic. Show learners they are improving. This is a core learning signal.

**Portfolio readiness improvement:** Track portfolio rubric scores across submissions on the same topic. Flag when a learner reaches a "portfolio-ready" threshold.

**Interview readiness improvement:** Track interview rubric scores over time. Show progress toward interview readiness.

**First-session activation:** Define what a successful first session looks like. A learner who reads one lesson and submits one quiz answer is activated. Track this rate.

**Golden eval examples:** Collect a small set of human-reviewed quiz/portfolio/interview answers with expected score ranges. Use these as regression anchors when changing rubrics or prompts.

---

## 7. Security and Privacy Audit

### Auth

- Verify that all learner-facing routes require a valid authenticated session.
- Confirm session tokens are signed and use a secret that is not hardcoded.
- Confirm logout invalidates the session server-side.

### User ownership

- Every DB query that reads or writes learner data must be scoped by authenticated user ID.
- No learner should be able to access another learner's todos, notes, quiz results, or submissions by manipulating request parameters.

### Secure sessions and cookies

- Confirm session cookies are `HttpOnly` and `SameSite=Lax` or `Strict`.
- Confirm cookies are `Secure` in production (HTTPS only).
- Confirm session secret is loaded from environment, not committed to code.

### No secrets in logs or debug views

- Confirm that the safe logging layer never logs API keys, session tokens, or raw user answers.
- Confirm that debug endpoints do not expose raw DB credentials or full stack traces to unauthenticated requests.

### Debug endpoints before public launch

- All debug and observability endpoints (`/debug/`, `/storage-status/`, `/mismatch/`) must require internal or admin auth before public launch.
- These endpoints expose internal architecture details and should not be publicly accessible.

### Privacy policy and terms of use

- A privacy policy page is required before collecting any learner data from real users.
- A terms of use page is required before public launch.
- Both should clearly state what data is collected, how it is used, and how learners can request deletion.

### User data export and deletion

- Can wait for private beta but should be planned before public free trial.
- A learner should be able to request export or deletion of their data.

---

## 8. Observability and Operations Audit

### Current strengths

- Safe logging layer is in place.
- Usage events are written to DB.
- Storage health endpoints expose mirror status and mismatch counts.
- Mismatch check services allow comparing in-memory vs DB state.

### What is missing

**Error tracking:** There is no integration with an error aggregator such as Sentry. Unhandled exceptions in production will silently fail unless logs are actively watched. Add Sentry before private beta.

**Uptime monitoring:** There is no external ping that confirms the app is alive. Add a simple uptime check (UptimeRobot or equivalent) before private beta. Alert on downtime.

**DB backups:** Confirm that the PostgreSQL instance (Supabase or equivalent) has automated backups enabled. Know the recovery point objective. Test that a restore works.

**Migration and rollback process:** Document the migration run process. Each DB schema change should have a clear rollback path. Do not apply migrations to production without a tested rollback plan.

**Structured logging for learner actions:** Consider structured JSON log lines for key learner events (lesson started, quiz submitted, portfolio submitted). These become useful for debugging and for lightweight analytics without a full analytics pipeline.

---

## 9. Free Trial Launch Requirements

These are the minimum requirements for a Month 1 free trial with real learners.

| Requirement                         | Status       | Notes                                      |
|-------------------------------------|--------------|--------------------------------------------|
| Signup and login                    | Needs Work   | Verify auth is complete and scoped         |
| Durable learner progress            | Blocker      | Move to DB-primary reads                   |
| Content caching for base lessons    | Blocker      | Implement cache-first lesson service       |
| Usage limits enforced               | Blocker      | Soft cap behind flag                       |
| One strong learning path end-to-end | Ready        | Core AI flows work                         |
| Feedback form for beta users        | Needs Work   | Simple form, email or Airtable             |
| Basic error monitoring              | Needs Work   | Sentry integration                         |
| Uptime check                        | Needs Work   | UptimeRobot or equivalent                  |
| Privacy policy page                 | Needs Work   | Required before collecting real user data  |
| Terms of use page                   | Needs Work   | Required before public access              |
| Debug endpoints protected           | Blocker      | Must require auth before public launch     |

---

## 10. What Can Wait

These are real features but they are not required for a private beta or Month 1 free trial.

- **Payments and subscriptions** — Wait until the free trial validates product-market fit.
- **Certificates and completion badges** — Nice to have; not a learning product requirement.
- **Complex gamification** — Streaks, leaderboards, XP systems can come later.
- **Community features** — Forums, peer review, cohorts — all post-beta.
- **Mobile app** — The web app is sufficient for early learners.
- **Multi-model routing** — Switching between Claude models per task is an optimization for later.
- **Complex agent workflows** — The current orchestrator + sub-agents pattern is appropriate for now.
- **Kubernetes and microservices** — Not needed until traffic exceeds a single well-configured server.
- **Advanced admin analytics** — A simple dashboard with learner counts and usage totals is enough for beta.
- **User data export/delete UI** — Plan the data model now; build the UI after beta.

---

## 11. Recommended Next Build Order

Execute in this order. Each item unblocks the next.

1. **Auth and user ownership review** — Audit all learner routes for correct scoping. Confirm session security. This is the foundation for everything else.

2. **DB-primary reads for todos behind flag** — Low risk. Todos have a DB mirror. Flip the read source behind a flag and validate with existing mismatch checks.

3. **DB-primary reads for topic progress behind flag** — Same pattern as todos. Once validated, enable by default.

4. **Content cache schema** — Add the `content_cache` table with the key structure defined in Section 5.

5. **Content cache service** — Implement cache-first lookup before calling Claude for base lessons.

6. **Use cache for base lessons** — Wire the cache service into the lesson generation flow. Confirm cache hits appear in the health endpoints.

7. **Usage limit enforcement behind flag** — Soft cap per user per day. Check before allowing AI generation calls. Return a friendly message on cap hit.

8. **Baseline and post-topic learning outcome flow** — Add pre-topic and post-topic knowledge checks. Store results. Show improvement.

9. **Onboarding flow** — First-session experience. Goal, track selection, first lesson. Define activation.

10. **Private beta launch checklist** — Sentry, uptime monitoring, privacy policy, terms, debug endpoint auth, DB backup confirmed, first 5 internal testers complete one full path.

---

## 12. Private Beta Exit Criteria

AI² is ready for a public free trial when all of the following are true:

- No learner data is lost after a server restart or redeploy.
- Learner topic progress, todos, notes, and submission history persist correctly.
- Core AI flows (lesson, practice, quiz, portfolio, interview) work reliably without unhandled errors.
- Repeated lesson requests for the same topic return cached content without calling Claude.
- Usage limits are active and a learner who hits the cap sees a clear message instead of an error.
- The first 20–50 beta users have each completed at least one full learning path end-to-end.
- At least some learners show measurable improvement between pre-topic and post-topic checks.
- Cost per learner per session is measurable and within an acceptable range.
- No P0 or P1 bugs are open.
- Debug and internal endpoints require auth or are not publicly reachable.
- Privacy policy and terms of use pages are live.
