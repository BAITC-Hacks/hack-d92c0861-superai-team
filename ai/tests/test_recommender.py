import csv
import json

import pytest

from ai.engine.data_loader import DataLoader, EmployeeNotFoundError
from ai.engine.recommender import DeterministicRecommender


def _event(event_id, event_type, develops_skills, *, mandatory=False):
    return {
        "event_id": event_id,
        "title": event_id,
        "description": "Synthetic event",
        "type": event_type,
        "format": "online",
        "duration_hours": 2,
        "mandatory": mandatory,
        "target_roles": ["Engineer"],
        "target_grades": ["Senior"],
        "develops_skills": develops_skills,
        "prerequisites": {},
        "upcoming_sessions": [],
    }


def _write_dataset(tmp_path, employees, events, history):
    skills = [
        {"skill_id": "system", "name": "System Design"},
        {"skill_id": "public", "name": "Public Speaking"},
    ]
    profiles = [
        {
            "role": "Engineer",
            "grade": "Senior",
            "required_skills": {"system": 3, "public": 5},
            "critical_skills": ["system"],
        }
    ]
    (tmp_path / "employees.json").write_text(json.dumps({"employees": employees}), encoding="utf-8")
    (tmp_path / "skills.json").write_text(
        json.dumps({"skills": skills, "role_profiles": profiles}), encoding="utf-8"
    )
    (tmp_path / "events.json").write_text(json.dumps({"events": events}), encoding="utf-8")
    columns = list(DataLoader.HISTORY_COLUMNS)
    with (tmp_path / "activity_history.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        for record in history:
            writer.writerow(record)


def _employee(employee_id, *, lead=False):
    return {
        "employee_id": employee_id,
        "role": "Engineer",
        "grade": "Lead" if lead else "Middle",
        "career_goal": None if lead else {"target_role": "Engineer", "target_grade": "Senior"},
        "skills": {"system": 0, "public": 0},
    }


def test_recommender_prioritizes_critical_system_skill_over_low_skill_with_negative_history(tmp_path):
    employees = [_employee("employee-adversarial")]
    events = [
        _event("system-candidate", "architecture", [{"skill_id": "system", "gain": 2, "max_level": 5}]),
        _event("public-candidate", "presentation", [{"skill_id": "public", "gain": 5, "max_level": 5}]),
        _event("public-history-one", "presentation", [{"skill_id": "public", "gain": 1, "max_level": 5}], mandatory=True),
        _event("public-history-two", "presentation", [{"skill_id": "public", "gain": 1, "max_level": 5}], mandatory=True),
        _event("public-history-three", "presentation", [{"skill_id": "public", "gain": 1, "max_level": 5}], mandatory=True),
    ]
    history = [
        {"record_id": f"record-{index}", "employee_id": "employee-adversarial", "event_id": event_id, "status": "no_show"}
        for index, event_id in enumerate(["public-history-one", "public-history-two", "public-history-three"])
    ]
    _write_dataset(tmp_path, employees, events, history)

    result = DeterministicRecommender(DataLoader.from_directory(tmp_path)).recommend(
        "employee-adversarial", top_k=2
    )

    assert result.target is not None
    assert result.target.grade == "Senior"
    assert [scored.candidate.event_id for scored in result.candidates] == [
        "system-candidate",
        "public-candidate",
    ]
    assert result.candidates[0].factors.critical_skill_impact > 0
    assert result.candidates[1].factors.history_fit < result.candidates[0].factors.history_fit


def test_recommender_handles_top_k_empty_candidates_unknown_employee_and_no_automatic_target(tmp_path):
    employees = [_employee("employee-no-events"), _employee("employee-lead", lead=True), _employee("employee-added")]
    mandatory_only = [_event("mandatory", "architecture", [{"skill_id": "system", "gain": 1, "max_level": 5}], mandatory=True)]
    _write_dataset(tmp_path, employees, mandatory_only, [])
    recommender = DeterministicRecommender(DataLoader.from_directory(tmp_path))

    empty = recommender.recommend("employee-no-events", top_k=5)
    lead = recommender.recommend("employee-lead")
    added = recommender.recommend("employee-added")

    assert empty.candidates == ()
    assert lead.target is None
    assert lead.target_source == "no_automatic_target"
    assert added.employee_id == "employee-added"
    with pytest.raises(EmployeeNotFoundError):
        recommender.recommend("unknown-employee")
