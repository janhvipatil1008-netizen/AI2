"""
AI² Platform — LearnerProfile

Persistent, cross-session learner data. Separate from SessionContext
(which is single-session only). Stored in the learner_profiles SQLite table.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from config import CareerTrack


@dataclass
class LearnerProfile:
    """Cross-session learner data — persists across all sessions for a user."""
    user_id:           str
    track:             CareerTrack

    # ── Lifetime counters ─────────────────────────────────────────────────────
    session_count:     int = 0
    total_exchanges:   int = 0
    total_quizzes:     int = 0
    total_exercises:   int = 0

    # ── Full quiz history across all sessions ─────────────────────────────────
    all_quiz_scores:   list[dict] = field(default_factory=list)
    # Each entry: {topic, mode, score, total, pct, difficulty, timestamp, session_id}

    # ── Mastery derived from quiz history ─────────────────────────────────────
    topics_mastered:   set[str] = field(default_factory=set)    # best pct > 80
    topics_struggling: set[str] = field(default_factory=set)    # best pct < 60

    # ── Cross-session goals and papers ───────────────────────────────────────
    career_goals:      list[str] = field(default_factory=list)
    papers_seen_all:   set[str]  = field(default_factory=set)

    # ── Timestamps ────────────────────────────────────────────────────────────
    created_at:        str = field(default_factory=lambda: datetime.now().isoformat())
    last_session_at:   str = field(default_factory=lambda: datetime.now().isoformat())

    # ── Mastery computation ───────────────────────────────────────────────────

    def _recompute_mastery(self) -> None:
        """Recompute topics_mastered and topics_struggling from all_quiz_scores."""
        best: dict[str, int] = {}
        for q in self.all_quiz_scores:
            topic = q.get("topic", "").lower().strip()
            pct   = q.get("pct", 0)
            if topic:
                best[topic] = max(best.get(topic, 0), pct)

        self.topics_mastered   = {t for t, p in best.items() if p >= 80}
        self.topics_struggling = {t for t, p in best.items() if p < 60}
        # A topic can't be both — mastered takes priority
        self.topics_struggling -= self.topics_mastered

    def mastery_summary(self) -> str:
        """Compact block injected into agent system prompts."""
        mastered   = ", ".join(sorted(self.topics_mastered)[-6:])   or "none yet"
        struggling = ", ".join(sorted(self.topics_struggling)[-4:]) or "none"
        goals_text = "; ".join(self.career_goals[-3:]) or "not stated"
        return (
            f"[LONG-TERM MEMORY]\n"
            f"Sessions completed: {self.session_count} | "
            f"Total exchanges: {self.total_exchanges} | "
            f"All-time quizzes: {self.total_quizzes}\n"
            f"Topics mastered (>80%): {mastered}\n"
            f"Topics to revisit (<60%): {struggling}\n"
            f"Career goals: {goals_text}\n"
            f"All-time papers seen: {len(self.papers_seen_all)}"
        )

    # ── Merge session data into profile ──────────────────────────────────────

    def update_from_session(self, session, session_id: str = "") -> None:
        """Merge a completed/ongoing session into this profile."""
        from context.session import SessionContext
        assert isinstance(session, SessionContext)

        self.session_count   += 1
        self.total_exchanges += len(session.history)
        self.total_quizzes   += len(session.quiz_scores)
        self.total_exercises += session.exercises_done
        self.last_session_at  = datetime.now().isoformat()
        self.track            = session.track  # update to latest track

        for q in session.quiz_scores:
            entry = dict(q)
            entry["session_id"] = session_id
            self.all_quiz_scores.append(entry)

        for goal in session.goals:
            if goal not in self.career_goals:
                self.career_goals.append(goal)

        self.papers_seen_all.update(session.papers_seen)
        self._recompute_mastery()

    # ── Serialisation ─────────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        return {
            "user_id":           self.user_id,
            "track":             self.track.value,
            "session_count":     self.session_count,
            "total_exchanges":   self.total_exchanges,
            "total_quizzes":     self.total_quizzes,
            "total_exercises":   self.total_exercises,
            "all_quiz_scores":   self.all_quiz_scores,
            "topics_mastered":   list(self.topics_mastered),
            "topics_struggling": list(self.topics_struggling),
            "career_goals":      self.career_goals,
            "papers_seen_all":   list(self.papers_seen_all),
            "created_at":        self.created_at,
            "last_session_at":   self.last_session_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "LearnerProfile":
        profile = cls(
            user_id         = data["user_id"],
            track           = CareerTrack(data["track"]),
            session_count   = data.get("session_count", 0),
            total_exchanges = data.get("total_exchanges", 0),
            total_quizzes   = data.get("total_quizzes", 0),
            total_exercises = data.get("total_exercises", 0),
            all_quiz_scores = data.get("all_quiz_scores", []),
            career_goals    = data.get("career_goals", []),
            created_at      = data.get("created_at", datetime.now().isoformat()),
            last_session_at = data.get("last_session_at", datetime.now().isoformat()),
        )
        profile.topics_mastered   = set(data.get("topics_mastered", []))
        profile.topics_struggling = set(data.get("topics_struggling", []))
        profile.papers_seen_all   = set(data.get("papers_seen_all", []))
        return profile

    @classmethod
    def new_for_user(cls, user_id: str, track: CareerTrack) -> "LearnerProfile":
        return cls(user_id=user_id, track=track)


# ── Storage helpers ───────────────────────────────────────────────────────────

def load_profile(user_id: str, conn) -> Optional[LearnerProfile]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT profile_data FROM learner_profiles WHERE user_id = %s", (user_id,)
        )
        row = cur.fetchone()
    if row:
        return LearnerProfile.from_dict(json.loads(row[0]))
    return None


def save_profile(profile: LearnerProfile, conn) -> None:
    now  = datetime.now().isoformat()
    data = json.dumps(profile.to_dict())
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO learner_profiles (user_id, profile_data, updated_at) "
            "VALUES (%s, %s, %s) "
            "ON CONFLICT (user_id) DO UPDATE SET profile_data=%s, updated_at=%s",
            (profile.user_id, data, now, data, now),
        )
