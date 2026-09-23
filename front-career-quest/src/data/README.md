# Career Quest snapshot

Synthetic Career Quest 1.0 dataset, as of **2026-10-01**. All employees are fictional.

- `employees.json`: 200 employee profiles.
- `skills.json`: 60 skills, 32 role/grade profiles and the 0–5 proficiency scale.
- `events.json`: 40 activities.
- `history.json`: all 2,743 records from `activity_history.csv`, stored as `columns` and `rows` to avoid repeating property names in the application bundle. `career.js` restores record objects.

Source: `career_quest_dataset/case_1/career_quest_dataset` supplied for this project. The frontend uses a local copy and has no dependency on that absolute filesystem path.

Progress uses the last reviewed skill levels. Training after the review has not been applied to skill levels. Missing skills count as zero. Critical requirements are marked separately; progress is not a promotion decision.

Recommendations exclude mandatory training and completed activities (except recurring `EV_036`), enforce role, grade and prerequisites, and require a gain in an under-target skill below the activity's cap.

UI messages live in `src/locales`. Dataset strings fall back to their original text; optional translations use `skills.<skill_id>.name` and `events.<event_id>.title/description`.

The personal plan is stored per employee in browser local storage. It is not an event registration. Changing the role or grade on the path page is a temporary comparison, not a persisted career-goal edit.
