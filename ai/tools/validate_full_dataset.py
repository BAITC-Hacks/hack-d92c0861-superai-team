"""Read-only Phase 2.5 validation for a Career Quest dataset directory.

Run from the repository root, for example:

    python -m ai.tools.validate_full_dataset --data-dir docs

The command does not alter any dataset or recommendation source file.
"""

from __future__ import annotations

import argparse
import time
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from statistics import mean
from typing import Any

from ai.engine.candidate_generator import is_event_repeatable
from ai.engine.data_loader import DataLoader, Dataset
from ai.engine.recommender import DeterministicRecommender
from ai.engine.target_resolver import CareerTarget


DATASET_FILENAMES = (
    "employees.json",
    "skills.json",
    "events.json",
    "activity_history.csv",
)


def find_dataset_directory(repository_root: Path | None = None) -> Path | None:
    """Locate a complete local dataset without assuming a record count.

    Phase 2.5 treats ``data/`` as the intended full-dataset location. A caller
    may still pass another directory explicitly to diagnose it.
    """
    root = repository_root or Path(__file__).resolve().parents[2]
    candidate = root / "data"
    if all((candidate / filename).is_file() for filename in DATASET_FILENAMES):
        return candidate
    return None


def validate_full_dataset(data_directory: str | Path) -> dict[str, Any]:
    """Load a dataset, validate it, and sweep every employee without mutation."""
    directory = Path(data_directory)
    loader = DataLoader.from_directory(directory)
    dataset = loader.load_all()
    reference_issues = validate_references(dataset)
    sweep = sweep_employees(loader, dataset)
    return {
        "data_directory": str(directory),
        "dataset": {
            "employees": len(dataset.employees),
            "skills": len(dataset.skills),
            "role_profiles": len(dataset.role_profiles),
            "events": len(dataset.events),
            "activity_history": len(dataset.activity_history),
        },
        "invalid_references": reference_issues,
        "sweep": sweep,
    }


def validate_references(dataset: Dataset) -> list[str]:
    """Return explicit cross-file reference and identifier consistency issues."""
    issues: list[str] = []
    employee_ids = _valid_ids(dataset.employees, "employee_id", "employee", issues)
    skill_ids = _valid_ids(dataset.skills, "skill_id", "skill", issues)
    event_ids = _valid_ids(dataset.events, "event_id", "event", issues)
    profile_keys = {
        (profile.get("role"), profile.get("grade"))
        for profile in dataset.role_profiles
        if isinstance(profile.get("role"), str) and isinstance(profile.get("grade"), str)
    }

    for employee in dataset.employees:
        employee_id = employee.get("employee_id", "<missing employee_id>")
        _check_skill_mapping(employee.get("skills"), skill_ids, f"employee {employee_id}", issues)
        if (employee.get("role"), employee.get("grade")) not in profile_keys:
            issues.append(
                f"Employee {employee_id} role/grade has no profile: "
                f"{employee.get('role')!r}/{employee.get('grade')!r}."
            )

    for profile in dataset.role_profiles:
        profile_label = f"role profile {profile.get('role')!r}/{profile.get('grade')!r}"
        _check_skill_mapping(profile.get("required_skills"), skill_ids, profile_label, issues)
        critical_skills = profile.get("critical_skills")
        if not isinstance(critical_skills, list):
            issues.append(f"{profile_label} critical_skills is not a list.")
        else:
            for skill_id in critical_skills:
                if skill_id not in skill_ids:
                    issues.append(f"{profile_label} references unknown critical skill {skill_id!r}.")

    for event in dataset.events:
        event_label = f"event {event.get('event_id', '<missing event_id>')!r}"
        developments = event.get("develops_skills")
        if not isinstance(developments, list):
            issues.append(f"{event_label} develops_skills is not a list.")
        else:
            for development in developments:
                if not isinstance(development, Mapping):
                    issues.append(f"{event_label} has a malformed skill development entry.")
                elif development.get("skill_id") not in skill_ids:
                    issues.append(
                        f"{event_label} references unknown developed skill "
                        f"{development.get('skill_id')!r}."
                    )
        _check_skill_mapping(event.get("prerequisites"), skill_ids, event_label, issues)

    for record in dataset.activity_history:
        record_id = record.get("record_id", "<missing record_id>")
        if record.get("employee_id") not in employee_ids:
            issues.append(
                f"History record {record_id!r} references unknown employee "
                f"{record.get('employee_id')!r}."
            )
        if record.get("event_id") not in event_ids:
            issues.append(
                f"History record {record_id!r} references unknown event {record.get('event_id')!r}."
            )
    return issues


def sweep_employees(loader: DataLoader, dataset: Dataset) -> dict[str, Any]:
    """Run the public recommender for every employee and collect diagnostics."""
    recommender = DeterministicRecommender(loader)
    event_count = len(dataset.events)
    events_by_id = {event["event_id"]: event for event in dataset.events}
    histories_by_employee = _history_by_employee(dataset.activity_history)
    counters: Counter[str] = Counter()
    errors: list[str] = []
    invariant_violations: list[str] = []
    zero_candidate_reasons: Counter[str] = Counter()
    top_events: Counter[str] = Counter()
    scores: list[float] = []
    candidate_counts: list[int] = []
    targeted_gap_counts: list[int] = []
    suspicious_rankings: list[dict[str, Any]] = []
    top_event_contexts: dict[str, set[tuple[str, str]]] = {}
    recommendation_durations: list[float] = []

    started_at = time.perf_counter()
    for employee in dataset.employees:
        employee_id = employee.get("employee_id")
        if not isinstance(employee_id, str):
            errors.append("Cannot process employee with missing or invalid employee_id.")
            continue
        counters["processed"] += 1
        try:
            employee_started_at = time.perf_counter()
            full_result = recommender.recommend(employee_id, top_k=event_count)
            recommendation_durations.append(time.perf_counter() - employee_started_at)
            limited_result = recommender.recommend(employee_id, top_k=min(5, event_count))
            _validate_top_k(full_result.candidates, limited_result.candidates, min(5, event_count), employee_id, invariant_violations)
            _validate_result(
                employee,
                full_result,
                events_by_id,
                histories_by_employee.get(employee_id, ()),
                invariant_violations,
            )
        except Exception as error:  # Continue the mandatory all-employee sweep.
            errors.append(f"{employee_id}: {type(error).__name__}: {error}")
            continue

        counters["successful"] += 1
        counters[f"target_source:{full_result.target_source}"] += 1
        _add_history_counts(counters, full_result.history_summary)
        if full_result.history_summary.total_records:
            counters["employees_with_history"] += 1

        if full_result.target is None:
            counters["employees_without_target"] += 1
            continue

        counters["targeted"] += 1
        positive_gap_count = len(full_result.skill_gaps)
        targeted_gap_counts.append(positive_gap_count)
        if positive_gap_count:
            counters["employees_with_positive_gaps"] += 1
        else:
            counters["employees_meeting_target"] += 1

        candidate_count = len(full_result.candidates)
        candidate_counts.append(candidate_count)
        if candidate_count:
            counters["employees_with_candidates"] += 1
            top_event_id = full_result.candidates[0].candidate.event_id
            top_events[top_event_id] += 1
            top_event_contexts.setdefault(top_event_id, set()).add(
                (full_result.target.role, full_result.target.grade)
            )
        else:
            counters["employees_without_candidates"] += 1
            if positive_gap_count:
                zero_candidate_reasons[
                    classify_zero_candidate_reason(
                        employee,
                        full_result.target,
                        full_result.skill_gaps,
                        dataset.events,
                        histories_by_employee.get(employee_id, ()),
                    )
                ] += 1
        for scored in full_result.candidates:
            scores.append(scored.score)
        suspicious_rankings.extend(_find_suspicious_rankings(employee_id, full_result.candidates))

    total_elapsed = time.perf_counter() - started_at
    _append_repetition_observations(top_events, top_event_contexts, suspicious_rankings)
    targeted = counters["targeted"]
    processed = counters["processed"]
    history_records = sum(
        counters[key]
        for key in (
            "history_completed",
            "history_in_progress",
            "history_dropped",
            "history_no_show",
            "history_declined",
            "history_overdue",
        )
    )
    return {
        "processing": {
            "employees_processed": processed,
            "successful": counters["successful"],
            "errors": errors,
            "total_seconds": sum(recommendation_durations),
            "average_seconds_per_processed_employee": (
                mean(recommendation_durations) if recommendation_durations else 0.0
            ),
            "diagnostic_wall_seconds": total_elapsed,
        },
        "targets": {
            "explicit_career_goal": counters["target_source:career_goal"],
            "automatic_next_grade": counters["target_source:next_grade"],
            "no_target_available": counters["employees_without_target"],
        },
        "gaps": {
            "employees_with_positive_skill_gaps": counters["employees_with_positive_gaps"],
            "employees_meeting_all_target_requirements": counters["employees_meeting_target"],
            "average_positive_skill_gaps_per_targeted_employee": mean(targeted_gap_counts) if targeted_gap_counts else 0.0,
        },
        "candidates": {
            "employees_with_at_least_one": counters["employees_with_candidates"],
            "employees_with_zero": counters["employees_without_candidates"],
            "average_eligible_candidates": mean(candidate_counts) if candidate_counts else 0.0,
            "minimum_eligible_candidates": min(candidate_counts) if candidate_counts else 0,
            "maximum_eligible_candidates": max(candidate_counts) if candidate_counts else 0,
            "zero_candidate_reasons": dict(sorted(zero_candidate_reasons.items())),
        },
        "top_recommendations": dict(top_events.most_common()),
        "scoring": {
            "minimum": min(scores) if scores else None,
            "average": mean(scores) if scores else None,
            "maximum": max(scores) if scores else None,
        },
        "history": {
            "employees_with_history": counters["employees_with_history"],
            "average_records_per_employee": (
                history_records / counters["successful"] if counters["successful"] else 0.0
            ),
            "completed": counters["history_completed"],
            "dropped": counters["history_dropped"],
            "no_show": counters["history_no_show"],
            "declined": counters["history_declined"],
            "overdue": counters["history_overdue"],
            "in_progress": counters["history_in_progress"],
        },
        "validation": {
            "invariant_violations": invariant_violations,
            "unexpected_exceptions": errors,
        },
        "suspicious_rankings": suspicious_rankings,
    }


def classify_zero_candidate_reason(
    employee: Mapping[str, Any],
    target: CareerTarget,
    skill_gaps: Sequence[Any],
    events: Sequence[Mapping[str, Any]],
    history: Sequence[Mapping[str, Any]],
) -> str:
    """Classify the first data-availability bottleneck for a zero-candidate case."""
    employee_skills = employee.get("skills", {})
    if not isinstance(employee_skills, Mapping):
        return "malformed_employee_skills"
    positive_gaps = {gap.skill_id for gap in skill_gaps if gap.gap > 0}
    role_events = [event for event in events if target.role in event.get("target_roles", [])]
    if not role_events:
        return "no_event_targets_role"
    grade_events = [event for event in role_events if target.grade in event.get("target_grades", [])]
    if not grade_events:
        return "no_event_targets_grade"
    relevant_developments = [
        event
        for event in grade_events
        if any(
            isinstance(development, Mapping) and development.get("skill_id") in positive_gaps
            for development in event.get("develops_skills", [])
        )
    ]
    if not relevant_developments:
        return "events_do_not_develop_required_gap_skills"
    improvable_events = [
        event
        for event in relevant_developments
        if _event_can_improve_gap(event, employee_skills, positive_gaps)
    ]
    if not improvable_events:
        return "event_max_level_cannot_improve_gap"
    voluntary_events = [event for event in improvable_events if event.get("mandatory") is False]
    if not voluntary_events:
        return "relevant_events_are_mandatory"
    prerequisite_events = [
        event for event in voluntary_events if _prerequisites_satisfied(event, employee_skills)
    ]
    if not prerequisite_events:
        return "prerequisites_fail"
    completed_ids = {
        record.get("event_id") for record in history if record.get("status") == "completed"
    }
    available_events = [
        event
        for event in prerequisite_events
        if event.get("event_id") not in completed_ids or is_event_repeatable(event)
    ]
    if not available_events:
        return "relevant_events_already_completed"
    return "other_deterministic_reason"


def _validate_result(
    employee: Mapping[str, Any],
    result: Any,
    events_by_id: Mapping[str, Mapping[str, Any]],
    employee_history: Sequence[Mapping[str, Any]],
    violations: list[str],
) -> None:
    scores = [scored.score for scored in result.candidates]
    if scores != sorted(scores, reverse=True):
        violations.append(f"{result.employee_id}: candidate scores are not sorted descending.")
    if any(score < 0 or score > 1 for score in scores):
        violations.append(f"{result.employee_id}: candidate score is outside 0..1.")
    if result.target is None:
        if result.candidates:
            violations.append(f"{result.employee_id}: no-target result returned candidates.")
        return

    gaps_by_id = {gap.skill_id: gap for gap in result.skill_gaps}
    employee_skills = employee.get("skills", {})
    completed_ids = {
        record.get("event_id") for record in employee_history if record.get("status") == "completed"
    }
    for scored in result.candidates:
        candidate = scored.candidate
        event = events_by_id.get(candidate.event_id)
        label = f"{result.employee_id}/{candidate.event_id}"
        if event is None:
            violations.append(f"{label}: recommended event does not exist.")
            continue
        if event.get("mandatory") is not False:
            violations.append(f"{label}: mandatory event was recommended.")
        if result.target.role not in event.get("target_roles", []):
            violations.append(f"{label}: event does not match target role.")
        if result.target.grade not in event.get("target_grades", []):
            violations.append(f"{label}: event does not match target grade.")
        if not _prerequisites_satisfied(event, employee_skills):
            violations.append(f"{label}: prerequisites are not satisfied.")
        if candidate.event_id in completed_ids and not is_event_repeatable(event):
            violations.append(f"{label}: completed non-repeatable event was recommended.")
        developments = {
            development.get("skill_id"): development
            for development in event.get("develops_skills", [])
            if isinstance(development, Mapping)
        }
        if not candidate.affected_skills:
            violations.append(f"{label}: candidate has no affected positive skill gaps.")
        for impact in candidate.affected_skills:
            development = developments.get(impact.skill_id)
            gap = gaps_by_id.get(impact.skill_id)
            if development is None or gap is None or gap.gap <= 0:
                violations.append(f"{label}: impact is not tied to a positive target gap.")
                continue
            expected_level = min(impact.current_level + development.get("gain", 0), development.get("max_level", 0))
            if impact.gain != development.get("gain") or impact.max_level != development.get("max_level"):
                violations.append(f"{label}: impact gain or max_level differs from event data.")
            if impact.expected_level_after_completion != expected_level:
                violations.append(f"{label}: expected level does not obey gain/max_level.")
            if impact.expected_level_after_completion > impact.max_level:
                violations.append(f"{label}: expected level exceeds max_level.")
            if impact.expected_level_after_completion < impact.current_level:
                violations.append(f"{label}: expected level is below current level.")


def _validate_top_k(
    full_candidates: Sequence[Any],
    limited_candidates: Sequence[Any],
    top_k: int,
    employee_id: str,
    violations: list[str],
) -> None:
    expected = tuple(full_candidates[:top_k])
    if tuple(limited_candidates) != expected:
        violations.append(f"{employee_id}: top_k result does not match full sorted prefix.")


def _find_suspicious_rankings(employee_id: str, candidates: Sequence[Any]) -> list[dict[str, Any]]:
    if len(candidates) < 2:
        return []
    top = candidates[0]
    observations: list[dict[str, Any]] = []
    top_has_critical = any(impact.critical for impact in top.candidate.affected_skills)
    top_largest_gap = max(impact.gap_before for impact in top.candidate.affected_skills)
    for alternative in candidates[1:]:
        alternative_has_critical = any(
            impact.critical for impact in alternative.candidate.affected_skills
        )
        alternative_largest_gap = max(
            impact.gap_before for impact in alternative.candidate.affected_skills
        )
        if not top_has_critical and alternative_has_critical and alternative_largest_gap > top_largest_gap:
            observations.append(
                _ranking_observation(
                    employee_id,
                    "noncritical_smaller_gap_outranks_critical_larger_gap",
                    top,
                    alternative,
                )
            )
        if (
            top.factors.history_fit > alternative.factors.history_fit
            and alternative.factors.career_relevance > top.factors.career_relevance
        ):
            observations.append(
                _ranking_observation(employee_id, "history_fit_may_influence_ranking", top, alternative)
            )
        if (
            top.factors.effective_gain < alternative.factors.effective_gain
            and top.factors.career_relevance < alternative.factors.career_relevance
        ):
            observations.append(
                _ranking_observation(
                    employee_id,
                    "lower_gain_and_relevance_outranks_alternative",
                    top,
                    alternative,
                )
            )
    return observations


def _ranking_observation(employee_id: str, reason: str, top: Any, alternative: Any) -> dict[str, Any]:
    return {
        "employee_id": employee_id,
        "reason": reason,
        "top_event": top.candidate.event_id,
        "alternative_event": alternative.candidate.event_id,
        "top_factors": vars(top.factors),
        "alternative_factors": vars(alternative.factors),
    }


def _append_repetition_observations(
    top_events: Counter[str],
    top_event_contexts: Mapping[str, set[tuple[str, str]]],
    observations: list[dict[str, Any]],
) -> None:
    for event_id, count in top_events.items():
        top_contexts = top_event_contexts.get(event_id, set())
        if count > 1 and len(top_contexts) > 1:
            observations.append(
                {
                    "reason": "popular_top_event_across_multiple_target_contexts",
                    "event_id": event_id,
                    "top_recommendation_count": count,
                    "observed_explicit_target_contexts": sorted(top_contexts),
                }
            )


def _event_can_improve_gap(
    event: Mapping[str, Any], employee_skills: Mapping[str, Any], positive_gaps: set[str]
) -> bool:
    for development in event.get("develops_skills", []):
        if not isinstance(development, Mapping) or development.get("skill_id") not in positive_gaps:
            continue
        skill_id = development["skill_id"]
        current = employee_skills.get(skill_id, 0)
        gain = development.get("gain")
        max_level = development.get("max_level")
        if all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in (current, gain, max_level)):
            if min(current + gain, max_level) > current:
                return True
    return False


def _prerequisites_satisfied(event: Mapping[str, Any], employee_skills: Mapping[str, Any]) -> bool:
    prerequisites = event.get("prerequisites", {})
    if not isinstance(prerequisites, Mapping):
        return False
    return all(employee_skills.get(skill_id, 0) >= required for skill_id, required in prerequisites.items())


def _history_by_employee(history: Sequence[Mapping[str, Any]]) -> dict[str, list[Mapping[str, Any]]]:
    indexed: dict[str, list[Mapping[str, Any]]] = {}
    for record in history:
        employee_id = record.get("employee_id")
        if isinstance(employee_id, str):
            indexed.setdefault(employee_id, []).append(record)
    return indexed


def _add_history_counts(counters: Counter[str], summary: Any) -> None:
    counters["history_completed"] += summary.completed_count
    counters["history_in_progress"] += summary.in_progress_count
    counters["history_dropped"] += summary.dropped_count
    counters["history_no_show"] += summary.no_show_count
    counters["history_declined"] += summary.declined_count
    counters["history_overdue"] += summary.overdue_count


def _valid_ids(
    records: Sequence[Mapping[str, Any]], key: str, label: str, issues: list[str]
) -> set[str]:
    values = [record.get(key) for record in records]
    valid = {value for value in values if isinstance(value, str) and value}
    if len(valid) != len(records):
        issues.append(f"{label.capitalize()} data contains missing or invalid {key} values.")
    duplicate_ids = [value for value, count in Counter(values).items() if count > 1]
    if duplicate_ids:
        issues.append(f"Duplicate {label} IDs: {', '.join(map(str, sorted(duplicate_ids)))}.")
    return valid


def _check_skill_mapping(
    values: Any, valid_skill_ids: set[str], owner: str, issues: list[str]
) -> None:
    if not isinstance(values, Mapping):
        issues.append(f"{owner} skill mapping is malformed.")
        return
    for skill_id in values:
        if skill_id not in valid_skill_ids:
            issues.append(f"{owner} references unknown skill {skill_id!r}.")


def _print_report(report: Mapping[str, Any]) -> None:
    dataset = report["dataset"]
    sweep = report["sweep"]
    print(f"Dataset directory: {report['data_directory']}")
    print("\nDATASET")
    for key, value in dataset.items():
        print(f"{key}: {value}")
    print("\nPROCESSING")
    for key, value in sweep["processing"].items():
        print(f"{key}: {value}")
    for section in ("targets", "gaps", "candidates", "scoring", "history", "validation"):
        print(f"\n{section.upper()}")
        for key, value in sweep[section].items():
            print(f"{key}: {value}")
    print("\nTOP RECOMMENDATIONS")
    for event_id, count in sweep["top_recommendations"].items():
        print(f"{event_id}: {count}")
    print("\nINVALID REFERENCES")
    for issue in report["invalid_references"] or ["none"]:
        print(issue)
    print("\nSUSPICIOUS RANKINGS")
    for observation in sweep["suspicious_rankings"] or ["none"]:
        print(observation)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=find_dataset_directory(),
        help="Directory containing the four Career Quest dataset files.",
    )
    args = parser.parse_args()
    if args.data_dir is None:
        parser.error("No complete dataset directory found; pass --data-dir explicitly.")
    _print_report(validate_full_dataset(args.data_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
