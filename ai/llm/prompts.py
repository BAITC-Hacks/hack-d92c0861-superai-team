"""Versioned prompt and compact deterministic-context construction."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Mapping

from ai.schemas.recommendation import DeterministicRecommendationResult


SYSTEM_PROMPT_VERSION = "career_quest_reranker_v1"

SYSTEM_PROMPT = """You are the Career Quest contextual reranker.
Return JSON only and follow the supplied schema exactly.

You may select only event_id values listed in deterministic_candidates. Never
create or modify events, employee facts, skill requirements, levels, gains,
history, or eligibility. Evaluate target-grade requirements, critical gaps,
expected progress, deterministic factor evidence, and history together.
History is a signal, never an absolute veto. Prefer complementary development
when selecting more than one event.

For every recommendation, cite only affected skill IDs from that same candidate
in evidence. Use critical_skill_gap only for a supplied critical affected skill.
Do not claim promotion is guaranteed or that a manager recommends an activity.
"""


def build_rerank_context(
    employee: Mapping[str, Any],
    deterministic_result: DeterministicRecommendationResult,
    events_by_id: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    """Build compact LLM context without serializing the full dataset."""
    target = deterministic_result.target
    return {
        "employee": {
            "role": employee.get("role"),
            "grade": employee.get("grade"),
            "tenure_months": employee.get("tenure_months"),
        },
        "target": {"role": target.role, "grade": target.grade} if target else None,
        "skill_gaps": [
            {
                "skill_id": gap.skill_id,
                "skill_name": gap.skill_name,
                "current_level": gap.current_level,
                "required_level": gap.required_level,
                "gap": gap.gap,
                "critical": gap.critical,
            }
            for gap in deterministic_result.skill_gaps
        ],
        "history_summary": asdict(deterministic_result.history_summary),
        "deterministic_candidates": [
            _candidate_context(scored, events_by_id.get(scored.candidate.event_id, {}))
            for scored in deterministic_result.candidates
        ],
    }


def _candidate_context(scored: Any, event: Mapping[str, Any]) -> dict[str, Any]:
    candidate = scored.candidate
    return {
        "event_id": candidate.event_id,
        "title": candidate.title,
        "description": event.get("description") if isinstance(event.get("description"), str) else None,
        "type": candidate.event_type,
        "format": event.get("format") if isinstance(event.get("format"), str) else None,
        "duration_hours": candidate.duration_hours,
        "deterministic_score": scored.score,
        "score_factors": asdict(scored.factors),
        "affected_skills": [asdict(impact) for impact in candidate.affected_skills],
        "history_signals": asdict(scored.history_signals),
    }
