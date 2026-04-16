"""
AI² Platform — Session Context
Shared state object passed to all agents. Tracks the learner's progress,
conversation history, and current position in the curriculum.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from config import CareerTrack, TOTAL_WEEKS


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

    # ── Progress helpers ──────────────────────────────────────────────────────

    def advance_week(self) -> bool:
        """Move to next week. Returns False if already at week 13."""
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
            f"Current week: {self.current_week} / {TOTAL_WEEKS}\n"
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
        session.quiz_state      = data.get("quiz_state", {})
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
            f"Track: {self.track.value}\n"
            f"Week: {self.current_week} of {TOTAL_WEEKS}\n"
            f"Tasks completed: {self.tasks_done_count()}\n"
            f"Exercises completed this session: {self.exercises_done}\n"
            f"Topics recently explored: {', '.join(list(self.topics_explored)[-5:]) or 'none yet'}\n"
            f"Practice history: {quiz_text}\n"
            f"Learner goals: {goals_text}"
        )
