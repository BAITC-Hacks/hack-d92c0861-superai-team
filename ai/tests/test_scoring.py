from ai.engine.scoring import calculate_history_fit, score_candidate
from ai.engine.skill_gap import SkillGap
from ai.schemas.recommendation import CandidateActivity, HistorySignals, SkillImpact


GAPS = [
    SkillGap("critical", "Critical", 0, 4, 4, True),
    SkillGap("regular", "Regular", 0, 4, 4, False),
]


def _signals(**changes):
    values = {
        "same_event_records": 0,
        "same_event_completed": 0,
        "similar_records": 0,
        "similar_completed": 0,
        "similar_negative": 0,
        "shared_skill_records": 0,
        "shared_skill_completed": 0,
        "average_feedback_rating": None,
        "assignment_sources": (),
    }
    values.update(changes)
    return HistorySignals(**values)


def _candidate(skill_id="regular", critical=False, effective_gain=2, max_level=5):
    impact = SkillImpact(
        skill_id=skill_id,
        skill_name=skill_id,
        current_level=0,
        required_level=4,
        gap_before=4,
        gain=effective_gain,
        max_level=max_level,
        expected_level_after_completion=effective_gain,
        gap_after=4 - effective_gain,
        effective_gain=effective_gain,
        critical=critical,
    )
    return CandidateActivity(
        event_id=f"event-{skill_id}-{effective_gain}-{max_level}",
        title="Candidate",
        event_type="course",
        duration_hours=1,
        affected_skills=(impact,),
    )


def test_score_contains_bounded_multi_factor_breakdown():
    scored = score_candidate(_candidate(), GAPS, _signals())
    assert 0.0 <= scored.score <= 1.0
    assert 0.0 <= scored.factors.career_relevance <= 1.0
    assert 0.0 <= scored.factors.gap_impact <= 1.0
    assert 0.0 <= scored.factors.critical_skill_impact <= 1.0
    assert 0.0 <= scored.factors.effective_gain <= 1.0
    assert 0.0 <= scored.factors.history_fit <= 1.0


def test_critical_skill_and_larger_useful_gap_increase_priority():
    regular = score_candidate(_candidate("regular", effective_gain=2), GAPS, _signals())
    critical = score_candidate(_candidate("critical", critical=True, effective_gain=2), GAPS, _signals())
    larger_gain = score_candidate(_candidate("regular", effective_gain=3), GAPS, _signals())

    assert critical.score > regular.score
    assert larger_gain.score > regular.score


def test_max_level_limited_effective_gain_reduces_score():
    limited = _candidate(effective_gain=1, max_level=1)
    useful = _candidate(effective_gain=4, max_level=5)
    assert score_candidate(useful, GAPS, _signals()).score > score_candidate(limited, GAPS, _signals()).score


def test_negative_history_reduces_fit_but_never_eliminates_candidate():
    repeated_negative = _signals(similar_records=3, similar_negative=3)
    neutral_score = score_candidate(_candidate(), GAPS, _signals())
    negative_score = score_candidate(_candidate(), GAPS, repeated_negative)

    assert calculate_history_fit(repeated_negative) < calculate_history_fit(_signals())
    assert negative_score.factors.history_fit < neutral_score.factors.history_fit
    assert negative_score.score > 0


def test_history_is_secondary_to_strong_critical_career_evidence():
    poor_history_critical = score_candidate(
        _candidate("critical", critical=True, effective_gain=2),
        GAPS,
        _signals(similar_records=3, similar_negative=3),
    )
    strong_history_regular = score_candidate(
        _candidate("regular", effective_gain=1),
        GAPS,
        _signals(similar_records=2, similar_completed=2, average_feedback_rating=5),
    )

    assert poor_history_critical.score > strong_history_regular.score
