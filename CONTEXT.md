# Context & Rules for Career Quest Hackathon Project

## Tech Stack

- Python 3.10+
- Streamlit (UI Framework)
- OpenAI API (gpt-4o) / NVIDIA API (Llama 3.1)
- Pandas / JSON (Data Processing)

## Core Domain Rules

1. Multi-factor Explainability: AI recommendations MUST be strictly based on 3+ factors (skill gaps for next grade, activity history/absences, tenure/current role). Single-factor or naive if/else logic is prohibited.
2. Skill Upgrade Formula: Updating employee skills after completing an event must strictly follow `gain` and `max_level` rules specified in `events.json`.
3. Data Safety: Synthetic data only. Must handle user-uploaded test JSON/CSV files dynamically.

## File Responsibilities

- `data_loader.py`: Parsers for `employees.json`, `events.json`, `skills.json`, `activity_history.csv`.
- `ai_engine.py`: Functions to construct system prompts and call OpenAI API with structured outputs.
- `app.py`: Streamlit UI, state management (`st.session_state`), rendering profile & HR dashboards.

## Code Style

- Write modular, well-commented Python code.
- Always handle API connection exceptions gracefully.
