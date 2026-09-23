"""Owner: Damir. Load official wrapped JSON and CSV without changing seed files."""
from __future__ import annotations
import csv
import io
import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

GRADES = ("Junior", "Middle", "Senior", "Lead")
STATUSES = {"completed", "in_progress", "dropped", "no_show", "declined", "overdue"}
CSV_COLUMNS = {"record_id", "employee_id", "event_id", "date", "due_date", "status",
               "completion_pct", "score", "feedback_rating", "assigned_by"}

class DatasetError(ValueError):
    pass

@dataclass
class Dataset:
    as_of_date: date
    employees: dict[str, dict[str, Any]]
    events: dict[str, dict[str, Any]]
    skills: dict[str, dict[str, Any]]
    role_profiles: dict[tuple[str, str], dict[str, Any]]
    history: list[dict[str, str]]
    version: int = 1

    def employee_history(self, employee_id: str) -> list[dict[str, str]]:
        return [r for r in self.history if r["employee_id"] == employee_id]


def read_json(raw: bytes) -> dict:
    try:
        value = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise DatasetError(f"Invalid UTF-8 JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise DatasetError("Official JSON must be an object with meta and a named array")
    return value


def read_history(raw: bytes) -> list[dict[str, str]]:
    try:
        reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig"), newline=""))
        if not CSV_COLUMNS.issubset(set(reader.fieldnames or [])):
            raise DatasetError(f"Missing CSV columns: {sorted(CSV_COLUMNS-set(reader.fieldnames or []))}")
        rows = list(reader)
        if any(None in row or any(value is None for value in row.values()) for row in rows):
            raise DatasetError("Malformed CSV row: column count does not match header")
        return rows
    except UnicodeError as exc:
        raise DatasetError("CSV must be UTF-8") from exc


def index_unique(rows: list[dict], key: str) -> dict[str, dict]:
    if not isinstance(rows, list):
        raise DatasetError(f"{key}: expected an array")
    result = {}
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get(key), str) or not row[key]:
            raise DatasetError(f"Invalid {key}")
        if row[key] in result:
            raise DatasetError(f"Duplicate {key}: {row[key]}")
        result[row[key]] = row
    return result


def level(value: Any, label: str) -> None:
    if type(value) is not int or not 0 <= value <= 5:
        raise DatasetError(f"{label}: expected integer 0..5")


def parse_dataset(employees_doc: dict, events_doc: dict, skills_doc: dict,
                  history: list[dict[str, str]]) -> Dataset:
    """Also call this against an assembled candidate snapshot BEFORE committing imports."""
    try:
        snapshot = date.fromisoformat(employees_doc["meta"]["as_of_date"])
        for doc in (events_doc, skills_doc):
            if date.fromisoformat(doc["meta"]["as_of_date"]) != snapshot:
                raise DatasetError("as_of_date must agree across all JSON files")
        employees = index_unique(employees_doc["employees"], "employee_id")
        events = index_unique(events_doc["events"], "event_id")
        skills = index_unique(skills_doc["skills"], "skill_id")
        profiles = {}
        for profile in skills_doc["role_profiles"]:
            key = (profile["role"], profile["grade"])
            if key in profiles or profile["grade"] not in GRADES:
                raise DatasetError(f"Invalid / duplicate role profile: {key}")
            profiles[key] = profile
            for sid, value in profile["required_skills"].items():
                if sid not in skills: raise DatasetError(f"Unknown skill {sid}")
                level(value, sid)
            if not set(profile["critical_skills"]).issubset(profile["required_skills"]):
                raise DatasetError(f"Critical skill without requirement: {key}")
        for employee in employees.values():
            eid = employee["employee_id"]
            if (employee["role"], employee["grade"]) not in profiles:
                raise DatasetError(f"Unknown role/grade: {eid}")
            if employee["manager_id"] is not None and employee["manager_id"] not in employees:
                raise DatasetError(f"Unknown manager: {eid}")
            if date.fromisoformat(employee["last_review_date"]) > snapshot:
                raise DatasetError(f"Assessment after snapshot: {eid}")
            date.fromisoformat(employee["hire_date"])
            if type(employee["tenure_months"]) is not int or employee["tenure_months"] < 0:
                raise DatasetError(f"Invalid tenure: {eid}")
            if employee["work_format"] not in {"office", "remote", "hybrid"}:
                raise DatasetError(f"Invalid work format: {eid}")
            if employee["preferred_language"] not in {"en", "ru", "kk"}:
                raise DatasetError(f"Invalid language: {eid}")
            for sid, value in employee["skills"].items():
                if sid not in skills: raise DatasetError(f"Unknown skill: {sid}")
                level(value, sid)
            goal = employee.get("career_goal")
            if goal and (goal["target_role"], goal["target_grade"]) not in profiles:
                raise DatasetError(f"Unknown career goal: {eid}")
        for event in events.values():
            if type(event["mandatory"]) is not bool:
                raise DatasetError("mandatory must be boolean")
            if event["format"] not in {"online", "offline", "self_paced"}:
                raise DatasetError("Unknown event format")
            if float(event["duration_hours"]) <= 0:
                raise DatasetError("duration_hours must be positive")
            for sid, value in event["prerequisites"].items():
                if sid not in skills: raise DatasetError(f"Unknown prerequisite: {sid}")
                level(value, sid)
            seen_skills = set()
            for change in event["develops_skills"]:
                sid = change["skill_id"]
                if sid not in skills or sid in seen_skills:
                    raise DatasetError(f"Unknown / duplicate event skill: {sid}")
                seen_skills.add(sid)
                level(change["gain"], "gain"); level(change["max_level"], "max_level")
            for session in event["upcoming_sessions"]: date.fromisoformat(session)
        index_unique(history, "record_id")
        for row in history:
            if row["employee_id"] not in employees or row["event_id"] not in events:
                raise DatasetError(f"Orphan history row: {row['record_id']}")
            if row["status"] not in STATUSES:
                raise DatasetError(f"Unknown status: {row['status']}")
            if date.fromisoformat(row["date"]) > snapshot:
                raise DatasetError(f"History after snapshot: {row['record_id']}")
            if row["due_date"]: date.fromisoformat(row["due_date"])
            pct = int(row["completion_pct"])
            if not 0 <= pct <= 100 or (row["status"] == "completed" and pct != 100):
                raise DatasetError("Invalid completion_pct")
            for field, lo, hi in (("score", 0, 100), ("feedback_rating", 1, 5)):
                if row[field] and not lo <= int(row[field]) <= hi:
                    raise DatasetError(f"Invalid {field}")
            if row["assigned_by"] not in {"self", "manager", "hr"}:
                raise DatasetError("Invalid assigned_by")
        return Dataset(snapshot, employees, events, skills, profiles,
                       sorted(history, key=lambda r: (r["date"], r["record_id"])))
    except (KeyError, TypeError, ValueError) as exc:
        if isinstance(exc, DatasetError): raise
        raise DatasetError(f"Dataset schema error: {exc}") from exc


def load_dataset(folder: Path) -> Dataset:
    try:
        return parse_dataset(
            read_json((folder/"employees.json").read_bytes()),
            read_json((folder/"events.json").read_bytes()),
            read_json((folder/"skills.json").read_bytes()),
            read_history((folder/"activity_history.csv").read_bytes()))
    except OSError as exc:
        raise DatasetError(f"Cannot read dataset from {folder}. Run scripts/seed_data.py first.") from exc
