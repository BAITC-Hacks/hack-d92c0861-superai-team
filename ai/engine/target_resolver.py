"""Career target and role-profile resolution without LLM involvement."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence


GRADE_PROGRESSION = ("Junior", "Middle", "Senior", "Lead")


class TargetResolutionError(ValueError):
    """Raised when an employee's target cannot be deterministically resolved."""


class RoleProfileNotFoundError(LookupError):
    """Raised when no role profile exists for a resolved role and grade."""


@dataclass(frozen=True)
class CareerTarget:
    role: str
    grade: str


@dataclass(frozen=True)
class TargetResolution:
    """A resolved target, or an explicit reason why automatic resolution stopped."""

    target: CareerTarget | None
    source: str
    reason: str | None = None


def resolve_target(employee: Mapping[str, Any]) -> TargetResolution:
    """Resolve career_goal first, otherwise promote to the next grade in-role.

    For a Lead without a career goal, ``target`` is ``None`` and ``reason``
    explains that a higher automatic grade is unavailable.
    """
    career_goal = employee.get("career_goal")
    if career_goal is not None:
        if not isinstance(career_goal, Mapping):
            raise TargetResolutionError("Employee career_goal must be an object or null.")
        role = _required_text(career_goal, "target_role", "career_goal")
        grade = _required_text(career_goal, "target_grade", "career_goal")
        return TargetResolution(CareerTarget(role=role, grade=grade), source="career_goal")

    role = _required_text(employee, "role", "employee")
    current_grade = _required_text(employee, "grade", "employee")
    try:
        grade_index = GRADE_PROGRESSION.index(current_grade)
    except ValueError as error:
        raise TargetResolutionError(
            f"Employee grade '{current_grade}' is not in the supported grade progression."
        ) from error

    if grade_index == len(GRADE_PROGRESSION) - 1:
        return TargetResolution(
            target=None,
            source="no_automatic_target",
            reason=f"No automatic next-grade target exists for {current_grade}.",
        )
    return TargetResolution(
        target=CareerTarget(role=role, grade=GRADE_PROGRESSION[grade_index + 1]),
        source="next_grade",
    )


def find_role_profile(
    role_profiles: Sequence[Mapping[str, Any]], role: str, grade: str
) -> Mapping[str, Any]:
    """Find the exact role-and-grade profile or raise a clear lookup error."""
    for profile in role_profiles:
        if profile.get("role") == role and profile.get("grade") == grade:
            return profile
    raise RoleProfileNotFoundError(
        f"Role profile not found for role '{role}' and grade '{grade}'."
    )


def _required_text(source: Mapping[str, Any], key: str, source_name: str) -> str:
    value = source.get(key)
    if not isinstance(value, str) or not value.strip():
        raise TargetResolutionError(f"{source_name} is missing a valid '{key}'.")
    return value
