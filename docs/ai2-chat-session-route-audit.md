# AI² Chat and Session Route Audit

## 1. Current Chat/Session Routes In app.py

The remaining learner chat/session routes in `app.py` are still defined directly on the FastAPI app. They should be treated as one tightly coupled runtime group until the dependencies below are made explicit in a later split.

| Method | Path | Function | Responsibility |
| --- | --- | --- | --- |
| GET | `/history` | `history_page` | Renders `history.html` with recent persisted conversation history for the current user. Uses `test-user` in test mode. |
| POST | `/session/start` | `start_session` | Creates a `SessionContext`, optionally creates/loads a `LearnerProfile`, creates an Anthropic client and `Orchestrator` outside TEST_MODE, stores the session in `_sessions`, persists it with `_save_session`, and returns `session_id` plus progress. |
| POST | `/chat` | `chat` | Main chat/orchestrator endpoint. Loads session data, validates non-empty input, handles active quiz A/B/C/D answers locally, uses `_mock_orchestrator_response` in TEST_MODE, otherwise calls `Orchestrator.process`, saves session state and conversation history, updates profile exchange count, and returns response/progress. |
| GET | `/progress/{session_id}` | `get_progress` | Loads a session and returns `_session_progress(session)` as JSON. |
| POST | `/quiz` | `quiz` | Legacy direct practice route for MCQ quiz generation. In TEST_MODE returns `_MOCK_RESPONSES["practice_arena_mcq"]`; outside TEST_MODE calls `agents.practice_arena.generate_mcq_quiz`. |
| POST | `/interview` | `interview` | Legacy direct practice route for interview-question generation. In TEST_MODE returns `_MOCK_RESPONSES["practice_arena_interview"]`; outside TEST_MODE calls `agents.practice_arena.generate_interview_questions`. |
| POST | `/evaluate` | `evaluate` | Legacy direct practice route for answer evaluation. In TEST_MODE returns an inline mock evaluation; outside TEST_MODE calls `agents.practice_arena.evaluate_answer`. Current behavior does not call `_save_session` in this route, so a split must preserve that unless intentionally changed later. |
| GET | `/chat/{session_id}` | `chat_page` | Loads the session and renders `templates/chat.html` with `session_id`, progress, and `test_mode`. The `prompt` query parameter is handled client-side inside `chat.html`, not by this route handler. |

Related helpers still in `app.py`:

| Helper | Responsibility |
| --- | --- |
| `_sessions` | In-memory session cache containing `session`, `orch`, `client`, and `profile`. |
| `_save_session` | Best-effort PostgreSQL write-through for serialized `SessionContext`; no-op in TEST_MODE. |
| `_save_exchange_to_history` | Best-effort append to `conversation_history`; no-op in TEST_MODE or without a user id. |
| `_get_user_history` | Reads persisted conversation history for `/history`. |
| `_get_user_sessions` | Reads recent sessions; currently injected into `routes.deps` for split route modules. |
| `_make_client` | Creates the Anthropic client from `ANTHROPIC_API_KEY`. |
| `_get_session_data` | Central session loader and ownership gate. Checks `_sessions`, restores from DB on cache miss, creates `Orchestrator` on restore, and raises 403/404 as appropriate. |
| `_mock_orchestrator_response` and `_MOCK_RESPONSES` | TEST_MODE-only mock response path for `/chat`, `/quiz`, and `/interview`. |
| `_session_progress` | Builds the progress payload used by chat/session routes and split route modules. |
| `_run_blocking` | Runs synchronous Claude/agent calls in the thread pool. |

Several debug endpoints also call `_get_session_data` for read-only comparisons, but they are not chat/session UX routes. Moving chat routes should not require moving those debug routes in the same slice.

## 2. Dependencies

| Route | SessionContext | `_get_session_data` / `_save_session` | `orchestrator.py` | `agents/` | Claude/Anthropic client | TEST_MODE mock block | `templates/chat.html` |
| --- | --- | --- | --- | --- | --- | --- | --- |
| GET `/history` | Indirect via stored history only | Uses `_get_user_history`; no `_get_session_data`; no `_save_session` | No | No | No | TEST_MODE returns empty history through helper | No |
| POST `/session/start` | Creates `SessionContext` | Calls `_save_session`; writes `_sessions` | Creates `Orchestrator` outside TEST_MODE | Indirect through orchestrator later | `_make_client` outside TEST_MODE | Skips client/orchestrator and DB persistence in TEST_MODE | No |
| POST `/chat` | Reads and mutates `SessionContext` history, topics, quiz state, progress | Calls `_get_session_data`, `_save_session`, `_save_exchange_to_history` | Calls `Orchestrator.process` outside TEST_MODE | Uses `agents.practice_arena.handle_quiz_answer` for active quiz answers; orchestrator may call all specialist agents | Uses existing orchestrator/client from session data; catches `anthropic.APIError` | Uses `_mock_orchestrator_response` outside active quiz answers | Frontend calls this route from `chat.html` |
| GET `/progress/{session_id}` | Reads `SessionContext` | Calls `_get_session_data`; no save | No | No | Only if DB restore needs `_make_client` while rebuilding session data | No route-specific mock | No |
| POST `/quiz` | Mutates topics/exercise state through practice arena or TEST_MODE branch | Calls `_get_session_data` and `_save_session` | No | Calls `agents.practice_arena.generate_mcq_quiz` outside TEST_MODE | Uses `data["client"]` outside TEST_MODE; route catches no Anthropic-specific exception | Uses `_MOCK_RESPONSES["practice_arena_mcq"]` | No |
| POST `/interview` | Mutates topics/exercise state through practice arena or TEST_MODE branch | Calls `_get_session_data` and `_save_session` | No | Calls `agents.practice_arena.generate_interview_questions` outside TEST_MODE | Uses `data["client"]` outside TEST_MODE; route catches no Anthropic-specific exception | Uses `_MOCK_RESPONSES["practice_arena_interview"]` | No |
| POST `/evaluate` | May mutate topic/exercise state inside `practice_arena.evaluate_answer` outside TEST_MODE | Calls `_get_session_data`; currently no `_save_session` | No | Calls `agents.practice_arena.evaluate_answer` outside TEST_MODE | Uses `data["client"]` outside TEST_MODE; route catches no Anthropic-specific exception | Uses inline mock response text | No |
| GET `/chat/{session_id}` | Reads `SessionContext` | Calls `_get_session_data`; no save | No direct call, but DB restore may rebuild `Orchestrator` | No direct call | Only if DB restore needs `_make_client` | Passes `test_mode` to template | Renders `templates/chat.html` |

## 3. Two AI Code Paths

### Chat/orchestrator path

The chat/orchestrator path is the free-form conversational learning path:

`GET /chat/{session_id}` renders `templates/chat.html` -> optional `?prompt=` is read by client-side JavaScript -> `POST /chat` sends `{session_id, message}` -> `_get_session_data` loads session/cache/ownership state -> active quiz answers may be handled by `agents.practice_arena.handle_quiz_answer` -> TEST_MODE uses `_mock_orchestrator_response` -> production uses `Orchestrator.process` -> `orchestrator.py` routes to `agents.learning_coach`, `agents.practice_arena`, `agents.idea_generator`, or `agents.job_search_agent` -> Claude calls happen through the orchestrator and specialist agents.

Use this path for open-ended questions, conversational coaching, paper recommendations, project ideas, job-search requests, and chat quick actions that intentionally enter the general assistant experience.

### Structured topic learning path

The structured topic learning path is the task-specific topic journey:

`routes/topics.py` owns topic list/detail/progress/notes/content/practice generation. `routes/submissions.py` owns quiz, portfolio, and interview submission plus feedback routes. `services/content_service.py` and `services/submission_service.py` build harness contexts, use prompt templates, enforce usage limits, call Claude directly through `make_client` and `run_blocking`, cache or reuse generated content, update `SessionContext`, and record usage events.

Use this path for topic-scoped lessons, generated practice artifacts, portfolio tasks, interview practice, quiz evaluation, portfolio feedback, and interview feedback where progress, submissions, caching, and topic-specific UI should stay inside the topic detail flow.

### Overlap and confusion

The overlap is mostly historical:

- Chat quick actions and topic links can still send `?prompt=` to `/chat/{session_id}` for Learn and Quiz flows.
- Portfolio Task and Interview Practice were previously chat prompt redirects in some UI paths; the structured flow now belongs in `routes/topics.py` and `routes/submissions.py`.
- `agents.practice_arena` is used by both paths: through `orchestrator.py` for chat intent routing, and directly by legacy `/quiz`, `/interview`, and `/evaluate` routes in `app.py`.
- TEST_MODE has separate mock behavior in the chat/orchestrator path and in the structured topic services. These should not be merged during a route split.

## 4. Recommended Split Destination

Move the remaining chat/session route group to `routes/chat.py` when ready:

- `GET /history`
- `POST /session/start`
- `POST /chat`
- `GET /progress/{session_id}`
- `POST /quiz`
- `POST /interview`
- `POST /evaluate`
- `GET /chat/{session_id}`

Keep orchestrator.py unchanged. Keep `agents/` unchanged. Keep the structured topic flow in `routes/topics.py` and `routes/submissions.py`. Keep `services/content_service.py` and `services/submission_service.py` as the structured AI service layer.

Do not move session persistence helpers yet. In the first split, `routes/chat.py` should use the same injected dependencies pattern as other route modules, or import only stable app-provided callables through `routes.deps`, while leaving `_get_session_data`, `_save_session`, `_make_client`, `_session_progress`, `_sessions`, and TEST_MODE mock data in `app.py`.

## 5. Risk Areas

- prompt query param behavior: `?prompt=` is implemented in `templates/chat.html`, auto-fills the textarea, removes the query string with `history.replaceState`, and calls `sendMessage()`. The route does not parse it, so URL and template behavior must remain stable.
- TEST_MODE risk: `AI2_TEST_MODE=1` bypasses auth, skips DB persistence, avoids Anthropic client creation, and uses mocks. Chat mocks and structured topic mocks are separate behaviors.
- session ownership: `_get_session_data` enforces cache-level and DB-level owner checks outside TEST_MODE. Any route split must preserve `request.state.user_id` usage and 403/404 behavior.
- cookie/user session behavior: auth middleware sets `request.state.user_id`; TEST_MODE allows unauthenticated test access. Chat routes rely on that state but do not own cookie parsing.
- Claude call path: `/chat` calls Claude through `orchestrator.py` and `agents/`; structured topic routes call Claude through services and harness prompt templates. These paths should remain distinct.
- route URL stability: existing URLs must remain unchanged: `/history`, `/session/start`, `/chat`, `/progress/{session_id}`, `/quiz`, `/interview`, `/evaluate`, and `/chat/{session_id}`.
- rate limits: `/session/start` and `/chat` use `_CHAT_RATE_LIMIT`; `/quiz`, `/interview`, and `/evaluate` use `_PRACTICE_RATE_LIMIT`.
- current `/evaluate` persistence behavior: the route currently does not call `_save_session`; preserve this during any no-behavior-change split.
- DB restore side effect: `_get_session_data` rebuilds `client`, `profile`, and `Orchestrator` on cache miss outside TEST_MODE. A route move must not create a second restore path.

## 6. Safe Split Plan

Move chat routes in one small slice only if dependencies are clear.

Recommended first implementation slice:

1. Create `routes/chat.py`.
2. Move only the route handlers and request models needed by the chat/session route group.
3. Preserve every method, path, response class, status behavior, template name, context key, rate limit decorator, and return payload.
4. Keep session persistence helpers, `_sessions`, `_get_session_data`, `_save_session`, `_make_client`, `_session_progress`, `_run_blocking`, `_MOCK_RESPONSES`, and `_mock_orchestrator_response` in `app.py` for now.
5. Wire dependencies through `routes.deps` or another already-established pattern before moving any helper.
6. Do not change `orchestrator.py`, `agents/`, Claude/Anthropic logic, schema, templates, static files, or structured topic services.

Do not move session persistence helpers yet. They are shared by split modules, debug endpoints, ownership checks, DB restore behavior, and write-through flows.

## 7. Test Plan

After a future split, run focused checks for:

- chat route loads: `GET /chat/{session_id}` still renders `templates/chat.html`.
- prompt query param still works: `/chat/{session_id}?prompt=...` still auto-sends from `templates/chat.html`.
- TEST_MODE mock behavior still works: `/chat`, `/quiz`, `/interview`, and structured topic service mocks still avoid Claude calls.
- `orchestrator.py` unchanged: no orchestrator routing, tool schema, model, synthesis, or agent dispatch changes.
- agents unchanged: no changes under `agents/`.
- topic structured routes still work: `/topics/{session_id}`, `/topic/{session_id}/{topic_id}`, `/topic/content/generate`, `/topic/practice/generate`, `/quiz/submit`, `/quiz/evaluate`, `/portfolio/submit`, `/portfolio/feedback`, `/interview/submit`, and `/interview/feedback`.
- route URLs unchanged: verify the same methods and paths remain registered for `/history`, `/session/start`, `/chat`, `/progress/{session_id}`, `/quiz`, `/interview`, `/evaluate`, and `/chat/{session_id}`.
- session ownership still works: cross-user requests to chat/session routes still return the existing 403/404 behavior outside TEST_MODE.
- cookie/user session behavior still works: authenticated users keep their sessions; TEST_MODE remains unauthenticated.
- Claude call path unchanged: chat still goes through `orchestrator.py`; structured topic learning still goes through `services/content_service.py` and `services/submission_service.py`.
