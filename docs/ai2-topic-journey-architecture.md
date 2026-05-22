# AI² Topic Journey Architecture

## 1. Product Summary

AI² is an adaptive AI learning platform that guides learners through a structured 5-week curriculum.
Each week contains a set of **topics**. For every topic, the learner follows a five-step journey:
read AI-generated content, take a quiz, complete a portfolio task, practice interview questions,
and write a reflection. Claude generates all content and feedback on demand. A dashboard, planner,
and progress system keep the learner oriented and motivated throughout.

---

## 2. Core Learner Flow

```
Dashboard
  └─ Topics page (/topics/{session_id})
       └─ Topic Detail (/topic/{session_id}/{topic_id})
            ├─ Generate Learning Content  → read, mark in_progress / done
            ├─ Generate Quiz              → submit answers → AI evaluation → quiz done
            ├─ Generate Portfolio Task    → submit work    → AI feedback   → portfolio done
            ├─ Generate Interview Qs      → submit answer  → AI feedback   → interview done
            └─ Write Reflection Notes                                      → reflection done
                 └─ Progress updates → Week Summary → Dashboard Summary
                      └─ Planner (/todos/{session_id})
```

---

## 3. Main Pages

| Route | Template | Purpose |
|---|---|---|
| `/dashboard` | `dashboard.html` | Home: stats bar, resume card, learning summary (3 cards), start-new-track |
| `/topics/{session_id}` | `topics.html` | Week topic grid: per-topic progress bar, step chips, smart continue button, week summary card |
| `/topic/{session_id}/{topic_id}` | `topic_detail.html` | Full topic journey: 4 AI content sections + reflection card + notes form |
| `/todos/{session_id}` | `todos.html` | Daily/weekly planner: create, complete, reorder todos |
| `/chat/{session_id}` | `chat.html` | Free-form AI learning coach conversation |
| `/syllabus/{session_id}` | `syllabus.html` | Full 5-week syllabus with phase/task breakdown and week navigation |

---

## 4. Route Modules

**`app.py`** — Core application layer. Owns: app setup, auth middleware, session start/restore,
chat endpoint, practice-arena endpoints (`/quiz`, `/interview`, `/evaluate`), syllabus, jobs,
dashboard route, `build_dashboard_learning_summary()` helper, `_run_blocking`, and the dependency
injection block that wires shared objects into `routes/deps.py` at startup.

**`routes/topics.py`** — Topic browsing and journey routes:
`GET /topics/{session_id}`, `GET /topic/{session_id}/{topic_id}`,
`POST /topic/progress`, `POST /topic/notes`,
`POST /topic/content/generate`, `POST /topic/practice/generate`.
Also owns `get_next_topic_step()` (re-exported from app.py for backward compat).

**`routes/todos.py`** — Planner routes:
`GET /todos/{session_id}`, `POST /todos/create`, `POST /todos/status`.

**`routes/submissions.py`** — Submission and AI feedback routes:
`POST /quiz/submit`, `POST /quiz/evaluate`,
`POST /portfolio/submit`, `POST /portfolio/feedback`,
`POST /interview/submit`, `POST /interview/feedback`.

**`routes/deps.py`** — Shared runtime dependency slots. Module-level variables (`templates`,
`get_session_data`, `save_session`, `session_progress`, `make_client`, `run_blocking`, `TEST_MODE`)
are set to `None` at import time and populated by app.py after all helpers are defined. Route
modules import `routes.deps as deps` and call `deps.*` — never importing private app.py symbols
directly. This avoids circular imports.

---

## 5. SessionContext State

All learner state lives in a single `SessionContext` dataclass, serialized as JSON and persisted
to the `sessions` PostgreSQL table on every write.

| Field | Type | Purpose |
|---|---|---|
| `topic_progress` | `dict[topic_id, dict[step, status]]` | Per-topic step statuses: `not_started` / `in_progress` / `done` |
| `generated_topic_content` | `dict[topic_id, dict]` | Cached AI-generated learning content + metadata |
| `generated_topic_practice` | `dict[topic_id, dict[type, dict]]` | Cached quiz / portfolio / interview practice content |
| `quiz_submissions` | `dict[topic_id, dict]` | Learner answers + AI evaluation + score |
| `portfolio_submissions` | `dict[topic_id, dict]` | Learner submission + AI feedback + score |
| `interview_submissions` | `dict[topic_id, dict]` | Learner answer + AI feedback + score |
| `topic_notes` | `dict[topic_id, dict]` | Reflection, confusions, application idea per topic |
| `todos` | `list[dict]` | Daily/weekly planner items with status, type, linked topic |

`SessionContext.from_dict()` uses `.get()` with defaults for every field to remain backward
compatible as new fields are added.

---

## 6. AI / Claude Usage

All Claude calls go through `anthropic.Anthropic` via the `_make_client()` helper in app.py.
Calls are dispatched through `_run_blocking()` — a thread-pool wrapper so sync SDK calls don't
block the async FastAPI event loop.

| Feature | Trigger | Max tokens |
|---|---|---|
| Learning content | `POST /topic/content/generate` | 1 500 |
| Practice (quiz/portfolio/interview) | `POST /topic/practice/generate` | 1 800 |
| Quiz evaluation | `POST /quiz/evaluate` | 1 000 |
| Portfolio feedback | `POST /portfolio/feedback` | 1 200 |
| Interview feedback | `POST /interview/feedback` | 1 000 |
| Chat / coaching | `POST /chat` | varies |

**TEST_MODE** (`AI2_TEST_MODE=1`): all Claude calls are skipped. Each route returns a hardcoded
deterministic mock response so the full test suite runs without an API key or network.

---

## 7. Progress Logic

**5 topic steps** (in order): `learn` → `quiz` → `portfolio_task` → `interview_practice` → `reflection`.

**Completion %** = `(done_steps / 5) × 100`. Implemented in `SessionContext.topic_completion_percent()`.

**Smart continue button** — `get_next_topic_step(progress)` walks the 5 steps in order and returns
the first step that is not `done`, along with its display label and page anchor. Used on the topic
card in `/topics/{session_id}`.

**Weekly progress summary** (top of `/topics/{session_id}`) — aggregates per-topic completion
percentages for the current week: average %, completed / in-progress / not-started counts.

**Dashboard learning summary** — `build_dashboard_learning_summary(session)` in app.py computes:
week topic stats, planner counts (daily/weekly/done/in-progress todos), and practice counts
(quiz evaluations done, portfolio reviews, interview feedback, reflections saved). Pure function,
no Claude calls.

---

## 8. Current Storage Model

All topic journey data — progress, generated content, submissions, notes, todos — is stored inside
`SessionContext` and serialized as a single JSON blob in the `sessions.session_data` column.

This is intentional for MVP speed: no schema migrations needed to add a new field, and the full
learner state is always a single DB read away.

**Trade-offs to be aware of:**
- The JSON blob grows as the learner progresses; no pagination or partial loads.
- No cross-session querying (e.g., "all quiz scores across a user's sessions") without parsing JSON.
- Concurrency: last write wins if two tabs update the same session simultaneously.

---

## 9. Future Architecture TODOs

- **Normalize topic data to DB tables**: `topic_progress`, `quiz_submissions`, `portfolio_submissions`,
  `interview_submissions`, `topic_notes` should each become a proper table once query needs arise.
- **Service layer**: extract repeated submission+feedback logic (save → Claude call → mark step → save session)
  into a shared `services/topic_feedback.py` instead of duplicating it across `routes/submissions.py`.
- **Content freshness refresh policies**: `generated_topic_content` and `generated_topic_practice`
  have a `freshness_label` field; add a background job to re-generate stale content automatically.
- **Portfolio artifact export**: allow learners to export their portfolio submissions as PDF or Markdown.
- **E2E browser tests**: add Playwright tests for the full topic journey (generate → submit → feedback).
- **LangGraph**: do not introduce LangGraph or multi-step agent graphs until there is a concrete
  workflow that cannot be handled by the existing single-call Claude pattern.

---

## 10. Developer Notes

- **Do not replace the Claude API** with another provider without updating all prompt structures and
  mock responses in TEST_MODE.
- **Preserve `SessionContext.from_dict()` backward compatibility**: always use `.get("field", default)`
  when adding new fields so existing sessions in the DB deserialize without error.
- **Do not change route URLs casually**: JavaScript in `topic_detail.js` and template action links
  hard-code paths like `/topic/progress`, `/topic/notes`, `/topic/content/generate`, etc.
- **Keep the fast TestClient suite green**: `pytest tests/` with `AI2_TEST_MODE=1` must pass on
  every commit. The suite covers 330+ cases across topics, todos, submissions, navigation,
  and dashboard summary — run it before merging any route or session change.
- **deps injection order matters**: `routes/deps.py` slots are populated at the bottom of `app.py`
  after all helper functions are defined. Route modules must never import private app.py symbols
  directly or the circular import will fail at startup.
