# Recommendation Logic

## Objective

Generate 1–3 development activity recommendations that move an employee
toward their career target.

Recommendations must be based on multiple factors.

## Step 1 — Resolve target

If `career_goal` exists, use:

- target_role
- target_grade

The recommendation engine should resolve the corresponding role profile.

## Step 2 — Calculate skill gaps

For every required skill of the target role/grade:

current = employee skill level, default 0
required = target role requirement
gap = max(required - current, 0)

Keep only positive gaps for development targeting.

Mark whether each gap is a critical skill.

## Step 3 — Generate candidates

Read events.json.

Reject events that:

- are mandatory;
- do not target the relevant role;
- do not target the relevant grade;
- fail prerequisites;
- develop none of the relevant skill gaps;
- were already completed and are not recurring.

## Step 4 — Analyze history

For each employee, summarize relevant participation behaviour.

Potential signals:

- completion rate;
- completed activities;
- dropped activities;
- no-shows;
- declined activities;
- overdue activities;
- feedback ratings;
- behaviour with similar activity types or skills.

Do not treat a single historical signal as decisive.

## Step 5 — Deterministic scoring

Candidate scoring should combine several signals.

Initial scoring concept:

candidate_score =
    skill_gap_impact
    + critical_skill_priority
    + career_target_relevance
    + event_skill_gain
    + participation_history_fit

Weights should be centralized and configurable.

Do not spread magic constants across the codebase.

## Critical principle

A large skill gap does not automatically mean its associated event
must be recommendation #1.

Example:

An employee may have a very low Public Speaking skill but repeatedly
skip similar activities.

At the same time, System Design may be critical for the employee's
target grade.

The engine must evaluate the complete context.

## Step 6 — Top candidates

The deterministic layer should produce a small candidate set.

Example:

Top 5 eligible candidates.

Do not send all employees or all events to the LLM.

## Step 7 — LLM contextual reranking

Provide the LLM with:

- current role and grade;
- career target;
- relevant skill gaps;
- critical skill information;
- summarized participation history;
- deterministic candidate list.

Ask it to return 1–3 recommendations.

## Step 8 — Explainability

Each recommendation should clearly show:

- what skill it develops;
- current level;
- required level;
- gap;
- whether the skill is critical;
- expected deterministic skill impact;
- how participation history affected the choice;
- why the activity helps the career target.

## Step 9 — Recalculation

After an activity is marked completed:

1. update affected skills according to gain/max_level;
2. update participation history/state;
3. recalculate skill gaps;
4. regenerate candidates;
5. rerun recommendation logic.

Recommendations are therefore dynamic rather than static.