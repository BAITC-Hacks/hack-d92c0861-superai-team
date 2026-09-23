"""Backend-facing Phase 3 API combining deterministic facts with safe LLM reranking."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ai.engine.data_loader import DataLoader
from ai.engine.recommender import DeterministicRecommender
from ai.engine.target_resolver import CareerTarget
from ai.llm.client import LLMRequestError, LLMUnavailableError, OpenAIResponsesClient
from ai.llm.prompts import SYSTEM_PROMPT_VERSION, build_rerank_context
from ai.llm.reranker import ContextualReranker, LLMResponseValidationError
from ai.llm.schemas import (
    AIRecommendation,
    AIRecommendationResult,
    LLMRecommendationSelection,
    RecommendationEvidence,
)


class CareerQuestAI:
    """Stable API for backend imports; deterministic facts always stay authoritative."""

    def __init__(
        self,
        data_loader: DataLoader,
        *,
        reranker: ContextualReranker | None = None,
        candidate_pool_size: int = 5,
    ) -> None:
        if not isinstance(candidate_pool_size, int) or candidate_pool_size < 1:
            raise ValueError("candidate_pool_size must be a positive integer.")
        self._data_loader = data_loader
        self._deterministic_recommender = DeterministicRecommender(data_loader)
        self._reranker = reranker or ContextualReranker(OpenAIResponsesClient())
        self._candidate_pool_size = candidate_pool_size

    @classmethod
    def from_directory(cls, directory: str | Path, **kwargs: Any) -> "CareerQuestAI":
        """Create the high-level service from any directory using standard dataset names."""
        return cls(DataLoader.from_directory(directory), **kwargs)

    def recommend(self, employee_id: str, *, limit: int = 3) -> AIRecommendationResult:
        """Return one to three reranked recommendations or a deterministic fallback."""
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 3:
            raise ValueError("limit must be an integer between 1 and 3.")
        deterministic = self._deterministic_recommender.recommend(
            employee_id,
            top_k=max(limit, self._candidate_pool_size),
        )
        if not deterministic.candidates:
            return self._fallback(deterministic, limit, "no_deterministic_candidates")

        dataset = self._data_loader.load_all()
        employee = DataLoader.get_employee(dataset.employees, employee_id)
        events_by_id = {event["event_id"]: event for event in dataset.events}
        context = build_rerank_context(employee, deterministic, events_by_id)
        try:
            selections, latency_ms = self._reranker.rerank(
                context,
                deterministic.candidates,
                limit=limit,
            )
            return AIRecommendationResult(
                employee_id=employee_id,
                target=deterministic.target,
                source="llm",
                recommendations=tuple(
                    _ground_selection(
                        selection,
                        deterministic.candidates,
                        deterministic.target,
                        events_by_id,
                    )
                    for selection in selections
                ),
                fallback_reason=None,
                llm_latency_ms=latency_ms,
                prompt_version=SYSTEM_PROMPT_VERSION,
            )
        except Exception as error:
            # The LLM is optional. Never surface provider or parse internals to users.
            return self._fallback(
                deterministic,
                limit,
                _fallback_reason(error),
                getattr(error, "latency_ms", None),
                events_by_id,
            )

    def _fallback(
        self,
        deterministic: Any,
        limit: int,
        reason: str,
        latency_ms: float | None = None,
        events_by_id: dict[str, dict[str, Any]] | None = None,
    ) -> AIRecommendationResult:
        return AIRecommendationResult(
            employee_id=deterministic.employee_id,
            target=deterministic.target,
            source="deterministic_fallback",
            recommendations=tuple(
                _fallback_recommendation(
                    scored,
                    priority,
                    (events_by_id or {}).get(scored.candidate.event_id, {}),
                )
                for priority, scored in enumerate(deterministic.candidates[:limit], start=1)
            ),
            fallback_reason=reason,
            llm_latency_ms=latency_ms,
            prompt_version=SYSTEM_PROMPT_VERSION,
        )


def _ground_selection(
    selection: LLMRecommendationSelection,
    candidates: tuple[Any, ...],
    target: CareerTarget | None = None,
    events_by_id: dict[str, dict[str, Any]] | None = None,
) -> AIRecommendation:
    scored = next(
        candidate
        for candidate in candidates
        if candidate.candidate.event_id == selection.event_id
    )
    event = (events_by_id or {}).get(selection.event_id, {})
    impacts_by_skill = {impact.skill_id: impact for impact in scored.candidate.affected_skills}
    evidence = tuple(
        _evidence(reference.type, impacts_by_skill[reference.skill_id])
        for reference in selection.evidence
    )
    return AIRecommendation(
        event_id=selection.event_id,
        priority=selection.priority,
        title=scored.candidate.title,
        type=scored.candidate.event_type,
        format=_event_format(event),
        duration_hours=scored.candidate.duration_hours,
        deterministic_score=scored.score,
        reason=_grounded_reason(evidence, target),
        evidence=evidence,
        history_consideration=_history_sentence(selection.history_consideration),
        skills_affected=scored.candidate.affected_skills,
        score_factors=scored.factors,
    )


def _fallback_recommendation(
    scored: Any, priority: int, event: dict[str, Any]
) -> AIRecommendation:
    impacts = scored.candidate.affected_skills
    primary = next((impact for impact in impacts if impact.critical), impacts[0])
    evidence_type = "critical_skill_gap" if primary.critical else "skill_gap"
    reason = (
        f"Develops {primary.skill_name} for the target role by moving the assessed level "
        f"from {primary.current_level} toward {primary.required_level}."
    )
    return AIRecommendation(
        event_id=scored.candidate.event_id,
        priority=priority,
        title=scored.candidate.title,
        type=scored.candidate.event_type,
        format=_event_format(event),
        duration_hours=scored.candidate.duration_hours,
        deterministic_score=scored.score,
        reason=reason,
        evidence=(_evidence(evidence_type, primary), _evidence("expected_progress", primary)),
        history_consideration=_fallback_history_sentence(scored),
        skills_affected=impacts,
        score_factors=scored.factors,
    )


def _evidence(evidence_type: str, impact: Any) -> RecommendationEvidence:
    return RecommendationEvidence(
        type=evidence_type,
        skill_id=impact.skill_id,
        skill_name=impact.skill_name,
        current_level=impact.current_level,
        required_level=impact.required_level,
        gap=impact.gap_before,
        expected_level_after_completion=impact.expected_level_after_completion,
        critical=impact.critical,
    )


def _event_format(event: dict[str, Any]) -> str | None:
    value = event.get("format")
    return value if isinstance(value, str) else None


def _grounded_reason(
    evidence: tuple[RecommendationEvidence, ...], target: CareerTarget | None
) -> str:
    """Render an explanation only from locally verified deterministic evidence."""
    primary = next(
        (item for item in evidence if item.type == "critical_skill_gap"), evidence[0]
    )
    target_phrase = (
        f"the {target.grade} {target.role} target"
        if target is not None
        else "the resolved career target"
    )
    importance = "critical " if primary.critical else ""
    return (
        f"Supports {target_phrase} by developing the {importance}{primary.skill_name} gap. "
        f"Deterministic completion changes the assessed level from {primary.current_level} "
        f"to {primary.expected_level_after_completion}, toward the required "
        f"level {primary.required_level}."
    )


def _history_sentence(value: str) -> str:
    return {
        "positive": "Comparable activity history includes more successful completions than negative outcomes.",
        "caution": "Comparable activity history includes negative outcomes, so this activity should be approached deliberately.",
        "neutral": "No decisive comparable history signal was applied.",
    }[value]


def _fallback_history_sentence(scored: Any) -> str:
    signals = scored.history_signals
    if signals.similar_negative:
        return _history_sentence("caution")
    if signals.similar_completed:
        return _history_sentence("positive")
    return _history_sentence("neutral")


def _fallback_reason(error: Exception) -> str:
    if isinstance(error, LLMUnavailableError):
        return "llm_not_configured"
    if isinstance(error, (LLMRequestError, TimeoutError)):
        return "llm_request_failed"
    if isinstance(error, LLMResponseValidationError):
        return "llm_response_rejected"
    return "llm_unavailable"
