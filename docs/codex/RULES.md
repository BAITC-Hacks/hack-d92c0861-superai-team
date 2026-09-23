# AI Implementation Rules

## General

1. Never hardcode employee IDs.
2. Never hardcode employee-specific recommendations.
3. Never assume a fixed number of employees, events or history records.
4. Treat dataset files as the source of truth.
5. Keep deterministic business rules outside the LLM.
6. All recommendation results must be explainable.

## Employee rules

Use the employee's career_goal when available.

Employee skills missing from the skills object are treated as level 0.

Do not infer unknown employee facts.

## Skill rules

Role requirements come from `role_profiles`.

Do not invent required skill levels.

Calculate a skill gap as:

gap = max(required_level - current_level, 0)

Critical skills must receive special consideration because they are
important for promotion.

Do not simply select the skill with the largest gap.

## Event rules

An event can be a recommendation candidate only when:

- mandatory == false;
- the employee matches its target role;
- the employee matches an appropriate target grade;
- prerequisites are satisfied;
- the activity develops a relevant skill.

Mandatory events are not recommendation targets.

Do not invent events.

Do not invent event effects.

## Completion rules

Normally, an event that has already been completed must not be
recommended again.

The dataset defines EV_036 as a recurring exception.

## Skill update rules

Skill changes are deterministic.

For each developed skill:

new_level = min(current_level + gain, max_level)

The LLM must never calculate or invent gain/max_level.

## History rules

Use participation history as one recommendation factor.

Relevant statuses include:

- completed;
- in_progress;
- dropped;
- no_show;
- declined;
- overdue.

Repeated negative history may reduce the suitability of a similar
activity, but it must not automatically eliminate a career-critical
skill.

History must never be the only recommendation factor.

## LLM rules

The LLM must only consider candidates supplied by the deterministic
engine.

The LLM must NOT:

- create new events;
- create new skills;
- create new employee facts;
- change career requirements;
- ignore prerequisites;
- recommend mandatory activities;
- modify skill levels;
- fabricate participation history.

If information is unavailable, the LLM must not fabricate it.

## Privacy

Do not expose one employee's engagement history to other employees.

HR and employee views must be treated as separate permission contexts.