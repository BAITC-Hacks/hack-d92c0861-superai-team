# AI Architecture

## Overview

Career Quest uses a hybrid recommendation architecture.

Deterministic logic is responsible for facts, eligibility, skill gaps
and candidate scoring.

The LLM is responsible for contextual reranking and explanation.

## Pipeline

Data Loader
    ↓
Employee Context
    ↓
Target Resolver
    ↓
Skill Gap Analyzer
    ↓
Candidate Generator
    ↓
History Analyzer
    ↓
Deterministic Scoring
    ↓
Top Candidates
    ↓
LLM Reranker
    ↓
Explainability Layer
    ↓
1–3 Recommendations

## Planned module structure

ai/
├── engine/
│   ├── data_loader.py
│   ├── target_resolver.py
│   ├── skill_gap.py
│   ├── candidate_generator.py
│   ├── history_analyzer.py
│   ├── scoring.py
│   └── recommender.py
│
├── llm/
│   ├── client.py
│   ├── prompts.py
│   └── reranker.py
│
├── schemas/
│   └── recommendation.py
│
└── tests/
    ├── test_skill_gap.py
    ├── test_candidates.py
    └── test_recommender.py

## Deterministic layer

This layer is the source of truth for:

- employee data;
- target role and grade;
- skill requirements;
- skill gaps;
- critical skills;
- event eligibility;
- prerequisites;
- completed events;
- event skill gains;
- candidate scores.

The LLM must not override deterministic restrictions.

## LLM layer

The LLM receives only eligible candidates and relevant employee context.

It may:

- compare eligible candidates;
- rerank candidates;
- select 1–3 recommendations;
- generate explanations.

It must never invent source data.

## Performance

Recommendation generation should remain suitable for the hackathon
requirement of an AI recommendation response within 10 seconds.

Avoid sending entire datasets to the LLM.

Preprocess data locally and send only the relevant employee context
and top candidate activities.