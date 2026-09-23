from ai.engine.skill_gap import calculate_skill_gaps


SKILL_CATALOG = [
    {"skill_id": "skill-critical", "name": "Critical Skill"},
    {"skill_id": "skill-large", "name": "Large Gap Skill"},
    {"skill_id": "skill-small", "name": "Small Gap Skill"},
    {"skill_id": "skill-met", "name": "Already Met Skill"},
]


def test_missing_employee_skill_defaults_to_zero_and_calculates_gap():
    gaps = calculate_skill_gaps(
        {"skills": {}},
        {
            "required_skills": {"skill-critical": 3},
            "critical_skills": ["skill-critical"],
        },
        SKILL_CATALOG,
    )

    assert len(gaps) == 1
    gap = gaps[0]
    assert (gap.skill_id, gap.skill_name) == ("skill-critical", "Critical Skill")
    assert (gap.current_level, gap.required_level, gap.gap, gap.critical) == (0, 3, 3, True)


def test_critical_gaps_sort_before_larger_noncritical_gaps():
    gaps = calculate_skill_gaps(
        {"skills": {"skill-critical": 2, "skill-large": 0, "skill-small": 1}},
        {
            "required_skills": {
                "skill-small": 2,
                "skill-large": 5,
                "skill-critical": 3,
            },
            "critical_skills": ["skill-critical"],
        },
        SKILL_CATALOG,
    )

    assert [gap.skill_id for gap in gaps] == [
        "skill-critical",
        "skill-large",
        "skill-small",
    ]
    assert [gap.gap for gap in gaps] == [1, 5, 1]


def test_returns_no_gap_when_employee_meets_or_exceeds_requirement():
    gaps = calculate_skill_gaps(
        {"skills": {"skill-met": 5}},
        {"required_skills": {"skill-met": 4}, "critical_skills": ["skill-met"]},
        SKILL_CATALOG,
    )

    assert gaps == []
