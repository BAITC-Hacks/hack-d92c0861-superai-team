import csv
import json

import pytest

from ai.engine.data_loader import (
    DataLoader,
    DatasetPaths,
    DatasetValidationError,
    EmployeeNotFoundError,
)


def _write_dataset(tmp_path):
    (tmp_path / "employees.json").write_text(
        json.dumps({"employees": [{"employee_id": "employee-a", "skills": {}}]}),
        encoding="utf-8",
    )
    (tmp_path / "skills.json").write_text(
        json.dumps(
            {
                "skills": [{"skill_id": "skill-a", "name": "Skill A"}],
                "role_profiles": [],
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "events.json").write_text(json.dumps({"events": []}), encoding="utf-8")
    columns = sorted(DataLoader.HISTORY_COLUMNS)
    with (tmp_path / "activity_history.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        writer.writerow({"record_id": "record-a", "employee_id": "employee-a"})


def test_loads_json_and_csv_files(tmp_path):
    _write_dataset(tmp_path)
    loader = DataLoader.from_directory(tmp_path)

    dataset = loader.load_all()

    assert dataset.employees[0]["employee_id"] == "employee-a"
    assert dataset.skills[0]["name"] == "Skill A"
    assert dataset.events == []
    assert dataset.activity_history == [
        {column: ("record-a" if column == "record_id" else "employee-a" if column == "employee_id" else "")
         for column in sorted(DataLoader.HISTORY_COLUMNS)}
    ]


def test_employee_lookup_returns_matching_record_and_missing_is_explicit(tmp_path):
    _write_dataset(tmp_path)
    employees = DataLoader.from_directory(tmp_path).load_employees()

    assert DataLoader.get_employee(employees, "employee-a")["employee_id"] == "employee-a"
    with pytest.raises(EmployeeNotFoundError, match="Employee not found"):
        DataLoader.get_employee(employees, "not-present")


def test_loader_rejects_missing_required_json_list(tmp_path):
    paths = DatasetPaths(
        employees=tmp_path / "employees.json",
        skills=tmp_path / "skills.json",
        events=tmp_path / "events.json",
        activity_history=tmp_path / "activity_history.csv",
    )
    paths.employees.write_text(json.dumps({"not_employees": []}), encoding="utf-8")

    with pytest.raises(DatasetValidationError, match="'employees' list"):
        DataLoader(paths).load_employees()
