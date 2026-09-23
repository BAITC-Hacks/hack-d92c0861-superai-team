"""Deterministic target-role skill-gap calculation."""

from __future__ import annotations

from dataclasses import dataclass
from numbers import Real
from typing import Any, Mapping, Sequence


class SkillGapValidationError(ValueError):
    """Raised when employee or role-profile fields needed for gaps are malformed."""


class SkillCatalogLookupError(LookupError):
    """Raised when a required role-profile skill has no catalog entry."""


@dataclass(frozen=True)
class SkillGap:
    skill_id: str
    skill_name: str
    current_level: int | float
    required_level: int | float
    gap: int | float
    critical: bool


def calculate_skill_gaps(
    employee: Mapping[str, Any],
    role_profile: Mapping[str, Any],
    skills: Sequence[Mapping[str, Any]],
) -> list[SkillGap]:
    """Return positive target-role gaps, ordered by criticality then size."""
    employee_skills = employee.get("skills", {})
    if not isinstance(employee_skills, Mapping):
        raise SkillGapValidationError("Employee 'skills' must be an object when provided.")

    required_skills = role_profile.get("required_skills")
    if not isinstance(required_skills, Mapping):
        raise SkillGapValidationError("Role profile 'required_skills' must be an object.")
    critical_skills = role_profile.get("critical_skills", [])
    if not isinstance(critical_skills, list) or not all(
        isinstance(skill_id, str) for skill_id in critical_skills
    ):
        raise SkillGapValidationError("Role profile 'critical_skills' must be a list of IDs.")

    names_by_id = _skill_names(skills)
    critical_ids = set(critical_skills)
    gaps: list[SkillGap] = []
    for skill_id, required_level in required_skills.items():
        if not isinstance(skill_id, str):
            raise SkillGapValidationError("Role profile skill IDs must be strings.")
        _validate_level(required_level, f"Required level for '{skill_id}'")
        if skill_id not in names_by_id:
            raise SkillCatalogLookupError(
                f"Required skill '{skill_id}' is missing from the skill catalog."
            )
        current_level = employee_skills.get(skill_id, 0)
        _validate_level(current_level, f"Employee level for '{skill_id}'")
        gap = max(required_level - current_level, 0)
        if gap > 0:
            gaps.append(
                SkillGap(
                    skill_id=skill_id,
                    skill_name=names_by_id[skill_id],
                    current_level=current_level,
                    required_level=required_level,
                    gap=gap,
                    critical=skill_id in critical_ids,
                )
            )

    return sorted(gaps, key=lambda item: (not item.critical, -item.gap, item.skill_id))


def _skill_names(skills: Sequence[Mapping[str, Any]]) -> dict[str, str]:
    names_by_id: dict[str, str] = {}
    for skill in skills:
        skill_id = skill.get("skill_id")
        name = skill.get("name")
        if not isinstance(skill_id, str) or not isinstance(name, str):
            raise SkillGapValidationError(
                "Every skill catalog entry must include string 'skill_id' and 'name'."
            )
        names_by_id[skill_id] = name
    return names_by_id


def _validate_level(value: Any, label: str) -> None:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise SkillGapValidationError(f"{label} must be numeric.")
