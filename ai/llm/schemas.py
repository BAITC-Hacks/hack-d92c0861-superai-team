"""Strict LLM response schema plus backend-facing Phase 3 result types."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from ai.engine.target_resolver import CareerTarget
    from ai.schemas.recommendation import ScoreBreakdown, SkillImpact


EvidenceType = Literal["critical_skill_gap", "skill_gap", "expected_progress"]
HistoryConsideration = Literal["positive", "caution", "neutral"]
RecommendationSource = Literal["llm", "deterministic_fallback"]


LLM_RESPONSE_JSON_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "recommendations": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "event_id": {"type": "string"},
                    "priority": {"type": "integer"},
                    "reason": {"type": "string"},
                    "evidence": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "type": {
                                    "type": "string",
                                    "enum": [
                                        "critical_skill_gap",
                                        "skill_gap",
                                        "expected_progress",
                                    ],
                                },
                                "skill_id": {"type": "string"},
                            },
                            "required": ["type", "skill_id"],
                        },
                    },
                    "history_consideration": {
                        "type": "string",
                        "enum": ["positive", "caution", "neutral"],
                    },
                },
                "required": [
                    "event_id",
                    "priority",
                    "reason",
                    "evidence",
                    "history_consideration",
                ],
            },
        }
    },
    "required": ["recommendations"],
}


@dataclass(frozen=True)
class LLMEvidenceReference:
    """An LLM-selected reference that must resolve to deterministic skill facts."""

    type: EvidenceType
    skill_id: str


@dataclass(frozen=True)
class LLMRecommendationSelection:
    """Validated LLM preference before factual evidence is reconstructed locally."""

    event_id: str
    priority: int
    reason: str
    evidence: tuple[LLMEvidenceReference, ...]
    history_consideration: HistoryConsideration


@dataclass(frozen=True)
class RecommendationEvidence:
    """A factual explanation item reconstructed solely from deterministic data."""

    type: EvidenceType
    skill_id: str
    skill_name: str
    current_level: int | float
    required_level: int | float
    gap: int | float
    expected_level_after_completion: int | float
    critical: bool


@dataclass(frozen=True)
class AIRecommendation:
    """Stable backend-facing recommendation with grounded evidence."""

    event_id: str
    priority: int
    title: str
    type: str
    format: str | None
    duration_hours: int | float
    deterministic_score: float
    reason: str
    evidence: tuple[RecommendationEvidence, ...]
    history_consideration: str
    skills_affected: tuple[SkillImpact, ...]
    score_factors: ScoreBreakdown


@dataclass(frozen=True)
class AIRecommendationResult:
    """Final Phase 3 result; selection is LLM-backed or safely deterministic."""

    employee_id: str
    target: CareerTarget | None
    source: RecommendationSource
    recommendations: tuple[AIRecommendation, ...]
    fallback_reason: str | None
    llm_latency_ms: float | None
    prompt_version: str

    def to_dict(self) -> dict[str, object]:
        """Return only JSON-native mappings, lists, scalars and null for a Python backend."""
        payload = _json_compatible(asdict(self))
        if not isinstance(payload, dict):  # Defensive guard for this stable public contract.
            raise TypeError("Recommendation result did not serialize to a JSON object.")
        return payload


def _json_compatible(value: object) -> object:
    """Convert dataclass output tuples to JSON arrays without changing factual values."""
    if isinstance(value, dict):
        return {str(key): _json_compatible(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_compatible(item) for item in value]
    return value
