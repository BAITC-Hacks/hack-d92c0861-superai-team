"""Deterministic eligibility filtering and impact calculation for activities."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from numbers import Real
from typing import Any

from ai.engine.skill_gap import SkillGap
from ai.engine.target_resolver import CareerTarget
from ai.schemas.recommendation import CandidateActivity, SkillImpact


# The documented current dataset has one legacy recurring exception. Future
# datasets should expose ``repeatable`` (or ``recurring``) per event instead.
DOCUMENTED_LEGACY_RECURRING_EVENT_IDS = frozenset({"EV_036"})


class CandidateValidationError(ValueError):
    """Raised when event data needed for deterministic eligibility is malformed."""


RepeatabilityPolicy = Callable[[Mapping[str, Any]], bool]


def is_event_repeatable(event: Mapping[str, Any]) -> bool:
    """Use event metadata when available, then the isolated legacy compatibility rule."""
    for field_name in ("repeatable", "recurring"):
        if field_name in event:
            value = event[field_name]
            if not isinstance(value, bool):
                raise CandidateValidationError(
                    f"Event '{_event_id(event)}' field '{field_name}' must be boolean."
                )
            return value
    return _event_id(event) in DOCUMENTED_LEGACY_RECURRING_EVENT_IDS


def generate_candidates(
    employee: Mapping[str, Any],
    target: CareerTarget,
    skill_gaps: Sequence[SkillGap],
    events: Sequence[Mapping[str, Any]],
    activity_history: Sequence[Mapping[str, Any]],
    *,
    repeatability_policy: RepeatabilityPolicy = is_event_repeatable,
) -> list[CandidateActivity]:
    """Return activities eligible for the target that can close positive skill gaps.

    Eligibility is deliberately binary here. Participation history is only used
    to exclude a completed non-repeatable event; its behavioural signals are
    used later by scoring and never act as a hard prohibition.
    """
    employee_skills = _employee_skills(employee)
    employee_id = _required_text(employee, "employee_id", "employee")
    gaps_by_id = {gap.skill_id: gap for gap in skill_gaps}
    completed_event_ids = _completed_event_ids(activity_history, employee_id)
    candidates: list[CandidateActivity] = []

    for event in events:
        event_id = _event_id(event)
        if _required_bool(event, "mandatory"):
            continue
        target_roles = _text_list(event, "target_roles")
        target_grades = _text_list(event, "target_grades")
        if target.role not in target_roles or target.grade not in target_grades:
            continue
        prerequisites = _number_mapping(event, "prerequisites")
        if not _prerequisites_satisfied(employee_skills, prerequisites):
            continue
        develops_skills = event.get("develops_skills")
        if not isinstance(develops_skills, list):
            raise CandidateValidationError(
                f"Event '{event_id}' field 'develops_skills' must be a list."
            )
        if not develops_skills:
            continue
        if event_id in completed_event_ids and not repeatability_policy(event):
            continue

        impacts = _relevant_impacts(employee_skills, gaps_by_id, develops_skills, event_id)
        if not impacts:
            continue
        candidates.append(
            CandidateActivity(
                event_id=event_id,
                title=_required_text(event, "title", f"event '{event_id}'"),
                event_type=_required_text(event, "type", f"event '{event_id}'"),
                duration_hours=_required_number(event, "duration_hours", event_id),
                affected_skills=tuple(impacts),
            )
        )
    return candidates


def _completed_event_ids(
    activity_history: Sequence[Mapping[str, Any]], employee_id: str
) -> set[str]:
    completed: set[str] = set()
    for record in activity_history:
        if record.get("employee_id") != employee_id or record.get("status") != "completed":
            continue
        event_id = record.get("event_id")
        if not isinstance(event_id, str) or not event_id:
            raise CandidateValidationError(
                f"Completed history record for '{employee_id}' is missing a valid event_id."
            )
        completed.add(event_id)
    return completed


def _relevant_impacts(
    employee_skills: Mapping[str, Any],
    gaps_by_id: Mapping[str, SkillGap],
    develops_skills: list[Any],
    event_id: str,
) -> list[SkillImpact]:
    impacts: list[SkillImpact] = []
    developed_ids: set[str] = set()
    for development in develops_skills:
        if not isinstance(development, Mapping):
            raise CandidateValidationError(
                f"Event '{event_id}' has a non-object develops_skills entry."
            )
        skill_id = _required_text(development, "skill_id", f"event '{event_id}' development")
        if skill_id in developed_ids:
            raise CandidateValidationError(
                f"Event '{event_id}' defines skill '{skill_id}' more than once."
            )
        developed_ids.add(skill_id)
        gain = _required_number(development, "gain", event_id)
        max_level = _required_number(development, "max_level", event_id)
        if gain < 0:
            raise CandidateValidationError(f"Event '{event_id}' has a negative skill gain.")

        gap = gaps_by_id.get(skill_id)
        if gap is None:
            continue
        current_level = employee_skills.get(skill_id, 0)
        _validate_number(current_level, f"Employee level for '{skill_id}'")
        expected_level = min(current_level + gain, max_level)
        effective_gain = max(expected_level - current_level, 0)
        if effective_gain <= 0:
            continue
        gap_after = max(gap.required_level - expected_level, 0)
        impacts.append(
            SkillImpact(
                skill_id=skill_id,
                skill_name=gap.skill_name,
                current_level=current_level,
                required_level=gap.required_level,
                gap_before=gap.gap,
                gain=gain,
                max_level=max_level,
                expected_level_after_completion=expected_level,
                gap_after=gap_after,
                effective_gain=effective_gain,
                critical=gap.critical,
            )
        )
    return impacts


def _employee_skills(employee: Mapping[str, Any]) -> Mapping[str, Any]:
    skills = employee.get("skills", {})
    if not isinstance(skills, Mapping):
        raise CandidateValidationError("Employee 'skills' must be an object when provided.")
    return skills


def _prerequisites_satisfied(
    employee_skills: Mapping[str, Any], prerequisites: Mapping[str, Real]
) -> bool:
    for skill_id, required_level in prerequisites.items():
        current_level = employee_skills.get(skill_id, 0)
        _validate_number(current_level, f"Employee level for prerequisite '{skill_id}'")
        if current_level < required_level:
            return False
    return True


def _event_id(event: Mapping[str, Any]) -> str:
    return _required_text(event, "event_id", "event")


def _required_text(source: Mapping[str, Any], key: str, source_name: str) -> str:
    value = source.get(key)
    if not isinstance(value, str) or not value.strip():
        raise CandidateValidationError(f"{source_name} is missing a valid '{key}'.")
    return value


def _required_bool(source: Mapping[str, Any], key: str) -> bool:
    value = source.get(key)
    if not isinstance(value, bool):
        raise CandidateValidationError(f"Event '{_event_id(source)}' field '{key}' must be boolean.")
    return value


def _text_list(event: Mapping[str, Any], key: str) -> list[str]:
    value = event.get(key)
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise CandidateValidationError(
            f"Event '{_event_id(event)}' field '{key}' must be a list of strings."
        )
    return value


def _number_mapping(event: Mapping[str, Any], key: str) -> Mapping[str, Real]:
    value = event.get(key)
    if not isinstance(value, Mapping):
        raise CandidateValidationError(
            f"Event '{_event_id(event)}' field '{key}' must be an object."
        )
    for skill_id, level in value.items():
        if not isinstance(skill_id, str):
            raise CandidateValidationError("Prerequisite skill IDs must be strings.")
        _validate_number(level, f"Prerequisite level for '{skill_id}'")
    return value


def _required_number(source: Mapping[str, Any], key: str, event_id: str) -> Real:
    value = source.get(key)
    _validate_number(value, f"Event '{event_id}' field '{key}'")
    return value


def _validate_number(value: Any, label: str) -> None:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise CandidateValidationError(f"{label} must be numeric.")
