"""HR summaries are deterministic and never call the AI provider."""
from collections import Counter

from backend.data_loader import Dataset, STATUSES
from backend.domain import build_context
from shared.contracts import HRResponse, HRSkillGap, HRNoStep, HREventParticipation


def overview(data: Dataset) -> HRResponse:
    gaps = {}
    no_step = []
    participation = {eid: Counter() for eid in data.events}
    for employee_id in data.employees:
        context = build_context(data, employee_id)
        for gap in context.trajectory.gaps:
            aggregate = gaps.setdefault(gap.skill_id, HRSkillGap(skill_id=gap.skill_id,
                name=gap.name, employees_with_gap=0, employees_requiring_skill=0,
                gap_rate=0, total_gap=0, critical_employee_count=0))
            aggregate.employees_requiring_skill += 1
            aggregate.employees_with_gap += int(gap.gap > 0)
            aggregate.total_gap += gap.gap
            aggregate.critical_employee_count += int(gap.critical and gap.gap > 0)
        if not context.candidates:
            reason = ('TARGET_REQUIREMENTS_MET' if context.trajectory.remaining_gap == 0 else
                'NO_ELIGIBLE_GAP_REDUCING_EVENT: ' + ', '.join(sorted({e.reason for e in context.excluded})))
            no_step.append(HRNoStep(employee_id=employee_id, reason=reason))
        for row in data.employee_history(employee_id):
            participation[row['event_id']][row['status']] += 1
    for gap in gaps.values():
        gap.gap_rate = gap.employees_with_gap / gap.employees_requiring_skill
    return HRResponse(as_of_date=data.as_of_date, data_version=data.version,
        employees_count=len(data.employees), skill_gaps=sorted(gaps.values(), key=lambda g: (-g.total_gap, g.skill_id)),
        employees_without_step=no_step,
        participation=[HREventParticipation(event_id=eid, title=data.events[eid]['title'],
            total_records=sum(counts.values()), by_status={status: counts[status] for status in sorted(STATUSES)})
            for eid, counts in participation.items()])
