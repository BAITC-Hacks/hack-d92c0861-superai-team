"""Owner: Mikhail. Stable async entry point; no database, FastAPI or file I/O."""
from __future__ import annotations
import asyncio
from time import perf_counter
import httpx
from ai import provider
from shared.contracts import (Candidate, Factor, RecommendationContext,
                             RecommendationResponse, RecommendationStep)


def baseline_score(c: Candidate, context: RecommendationContext) -> float:
    """Transparent starter heuristic, NOT a trained model or calibrated probability."""
    history = c.history
    friction = (history.similar_no_show + history.similar_dropped + history.similar_declined)
    friction_rate = friction / max(1, history.similar_total)
    remote_fit = context.work_format == "remote" and c.format != "offline"
    return (4*c.critical_gap_reduction + 2*c.target_gap_reduction
            + (1 if c.action == "continue" else 0) + (0.5 if remote_fit else 0)
            - 2*friction_rate)


def build_step(candidate: Candidate, context: RecommendationContext) -> RecommendationStep:
    relevant = {g.skill_id: g for g in context.trajectory.gaps if g.gap > 0}
    changes = [change for change in candidate.skill_deltas
               if change.delta > 0 and change.skill_id in relevant]
    gap_text = "; ".join(f"{relevant[c.skill_id].name}: {c.before} → {c.after}, "
                         f"нужно {relevant[c.skill_id].required}"
                         + (" (критический навык)" if relevant[c.skill_id].critical else "")
                         for c in changes)
    h = candidate.history
    history_text = (f"В похожих активностях: завершено {h.similar_completed} из {h.similar_total}; "
                    f"пропусков {h.similar_no_show}, отказов {h.similar_declined}, "
                    f"прервано {h.similar_dropped}. Это наблюдения, не оценка мотивации.")
    if h.similar_total == 0:
        history_text = "Похожих активностей в истории нет; предпочтения по ней не установлены."
    factors = [
        Factor(code="grade_goal", text=f"{context.role}, {context.grade} → "
               f"{context.trajectory.target_role}, {context.trajectory.target_grade}.",
               evidence={"role": context.role, "grade": context.grade,
                         "target_role": context.trajectory.target_role,
                         "target_grade": context.trajectory.target_grade,
                         "target_source": context.trajectory.target_source}),
        Factor(code="skill_gap", text=gap_text,
               evidence={"gap_reduction": candidate.target_gap_reduction,
                         "critical_gap_reduction": candidate.critical_gap_reduction,
                         "changes": [c.model_dump() for c in changes]}),
        Factor(code="history", text=history_text, evidence=h.model_dump()),
        Factor(code="format", text=f"Формат: {candidate.format}; объём: "
               f"{candidate.duration_hours:g} ч. Формат работы сотрудника: {context.work_format}.",
               evidence={"format": candidate.format, "work_format": context.work_format,
                         "duration_hours": candidate.duration_hours}),
    ]
    return RecommendationStep(event_id=candidate.event_id, title=candidate.title,
        action=candidate.action, format=candidate.format, duration_hours=candidate.duration_hours,
        next_session=candidate.next_session, factors=factors, skill_deltas=candidate.skill_deltas,
        progress_before_pct=candidate.progress_before_pct, progress_after_pct=candidate.progress_after_pct)


async def recommend(context: RecommendationContext) -> RecommendationResponse:
    start = perf_counter()
    ordered = sorted(context.candidates, key=lambda c: (-baseline_score(c, context), c.event_id))
    ids = [candidate.event_id for candidate in ordered[:3]]
    mode, fallback_reason = "fallback", "AI_DISABLED"
    if context.candidates and provider.enabled():
        if not provider.configured():
            fallback_reason = "AI_NOT_CONFIGURED"
        else:
            try:
                # Overall wall-clock deadline, not merely a timeout for each network phase.
                ids = await asyncio.wait_for(provider.select_events(context), timeout=8.0)
                ids = provider.validate_selection({"event_ids": ids}, context)
                mode, fallback_reason = "llm", None
            except (asyncio.TimeoutError, httpx.TimeoutException):
                fallback_reason = "AI_TIMEOUT"
            except (ValueError, KeyError, IndexError, TypeError):
                fallback_reason = "INVALID_AI_RESPONSE"
            except httpx.HTTPError:
                fallback_reason = "AI_PROVIDER_ERROR"
    candidates = {c.event_id: c for c in context.candidates}
    reason = None
    if not ids:
        reason = ("Требования выбранной цели по навыкам уже покрыты; повышение не выполняется автоматически."
                  if context.trajectory.remaining_gap == 0 else
                  "В каталоге нет доступного шага, уменьшающего разрыв выбранной цели. "
                  "Проверьте причины исключения; HR может предложить индивидуальную траекторию.")
    return RecommendationResponse(employee_id=context.employee_id, as_of_date=context.as_of_date,
        data_version=context.data_version, mode=mode, fallback_reason=fallback_reason,
        trajectory=context.trajectory, steps=[build_step(candidates[eid], context) for eid in ids],
        no_step_reason=reason, excluded=context.excluded, elapsed_ms=round((perf_counter()-start)*1000))
