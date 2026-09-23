{
  "meta": {
    "dataset": "Career Quest",
    "version": "1.0",
    "as_of_date": "2026-10-01"
  },
  "proficiency_scale": {
    "0": "No knowledge",
    "1": "Basic awareness: knows key concepts, needs guidance",
    "2": "Working knowledge: handles routine tasks with some support",
    "3": "Proficient: works independently on typical tasks",
    "4": "Advanced: handles complex cases, guides others",
    "5": "Expert: sets standards and shapes practice across the company"
  },
  "skills": [
    {
      "skill_id": "SK_PYTHON",
      "name": "Python",
      "type": "hard",
      "category": "engineering",
      "description": "Writing, testing and maintaining Python code."
    },
    {
      "skill_id": "SK_JAVA",
      "name": "Java",
      "type": "hard",
      "category": "engineering",
      "description": "Writing, testing and maintaining Java code."
    },
    {
      "skill_id": "SK_SQL",
      "name": "SQL",
      "type": "hard",
      "category": "engineering",
      "description": "Querying and transforming relational data."
    },
    {
      "skill_id": "SK_API_DESIGN",
      "name": "API Design",
      "type": "hard",
      "category": "engineering",
      "description": "Designing clear, versioned and secure service interfaces."
    }
  ],
  "role_profiles": [
    {
      "role": "Backend Engineer",
      "grade": "Junior",
      "required_skills": {
        "SK_PYTHON": 2,
        "SK_SQL": 2,
        "SK_API_DESIGN": 1,
        "SK_SYSTEM_DESIGN": 1,
        "SK_CLOUD": 1,
        "SK_CONTAINERS": 1,
        "SK_CICD": 1,
        "SK_APP_SECURITY": 1,
        "SK_COMMUNICATION": 2,
        "SK_TEAMWORK": 2,
        "SK_PROBLEM_SOLVING": 2
      },
      "critical_skills": [
        "SK_PYTHON"
      ]
    },
    {
      "role": "Backend Engineer",
      "grade": "Middle",
      "required_skills": {
        "SK_PYTHON": 3,
        "SK_SQL": 3,
        "SK_API_DESIGN": 3,
        "SK_SYSTEM_DESIGN": 2,
        "SK_CLOUD": 2,
        "SK_CONTAINERS": 2,
        "SK_CICD": 2,
        "SK_APP_SECURITY": 2,
        "SK_OBSERVABILITY": 2,
        "SK_COMMUNICATION": 3,
        "SK_TEAMWORK": 3,
        "SK_PROBLEM_SOLVING": 3,
        "SK_MENTORING": 1,
        "SK_STAKEHOLDER_MGMT": 1,
        "SK_PUBLIC_SPEAKING": 1
      },
      "critical_skills": [
        "SK_PYTHON",
        "SK_API_DESIGN"
      ]
    },
    {
      "role": "Backend Engineer",
      "grade": "Senior",
      "required_skills": {
        "SK_PYTHON": 4,
        "SK_SQL": 4,
        "SK_API_DESIGN": 4,
        "SK_SYSTEM_DESIGN": 4,
        "SK_CLOUD": 3,
        "SK_CONTAINERS": 3,
        "SK_CICD": 3,
        "SK_APP_SECURITY": 3,
        "SK_OBSERVABILITY": 3,
        "SK_COMMUNICATION": 3,
        "SK_TEAMWORK": 3,
        "SK_PROBLEM_SOLVING": 4,
        "SK_MENTORING": 3,
        "SK_LEADERSHIP": 2,
        "SK_STAKEHOLDER_MGMT": 2,
        "SK_PUBLIC_SPEAKING": 2
      },
      "critical_skills": [
        "SK_SYSTEM_DESIGN",
        "SK_API_DESIGN"
      ]
  
    }
  ]
}
