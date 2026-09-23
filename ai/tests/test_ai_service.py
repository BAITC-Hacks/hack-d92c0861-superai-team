"""Tests for the safe Phase 3 public recommendation API."""

from __future__ import annotations

import copy
import csv
import json
from pathlib import Path
from typing import Any, Mapping

import pytest

from ai.engine.data_loader import DataLoader
from ai.engine.recommender import DeterministicRecommender
from ai.llm.client import LLMClientResponse, LLMRequestError
from ai.llm.reranker import ContextualReranker
from ai.service import CareerQuestAI
from ai.tools.mvp_smoke import main as mvp_smoke_main


class FakeRerankerClient:
    def __init__(self, output: str = "", *, configured: bool = True, error: Exception | None = None) -> None:
        self.output = output
        self.configured = configured
        self.error = error
        self.contexts: list[dict[str, Any]] = []

    @property
    def is_configured(self) -> bool:
        return self.configured

    def request_json(
        self,
        *,
        system_prompt: str,
        context: Mapping[str, Any],
        output_schema: Mapping[str, Any],
    ) -> LLMClientResponse:
        self.contexts.append(copy.deepcopy(dict(context)))
        if self.error:
            raise self.error
        return LLMClientResponse(self.output, latency_ms=8.0)


def _event(event_id: str, skill_id: str, gain: int, *, mandatory: bool = False) -> dict[str, Any]:
    return {
        "event_id": event_id,
        "title": f"{skill_id} development",
        "description": f"Develop {skill_id} with practical exercises.",
        "type": "workshop" if skill_id == "system" else "course",
        "format": "online",
        "duration_hours": 3,
        "mandatory": mandatory,
        "target_roles": ["Engineer"],
        "target_grades": ["Senior"],
        "develops_skills": [{"skill_id": skill_id, "gain": gain, "max_level": 5}],
        "prerequisites": {},
        "upcoming_sessions": [],
    }


def _write_dataset(tmp_path: Path, *, no_candidates: bool = False) -> None:
    employees = [
        {
            "employee_id": "synthetic-employee",
            "role": "Engineer",
            "grade": "Middle",
            "tenure_months": 18,
            "career_goal": {"target_role": "Engineer", "target_grade": "Senior"},
            "skills": {"system": 0, "public": 0, "testing": 0},
        }
    ]
    skills = {
        "skills": [
            {"skill_id": "system", "name": "System Design"},
            {"skill_id": "public", "name": "Public Speaking"},
            {"skill_id": "testing", "name": "Testing"},
        ],
        "role_profiles": [
            {
                "role": "Engineer",
                "grade": "Senior",
                "required_skills": {"system": 3, "public": 4, "testing": 2},
                "critical_skills": ["system"],
            }
        ],
    }
    events = [
        _event("public-event", "public", 4, mandatory=no_candidates),
        _event("system-event", "system", 1, mandatory=no_candidates),
        _event("testing-event", "testing", 2, mandatory=no_candidates),
        _event("public-history", "public", 1, mandatory=True),
    ]
    (tmp_path / "employees.json").write_text(json.dumps({"employees": employees}), encoding="utf-8")
    (tmp_path / "skills.json").write_text(json.dumps(skills), encoding="utf-8")
    (tmp_path / "events.json").write_text(json.dumps({"events": events}), encoding="utf-8")
    with (tmp_path / "activity_history.csv").open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=sorted(DataLoader.HISTORY_COLUMNS))
        writer.writeheader()
        writer.writerow(
            {
                "record_id": "synthetic-history",
                "employee_id": "synthetic-employee",
                "event_id": "public-history",
                "status": "completed",
            }
        )


def _response(*items: dict[str, Any]) -> str:
    return json.dumps({"recommendations": list(items)})


def _item(event_id: str, skill_id: str, priority: int, *, evidence_type: str = "skill_gap") -> dict[str, Any]:
    return {
        "event_id": event_id,
        "priority": priority,
        "reason": "It targets the supplied target-grade development evidence.",
        "evidence": [{"type": evidence_type, "skill_id": skill_id}],
        "history_consideration": "neutral",
    }


def _service(tmp_path: Path, client: FakeRerankerClient | None = None) -> CareerQuestAI:
    reranker = ContextualReranker(client) if client is not None else None
    return CareerQuestAI(DataLoader.from_directory(tmp_path), reranker=reranker, candidate_pool_size=5)


def test_service_returns_grounded_llm_reranking_for_critical_skill(tmp_path: Path) -> None:
    _write_dataset(tmp_path)
    client = FakeRerankerClient(
        _response(_item("system-event", "system", 1, evidence_type="critical_skill_gap"))
    )

    deterministic = DeterministicRecommender(DataLoader.from_directory(tmp_path)).recommend(
        "synthetic-employee", top_k=3
    )
    result = _service(tmp_path, client).recommend("synthetic-employee", limit=3)

    # The non-critical public course has a high gain and positive similar history,
    # yet mocked contextual reasoning can select the promotion-critical system gap.
    assert deterministic.candidates[0].candidate.event_id == "public-event"
    assert result.source == "llm"
    assert [item.event_id for item in result.recommendations] == ["system-event"]
    evidence = result.recommendations[0].evidence[0]
    assert (evidence.skill_id, evidence.current_level, evidence.required_level, evidence.critical) == (
        "system",
        0,
        3,
        True,
    )
    assert result.recommendations[0].skills_affected[0].expected_level_after_completion == 1
    assert "from 0 to 1" in result.recommendations[0].reason
    assert "required level 3" in result.recommendations[0].reason
    payload = result.to_dict()
    assert json.loads(json.dumps(payload)) == payload
    assert payload["recommendations"][0]["title"] == "system development"
    assert payload["recommendations"][0]["type"] == "workshop"
    assert payload["recommendations"][0]["format"] == "online"
    assert payload["recommendations"][0]["duration_hours"] == 3
    sent_context = client.contexts[0]
    assert set(sent_context) == {"employee", "target", "skill_gaps", "history_summary", "deterministic_candidates"}
    assert "employees" not in sent_context
    assert "activity_history" not in sent_context


@pytest.mark.parametrize(
    "client",
    [
        FakeRerankerClient(configured=False),
        FakeRerankerClient("{malformed-json"),
        FakeRerankerClient(error=TimeoutError("simulated timeout")),
        FakeRerankerClient(error=LLMRequestError("simulated provider error", latency_ms=7.5)),
    ],
)
def test_service_falls_back_safely_for_unavailable_or_invalid_llm(
    tmp_path: Path, client: FakeRerankerClient
) -> None:
    _write_dataset(tmp_path)

    result = _service(tmp_path, client).recommend("synthetic-employee", limit=2)

    assert result.source == "deterministic_fallback"
    assert 1 <= len(result.recommendations) <= 2
    assert result.fallback_reason is not None
    assert all(item.evidence for item in result.recommendations)


def test_service_missing_environment_key_uses_fallback_without_network(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_dataset(tmp_path)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    result = CareerQuestAI.from_directory(tmp_path).recommend("synthetic-employee", limit=1)

    assert result.source == "deterministic_fallback"
    assert result.fallback_reason == "llm_not_configured"
    assert len(result.recommendations) == 1


def test_service_invalid_llm_configuration_uses_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_dataset(tmp_path)
    monkeypatch.setenv("OPENAI_TIMEOUT_SECONDS", "not-a-number")

    result = CareerQuestAI.from_directory(tmp_path).recommend("synthetic-employee", limit=1)

    assert result.source == "deterministic_fallback"
    assert result.fallback_reason == "llm_not_configured"
    assert len(result.recommendations) == 1


def test_service_returns_zero_when_no_deterministic_candidates(tmp_path: Path) -> None:
    _write_dataset(tmp_path, no_candidates=True)

    result = _service(tmp_path, FakeRerankerClient()).recommend("synthetic-employee")

    assert result.source == "deterministic_fallback"
    assert result.fallback_reason == "no_deterministic_candidates"
    assert result.recommendations == ()


def test_mvp_smoke_prints_json_using_deterministic_fallback_without_api_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _write_dataset(tmp_path)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    assert mvp_smoke_main(["--data-dir", str(tmp_path), "--employee-id", "synthetic-employee"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["source"] == "deterministic_fallback"
    assert payload["recommendations"]


def test_service_limits_valid_llm_response_to_three_recommendations(tmp_path: Path) -> None:
    _write_dataset(tmp_path)
    client = FakeRerankerClient(
        _response(
            _item("system-event", "system", 1, evidence_type="critical_skill_gap"),
            _item("public-event", "public", 2),
            _item("testing-event", "testing", 3),
        )
    )

    result = _service(tmp_path, client).recommend("synthetic-employee", limit=3)

    assert result.source == "llm"
    assert len(result.recommendations) == 3
    assert [item.priority for item in result.recommendations] == [1, 2, 3]


def test_service_does_not_mutate_deterministic_dataset_facts(tmp_path: Path) -> None:
    _write_dataset(tmp_path)
    employees_path = tmp_path / "employees.json"
    events_path = tmp_path / "events.json"
    original_employees = employees_path.read_text(encoding="utf-8")
    original_events = events_path.read_text(encoding="utf-8")
    client = FakeRerankerClient(_response(_item("system-event", "system", 1, evidence_type="critical_skill_gap")))

    _service(tmp_path, client).recommend("synthetic-employee", limit=1)

    assert employees_path.read_text(encoding="utf-8") == original_employees
    assert events_path.read_text(encoding="utf-8") == original_events
