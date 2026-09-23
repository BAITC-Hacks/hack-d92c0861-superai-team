"""Phase 2 deterministic orchestration for Career Quest recommendations."""

from __future__ import annotations

from ai.engine.candidate_generator import generate_candidates
from ai.engine.data_loader import DataLoader
from ai.engine.history_analyzer import analyze_candidate_history, summarize_history
from ai.engine.scoring import DEFAULT_SCORING_CONFIG, ScoringConfig, score_candidate
from ai.engine.skill_gap import calculate_skill_gaps
from ai.engine.target_resolver import find_role_profile, resolve_target
from ai.schemas.recommendation import DeterministicRecommendationResult


class RecommenderValidationError(ValueError):
    """Raised when the deterministic recommendation request is invalid."""


class DeterministicRecommender:
    """Compose Phase 1 facts and Phase 2 deterministic ranking into one API."""

    def __init__(
        self, data_loader: DataLoader, scoring_config: ScoringConfig = DEFAULT_SCORING_CONFIG
    ) -> None:
        self._data_loader = data_loader
        self._scoring_config = scoring_config

    def recommend(
        self, employee_id: str, *, top_k: int = 5
    ) -> DeterministicRecommendationResult:
        """Return up to ``top_k`` eligible candidates, sorted by score descending."""
        if not isinstance(top_k, int) or isinstance(top_k, bool) or top_k < 0:
            raise RecommenderValidationError("top_k must be a non-negative integer.")
        dataset = self._data_loader.load_all()
        employee = DataLoader.get_employee(dataset.employees, employee_id)
        target_resolution = resolve_target(employee)
        history_summary = summarize_history(employee_id, dataset.activity_history)
        if target_resolution.target is None:
            return DeterministicRecommendationResult(
                employee_id=employee_id,
                target=None,
                target_source=target_resolution.source,
                target_reason=target_resolution.reason,
                skill_gaps=(),
                history_summary=history_summary,
                candidates=(),
            )

        target = target_resolution.target
        role_profile = find_role_profile(dataset.role_profiles, target.role, target.grade)
        skill_gaps = calculate_skill_gaps(employee, role_profile, dataset.skills)
        candidates = generate_candidates(
            employee,
            target,
            skill_gaps,
            dataset.events,
            dataset.activity_history,
        )
        scored_candidates = []
        for candidate in candidates:
            signals = analyze_candidate_history(
                employee_id, candidate, dataset.activity_history, dataset.events
            )
            scored_candidates.append(
                score_candidate(candidate, skill_gaps, signals, self._scoring_config)
            )
        ordered_candidates = tuple(
            sorted(
                scored_candidates,
                key=lambda scored: (-scored.score, scored.candidate.event_id),
            )[:top_k]
        )
        return DeterministicRecommendationResult(
            employee_id=employee_id,
            target=target,
            target_source=target_resolution.source,
            target_reason=target_resolution.reason,
            skill_gaps=tuple(skill_gaps),
            history_summary=history_summary,
            candidates=ordered_candidates,
        )
