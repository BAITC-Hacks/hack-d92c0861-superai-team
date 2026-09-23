"""Shared deterministic calculations. Owner: Damir; AI owner requests changes via contract."""
from __future__ import annotations
from collections import Counter
from datetime import date
from backend.data_loader import Dataset, GRADES
from shared.contracts import (Candidate, ExcludedEvent, HistoryEvidence, ProfileResponse,
                             RecommendationContext, SkillDelta, SkillGap, Trajectory)

REPEATABLE_EVENTS = {"EV_036"}  # Explicit exception in the supplied dataset README.


def apply_gains(skills: dict[str, int], event: dict) -> tuple[dict[str, int], list[SkillDelta]]:
    result = dict(skills)
    changes = []
    for rule in event["develops_skills"]:
        sid = rule["skill_id"]
        before = result.get(sid, 0)
        # A beginner course cannot REDUCE an already advanced skill.
        after = max(before, min(5, before + rule["gain"], rule["max_level"]))
        result[sid] = after
        changes.append(SkillDelta(skill_id=sid, before=before, after=after,
                                  delta=after-before, gain=rule["gain"], max_level=rule["max_level"]))
    return result, changes


def effective_skills(data: Dataset, employee_id: str) -> dict[str, int]:
    employee = data.employees[employee_id]
    result = dict(employee["skills"])
    # employees.skills is an assessment snapshot, not a zero-point history replay.
    for row in data.employee_history(employee_id):
        if (row["status"] == "completed" and
            employee["last_review_date"] < row["date"] <= data.as_of_date.isoformat()):
            result, _ = apply_gains(result, data.events[row["event_id"]])
    return result


def trajectory(data: Dataset, employee: dict, skills: dict[str, int]) -> Trajectory:
    goal = employee.get("career_goal")
    if goal:
        role, grade, source = goal["target_role"], goal["target_grade"], "career_goal"
    else:
        i = GRADES.index(employee["grade"])
        role = employee["role"]
        grade = GRADES[min(i+1, len(GRADES)-1)]
        source = "next_grade" if i+1 < len(GRADES) else "current_grade"
    target = data.role_profiles[(role, grade)]
    gaps = [SkillGap(skill_id=sid, name=data.skills[sid]["name"], current=skills.get(sid, 0),
                     required=need, gap=max(0, need-skills.get(sid, 0)),
                     critical=sid in target["critical_skills"])
            for sid, need in target["required_skills"].items()]
    total = sum(g.required for g in gaps)
    covered = sum(min(g.current, g.required) for g in gaps)
    return Trajectory(target_role=role, target_grade=grade, target_source=source,
        progress_pct=round(100*covered/total, 2) if total else 100.0,
        remaining_gap=sum(g.gap for g in gaps),
        critical_gaps=sum(g.critical and g.gap > 0 for g in gaps), gaps=gaps,
        note="Покрытие требований по навыкам, не вероятность и не гарантия повышения."
             + (" Следующий грейд в датасете отсутствует." if source == "current_grade" else ""))


def history_evidence(data: Dataset, employee_id: str, event: dict) -> HistoryEvidence:
    rows = data.employee_history(employee_id)
    totals = Counter(row["status"] for row in rows)
    # Explicit definition, not a fabricated preference: same type OR same developed skill.
    sids = {r["skill_id"] for r in event["develops_skills"]}
    similar = []
    for row in rows:
        other = data.events[row["event_id"]]
        if not other["mandatory"] and (other["type"] == event["type"] or
                sids.intersection(r["skill_id"] for r in other["develops_skills"])):
            similar.append(row)
    counts = Counter(row["status"] for row in similar)
    return HistoryEvidence(total=len(rows), completed=totals["completed"],
        no_show=totals["no_show"], dropped=totals["dropped"], declined=totals["declined"],
        in_progress=totals["in_progress"], similar_total=len(similar),
        similar_completed=counts["completed"], similar_no_show=counts["no_show"],
        similar_dropped=counts["dropped"], similar_declined=counts["declined"],
        similar_record_ids=[r["record_id"] for r in similar],
        similar_definition="Добровольные активности того же типа ИЛИ с общим развиваемым навыком.")


def build_context(data: Dataset, employee_id: str) -> RecommendationContext:
    employee = data.employees[employee_id]
    current = effective_skills(data, employee_id)
    target = trajectory(data, employee, current)
    rows = data.employee_history(employee_id)
    completed = {r["event_id"] for r in rows if r["status"] == "completed"}
    latest = {r["event_id"]: r for r in rows}
    candidates, excluded = [], []
    for event in data.events.values():
        eid = event["event_id"]
        reason = None
        upcoming = sorted(date.fromisoformat(s) for s in event["upcoming_sessions"]
                          if date.fromisoformat(s) >= data.as_of_date)
        action = "continue" if latest.get(eid, {}).get("status") == "in_progress" else "start"
        if event["mandatory"]: reason = "MANDATORY_NOT_A_RECOMMENDATION"
        elif employee["role"] not in event["target_roles"]: reason = "ROLE_NOT_ELIGIBLE"
        elif employee["grade"] not in event["target_grades"]: reason = "GRADE_NOT_ELIGIBLE"
        elif any(current.get(sid, 0) < need for sid, need in event["prerequisites"].items()):
            reason = "PREREQUISITES_NOT_MET"
        elif eid in completed and eid not in REPEATABLE_EVENTS: reason = "ALREADY_COMPLETED"
        elif event["format"] != "self_paced" and not upcoming and action != "continue":
            reason = "NO_UPCOMING_SESSION"
        new_skills, deltas = apply_gains(current, event)
        after = trajectory(data, employee, new_skills)
        reduction = target.remaining_gap-after.remaining_gap
        critical_reduction = sum(min(g.gap, max(0, new_skills.get(g.skill_id, 0)-g.current))
                                 for g in target.gaps if g.critical)
        if reason is None and reduction <= 0: reason = "NO_TARGET_GAP_REDUCTION"
        if reason:
            excluded.append(ExcludedEvent(event_id=eid, reason=reason))
            continue
        candidates.append(Candidate(event_id=eid, title=event["title"], type=event["type"],
            format=event["format"], duration_hours=event["duration_hours"], action=action,
            next_session=upcoming[0] if upcoming and action == "start" else None,
            skill_deltas=deltas, target_gap_reduction=reduction,
            critical_gap_reduction=critical_reduction, progress_before_pct=target.progress_pct,
            progress_after_pct=after.progress_pct, history=history_evidence(data, employee_id, event)))
    return RecommendationContext(employee_id=employee_id, role=employee["role"],
        grade=employee["grade"], tenure_months=employee["tenure_months"],
        work_format=employee["work_format"], as_of_date=data.as_of_date,
        data_version=data.version, trajectory=target, candidates=candidates, excluded=excluded)


def profile(data: Dataset, employee_id: str) -> ProfileResponse:
    employee = data.employees[employee_id]
    current = effective_skills(data, employee_id)
    return ProfileResponse(employee=employee, effective_skills=current,
        trajectory=trajectory(data, employee, current), history=data.employee_history(employee_id),
        as_of_date=data.as_of_date, data_version=data.version)
