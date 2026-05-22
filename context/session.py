"""
AI² Platform — Session Context
Shared state object passed to all agents. Tracks the learner's progress,
conversation history, and current position in the curriculum.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
# compatibility-only: TOTAL_WEEKS bounds old current_week fallback behavior.
# New modular curriculum features should use course/module/topic sequence_order
# plus learner enrollment/progress state.
from config import CareerTrack, TOTAL_WEEKS
from harness.run_records import create_usage_event as _create_usage_event

VALID_TOPIC_STEPS    = frozenset({"learn", "quiz", "portfolio_task", "interview_practice", "reflection"})
VALID_TOPIC_STATUSES = frozenset({"not_started", "in_progress", "done"})

VALID_TODO_TYPES     = frozenset({"daily", "weekly"})
VALID_TODO_STATUSES  = frozenset({"todo", "in_progress", "done"})
VALID_PRACTICE_TYPES = frozenset({"quiz", "portfolio_task", "interview_practice"})
VALID_USAGE_SOURCES  = frozenset({"cache", "test_mode", "claude", "manual", "shared_cache", "limit_blocked"})
VALID_USAGE_STATUSES = frozenset({"success", "error"})
VALID_ONBOARDING_GOALS = frozenset({"aipm", "ai_builder", "interview_prep"})
VALID_ONBOARDING_LEVELS = frozenset({"beginner", "some_experience", "building_projects", "job_ready"})
VALID_ONBOARDING_WEEKLY_TIMES = frozenset({"two_hours", "five_hours", "ten_hours"})


@dataclass
class ExchangeRecord:
    """A single user/assistant exchange in the conversation history."""
    user_message:    str
    agent_used:      str          # which sub-agent responded
    assistant_reply: str
    timestamp:       str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class SessionContext:
    """
    Central state object for a learning session.
    Passed to the Orchestrator and all sub-agents to enable:
      - Personalized responses based on track and week
      - Coherent multi-turn conversation
      - Progress tracking and continuity
    """
    track:              CareerTrack
    user_id:            str = ""
    # compatibility-only: keep for old serialized sessions/static fallback.
    # New modular curriculum features should use course/module/topic
    # sequence_order plus learner enrollment/progress state.
    current_week:       int = 1
    history:            list[ExchangeRecord] = field(default_factory=list)
    topics_explored:    set[str]             = field(default_factory=set)
    exercises_done:     int = 0
    start_time:         str = field(default_factory=lambda: datetime.now().isoformat())
    # Task completion: task_key → "todo" | "in_progress" | "done"
    syllabus_progress:  dict[str, str]       = field(default_factory=dict)
    # Learner's stated goals for this session or overall
    goals:              list[str]            = field(default_factory=list)
    # Paper/resource titles shown this session — avoid recommending twice
    papers_seen:        set[str]             = field(default_factory=set)
    # Practice Arena: completed quiz results
    # Each entry: {topic, mode, score, total, pct, difficulty, timestamp}
    quiz_scores:        list[dict]           = field(default_factory=list)
    # Topics that have been quizzed at least once (for progress awareness)
    topics_quizzed:     set[str]             = field(default_factory=set)
    # Active interactive quiz state — populated by practice_arena, cleared on completion
    # Schema: {topic, questions: [...], current_q: int, score: int, user_answers: [...]}
    quiz_state:         dict                 = field(default_factory=dict)
    # Per-topic journey step progress: {topic_id: {step: status}}
    topic_progress:     dict[str, dict[str, str]] = field(default_factory=dict)
    # Daily / weekly learning todos: [{todo_id, title, todo_type, status, ...}]
    todos:              list[dict]                = field(default_factory=list)
    # Per-topic reflection notes: {topic_id: {reflection, confusions, application_idea, updated_at}}
    topic_notes:        dict[str, dict]           = field(default_factory=dict)
    # AI-generated topic learning content: {topic_id: {content, generated_at, model, version, freshness_label}}
    generated_topic_content:  dict[str, dict]     = field(default_factory=dict)
    # AI-generated practice per type: {topic_id: {quiz|portfolio_task|interview_practice: {content, ...}}}
    generated_topic_practice: dict[str, dict]     = field(default_factory=dict)
    # Portfolio task submissions & AI feedback: {topic_id: {submission, feedback, score, submitted_at, reviewed_at, model}}
    portfolio_submissions:    dict[str, dict]     = field(default_factory=dict)
    # Quiz answer submissions & AI evaluation: {topic_id: {answers, evaluation, score, submitted_at, evaluated_at, model}}
    quiz_submissions:         dict[str, dict]     = field(default_factory=dict)
    # Interview answer submissions & AI feedback: {topic_id: {answer, feedback, score, submitted_at, reviewed_at, model}}
    interview_submissions:    dict[str, dict]     = field(default_factory=dict)
    # Lightweight AI usage monitoring events; persisted inside the session JSON for now.
    usage_events:             list[dict]          = field(default_factory=list)
    # Lightweight beta onboarding profile for recommendation/start guidance.
    onboarding:               dict                = field(default_factory=dict)

    # ── Progress helpers ──────────────────────────────────────────────────────

    def advance_week(self) -> bool:
        """compatibility-only old week increment helper.

        Do not use for new modular curriculum features. Modular runtime should
        derive position from course/module/topic sequence_order plus learner
        enrollment/progress state. Kept temporarily for old sessions/static
        fallback.
        """
        if self.current_week < TOTAL_WEEKS:
            self.current_week += 1
            return True
        return False

    def mark_exercise_done(self) -> None:
        self.exercises_done += 1

    def note_topic(self, topic: str) -> None:
        cleaned = topic.lower().strip()
        if cleaned:
            self.topics_explored.add(cleaned)
        # Cap at 50 to keep prompt context lean
        if len(self.topics_explored) > 50:
            oldest = next(iter(self.topics_explored))
            self.topics_explored.discard(oldest)

    # ── Conversation history helpers ──────────────────────────────────────────

    def add_exchange(
        self,
        user_message:    str,
        assistant_reply: str,
        agent_used:      str = "orchestrator",
    ) -> None:
        self.history.append(ExchangeRecord(
            user_message    = user_message,
            agent_used      = agent_used,
            assistant_reply = assistant_reply,
        ))

    def recent_history(self, n: int = 6) -> list[ExchangeRecord]:
        """Return the n most recent exchanges (for context injection)."""
        return self.history[-n:]

    def format_history_for_prompt(self, n: int = 6) -> str:
        """Format recent history as a human-readable string for prompt injection."""
        records = self.recent_history(n)
        if not records:
            return "(No prior conversation in this session.)"
        lines = []
        for r in records:
            lines.append(f"Student: {r.user_message}")
            lines.append(f"AI² ({r.agent_used}): {r.assistant_reply[:300]}{'...' if len(r.assistant_reply) > 300 else ''}")
        return "\n".join(lines)

    # ── Display helpers ───────────────────────────────────────────────────────

    def record_quiz(
        self,
        topic:      str,
        mode:       str,
        score:      int,
        total:      int,
        difficulty: str = "mixed",
    ) -> None:
        """Log a completed quiz result."""
        self.quiz_scores.append({
            "topic":      topic,
            "mode":       mode,
            "score":      score,
            "total":      total,
            "pct":        round(score / total * 100) if total else 0,
            "difficulty": difficulty,
            "timestamp":  datetime.now().isoformat(),
        })
        self.topics_quizzed.add(topic.lower().strip())

    def best_score_for(self, topic: str) -> Optional[dict]:
        """Return the highest-scoring quiz result for a topic, or None."""
        results = [q for q in self.quiz_scores if q["topic"].lower() == topic.lower()]
        return max(results, key=lambda q: q["pct"]) if results else None

    def mark_task(self, task_key: str, status: str = "done") -> None:
        """Update a task's completion status in syllabus_progress."""
        self.syllabus_progress[task_key] = status

    def get_topic_progress(self, topic_id: str) -> dict[str, str]:
        """Return step statuses for a topic, filling missing steps with 'not_started'."""
        base = {s: "not_started" for s in ("learn", "quiz", "portfolio_task", "interview_practice", "reflection")}
        base.update(self.topic_progress.get(topic_id, {}))
        return base

    def mark_topic_step(self, topic_id: str, step: str, status: str = "in_progress") -> None:
        """Update one step's status for a topic. Raises ValueError on invalid inputs."""
        if step not in VALID_TOPIC_STEPS:
            raise ValueError(f"Invalid step '{step}'. Valid: {sorted(VALID_TOPIC_STEPS)}")
        if status not in VALID_TOPIC_STATUSES:
            raise ValueError(f"Invalid status '{status}'. Valid: {sorted(VALID_TOPIC_STATUSES)}")
        if topic_id not in self.topic_progress:
            self.topic_progress[topic_id] = {}
        self.topic_progress[topic_id][step] = status

    def topic_completion_percent(self, topic_id: str) -> int:
        """Return percentage of steps marked 'done' for a topic (0–100)."""
        progress = self.get_topic_progress(topic_id)
        done = sum(1 for s in progress.values() if s == "done")
        return round(done / len(progress) * 100)

    # AI usage helpers

    def record_usage_event(
        self,
        event_type: str,
        topic_id: Optional[str] = None,
        model: str = "",
        source: str = "manual",
        status: str = "success",
        metadata: Optional[dict] = None,
    ) -> dict:
        """Append a lightweight usage event to this session."""
        if source not in VALID_USAGE_SOURCES:
            raise ValueError(f"Invalid usage source '{source}'. Valid: {sorted(VALID_USAGE_SOURCES)}")
        if status not in VALID_USAGE_STATUSES:
            raise ValueError(f"Invalid usage status '{status}'. Valid: {sorted(VALID_USAGE_STATUSES)}")

        event = _create_usage_event(
            event_type=event_type,
            topic_id=topic_id,
            model=model,
            source=source,
            status=status,
            metadata=metadata,
        )
        self.usage_events.append(event)
        return event

    def usage_summary(self) -> dict:
        """Return aggregate usage counters for the current session."""
        by_event_type: dict[str, int] = {}
        for event in self.usage_events:
            event_type = event.get("event_type", "")
            by_event_type[event_type] = by_event_type.get(event_type, 0) + 1

        return {
            "total_events":     len(self.usage_events),
            "claude_events":    sum(1 for e in self.usage_events if e.get("source") == "claude"),
            "cache_events":     sum(1 for e in self.usage_events if e.get("source") == "cache"),
            "test_mode_events": sum(1 for e in self.usage_events if e.get("source") == "test_mode"),
            "error_events":     sum(1 for e in self.usage_events if e.get("status") == "error"),
            "by_event_type":    by_event_type,
        }

    # ── Todo planner helpers ──────────────────────────────────────────────────

    # Beta onboarding helpers

    def get_onboarding_profile(self) -> dict:
        """Return a copy of the lightweight onboarding profile."""
        return dict(self.onboarding or {})

    def save_onboarding_profile(self, goal: str, level: str, weekly_time: str) -> dict:
        """Validate and save beta onboarding choices."""
        if goal not in VALID_ONBOARDING_GOALS:
            raise ValueError(f"Invalid onboarding goal '{goal}'.")
        if level not in VALID_ONBOARDING_LEVELS:
            raise ValueError(f"Invalid onboarding level '{level}'.")
        if weekly_time not in VALID_ONBOARDING_WEEKLY_TIMES:
            raise ValueError(f"Invalid onboarding weekly_time '{weekly_time}'.")

        recommended_track = _recommended_track_for_goal(goal)
        profile = {
            "goal":              goal,
            "level":             level,
            "weekly_time":       weekly_time,
            "recommended_track": recommended_track,
            "completed_at":      datetime.now().isoformat(),
        }
        if goal != recommended_track:
            profile["recommendation_note"] = (
                f"Using {recommended_track} as the closest available track for {goal}."
            )
        self.onboarding = profile
        return self.get_onboarding_profile()

    def has_completed_onboarding(self) -> bool:
        profile = self.onboarding or {}
        return bool(
            profile.get("goal")
            and profile.get("level")
            and profile.get("weekly_time")
            and profile.get("recommended_track")
            and profile.get("completed_at")
        )

    def add_todo(
        self,
        title: str,
        todo_type: str = "daily",
        linked_topic_id: Optional[str] = None,
        created_by: str = "learner",
        due_label: Optional[str] = None,
    ) -> dict:
        """Create and append a todo. Raises ValueError on invalid todo_type."""
        if todo_type not in VALID_TODO_TYPES:
            raise ValueError(f"Invalid todo_type '{todo_type}'. Valid: {sorted(VALID_TODO_TYPES)}")
        todo: dict = {
            "todo_id":         str(uuid.uuid4()),
            "title":           title.strip(),
            "todo_type":       todo_type,
            "status":          "todo",
            "linked_topic_id": linked_topic_id,
            "created_by":      created_by,
            "created_at":      datetime.now().isoformat(),
            "due_label":       due_label,
        }
        self.todos.append(todo)
        return todo

    def update_todo_status(self, todo_id: str, status: str) -> Optional[dict]:
        """Update status of an existing todo. Returns the todo or None if not found."""
        if status not in VALID_TODO_STATUSES:
            raise ValueError(f"Invalid status '{status}'. Valid: {sorted(VALID_TODO_STATUSES)}")
        for todo in self.todos:
            if todo["todo_id"] == todo_id:
                todo["status"] = status
                return todo
        return None

    def get_todos(self, todo_type: Optional[str] = None) -> list[dict]:
        """Return todos, optionally filtered by type."""
        if todo_type is None:
            return list(self.todos)
        return [t for t in self.todos if t["todo_type"] == todo_type]

    def todo_counts(self) -> dict:
        """Return counts of todos by status."""
        counts: dict = {"total": 0, "todo": 0, "in_progress": 0, "done": 0}
        for t in self.todos:
            counts["total"] += 1
            counts[t.get("status", "todo")] = counts.get(t.get("status", "todo"), 0) + 1
        return counts

    # ── Topic notes / reflection helpers ─────────────────────────────────────

    def get_topic_notes(self, topic_id: str) -> dict:
        """Return notes for a topic, filling missing fields with empty strings."""
        default: dict = {"reflection": "", "confusions": "", "application_idea": "", "updated_at": ""}
        return {**default, **self.topic_notes.get(topic_id, {})}

    def save_topic_notes(
        self,
        topic_id: str,
        reflection: str = "",
        confusions: str = "",
        application_idea: str = "",
    ) -> dict:
        """Save or update notes for a topic. Returns the saved dict."""
        notes: dict = {
            "reflection":       reflection.strip(),
            "confusions":       confusions.strip(),
            "application_idea": application_idea.strip(),
            "updated_at":       datetime.now().isoformat(),
        }
        self.topic_notes[topic_id] = notes
        return notes

    # ── Generated topic content helpers ──────────────────────────────────────

    def get_generated_topic_content(self, topic_id: str) -> dict:
        """Return AI-generated content for a topic, filling missing fields with empty defaults."""
        default: dict = {
            "content": "", "generated_at": "", "model": "", "version": 0, "freshness_label": ""
        }
        return {**default, **self.generated_topic_content.get(topic_id, {})}

    def save_generated_topic_content(
        self,
        topic_id:       str,
        content:        str,
        model:          str,
        freshness_label: str = "AI-generated",
    ) -> dict:
        """Save or overwrite AI-generated content for a topic. Increments version."""
        existing = self.generated_topic_content.get(topic_id, {})
        entry: dict = {
            "content":        content.strip(),
            "generated_at":   datetime.now().isoformat(),
            "model":          model,
            "version":        existing.get("version", 0) + 1,
            "freshness_label": freshness_label,
        }
        self.generated_topic_content[topic_id] = entry
        return entry

    # ── Generated topic practice helpers ─────────────────────────────────────

    def get_generated_topic_practice(
        self, topic_id: str, practice_type: Optional[str] = None
    ) -> dict:
        """Return saved practice content. If practice_type given, return that type's dict.
        If None, return a dict of all three types with safe defaults."""
        default: dict = {
            "content": "", "generated_at": "", "model": "", "version": 0, "freshness_label": ""
        }
        topic_data = self.generated_topic_practice.get(topic_id, {})
        if practice_type is not None:
            return {**default, **topic_data.get(practice_type, {})}
        return {
            pt: {**default, **topic_data.get(pt, {})}
            for pt in ("quiz", "portfolio_task", "interview_practice")
        }

    def save_generated_topic_practice(
        self,
        topic_id:       str,
        practice_type:  str,
        content:        str,
        model:          str,
        freshness_label: str = "AI-generated",
    ) -> dict:
        """Save or overwrite AI-generated practice for a topic/type. Increments version."""
        if practice_type not in VALID_PRACTICE_TYPES:
            raise ValueError(
                f"Invalid practice_type '{practice_type}'. "
                f"Valid: {sorted(VALID_PRACTICE_TYPES)}"
            )
        if topic_id not in self.generated_topic_practice:
            self.generated_topic_practice[topic_id] = {}
        existing = self.generated_topic_practice[topic_id].get(practice_type, {})
        entry: dict = {
            "content":        content.strip(),
            "generated_at":   datetime.now().isoformat(),
            "model":          model,
            "version":        existing.get("version", 0) + 1,
            "freshness_label": freshness_label,
        }
        self.generated_topic_practice[topic_id][practice_type] = entry
        return entry

    # ── Portfolio submission helpers ──────────────────────────────────────────

    def get_portfolio_submission(self, topic_id: str) -> dict:
        """Return the portfolio submission for a topic, filling missing fields with safe defaults."""
        default: dict = {
            "submission": "", "feedback": "", "score": None,
            "submitted_at": "", "reviewed_at": "", "model": "",
        }
        return {**default, **self.portfolio_submissions.get(topic_id, {})}

    def save_portfolio_submission(self, topic_id: str, submission: str) -> dict:
        """Save a learner's submission. If the submission text changed, clears any prior feedback."""
        stripped = submission.strip()
        existing = self.portfolio_submissions.get(topic_id, {})
        if stripped != existing.get("submission", ""):
            entry: dict = {
                "submission":   stripped,
                "feedback":     "",
                "score":        None,
                "submitted_at": datetime.now().isoformat(),
                "reviewed_at":  "",
                "model":        "",
            }
        else:
            entry = {**existing, "submission": stripped, "submitted_at": datetime.now().isoformat()}
        self.portfolio_submissions[topic_id] = entry
        return entry

    def save_portfolio_feedback(
        self,
        topic_id: str,
        feedback: str,
        model: str,
        score: Optional[int] = None,
    ) -> dict:
        """Save AI feedback for a topic's portfolio submission. Preserves the latest submission."""
        existing = self.portfolio_submissions.get(topic_id, {})
        entry: dict = {
            **existing,
            "feedback":    feedback.strip(),
            "model":       model,
            "score":       score,
            "reviewed_at": datetime.now().isoformat(),
        }
        self.portfolio_submissions[topic_id] = entry
        return entry

    # ── Quiz submission helpers ───────────────────────────────────────────────

    def get_quiz_submission(self, topic_id: str) -> dict:
        """Return the quiz submission for a topic, filling missing fields with safe defaults."""
        default: dict = {
            "answers": "", "evaluation": "", "score": None,
            "submitted_at": "", "evaluated_at": "", "model": "",
        }
        return {**default, **self.quiz_submissions.get(topic_id, {})}

    def save_quiz_answers(self, topic_id: str, answers: str) -> dict:
        """Save a learner's quiz answers. If the answer text changed, clears any prior evaluation."""
        stripped = answers.strip()
        existing = self.quiz_submissions.get(topic_id, {})
        if stripped != existing.get("answers", ""):
            entry: dict = {
                "answers":      stripped,
                "evaluation":   "",
                "score":        None,
                "submitted_at": datetime.now().isoformat(),
                "evaluated_at": "",
                "model":        "",
            }
        else:
            entry = {**existing, "answers": stripped, "submitted_at": datetime.now().isoformat()}
        self.quiz_submissions[topic_id] = entry
        return entry

    def save_quiz_evaluation(
        self,
        topic_id: str,
        evaluation: str,
        model: str,
        score: Optional[int] = None,
    ) -> dict:
        """Save AI evaluation for a topic's quiz answers. Preserves the latest answers."""
        existing = self.quiz_submissions.get(topic_id, {})
        entry: dict = {
            **existing,
            "evaluation":  evaluation.strip(),
            "model":       model,
            "score":       score,
            "evaluated_at": datetime.now().isoformat(),
        }
        self.quiz_submissions[topic_id] = entry
        return entry

    # ── Interview submission helpers ─────────────────────────────────────────────

    def get_interview_submission(self, topic_id: str) -> dict:
        """Return the interview submission for a topic, filling missing fields with safe defaults."""
        default: dict = {
            "answer": "", "feedback": "", "score": None,
            "submitted_at": "", "reviewed_at": "", "model": "",
        }
        return {**default, **self.interview_submissions.get(topic_id, {})}

    def save_interview_answer(self, topic_id: str, answer: str) -> dict:
        """Save a learner's interview answer. If the answer changed, clears any prior feedback."""
        stripped = answer.strip()
        existing = self.interview_submissions.get(topic_id, {})
        if stripped != existing.get("answer", ""):
            entry: dict = {
                "answer":       stripped,
                "feedback":     "",
                "score":        None,
                "submitted_at": datetime.now().isoformat(),
                "reviewed_at":  "",
                "model":        "",
            }
        else:
            entry = {**existing, "answer": stripped, "submitted_at": datetime.now().isoformat()}
        self.interview_submissions[topic_id] = entry
        return entry

    def save_interview_feedback(
        self,
        topic_id: str,
        feedback: str,
        model: str,
        score: Optional[int] = None,
    ) -> dict:
        """Save AI feedback for a topic's interview answer. Preserves the latest answer."""
        existing = self.interview_submissions.get(topic_id, {})
        entry: dict = {
            **existing,
            "feedback":    feedback.strip(),
            "model":       model,
            "score":       score,
            "reviewed_at": datetime.now().isoformat(),
        }
        self.interview_submissions[topic_id] = entry
        return entry

    def add_goal(self, goal: str) -> None:
        """Record a learner-stated goal."""
        self.goals.append(goal.strip())

    def note_paper_seen(self, title: str) -> None:
        """Record that a paper/resource was recommended this session."""
        self.papers_seen.add(title.lower().strip())

    def tasks_done_count(self) -> int:
        return sum(1 for s in self.syllabus_progress.values() if s == "done")

    def progress_summary(self) -> str:
        tasks_done = self.tasks_done_count()
        quiz_summary = ""
        if self.quiz_scores:
            last = self.quiz_scores[-1]
            quiz_summary = (
                f"\nLast quiz: {last['topic']} ({last['mode']}) — "
                f"{last['score']}/{last['total']} ({last['pct']}%)"
            )
        return (
            f"Track: {self.track.value.replace('_', ' ').title()}\n"
            f"Current module: {self.current_week} / {TOTAL_WEEKS}\n"
            f"Tasks completed: {tasks_done}\n"
            f"Exercises completed: {self.exercises_done}\n"
            f"Topics explored: {len(self.topics_explored)}\n"
            f"Quizzes taken: {len(self.quiz_scores)}{quiz_summary}\n"
            f"Goals: {'; '.join(self.goals) or 'not set'}\n"
            f"Exchanges this session: {len(self.history)}"
        )

    # ── Serialisation ─────────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        """Serialise to a JSON-safe dict (for SQLite persistence)."""
        return {
            "track":            self.track.value,
            "user_id":          self.user_id,
            "current_week":     self.current_week,
            "exercises_done":   self.exercises_done,
            "start_time":       self.start_time,
            "syllabus_progress": self.syllabus_progress,
            "goals":            self.goals,
            "quiz_scores":      self.quiz_scores,
            "topics_explored":  list(self.topics_explored),
            "papers_seen":      list(self.papers_seen),
            "topics_quizzed":   list(self.topics_quizzed),
            "quiz_state":       self.quiz_state,
            "topic_progress":          self.topic_progress,
            "todos":                   self.todos,
            "topic_notes":             self.topic_notes,
            "generated_topic_content":  self.generated_topic_content,
            "generated_topic_practice": self.generated_topic_practice,
            "portfolio_submissions":    self.portfolio_submissions,
            "quiz_submissions":        self.quiz_submissions,
            "interview_submissions":   self.interview_submissions,
            "usage_events":            self.usage_events,
            "onboarding":              self.onboarding,
            "history": [
                {
                    "user_message":    r.user_message,
                    "agent_used":      r.agent_used,
                    "assistant_reply": r.assistant_reply,
                    "timestamp":       r.timestamp,
                }
                for r in self.history
            ],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SessionContext":
        """Reconstruct a SessionContext from a serialised dict."""
        session = cls(
            track          = CareerTrack(data["track"]),
            user_id        = data.get("user_id", ""),
            current_week   = data["current_week"],
            exercises_done = data["exercises_done"],
            start_time     = data["start_time"],
            syllabus_progress = data.get("syllabus_progress", {}),
            goals          = data.get("goals", []),
            quiz_scores    = data.get("quiz_scores", []),
        )
        session.topics_explored = set(data.get("topics_explored", []))
        session.papers_seen     = set(data.get("papers_seen",     []))
        session.topics_quizzed  = set(data.get("topics_quizzed",  []))
        session.quiz_state               = data.get("quiz_state", {})
        session.topic_progress           = data.get("topic_progress", {})
        session.todos                    = data.get("todos", [])
        session.topic_notes              = data.get("topic_notes", {})
        session.generated_topic_content  = data.get("generated_topic_content", {})
        session.generated_topic_practice = data.get("generated_topic_practice", {})
        session.portfolio_submissions    = data.get("portfolio_submissions", {})
        session.quiz_submissions         = data.get("quiz_submissions", {})
        session.interview_submissions    = data.get("interview_submissions", {})
        session.usage_events             = data.get("usage_events", [])
        session.onboarding               = data.get("onboarding", {})
        session.history = [
            ExchangeRecord(
                user_message    = r["user_message"],
                agent_used      = r["agent_used"],
                assistant_reply = r["assistant_reply"],
                timestamp       = r["timestamp"],
            )
            for r in data.get("history", [])
        ]
        return session

    def as_prompt_context(self) -> str:
        """Compact representation for injection into agent system prompts."""
        goals_text = "; ".join(self.goals[-3:]) if self.goals else "not stated"
        quiz_text = (
            f"{len(self.quiz_scores)} quiz(zes) taken; "
            f"topics: {', '.join(list(self.topics_quizzed)[-4:])}"
            if self.topics_quizzed else "no quizzes yet"
        )
        return (
            f"[LEARNER CONTEXT]\n"
            f"Current learning path: {self.track.value}\n"
            f"Current module: {self.current_week} of {TOTAL_WEEKS}\n"
            f"Tasks completed: {self.tasks_done_count()}\n"
            f"Exercises completed this session: {self.exercises_done}\n"
            f"Topics recently explored: {', '.join(list(self.topics_explored)[-5:]) or 'none yet'}\n"
            f"Practice history: {quiz_text}\n"
            f"Learner goals: {goals_text}"
        )


def _recommended_track_for_goal(goal: str) -> str:
    available = {track.value for track in CareerTrack}
    if goal == "aipm":
        return "aipm"
    if goal == "ai_builder" and "context" in available:
        return "context"
    if goal == "interview_prep" and "aipm" in available:
        return "aipm"
    return "aipm"
