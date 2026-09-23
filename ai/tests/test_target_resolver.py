import pytest

from ai.engine.target_resolver import (
    RoleProfileNotFoundError,
    find_role_profile,
    resolve_target,
)


def test_career_goal_has_priority_over_automatic_next_grade():
    employee = {
        "role": "Engineer",
        "grade": "Junior",
        "career_goal": {"target_role": "Architect", "target_grade": "Senior"},
    }

    result = resolve_target(employee)

    assert result.source == "career_goal"
    assert result.target is not None
    assert result.target.role == "Architect"
    assert result.target.grade == "Senior"


def test_null_career_goal_uses_next_grade_for_current_role():
    result = resolve_target({"role": "Engineer", "grade": "Middle", "career_goal": None})

    assert result.source == "next_grade"
    assert result.target is not None
    assert result.target.role == "Engineer"
    assert result.target.grade == "Senior"


def test_lead_without_goal_has_no_automatic_next_grade_target():
    result = resolve_target({"role": "Engineer", "grade": "Lead", "career_goal": None})

    assert result.target is None
    assert result.source == "no_automatic_target"
    assert "No automatic next-grade target" in result.reason


def test_missing_role_profile_raises_explicit_error():
    with pytest.raises(RoleProfileNotFoundError, match="Role profile not found"):
        find_role_profile([], "Engineer", "Senior")


def test_role_profile_lookup_matches_role_and_grade():
    profile = {"role": "Engineer", "grade": "Senior", "required_skills": {}}
    assert find_role_profile([profile], "Engineer", "Senior") is profile
