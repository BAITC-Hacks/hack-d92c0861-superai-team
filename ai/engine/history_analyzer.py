"""Employee-scoped participation summaries and candidate-relevant history facts."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from numbers import Real
from typing import Any

from ai.schemas.recommendation import CandidateActivity, HistorySignals, HistorySummary


SUPPORTED_STATUSES = frozenset(
    {"completed", "in_progress", "dropped", "no_show", "declined", "overdue"}
)
NEGATIVE_STATUSES = frozenset({"dropped", "no_show", "declined", "overdue"})


class HistoryValidationError(ValueError):
    """Raised when relevant participation history cannot be interpreted safely."""


def summarize_history(
    employee_id: str, activity_history: Sequence[Mapping[str, Any]]
) -> HistorySummary:
    """Summarize supported participation statuses for exactly one employee."""
    records = _employee_records(employee_id, activity_history)
    counts = Counter(_status(record) for record in records)
    total_records = len(records)
    completed_count = counts["completed"]
    return HistorySummary(
        total_records=total_records,
        completed_count=completed_count,
        in_progress_count=counts["in_progress"],
        dropped_count=counts["dropped"],
        no_show_count=counts["no_show"],
        declined_count=counts["declined"],
        overdue_count=counts["overdue"],
        completion_rate=completed_count / total_records if total_records else 0.0,
    )


def analyze_candidate_history(
    employee_id: str,
    candidate: CandidateActivity,
    activity_history: Sequence[Mapping[str, Any]],
    events: Sequence[Mapping[str, Any]],
) -> HistorySignals:
    """Return same-event and similarity signals for one employee and candidate.

    Events are considered similar only when a known historical event has the
    same type or develops an affected candidate skill. Records for other
    employees are excluded before any counting takes place.
    """
    events_by_id = _events_by_id(events)
    candidate_skills = {impact.skill_id for impact in candidate.affected_skills}
    same_event_records = 0
    same_event_completed = 0
    similar_records = 0
    similar_completed = 0
    similar_negative = 0
    shared_skill_records = 0
    shared_skill_completed = 0
    feedback_ratings: list[float] = []
    assignment_sources: Counter[str] = Counter()

    for record in _employee_records(employee_id, activity_history):
        event_id = _required_event_id(record, employee_id)
        same_event = event_id == candidate.event_id
        historical_event = events_by_id.get(event_id)
        shared_skill = False
        same_type = False
        if historical_event is not None:
            shared_skill = bool(candidate_skills & _developed_skill_ids(historical_event))
            historical_type = historical_event.get("type")
            if not isinstance(historical_type, str):
                raise HistoryValidationError(
                    f"Event '{event_id}' is missing a valid type for history analysis."
                )
            same_type = historical_type == candidate.event_type
        if not (same_event or shared_skill or same_type):
            continue

        status = _status(record)
        similar_records += 1
        same_event_records += int(same_event)
        shared_skill_records += int(shared_skill)
        if status == "completed":
            similar_completed += 1
            same_event_completed += int(same_event)
            shared_skill_completed += int(shared_skill)
        if status in NEGATIVE_STATUSES:
            similar_negative += 1
        feedback_rating = _feedback_rating(record)
        if feedback_rating is not None:
            feedback_ratings.append(feedback_rating)
        assigned_by = record.get("assigned_by")
        if isinstance(assigned_by, str) and assigned_by:
            assignment_sources[assigned_by] += 1

    average_feedback = (
        sum(feedback_ratings) / len(feedback_ratings) if feedback_ratings else None
    )
    return HistorySignals(
        same_event_records=same_event_records,
        same_event_completed=same_event_completed,
        similar_records=similar_records,
        similar_completed=similar_completed,
        similar_negative=similar_negative,
        shared_skill_records=shared_skill_records,
        shared_skill_completed=shared_skill_completed,
        average_feedback_rating=average_feedback,
        assignment_sources=tuple(sorted(assignment_sources.items())),
    )


def _employee_records(
    employee_id: str, activity_history: Sequence[Mapping[str, Any]]
) -> list[Mapping[str, Any]]:
    if not isinstance(employee_id, str) or not employee_id:
        raise HistoryValidationError("employee_id must be a non-empty string.")
    return [record for record in activity_history if record.get("employee_id") == employee_id]


def _status(record: Mapping[str, Any]) -> str:
    status = record.get("status")
    if not isinstance(status, str) or status not in SUPPORTED_STATUSES:
        raise HistoryValidationError(f"History record has unsupported status: {status!r}.")
    return status


def _events_by_id(events: Sequence[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    indexed_events: dict[str, Mapping[str, Any]] = {}
    for event in events:
        event_id = event.get("event_id")
        if not isinstance(event_id, str) or not event_id:
            raise HistoryValidationError("Event data contains an entry without a valid event_id.")
        indexed_events[event_id] = event
    return indexed_events


def _developed_skill_ids(event: Mapping[str, Any]) -> set[str]:
    developments = event.get("develops_skills")
    if not isinstance(developments, list):
        raise HistoryValidationError(
            f"Event '{event.get('event_id')}' has malformed develops_skills data."
        )
    skill_ids: set[str] = set()
    for development in developments:
        if not isinstance(development, Mapping) or not isinstance(
            development.get("skill_id"), str
        ):
            raise HistoryValidationError(
                f"Event '{event.get('event_id')}' has malformed skill development data."
            )
        skill_ids.add(development["skill_id"])
    return skill_ids


def _required_event_id(record: Mapping[str, Any], employee_id: str) -> str:
    event_id = record.get("event_id")
    if not isinstance(event_id, str) or not event_id:
        raise HistoryValidationError(
            f"History record for employee '{employee_id}' is missing a valid event_id."
        )
    return event_id


def _feedback_rating(record: Mapping[str, Any]) -> float | None:
    value = record.get("feedback_rating")
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        raise HistoryValidationError("feedback_rating must be numeric when present.")
    if isinstance(value, str):
        try:
            value = float(value)
        except ValueError as error:
            raise HistoryValidationError("feedback_rating must be numeric when present.") from error
    if not isinstance(value, Real):
        raise HistoryValidationError("feedback_rating must be numeric when present.")
    return float(value)
