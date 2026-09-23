from ai.engine.candidate_generator import generate_candidates
from ai.engine.skill_gap import SkillGap
from ai.engine.target_resolver import CareerTarget


TARGET = CareerTarget(role="Test Engineer", grade="Senior")
EMPLOYEE = {"employee_id": "test-employee", "skills": {"skill-a": 2, "skill-b": 1}}
GAPS = [
    SkillGap("skill-a", "Skill A", 2, 4, 2, True),
    SkillGap("skill-b", "Skill B", 1, 3, 2, False),
]


def _event(**changes):
    event = {
        "event_id": "event-a",
        "title": "Skill A workshop",
        "type": "workshop",
        "duration_hours": 2,
        "mandatory": False,
        "target_roles": ["Test Engineer"],
        "target_grades": ["Senior"],
        "prerequisites": {},
        "develops_skills": [{"skill_id": "skill-a", "gain": 1, "max_level": 5}],
    }
    event.update(changes)
    return event


def _candidates(event, employee=EMPLOYEE, history=()):
    return generate_candidates(employee, TARGET, GAPS, [event], history)


def test_mandatory_event_is_rejected():
    assert _candidates(_event(mandatory=True)) == []


def test_wrong_role_or_grade_is_rejected():
    assert _candidates(_event(target_roles=["Different Role"])) == []
    assert _candidates(_event(target_grades=["Junior"])) == []


def test_unmet_prerequisite_and_missing_skill_default_to_zero_are_rejected():
    assert _candidates(_event(prerequisites={"skill-a": 3})) == []
    assert _candidates(_event(prerequisites={"missing-skill": 1})) == []


def test_empty_or_irrelevant_skill_development_is_rejected():
    assert _candidates(_event(develops_skills=[])) == []
    assert _candidates(
        _event(develops_skills=[{"skill_id": "not-a-gap", "gain": 2, "max_level": 5}])
    ) == []


def test_completed_non_repeatable_event_is_rejected():
    history = [{"employee_id": "test-employee", "event_id": "event-a", "status": "completed"}]
    assert _candidates(_event(), history=history) == []


def test_explicitly_repeatable_completed_event_is_eligible():
    history = [{"employee_id": "test-employee", "event_id": "event-a", "status": "completed"}]
    candidates = _candidates(_event(repeatable=True), history=history)
    assert [candidate.event_id for candidate in candidates] == ["event-a"]


def test_eligible_event_calculates_effective_gain_with_max_level():
    candidates = _candidates(
        _event(develops_skills=[{"skill_id": "skill-a", "gain": 2, "max_level": 3}])
    )

    impact = candidates[0].affected_skills[0]
    assert impact.current_level == 2
    assert impact.required_level == 4
    assert impact.gap_before == 2
    assert impact.expected_level_after_completion == 3
    assert impact.gap_after == 1
    assert impact.effective_gain == 1
    assert impact.critical is True


def test_event_can_affect_multiple_relevant_gaps():
    candidates = _candidates(
        _event(
            develops_skills=[
                {"skill_id": "skill-a", "gain": 1, "max_level": 5},
                {"skill_id": "skill-b", "gain": 2, "max_level": 3},
            ]
        )
    )

    assert [impact.skill_id for impact in candidates[0].affected_skills] == ["skill-a", "skill-b"]
    assert [impact.effective_gain for impact in candidates[0].affected_skills] == [1, 2]
