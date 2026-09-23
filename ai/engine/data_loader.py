"""Loading and basic validation for Career Quest dataset files."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


JsonObject = dict[str, Any]


class DatasetValidationError(ValueError):
    """Raised when a dataset file does not match the required basic shape."""


class EmployeeNotFoundError(LookupError):
    """Raised when an employee ID cannot be found in loaded employee data."""


@dataclass(frozen=True)
class DatasetPaths:
    """Locations of the four dataset files used by the deterministic engine."""

    employees: Path
    skills: Path
    events: Path
    activity_history: Path

    @classmethod
    def from_directory(cls, directory: str | Path) -> "DatasetPaths":
        """Build paths for dataset files with their standard file names."""
        base_path = Path(directory)
        return cls(
            employees=base_path / "employees.json",
            skills=base_path / "skills.json",
            events=base_path / "events.json",
            activity_history=base_path / "activity_history.csv",
        )


@dataclass(frozen=True)
class Dataset:
    """The loaded dataset, kept as source-shaped dictionaries for easy integration."""

    employees: list[JsonObject]
    skills: list[JsonObject]
    role_profiles: list[JsonObject]
    events: list[JsonObject]
    activity_history: list[dict[str, str]]


class DataLoader:
    """Load Career Quest files from configurable paths.

    The loader deliberately performs only basic structural validation. Domain
    logic belongs in the focused engine modules rather than in I/O code.
    """

    HISTORY_COLUMNS = frozenset(
        {
            "record_id",
            "employee_id",
            "event_id",
            "date",
            "due_date",
            "status",
            "completion_pct",
            "score",
            "feedback_rating",
            "assigned_by",
        }
    )

    def __init__(self, paths: DatasetPaths) -> None:
        self.paths = paths

    @classmethod
    def from_directory(cls, directory: str | Path) -> "DataLoader":
        """Create a loader for a directory using the standard dataset names."""
        return cls(DatasetPaths.from_directory(directory))

    def load_employees(self) -> list[JsonObject]:
        payload = self._load_json(self.paths.employees, "employees")
        return self._required_list(payload, "employees", self.paths.employees)

    def load_skills(self) -> JsonObject:
        payload = self._load_json(self.paths.skills, "skills")
        self._required_list(payload, "skills", self.paths.skills)
        self._required_list(payload, "role_profiles", self.paths.skills)
        return payload

    def load_events(self) -> list[JsonObject]:
        payload = self._load_json(self.paths.events, "events")
        return self._required_list(payload, "events", self.paths.events)

    def load_activity_history(self) -> list[dict[str, str]]:
        path = self.paths.activity_history
        try:
            with path.open("r", encoding="utf-8-sig", newline="") as file:
                reader = csv.DictReader(file)
                headers = set(reader.fieldnames or [])
                missing = self.HISTORY_COLUMNS - headers
                if missing:
                    names = ", ".join(sorted(missing))
                    raise DatasetValidationError(
                        f"Activity history file '{path}' is missing required columns: {names}."
                    )
                return [dict(row) for row in reader]
        except FileNotFoundError as error:
            raise FileNotFoundError(f"Dataset file not found: '{path}'.") from error
        except csv.Error as error:
            raise DatasetValidationError(
                f"Activity history file '{path}' is malformed CSV: {error}."
            ) from error

    def load_all(self) -> Dataset:
        """Load all Phase 1 source files in one operation."""
        skills_payload = self.load_skills()
        return Dataset(
            employees=self.load_employees(),
            skills=self._required_list(skills_payload, "skills", self.paths.skills),
            role_profiles=self._required_list(
                skills_payload, "role_profiles", self.paths.skills
            ),
            events=self.load_events(),
            activity_history=self.load_activity_history(),
        )

    @staticmethod
    def get_employee(
        employees: list[Mapping[str, Any]], employee_id: str
    ) -> Mapping[str, Any]:
        """Return an employee by ID or raise an explicit lookup error."""
        for employee in employees:
            if employee.get("employee_id") == employee_id:
                return employee
        raise EmployeeNotFoundError(f"Employee not found: '{employee_id}'.")

    @staticmethod
    def _load_json(path: Path, label: str) -> JsonObject:
        try:
            with path.open("r", encoding="utf-8") as file:
                payload = json.load(file)
        except FileNotFoundError as error:
            raise FileNotFoundError(f"Dataset file not found: '{path}'.") from error
        except json.JSONDecodeError as error:
            raise DatasetValidationError(
                f"{label.capitalize()} file '{path}' contains invalid JSON: {error.msg}."
            ) from error

        if not isinstance(payload, dict):
            raise DatasetValidationError(
                f"{label.capitalize()} file '{path}' must contain a JSON object at the top level."
            )
        return payload

    @staticmethod
    def _required_list(payload: JsonObject, key: str, path: Path) -> list[JsonObject]:
        value = payload.get(key)
        if not isinstance(value, list):
            raise DatasetValidationError(
                f"Dataset file '{path}' must contain a '{key}' list."
            )
        if not all(isinstance(item, dict) for item in value):
            raise DatasetValidationError(
                f"Dataset file '{path}' contains a non-object item in '{key}'."
            )
        return value
