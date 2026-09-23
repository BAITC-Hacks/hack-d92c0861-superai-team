"""Manually exercise one real Phase 3 reranking request; never imported by pytest."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Sequence

if __package__ in {None, ""}:
    # Permit the documented ``python ai/tools/openai_reranker_smoke.py`` invocation.
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ai.service import CareerQuestAI


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run one sanitized OpenAI contextual-reranking request for a selected employee."
    )
    parser.add_argument(
        "--employee-id",
        required=True,
        help="Employee ID to process. It is never inferred or enumerated.",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("docs"),
        help="Directory containing the four dataset files (default: docs).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        choices=(1, 2, 3),
        default=3,
        help="Maximum number of recommendations to return (default: 3).",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run exactly one request after explicitly selecting an employee and dataset."""
    parser = _parser()
    arguments = parser.parse_args(argv)
    if not os.getenv("OPENAI_API_KEY"):
        parser.error("OPENAI_API_KEY must be set before running the real OpenAI smoke utility.")

    result = CareerQuestAI.from_directory(arguments.data_dir).recommend(
        arguments.employee_id,
        limit=arguments.limit,
    )
    # AIRecommendationResult intentionally contains no credential or raw provider response.
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
