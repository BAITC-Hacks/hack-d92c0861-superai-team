"""Run the public AI API once and print a JSON-serializable MVP response."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

if __package__ in {None, ""}:
    # Permit ``python ai/tools/mvp_smoke.py`` from the repository root on Windows and Unix.
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ai import CareerQuestAI
from ai.engine.data_loader import DataLoader


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run one Career Quest AI recommendation and print its JSON payload."
    )
    parser.add_argument(
        "--employee-id",
        help="Optional employee ID. When omitted, uses the first employee in the supplied dataset.",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("docs"),
        help="Directory containing employees.json, skills.json, events.json and activity_history.csv.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        choices=(1, 2, 3),
        default=3,
        help="Maximum recommendation count (default: 3).",
    )
    return parser


def _default_employee_id(data_directory: Path) -> str:
    employees = DataLoader.from_directory(data_directory).load_employees()
    if not employees or not isinstance(employees[0].get("employee_id"), str):
        raise ValueError("The dataset has no employee available for the local smoke test.")
    return employees[0]["employee_id"]


def main(argv: Sequence[str] | None = None) -> int:
    """Call the stable public API once; OpenAI failure remains a deterministic fallback."""
    arguments = _parser().parse_args(argv)
    employee_id = arguments.employee_id or _default_employee_id(arguments.data_dir)
    result = CareerQuestAI.from_directory(arguments.data_dir).recommend(
        employee_id,
        limit=arguments.limit,
    )
    # ``to_dict`` contains only JSON primitives, lists and mappings; never credentials.
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
