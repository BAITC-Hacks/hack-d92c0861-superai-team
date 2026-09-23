"""API v1 / Python boundary. Changes require agreement by all three owners."""
from __future__ import annotations
from datetime import date
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field

class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")

class SkillGap(Contract):
    skill_id: str
    name: str
    current: int
    required: int
    gap: int
    critical: bool

class Trajectory(Contract):
    target_role: str
    target_grade: str
    target_source: Literal["career_goal", "next_grade", "current_grade"]
    progress_pct: float
    remaining_gap: int
    critical_gaps: int
    gaps: list[SkillGap]
    note: str

class SkillDelta(Contract):
    skill_id: str
    before: int
    after: int
    delta: int
    gain: int
    max_level: int

class HistoryEvidence(Contract):
    total: int
    completed: int
    no_show: int
    dropped: int
    declined: int
    in_progress: int
    similar_total: int
    similar_completed: int
    similar_no_show: int
    similar_dropped: int
    similar_declined: int
    similar_record_ids: list[str]
    similar_definition: str

class Candidate(Contract):
    event_id: str
    title: str
    type: str
    format: str
    duration_hours: float
    action: Literal["start", "continue"]
    next_session: date | None
    skill_deltas: list[SkillDelta]
    target_gap_reduction: int
    critical_gap_reduction: int
    progress_before_pct: float
    progress_after_pct: float
    history: HistoryEvidence

class ExcludedEvent(Contract):
    event_id: str
    reason: str

class RecommendationContext(Contract):
    employee_id: str
    role: str
    grade: str
    tenure_months: int
    work_format: str
    as_of_date: date
    data_version: int
    trajectory: Trajectory
    candidates: list[Candidate]
    excluded: list[ExcludedEvent]

class Factor(Contract):
    code: Literal["grade_goal", "skill_gap", "history", "format"]
    text: str
    evidence: dict[str, Any]

class RecommendationStep(Contract):
    event_id: str
    title: str
    action: Literal["start", "continue"]
    format: str
    duration_hours: float
    next_session: date | None
    factors: list[Factor] = Field(min_length=3)
    skill_deltas: list[SkillDelta]
    progress_before_pct: float
    progress_after_pct: float

class RecommendationResponse(Contract):
    employee_id: str
    as_of_date: date
    data_version: int
    mode: Literal["llm", "fallback"]
    fallback_reason: str | None = None
    trajectory: Trajectory
    steps: list[RecommendationStep] = Field(max_length=3)
    no_step_reason: str | None = None
    excluded: list[ExcludedEvent]
    elapsed_ms: int = 0

class ProfileResponse(Contract):
    employee: dict[str, Any]
    effective_skills: dict[str, int]
    trajectory: Trajectory
    history: list[dict[str, str]]
    as_of_date: date
    data_version: int

class CompletionRequest(Contract):
    event_id: str
    idempotency_key: str = Field(min_length=8, max_length=100)
    expected_data_version: int = Field(ge=1)
    participation_record_id: str | None = None
    session_date: date | None = None

class CompletionResponse(Contract):
    employee_id: str
    event_id: str
    already_applied: bool
    data_version: int
    skill_deltas: list[SkillDelta]
    trajectory: Trajectory

class ImportResponse(Contract):
    employees_added: int
    employees_updated: int
    history_added: int
    history_unchanged: int
    data_version: int
    warnings: list[str]

class HRSkillGap(Contract):
    skill_id: str
    name: str
    employees_with_gap: int
    employees_requiring_skill: int
    gap_rate: float
    total_gap: int
    critical_employee_count: int

class HRNoStep(Contract):
    employee_id: str
    reason: str

class HREventParticipation(Contract):
    event_id: str
    title: str
    total_records: int
    by_status: dict[str, int]

class HRResponse(Contract):
    as_of_date: date
    data_version: int
    employees_count: int
    skill_gaps: list[HRSkillGap]
    employees_without_step: list[HRNoStep]
    participation: list[HREventParticipation]
