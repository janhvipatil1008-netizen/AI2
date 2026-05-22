# AI² Harness Engineering Plan

## 1. Why AI² Needs a Harness Layer

AI² should not treat Claude as a raw chatbot only. The product is a structured learning system, so Claude should run inside controlled workflows that provide the right context, prompt shape, rubric, progress state, logging, and usage tracking for each task.

A harness layer makes AI behavior easier to test, monitor, cache, constrain, and evolve. Instead of each service hand-building prompts and interpreting output independently, the harness becomes the shared execution boundary for learning content, practice generation, evaluation, feedback, usage policy, and safe observability.

## 2. Current Harness-Like Pieces Already Built

AI² already has several harness-like foundations:

- Topic journey flow for learn, quiz, portfolio task, interview practice, and reflection.
- `SessionContext` state for progress, generated content, submissions, notes, todos, and usage events.
- `services/content_service.py` for learning/practice generation.
- `services/submission_service.py` for quiz, portfolio, and interview submission feedback.
- `usage_events` for cache/test/Claude events.
- Safe logging for Claude error paths.
- Topic progress tracking.
- Feedback and evaluation loops.
- Deterministic `TEST_MODE` mocks for non-Claude test execution.

The next step is to make these pieces explicit as a harness package without changing route behavior.

## 3. Target Harness Architecture

```text
Learner UI
   ↓
FastAPI Routes
   ↓
Services Layer
   ↓
AI Harness Layer
   ├── Context Builder
   ├── Prompt Templates
   ├── Rubrics
   ├── Usage Policy
   ├── Guardrails
   ├── Run Records
   └── Output Validators
   ↓
Claude API
   ↓
Saved State + Feedback + Progress + Usage Events
```

Routes should remain thin and HTTP-focused. Services should own business workflows. The harness should own AI-call preparation, prompt/rubric composition, safety checks, run metadata, and output validation.

## 4. Proposed Harness Package Structure

Future package:

```text
harness/
  __init__.py
  context_builder.py
  prompt_templates.py
  rubrics.py
  usage_policy.py
  run_records.py
  guardrails.py
  output_validators.py
```

Responsibilities:

- `context_builder.py`: Build task-specific Claude context from learner/session/topic state.
- `prompt_templates.py`: Store reusable prompt templates for each AI workflow.
- `rubrics.py`: Store reusable scoring and feedback rubrics.
- `usage_policy.py`: Decide whether an action can run, should use cache, or should require refresh limits/quotas later.
- `run_records.py`: Define lightweight run metadata structures that later map to DB tables.
- `guardrails.py`: Centralize validation and safety checks before/after AI calls.
- `output_validators.py`: Parse scores, validate expected sections, and normalize outputs.

## 5. Context Builder Design

Before calling Claude, AI² should assemble only the context needed for the specific task. Candidate context:

- Learner track.
- Current topic.
- Topic description.
- Module/week.
- Prior generated learning content.
- Prior quiz, portfolio, or interview practice content.
- Learner quiz answers, portfolio submission, or interview answer when relevant.
- Notes/reflections when relevant.
- Topic progress.
- Freshness label.
- Usage constraints or refresh policy.

Rules:

- Do not overload Claude with unnecessary context.
- Context should be task-specific, not a dump of the whole session.
- The current syllabus is seed data and should not be hardcoded into harness logic.
- Context building should work for future tracks, modules, and topics.

## 6. Prompt Template Design

Prompts should later move out of service functions into reusable templates. This keeps services easier to read and makes prompt changes easier to test.

Prompt types:

- `learning_content`
- `quiz_generation`
- `portfolio_task_generation`
- `interview_practice_generation`
- `quiz_evaluation`
- `portfolio_feedback`
- `interview_feedback`

Templates should define expected structure, tone, constraints, and output sections. Services should pass task context into templates rather than assembling large prompt strings inline.

## 7. Rubric Design

Rubrics should be reusable and explicit. They should guide Claude feedback and provide stable scoring semantics.

Rubric areas:

- Quiz answers.
- Portfolio submissions.
- Interview answers.

Scoring dimensions:

- Clarity.
- Correctness.
- Depth.
- Practical application.
- Completeness.
- Interview readiness.
- Portfolio readiness.

Rubrics should remain syllabus-agnostic. They should evaluate the learner's work against the topic and task, not against hardcoded curriculum assumptions.

## 8. Usage Policy Design

Future usage policy should control cost and product behavior before Claude is called.

Policy capabilities:

- Cache-first behavior.
- Refresh limits.
- Daily generation limits.
- User-level quotas.
- Expensive action protection.
- `TEST_MODE` bypass.
- Future cost estimation.

The first version can be lightweight and return decisions such as `use_cache`, `allow_claude`, or `deny_with_reason`. Later, it can consult DB-backed usage events and quota settings.

## 9. Run Records / Trace Design

Future run records should capture safe metadata for each AI action:

- `run_id`
- `user_id`
- `session_id`
- `topic_id`
- `event_type`
- `model`
- `source`
- `status`
- `created_at`
- Safe metadata

By default, do not store full prompts, full user answers, portfolio submissions, interview answers, or generated content in logs/run records. Those belong in controlled content/submission tables, not observability metadata.

## 10. Guardrails and Safety

Harness guardrails should include:

- Do not log full user submissions.
- Do not expose internal errors to learners.
- Validate `practice_type`.
- Validate `topic_id`.
- Use structured outputs where possible.
- Keep route behavior stable.
- Preserve `SessionContext` backward compatibility.
- Keep prompt and output validation separate from HTTP route code.

## 11. How This Connects to DB Migration

Harness logic should not depend on `SessionContext` forever. During migration, services can continue using `SessionContext` while repositories are introduced underneath.

Later:

- Services read/write through repositories.
- DB tables support run records, generated content versions, submissions, notes, and usage events.
- The harness emits run metadata that maps cleanly to `usage_events` and future AI run tables.
- Current session JSON remains a fallback during migration.

This keeps the AI execution boundary stable while persistence moves from session JSON to normalized tables.

## 12. Step-by-Step Harness Implementation Plan

- Step 37: Add harness package foundation.
- Step 38: Move prompt templates into `harness/prompt_templates.py`.
- Step 39: Move rubrics into `harness/rubrics.py`.
- Step 40: Add `context_builder.py`.
- Step 41: Add `run_records.py` structures.
- Step 42: Add `usage_policy.py`.
- Step 43: Begin DB migration.

Each step should be small, testable, and backward compatible. Routes and UI behavior should remain unchanged while the harness becomes the internal boundary for Claude-powered learning workflows.
