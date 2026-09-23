"""Explainable, configurable deterministic ranking for eligible activities."""

from __future__ import annotations

from dataclasses import dataclass
from numbers import Real
from typing import Sequence

from ai.engine.skill_gap import SkillGap
from ai.schemas.recommendation import (
    CandidateActivity,
    HistorySignals,
    ScoreBreakdown,
    ScoredCandidate,
)


class ScoringValidationError(ValueError):
    """Raised when a scoring input cannot produce a meaningful normalized score."""


@dataclass(frozen=True)
class ScoringWeights:
    """Default factor weights; their values intentionally sum to 1.0.

    Critical target skills receive the largest single share, while career
    relevance and actual gap closure together remain more influential.
    """

    career_relevance: float = 0.20
    gap_impact: float = 0.22
    critical_skill_impact: float = 0.28
    effective_gain: float = 0.15
    history_fit: float = 0.15

    @property
    def total(self) -> float:
        return (
            self.career_relevance
            + self.gap_impact
            + self.critical_skill_impact
            + self.effective_gain
            + self.history_fit
        )


@dataclass(frozen=True)
class ScoringConfig:
    """All Phase 2 tuning values are centralized here for later adjustment."""

    weights: ScoringWeights = ScoringWeights()
    neutral_history_fit: float = 0.50
    completion_history_bonus: float = 0.25
    negative_history_penalty: float = 0.45
    negative_history_rate_weight: float = 0.60
    negative_history_repetition_weight: float = 0.40
    negative_history_repetition_reference: int = 3
    feedback_adjustment_weight: float = 0.10
    same_event_completion_bonus: float = 0.10
    maximum_feedback_rating: float = 5.0


DEFAULT_SCORING_CONFIG = ScoringConfig()


def score_candidate(
    candidate: CandidateActivity,
    skill_gaps: Sequence[SkillGap],
    history_signals: HistorySignals,
    config: ScoringConfig = DEFAULT_SCORING_CONFIG,
) -> ScoredCandidate:
    """Score one eligible candidate in the bounded 0..1 range.

    The score blends five independent normalized factors. It never changes
    candidate eligibility, so weak history can reduce ranking but cannot
    silently suppress a career-relevant activity.
    """
    _validate_config(config)
    if not candidate.affected_skills:
        raise ScoringValidationError("Cannot score a candidate without affected skills.")
    positive_gaps = [gap for gap in skill_gaps if gap.gap > 0]
    if not positive_gaps:
        raise ScoringValidationError("Cannot score a candidate without positive skill gaps.")

    affected = candidate.affected_skills
    total_gap = sum(gap.gap for gap in positive_gaps)
    total_critical_gap = sum(gap.gap for gap in positive_gaps if gap.critical)
    useful_closure = sum(min(impact.effective_gain, impact.gap_before) for impact in affected)
    critical_closure = sum(
        min(impact.effective_gain, impact.gap_before)
        for impact in affected
        if impact.critical
    )
    candidate_gap_total = sum(impact.gap_before for impact in affected)
    factors = ScoreBreakdown(
        career_relevance=_ratio(len(affected), len(positive_gaps)),
        gap_impact=_ratio(useful_closure, total_gap),
        critical_skill_impact=_ratio(critical_closure, total_critical_gap),
        effective_gain=_ratio(useful_closure, candidate_gap_total),
        history_fit=calculate_history_fit(history_signals, config),
    )
    weights = config.weights
    score = (
        factors.career_relevance * weights.career_relevance
        + factors.gap_impact * weights.gap_impact
        + factors.critical_skill_impact * weights.critical_skill_impact
        + factors.effective_gain * weights.effective_gain
        + factors.history_fit * weights.history_fit
    ) / weights.total
    return ScoredCandidate(
        candidate=candidate,
        score=_clamp(score),
        factors=factors,
        history_signals=history_signals,
    )


def calculate_history_fit(
    signals: HistorySignals, config: ScoringConfig = DEFAULT_SCORING_CONFIG
) -> float:
    """Convert factual candidate history signals into a bounded, secondary factor.

    With no comparable record the factor is neutral. Successful similar
    participation increases it; negative outcomes reduce it more as they are
    repeated. Available feedback makes only a small adjustment.
    """
    _validate_config(config)
    if signals.similar_records == 0:
        return config.neutral_history_fit

    completion_rate = _ratio(signals.similar_completed, signals.similar_records)
    negative_rate = _ratio(signals.similar_negative, signals.similar_records)
    repeated_negative = min(
        _ratio(signals.similar_negative, config.negative_history_repetition_reference), 1.0
    )
    negative_component = config.negative_history_penalty * (
        negative_rate * config.negative_history_rate_weight
        + repeated_negative * config.negative_history_repetition_weight
    )
    same_event_completion_rate = _ratio(
        signals.same_event_completed, signals.same_event_records
    )
    fit = (
        config.neutral_history_fit
        + config.completion_history_bonus * completion_rate
        - negative_component
        + config.same_event_completion_bonus * same_event_completion_rate
    )
    if signals.average_feedback_rating is not None:
        feedback_position = _ratio(
            signals.average_feedback_rating, config.maximum_feedback_rating
        )
        fit += config.feedback_adjustment_weight * (
            feedback_position - config.neutral_history_fit
        )
    return _clamp(fit)


def _validate_config(config: ScoringConfig) -> None:
    weights = config.weights
    values: tuple[Real, ...] = (
        weights.career_relevance,
        weights.gap_impact,
        weights.critical_skill_impact,
        weights.effective_gain,
        weights.history_fit,
        config.neutral_history_fit,
        config.completion_history_bonus,
        config.negative_history_penalty,
        config.negative_history_rate_weight,
        config.negative_history_repetition_weight,
        config.feedback_adjustment_weight,
        config.same_event_completion_bonus,
        config.maximum_feedback_rating,
    )
    if any(isinstance(value, bool) or not isinstance(value, Real) for value in values):
        raise ScoringValidationError("Scoring configuration values must be numeric.")
    if any(value < 0 for value in values):
        raise ScoringValidationError("Scoring configuration values cannot be negative.")
    if weights.total <= 0:
        raise ScoringValidationError("At least one scoring weight must be positive.")
    if config.negative_history_repetition_reference <= 0:
        raise ScoringValidationError("negative_history_repetition_reference must be positive.")
    if config.maximum_feedback_rating <= 0:
        raise ScoringValidationError("maximum_feedback_rating must be positive.")


def _ratio(numerator: Real, denominator: Real) -> float:
    return float(numerator / denominator) if denominator else 0.0


def _clamp(value: Real) -> float:
    return float(max(0.0, min(float(value), 1.0)))
