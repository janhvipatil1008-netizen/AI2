# AI² DB Read Migration Plan

## 1. Current Storage State

`SessionContext` remains the runtime source of truth for AI² learner state. Topic progress, todos, notes, generated content, submissions, and usage events are still read from the session JSON stored in `sessions.session_data`.

The new database tables and repositories are currently a mirror path only. DB write-through for topic progress and todos is optional and controlled by `AI2_DB_WRITE_THROUGH_ENABLED`. Runtime DB reads are disabled.

`GET /debug/storage-status` confirms this state:

- `session_context_source_of_truth` is `true`.
- `db_reads_enabled` is `false`.
- `curriculum_db_reads_enabled` is `false`.
- `progress_db_reads_enabled` is `false`.
- `todos_db_reads_enabled` is `false`.

## 2. Why DB Reads Should Be Introduced Gradually

DB reads should be phased in carefully because existing sessions already rely on serialized `SessionContext` JSON. A sudden source-of-truth change could break learners with old session data, incomplete mirror rows, or curriculum seed mismatches.

Gradual rollout lets AI²:

- Avoid breaking existing sessions.
- Fall back to `sessions.session_data` JSON.
- Verify seed data quality before production use.
- Verify write-through quality for progress and todos.
- Avoid frontend and user-visible regressions.
- Compare DB-derived state with current runtime state before enabling reads broadly.

## 3. Proposed Read Phases

### Phase 1: Debug-Only Curriculum Reads

- Read curriculum tracks/modules/topics from DB only in a debug or test endpoint.
- Do not change user-facing routes.
- Do not change topic detail, topics list, planner, or dashboard behavior.
- Use this phase to validate seed data and repository read behavior.

### Phase 2: Curriculum Fallback Reader

- Add a fallback reader: DB first, existing curriculum helpers fallback.
- Keep the reader behind `AI2_CURRICULUM_DB_READS_ENABLED`.
- If DB read fails or returns incomplete data, fall back to current curriculum helpers.
- Keep response shapes unchanged.

### Phase 3: Progress and Todos Reads Behind Flags

- Read `topic_progress` from DB only when `AI2_PROGRESS_DB_READS_ENABLED` is enabled.
- Read `todos` from DB only when `AI2_TODOS_DB_READS_ENABLED` is enabled.
- Keep `SessionContext` fallback for both.
- Do not remove JSON writes or session serialization.

### Phase 4: Mismatch Comparison and Safe Logging

- Compare DB state vs `SessionContext` state for topic progress and todos.
- Log mismatches safely with IDs, counts, statuses, and short metadata.
- Do not log full learner content, notes, submissions, prompts, or generated content.
- Do not expose mismatch details to learners.

### Phase 5: DB Primary After Confidence

- Make DB primary only after seed data, write-through, fallback reads, and mismatch logs are stable.
- Keep JSON fallback during an extended rollback window.
- Remove JSON dependency only after a separate migration and explicit cleanup plan.

## 4. Feature Flags

Proposed flags:

- `AI2_DB_WRITE_THROUGH_ENABLED`
- `AI2_CURRICULUM_DB_READS_ENABLED`
- `AI2_PROGRESS_DB_READS_ENABLED`
- `AI2_TODOS_DB_READS_ENABLED`

All DB read flags should default off. `AI2_DB_WRITE_THROUGH_ENABLED` may be enabled manually for mirror writes, but it should not imply runtime DB reads.

Recommended defaults:

```text
AI2_DB_WRITE_THROUGH_ENABLED=false
AI2_CURRICULUM_DB_READS_ENABLED=false
AI2_PROGRESS_DB_READS_ENABLED=false
AI2_TODOS_DB_READS_ENABLED=false
```

## 5. Fallback Strategy

DB read failure must not break the learner flow.

Rules:

- Curriculum DB read failure falls back to current curriculum helpers.
- Progress DB read failure falls back to `SessionContext.topic_progress`.
- Todos DB read failure falls back to `SessionContext.todos`.
- Log a safe warning with table/action identifiers and short error metadata.
- Never expose DB errors, stack traces, DB URLs, or raw SQL errors to learners.
- Keep route response shapes unchanged during fallback.

## 6. Data Consistency Strategy

During transition:

- Use `legacy_topic_id` to map current string topic IDs to DB rows.
- Preserve `sessions.session_data`.
- Avoid deleting JSON state.
- Compare topic progress maps and `completion_percent`.
- Compare todo counts, IDs, types, and statuses.
- Treat DB rows as a mirror until mismatch rates are low and well understood.
- Prefer additive validation and logging before any source-of-truth switch.

## 7. Recommended Next Implementation Steps

- Step 51: Add read flag helpers.
- Step 52: Add curriculum read service, disabled by default.
- Step 53: Add debug endpoint for curriculum DB read check.
- Step 54: Add progress/todos read service, disabled by default.
- Step 55: Add mismatch logging, no user-facing behavior change.

Until those steps are complete and verified, `SessionContext` remains the runtime source of truth and `/debug/storage-status` read flags should remain false.
