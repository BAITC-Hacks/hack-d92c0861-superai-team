# Recommendation Output Contract

## Purpose

Defines the stable output interface between the AI recommendation
module and the backend.

The backend should not depend on internal AI implementation details.

## Recommendation result

Recommended structure:

{
  "employee_id": "E0002",
  "target": {
    "role": "Backend Engineer",
    "grade": "Senior"
  },
  "recommendations": [
    {
      "event_id": "EV_021",
      "priority": 1,
      "score": 0.91,
      "reason": "Human-readable explanation",
      "skills_affected": [
        {
          "skill_id": "SK_SYSTEM_DESIGN",
          "current_level": 1,
          "required_level": 4,
          "gap": 3,
          "critical": true,
          "expected_level_after_completion": 2
        }
      ],
      "factors": {
        "career_target": true,
        "skill_gap": true,
        "critical_skill": true,
        "participation_history": true
      }
    }
  ]
}

## Requirements

recommendations must contain between 0 and 3 items.

Zero recommendations is valid if no eligible activity exists.

Never fabricate an activity just to ensure the list is non-empty.

`event_id` must exist in events.json.

Skill IDs must exist in skills.json.

Calculated levels must follow deterministic dataset rules.

## Backend integration target

The AI module should expose a simple interface similar to:

recommend(employee_id)

The implementation may evolve, but the backend-facing contract should
remain simple and stable.

## Errors

Expected error cases should be explicit.

Examples:

- employee not found;
- target role profile not found;
- invalid dataset;
- no career target;
- LLM unavailable.

Where possible, deterministic recommendations should remain usable
even if the LLM layer is unavailable.