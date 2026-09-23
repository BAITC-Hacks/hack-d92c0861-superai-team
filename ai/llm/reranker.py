"""LLM contextual reranking guarded by deterministic candidate validation."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any, Protocol

from ai.llm.client import LLMClientResponse, LLMUnavailableError
from ai.llm.prompts import SYSTEM_PROMPT
from ai.llm.schemas import (
    LLM_RESPONSE_JSON_SCHEMA,
    LLMEvidenceReference,
    LLMRecommendationSelection,
)
from ai.schemas.recommendation import ScoredCandidate


class LLMResponseValidationError(ValueError):
    """Raised when structured LLM output violates Career Quest safety rules."""


class RerankerClient(Protocol):
    @property
    def is_configured(self) -> bool: ...

    def request_json(
        self,
        *,
        system_prompt: str,
        context: Mapping[str, Any],
        output_schema: Mapping[str, Any],
    ) -> LLMClientResponse: ...


class ContextualReranker:
    """Select from deterministic candidates only; never decides eligibility."""

    def __init__(self, client: RerankerClient) -> None:
        self._client = client

    def rerank(
        self,
        context: Mapping[str, Any],
        candidates: Sequence[ScoredCandidate],
        *,
        limit: int,
    ) -> tuple[tuple[LLMRecommendationSelection, ...], float]:
        """Request and validate 1..limit LLM selections from the candidate set."""
        if not candidates:
            raise LLMResponseValidationError("Cannot rerank an empty candidate set.")
        if limit < 1 or limit > 3:
            raise ValueError("limit must be between 1 and 3.")
        if not self._client.is_configured:
            raise LLMUnavailableError("llm_not_configured")
        response = self._client.request_json(
            system_prompt=SYSTEM_PROMPT,
            context=context,
            output_schema=LLM_RESPONSE_JSON_SCHEMA,
        )
        return (
            _validate_payload(response.output_text, candidates, limit),
            response.latency_ms,
        )


def _validate_payload(
    raw_output: str,
    candidates: Sequence[ScoredCandidate],
    limit: int,
) -> tuple[LLMRecommendationSelection, ...]:
    try:
        payload = json.loads(raw_output)
    except json.JSONDecodeError as error:
        raise LLMResponseValidationError("LLM response is not valid JSON.") from error
    if not isinstance(payload, dict) or set(payload) != {"recommendations"}:
        raise LLMResponseValidationError("LLM response must contain only recommendations.")
    recommendations = payload["recommendations"]
    if not isinstance(recommendations, list) or not 1 <= len(recommendations) <= limit:
        raise LLMResponseValidationError("LLM must return between one and limit recommendations.")

    candidates_by_id = {candidate.candidate.event_id: candidate for candidate in candidates}
    selections: list[LLMRecommendationSelection] = []
    for item in recommendations:
        selections.append(_selection_from_item(item, candidates_by_id))
    event_ids = [selection.event_id for selection in selections]
    priorities = [selection.priority for selection in selections]
    if len(event_ids) != len(set(event_ids)):
        raise LLMResponseValidationError("LLM response contains duplicate event IDs.")
    if sorted(priorities) != list(range(1, len(selections) + 1)):
        raise LLMResponseValidationError("LLM priorities must be unique and consecutive from 1.")
    return tuple(sorted(selections, key=lambda selection: selection.priority))


def _selection_from_item(
    item: Any, candidates_by_id: Mapping[str, ScoredCandidate]
) -> LLMRecommendationSelection:
    expected_keys = {"event_id", "priority", "reason", "evidence", "history_consideration"}
    if not isinstance(item, dict) or set(item) != expected_keys:
        raise LLMResponseValidationError("LLM recommendation has an invalid shape.")
    event_id = item["event_id"]
    if not isinstance(event_id, str) or event_id not in candidates_by_id:
        raise LLMResponseValidationError("LLM selected an event outside deterministic candidates.")
    priority = item["priority"]
    if isinstance(priority, bool) or not isinstance(priority, int):
        raise LLMResponseValidationError("LLM recommendation priority must be an integer.")
    reason = item["reason"]
    _validate_reason(reason)
    history_consideration = item["history_consideration"]
    if history_consideration not in {"positive", "caution", "neutral"}:
        raise LLMResponseValidationError("LLM returned an invalid history consideration.")
    candidate = candidates_by_id[event_id]
    _validate_history_consideration(history_consideration, candidate)
    evidence = _validate_evidence(item["evidence"], candidate)
    return LLMRecommendationSelection(
        event_id=event_id,
        priority=priority,
        reason=reason.strip(),
        evidence=evidence,
        history_consideration=history_consideration,
    )


def _validate_reason(reason: Any) -> None:
    if not isinstance(reason, str) or not reason.strip() or len(reason) > 600:
        raise LLMResponseValidationError("LLM reason must be a concise non-empty string.")
    normalized = reason.casefold()
    unsupported_claims = ("guarantee", "guaranteed", "manager recommends", "your manager")
    if any(claim in normalized for claim in unsupported_claims):
        raise LLMResponseValidationError("LLM reason contains an unsupported claim.")


def _validate_history_consideration(value: str, candidate: ScoredCandidate) -> None:
    signals = candidate.history_signals
    if value == "positive" and signals.similar_completed <= signals.similar_negative:
        raise LLMResponseValidationError("Positive history consideration is not supported by signals.")
    if value == "caution" and signals.similar_negative == 0:
        raise LLMResponseValidationError("Caution history consideration is not supported by signals.")


def _validate_evidence(
    evidence: Any, candidate: ScoredCandidate
) -> tuple[LLMEvidenceReference, ...]:
    if not isinstance(evidence, list) or not evidence:
        raise LLMResponseValidationError("LLM recommendation must include evidence references.")
    impacts_by_skill = {impact.skill_id: impact for impact in candidate.candidate.affected_skills}
    allowed_types = {"critical_skill_gap", "skill_gap", "expected_progress"}
    validated: list[LLMEvidenceReference] = []
    seen: set[tuple[str, str]] = set()
    for item in evidence:
        if not isinstance(item, dict) or set(item) != {"type", "skill_id"}:
            raise LLMResponseValidationError("LLM evidence has an invalid shape.")
        evidence_type = item["type"]
        skill_id = item["skill_id"]
        impact = impacts_by_skill.get(skill_id)
        if evidence_type not in allowed_types or impact is None:
            raise LLMResponseValidationError("LLM evidence does not reference supplied candidate facts.")
        if evidence_type == "critical_skill_gap" and not impact.critical:
            raise LLMResponseValidationError("Critical evidence requires a critical affected skill.")
        key = (evidence_type, skill_id)
        if key in seen:
            raise LLMResponseValidationError("LLM evidence contains a duplicate reference.")
        seen.add(key)
        validated.append(LLMEvidenceReference(type=evidence_type, skill_id=skill_id))
    return tuple(validated)
