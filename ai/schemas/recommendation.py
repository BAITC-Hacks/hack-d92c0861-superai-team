"""Typed deterministic recommendation data shared by the Phase 2 engine."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ai.engine.skill_gap import SkillGap
    from ai.engine.target_resolver import CareerTarget


Number = int | float


@dataclass(frozen=True)
class SkillImpact:
    """The deterministic effect of an activity on one currently open skill gap."""

    skill_id: str
    skill_name: str
    current_level: Number
    required_level: Number
    gap_before: Number
    gain: Number
    max_level: Number
    expected_level_after_completion: Number
    gap_after: Number
    effective_gain: Number
    critical: bool


@dataclass(frozen=True)
class CandidateActivity:
    """An activity that passed all deterministic eligibility checks."""

    event_id: str
    title: str
    event_type: str
    duration_hours: Number
    affected_skills: tuple[SkillImpact, ...]


@dataclass(frozen=True)
class HistorySummary:
    """Counts calculated from only one employee's participation records."""

    total_records: int
    completed_count: int
    in_progress_count: int
    dropped_count: int
    no_show_count: int
    declined_count: int
    overdue_count: int
    completion_rate: float

    @property
    def negative_count(self) -> int:
        """Return outcomes that signal a negative participation experience."""
        return self.dropped_count + self.no_show_count + self.declined_count + self.overdue_count


@dataclass(frozen=True)
class HistorySignals:
    """Candidate-specific history facts, without making an eligibility decision."""

    same_event_records: int
    same_event_completed: int
    similar_records: int
    similar_completed: int
    similar_negative: int
    shared_skill_records: int
    shared_skill_completed: int
    average_feedback_rating: float | None
    assignment_sources: tuple[tuple[str, int], ...]


@dataclass(frozen=True)
class ScoreBreakdown:
    """Normalized components of a deterministic candidate score."""

    career_relevance: float
    gap_impact: float
    critical_skill_impact: float
    effective_gain: float
    history_fit: float


@dataclass(frozen=True)
class ScoredCandidate:
    """A candidate and the factual evidence behind its deterministic ranking."""

    candidate: CandidateActivity
    score: float
    factors: ScoreBreakdown
    history_signals: HistorySignals


@dataclass(frozen=True)
class DeterministicRecommendationResult:
    """Phase 2 result; no LLM ranking or generated explanation is included."""

    employee_id: str
    target: CareerTarget | None
    target_source: str
    target_reason: str | None
    skill_gaps: tuple[SkillGap, ...]
    history_summary: HistorySummary
    candidates: tuple[ScoredCandidate, ...]

    @property
    def recommendations(self) -> tuple[ScoredCandidate, ...]:
        """Backend-friendly alias for the deterministic candidate list."""
        return self.candidates
