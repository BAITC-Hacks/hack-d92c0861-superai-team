"""Unit tests for strict, deterministic validation of LLM reranking output."""

from __future__ import annotations

import copy
import json
import os
from typing import Any, Mapping

import pytest

from ai.llm.client import (
    DEFAULT_OPENAI_MODEL,
    LLMClientResponse,
    LLMConfig,
    OpenAIResponsesClient,
)
from ai.llm import client as client_module
from ai.llm.reranker import ContextualReranker, LLMResponseValidationError
from ai.schemas.recommendation import CandidateActivity, HistorySignals, ScoreBreakdown, ScoredCandidate, SkillImpact


class FakeRerankerClient:
    """In-memory client that never calls OpenAI."""

    def __init__(self, output: str, *, configured: bool = True, error: Exception | None = None) -> None:
        self.output = output
        self.configured = configured
        self.error = error
        self.calls: list[dict[str, Any]] = []

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
        self.calls.append(
            {
                "system_prompt": system_prompt,
                "context": copy.deepcopy(context),
                "output_schema": copy.deepcopy(output_schema),
            }
        )
        if self.error is not None:
            raise self.error
        return LLMClientResponse(output_text=self.output, latency_ms=12.5)


def _impact(skill_id: str, *, critical: bool = False) -> SkillImpact:
    return SkillImpact(
        skill_id=skill_id,
        skill_name="System Design" if skill_id == "system" else "Public Speaking",
        current_level=1,
        required_level=4,
        gap_before=3,
        gain=1,
        max_level=5,
        expected_level_after_completion=2,
        gap_after=2,
        effective_gain=1,
        critical=critical,
    )


def _candidate(event_id: str, skill_id: str, *, critical: bool = False) -> ScoredCandidate:
    return ScoredCandidate(
        candidate=CandidateActivity(
            event_id=event_id,
            title=event_id,
            event_type="workshop",
            duration_hours=2,
            affected_skills=(_impact(skill_id, critical=critical),),
        ),
        score=0.55 if critical else 0.70,
        factors=ScoreBreakdown(0.5, 0.5, 1.0 if critical else 0.0, 0.5, 0.5),
        history_signals=HistorySignals(0, 0, 0, 0, 0, 0, 0, None, ()),
    )


def _selection(event_id: str, skill_id: str, *, priority: int = 1, evidence_type: str = "skill_gap") -> dict[str, Any]:
    return {
        "event_id": event_id,
        "priority": priority,
        "reason": "This activity addresses the supplied target-grade skill gap.",
        "evidence": [{"type": evidence_type, "skill_id": skill_id}],
        "history_consideration": "neutral",
    }


def test_valid_llm_reranking_can_legitimately_change_deterministic_order() -> None:
    non_critical = _candidate("public-event", "public")
    critical = _candidate("system-event", "system", critical=True)
    payload = json.dumps(
        {"recommendations": [_selection("system-event", "system", evidence_type="critical_skill_gap")]}
    )
    client = FakeRerankerClient(payload)
    context = {"deterministic_candidates": [{"event_id": "public-event"}, {"event_id": "system-event"}]}

    selections, latency_ms = ContextualReranker(client).rerank(
        context, (non_critical, critical), limit=2
    )

    assert [selection.event_id for selection in selections] == ["system-event"]
    assert selections[0].evidence[0].type == "critical_skill_gap"
    assert latency_ms == 12.5


@pytest.mark.parametrize(
    "output",
    [
        "not-json",
        json.dumps({"recommendations": [_selection("invented-event", "system")]}),
        json.dumps(
            {
                "recommendations": [
                    _selection("system-event", "system"),
                    _selection("system-event", "system", priority=2),
                ]
            }
        ),
        json.dumps(
            {
                "recommendations": [
                    _selection("public-event", "public", evidence_type="critical_skill_gap")
                ]
            }
        ),
    ],
)
def test_invalid_or_hallucinated_llm_output_is_rejected(output: str) -> None:
    candidates = (
        _candidate("public-event", "public"),
        _candidate("system-event", "system", critical=True),
    )

    with pytest.raises(LLMResponseValidationError):
        ContextualReranker(FakeRerankerClient(output)).rerank({}, candidates, limit=2)


def test_reranker_does_not_mutate_context_or_deterministic_candidates() -> None:
    candidate = _candidate("system-event", "system", critical=True)
    context = {"nested": {"candidate_ids": ["system-event"]}}
    original_context = copy.deepcopy(context)
    original_candidate = candidate
    client = FakeRerankerClient(
        json.dumps(
            {"recommendations": [_selection("system-event", "system", evidence_type="critical_skill_gap")]}
        )
    )

    ContextualReranker(client).rerank(context, (candidate,), limit=1)

    assert context == original_context
    assert candidate == original_candidate
    assert client.calls[0]["context"] == original_context


def test_unsupported_promotion_or_manager_claim_is_rejected() -> None:
    item = _selection("system-event", "system", evidence_type="critical_skill_gap")
    item["reason"] = "Your manager recommends this and it guarantees promotion."

    with pytest.raises(LLMResponseValidationError, match="unsupported claim"):
        ContextualReranker(FakeRerankerClient(json.dumps({"recommendations": [item]}))).rerank(
            {}, (_candidate("system-event", "system", critical=True),), limit=1
        )


def test_openai_client_uses_responses_api_strict_schema_without_real_network() -> None:
    class FakeResponses:
        def __init__(self) -> None:
            self.kwargs: dict[str, Any] | None = None

        def create(self, **kwargs: Any) -> Any:
            self.kwargs = kwargs
            return type("Response", (), {"output_text": '{"recommendations": []}'})()

    responses = FakeResponses()
    sdk_client = type("SDK", (), {"responses": responses})()
    client = OpenAIResponsesClient(
        LLMConfig(api_key="unit-test-key", model="unit-test-model", timeout_seconds=8),
        sdk_client=sdk_client,
    )

    result = client.request_json(
        system_prompt="system",
        context={"candidate": "event"},
        output_schema={"type": "object"},
    )

    assert result.output_text == '{"recommendations": []}'
    assert responses.kwargs is not None
    assert responses.kwargs["model"] == "unit-test-model"
    assert responses.kwargs["text"]["format"]["type"] == "json_schema"
    assert responses.kwargs["text"]["format"]["strict"] is True
    assert responses.kwargs["store"] is False


def test_timeout_configuration_is_positive_and_remains_configurable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_TIMEOUT_SECONDS", "15")

    assert LLMConfig.from_environment().timeout_seconds == 15

    monkeypatch.setenv("OPENAI_TIMEOUT_SECONDS", "0")

    with pytest.raises(ValueError, match="positive"):
        LLMConfig.from_environment()


def test_model_uses_the_centralized_default_when_environment_is_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_MODEL", "")

    assert LLMConfig.from_environment().model == DEFAULT_OPENAI_MODEL


def test_optional_dotenv_does_not_replace_an_explicitly_empty_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "")

    client_module._load_optional_dotenv()

    assert os.environ["OPENAI_API_KEY"] == ""
