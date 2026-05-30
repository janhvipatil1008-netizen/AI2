# AI² LangSmith Observability Plan

## 1. Purpose

AI² makes Claude API calls across two distinct paths. During beta, failures are currently invisible beyond the existing `logger.error` lines. LangSmith adds:

- **Tracing** — full input/output/latency visibility per call, without adding per-route logging boilerplate
- **Debugging** — reproduce exact prompt + response for any failing session
- **Prompt/eval visibility** — compare prompt versions side by side across runs
- **Beta quality monitoring** — track error rates, latency p95, and cache-hit ratios at the call level, not just the route level

LangSmith is kept **off by default** (`LANGSMITH_TRACING=false`). It activates only when the API key is present and the flag is explicitly set to `true`. No tracing data is sent unless opted in.

---

## 2. AI Call Inventory

| flow name | file / function | path | model | user-facing feature | tracing priority |
|---|---|---|---|---|---|
| Generate Lesson | `services/content_service.py` → `generate_learning_content_for_topic` | structured | `claude-sonnet-4-6` (passed as `model` arg) | Topic learning content page | **P1** |
| Generate Quiz content | `services/content_service.py` → `generate_practice_content_for_topic` (quiz) | structured | `claude-sonnet-4-6` | Topic quiz tab | **P1** |
| Generate Portfolio Task | `services/content_service.py` → `generate_practice_content_for_topic` (portfolio_task) | structured | `claude-sonnet-4-6` | Topic portfolio tab | **P1** |
| Generate Interview Practice | `services/content_service.py` → `generate_practice_content_for_topic` (interview_practice) | structured | `claude-sonnet-4-6` | Topic interview tab | **P1** |
| Quiz Feedback | `services/submission_service.py` → `evaluate_quiz_answers` | structured | `claude-sonnet-4-6` | Quiz submit → feedback | **P1** |
| Portfolio Feedback | `services/submission_service.py` → `generate_portfolio_feedback` | structured | `claude-sonnet-4-6` | Portfolio submit → feedback | **P1** |
| Interview Feedback | `services/submission_service.py` → `generate_interview_feedback` | structured | `claude-sonnet-4-6` | Interview submit → feedback | **P1** |
| Chat / Routing | `orchestrator.py` → `Orchestrator.process` (routing call) | chat/orchestrator | `claude-sonnet-4-6` (`ORCHESTRATOR_MODEL`) | POST /chat routing decision | **P2** |
| Chat / Synthesis | `orchestrator.py` → `Orchestrator.process` (synthesis call) | chat/orchestrator | `claude-sonnet-4-6` | POST /chat final reply | **P2** |
| Learning Coach | `agents/learning_coach.py` → `respond` | chat/orchestrator | `claude-sonnet-4-6` (`AGENT_MODEL`) | Chat — learning advice | **P2** |
| Idea Generator | `agents/idea_generator.py` → `respond` | chat/orchestrator | `claude-sonnet-4-6` (`AGENT_MODEL`) | Chat — project ideas | **P2** |
| Practice Arena (MCQ) | `agents/practice_arena.py` → `generate_mcq_quiz` | chat/orchestrator | `claude-sonnet-4-6` (`AGENT_MODEL`) | Chat — quick quiz | **P2** |
| Practice Arena (Interview Qs) | `agents/practice_arena.py` → `generate_interview_questions` | chat/orchestrator | `claude-sonnet-4-6` (`AGENT_MODEL`) | Chat — interview prep | **P2** |
| Practice Arena (Eval) | `agents/practice_arena.py` → `evaluate_answer` | chat/orchestrator | `claude-sonnet-4-6` (`AGENT_MODEL`) | Chat — answer evaluation | **P2** |
| Job Search Agent | `agents/job_search_agent.py` → `respond` | chat/orchestrator | `claude-sonnet-4-6` (`AGENT_MODEL`) | Chat — job search | **P3** |

---

## 3. First Tracing Scope — Structured Learning Path

Trace structured content and feedback generation first. These calls are the most predictable (fixed prompt templates, no multi-turn state), highest value for eval datasets, and easiest to instrument without touching orchestrator state.

**Calls in scope:**

| call | entry point | route trigger |
|---|---|---|
| Generate Lesson | `generate_learning_content_for_topic` | `POST /topics/{id}/generate` |
| Generate Quiz | `generate_practice_content_for_topic(practice_type="quiz")` | `POST /topics/{id}/practice/generate` |
| Generate Portfolio Task | `generate_practice_content_for_topic(practice_type="portfolio_task")` | `POST /topics/{id}/practice/generate` |
| Generate Interview Practice | `generate_practice_content_for_topic(practice_type="interview_practice")` | `POST /topics/{id}/practice/generate` |
| Quiz Feedback | `evaluate_quiz_answers` | `POST /submissions/quiz` |
| Portfolio Feedback | `generate_portfolio_feedback` | `POST /submissions/portfolio` |
| Interview Feedback | `generate_interview_feedback` | `POST /submissions/interview` |

**Why first:**
- All calls go through `harness/prompt_templates.py` — a single wrapping point
- Prompts are deterministic: `topic_id` + `track_key` → fixed template → Claude → structured output
- These are the calls learners depend on most; latency and failure visibility have direct impact
- No session history or multi-turn state to sanitize

---

## 4. Second Tracing Scope — Chat / Orchestrator Path

Trace chat and agent calls after the structured path is stable. These involve multi-turn session history and require more careful metadata sanitization.

**Calls in scope:**

| call | entry point | notes |
|---|---|---|
| Orchestrator routing | `Orchestrator.process` — first `client.messages.create` | Single-turn routing decision; system prompt is large |
| Orchestrator synthesis | `Orchestrator.process` — second `client.messages.create` | Delegates to agent; synthesis merges agent reply |
| Learning Coach | `agents/learning_coach.py:respond` | Two-call pattern (standard + multi-turn context) |
| Idea Generator | `agents/idea_generator.py:respond` | Single call |
| Practice Arena | `agents/practice_arena.py` — `generate_mcq_quiz`, `generate_interview_questions`, `evaluate_answer` | Three distinct call types |
| Job Search Agent | `agents/job_search_agent.py:respond` | Single call; includes job listing context |

**Deferral rationale:**
- Session history (`session.history`) may contain learner messages — must never be sent as raw metadata
- Orchestrator system prompt is large (dynamic, built at runtime from session state) — requires sanitization design before tracing
- Chat latency is already observable via the `source` field on usage events

---

## 5. Safe Metadata Policy

### Allowed in LangSmith run metadata

- `session_id` — UUID safe to include; no PII
- `topic_id` — safe static identifier
- `track_key` — e.g. `"aipm"`, `"mle"` — safe
- `route_type` — e.g. `"structured_content"`, `"chat"` — safe
- `activity_type` — e.g. `"generate_lesson"`, `"quiz_feedback"` — safe
- `model` — e.g. `"claude-sonnet-4-6"` — safe
- `practice_type` — e.g. `"quiz"`, `"portfolio_task"` — safe
- `success` / `status` — `"success"` or `"error"` — safe
- `latency_ms` — numeric — safe
- `from_cache` — boolean — safe
- `usage_limit_blocked` — boolean — safe
- `error_type` — exception class name only (via `safe_error_metadata`) — safe

### Disallowed in LangSmith run metadata

- Raw learner submitted text (quiz answers, portfolio submissions, interview answers)
- Raw learner private notes (`session.notes`)
- Full generated content body (lesson text, quiz content, feedback text)
- API keys (`ANTHROPIC_API_KEY`, `LANGSMITH_API_KEY`)
- Database URLs (`DATABASE_URL`, `SUPABASE_DATABASE_URL`)
- Auth cookies or session tokens
- Personal profile details (display name, email, goals free-text)
- Full exception message strings unless scrubbed via `safe_error_metadata`
- Debug tokens

### Rule

All metadata passed to LangSmith must pass the same check as `safe_error_metadata`: structured fields only, no free-text user content, no credentials.

---

## 6. Environment Variables

Add to `.env` (never commit real values):

```
# LangSmith observability — off by default
LANGSMITH_TRACING=false
LANGSMITH_API_KEY=
LANGSMITH_PROJECT=ai2-render-beta
LANGSMITH_ENDPOINT=https://api.smith.langchain.com
```

**Policy:**
- `LANGSMITH_TRACING=false` is the default. No tracing happens unless explicitly set to `true`.
- If `LANGSMITH_API_KEY` is absent or empty, the wrapper is a no-op even if `LANGSMITH_TRACING=true`.
- CI sets `LANGSMITH_TRACING=false` (or omits the key) so no network calls are made during test runs.
- The production Render environment will set `LANGSMITH_TRACING=true` and the real `LANGSMITH_API_KEY` as a secret env var — never committed to the repo.

---

## 7. Implementation Plan

Each slice is independently mergeable and independently testable. No slice changes learner-facing behavior.

**Slice 1 — Env flags only**
- Add `LANGSMITH_TRACING`, `LANGSMITH_API_KEY`, `LANGSMITH_PROJECT`, `LANGSMITH_ENDPOINT` to `.env.example` (not `.env`)
- Add `langsmith` to `requirements.txt`
- No application code changes

**Slice 2 — `services/llm_observability.py` no-op wrapper**
- Create `services/llm_observability.py` with a `trace_call(name, fn, metadata)` wrapper
- If `LANGSMITH_TRACING != "true"` or `LANGSMITH_API_KEY` is absent: call `fn()` directly and return
- If enabled: wrap with `langsmith.traceable` or `RunTree`
- Zero behavior change: wrapper always calls and returns `fn()` result

**Slice 3 — Trace structured content generation**
- Wrap `generate_learning_content_for_topic` and `generate_practice_content_for_topic` Claude calls via the wrapper
- Metadata: `topic_id`, `track_key`, `model`, `activity_type`, `from_cache`, `latency_ms`
- Tests: assert no network call when disabled, assert metadata fields are safe

**Slice 4 — Trace structured feedback generation**
- Wrap `evaluate_quiz_answers`, `generate_portfolio_feedback`, `generate_interview_feedback`
- Metadata: `topic_id`, `practice_type`, `model`, `activity_type`, `latency_ms`, `score` (numeric only)
- No submission text in metadata

**Slice 5 — Trace chat / orchestrator**
- Wrap `Orchestrator.process` routing and synthesis calls
- Wrap agent `respond` functions
- Metadata: `session_id`, `agent_used`, `model`, `latency_ms`, `turn_count` (numeric)
- Session history must NOT be included in metadata

**Slice 6 — Beta eval datasets**
- Export structured content generation traces as seed eval datasets in LangSmith
- Define evals: content format compliance, feedback score distribution, latency SLOs
- Out of scope until slices 1–5 are verified in production

---

## 8. Test Plan

For each implementation slice, tests must verify:

1. **Tracing disabled = no network call.** Monkeypatch `LANGSMITH_TRACING=false`; assert the LangSmith client `create_run` or equivalent is never called.

2. **Missing API key = no failure.** Set `LANGSMITH_API_KEY=""` with `LANGSMITH_TRACING=true`; assert the wrapper returns the function result without raising.

3. **Safe metadata only.** For each traced call, assert the metadata dict passed to the wrapper does not contain: generated content text, submission text, profile details, API keys, or DB URLs.

4. **AI generation behavior unchanged.** The existing test suite (`test_topic_content.py`, `test_topic_practice.py`, `test_usage_limit_enforcement.py`, `test_content_cache_write_failure_logging.py`) must pass without modification after any tracing wrapper is added.

5. **No secrets logged or sent.** `caplog` assertions on `logger.warning`/`logger.error` records and metadata dicts must not find `sk-ant-`, `ANTHROPIC_API_KEY`, `postgres://`, or `supabase.co`.

6. **Structured and chat paths still pass tests.** The full stable CI suite (`test_chat_routes_split.py`, `test_topics_routes.py`, `test_dashboard_summary.py`, etc.) must pass after each slice.
