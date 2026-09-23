# Career Quest — AI Development Guide

This directory contains implementation instructions for the Career Quest
AI recommendation module.

Before modifying AI code, read:

1. `docs/codex/ARCHITECTURE.md`
2. `docs/codex/RULES.md`
3. `docs/codex/RECOMMENDATION_LOGIC.md`
4. `docs/codex/OUTPUT_CONTRACT.md`

Dataset documentation:

- `docs/employees.md`
- `docs/skills.md`
- `docs/events.md`
- `docs/activity_history.md`
- `docs/recommendation.md`

## Project goal

Career Quest recommends 1–3 relevant development activities to an employee.

The recommendation must be explainable and based on multiple factors,
including:

- employee grade;
- career goal;
- requirements of the target grade;
- skill gaps;
- critical skills;
- participation history;
- event eligibility;
- event skill impact.

The system must NOT use a simple rule such as
"recommend an activity for the employee's lowest skill".

## Important evaluation requirement

The evaluation system may provide additional employee profiles and
activity history records using the same dataset schema.

Therefore:

- do not hardcode employee IDs;
- do not hardcode dataset sizes;
- do not build logic specifically for sample employees;
- loaders must support replacement with the full dataset;
- recommendation logic must work without code changes.

## Ownership

The AI module lives under:

`ai/`

Do not modify frontend or backend unless explicitly requested.

Keep the AI module independently testable.