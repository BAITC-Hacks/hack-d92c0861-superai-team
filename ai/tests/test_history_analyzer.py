from ai.engine.history_analyzer import analyze_candidate_history, summarize_history
from ai.schemas.recommendation import CandidateActivity, SkillImpact


def _candidate():
    return CandidateActivity(
        event_id="candidate-event",
        title="Candidate",
        event_type="presentation",
        duration_hours=1,
        affected_skills=(
            SkillImpact("skill-a", "Skill A", 1, 3, 2, 1, 5, 2, 1, 1, False),
        ),
    )


def _events():
    return [
        {"event_id": "candidate-event", "type": "presentation", "develops_skills": [{"skill_id": "skill-a"}]},
        {"event_id": "shared-skill", "type": "course", "develops_skills": [{"skill_id": "skill-a"}]},
        {"event_id": "same-type", "type": "presentation", "develops_skills": [{"skill_id": "skill-b"}]},
        {"event_id": "unrelated", "type": "course", "develops_skills": [{"skill_id": "skill-c"}]},
    ]


def test_empty_history_has_zero_counts_and_zero_completion_rate():
    summary = summarize_history("employee-a", [])
    assert summary.total_records == 0
    assert summary.completion_rate == 0.0
    assert summary.negative_count == 0


def test_summary_counts_all_supported_statuses_and_completion_rate():
    history = [
        {"employee_id": "employee-a", "event_id": f"event-{index}", "status": status}
        for index, status in enumerate(
            ["completed", "in_progress", "dropped", "no_show", "declined", "overdue"]
        )
    ]

    summary = summarize_history("employee-a", history)

    assert summary.total_records == 6
    assert summary.completed_count == summary.in_progress_count == 1
    assert summary.dropped_count == summary.no_show_count == 1
    assert summary.declined_count == summary.overdue_count == 1
    assert summary.completion_rate == 1 / 6
    assert summary.negative_count == 4


def test_candidate_signals_use_same_event_type_and_skill_without_cross_employee_leakage():
    history = [
        {"employee_id": "employee-a", "event_id": "candidate-event", "status": "completed", "feedback_rating": "5", "assigned_by": "hr"},
        {"employee_id": "employee-a", "event_id": "shared-skill", "status": "dropped", "feedback_rating": "2", "assigned_by": "manager"},
        {"employee_id": "employee-a", "event_id": "same-type", "status": "no_show", "feedback_rating": "", "assigned_by": "self"},
        {"employee_id": "employee-a", "event_id": "unrelated", "status": "completed"},
        {"employee_id": "employee-b", "event_id": "same-type", "status": "completed", "feedback_rating": "5"},
    ]

    summary = summarize_history("employee-a", history)
    signals = analyze_candidate_history("employee-a", _candidate(), history, _events())

    assert summary.total_records == 4
    assert summary.completed_count == 2
    assert summary.dropped_count == 1
    assert summary.no_show_count == 1
    assert signals.same_event_records == signals.same_event_completed == 1
    assert signals.similar_records == 3
    assert signals.similar_completed == 1
    assert signals.similar_negative == 2
    assert signals.shared_skill_records == 2
    assert signals.shared_skill_completed == 1
    assert signals.average_feedback_rating == 3.5
    assert signals.assignment_sources == (("hr", 1), ("manager", 1), ("self", 1))
