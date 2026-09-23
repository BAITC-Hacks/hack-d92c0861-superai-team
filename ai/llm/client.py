"""Small OpenAI Responses API adapter used by the contextual reranker."""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

try:
    from dotenv import dotenv_values
except ImportError:  # pragma: no cover - supported for minimal deployments.
    dotenv_values = None  # type: ignore[assignment]


DEFAULT_OPENAI_MODEL = "gpt-6-astra"
DEFAULT_TIMEOUT_SECONDS = 8.0


def _load_optional_dotenv() -> None:
    """Load a local .env when available without replacing real environment values."""
    if dotenv_values is None:
        return
    try:
        values = dotenv_values(Path(__file__).resolve().parents[2] / ".env")
    except OSError:
        # A missing or unreadable optional configuration file must not block fallback.
        return
    for name, value in values.items():
        # ``python-dotenv`` treats an empty environment value as absent. For a
        # backend process, an explicitly empty key must instead reliably disable
        # OpenAI, including during deterministic-fallback diagnostics.
        if value is not None and name not in os.environ:
            os.environ[name] = value


_load_optional_dotenv()


class LLMUnavailableError(RuntimeError):
    """Raised when an LLM request cannot be made in the current environment."""


class LLMRequestError(RuntimeError):
    """Raised for a failed OpenAI request without exposing provider details."""

    def __init__(self, message: str, latency_ms: float | None = None) -> None:
        super().__init__(message)
        self.latency_ms = latency_ms


@dataclass(frozen=True)
class LLMConfig:
    """Environment-only LLM configuration; the API key is never logged or repr'd."""

    api_key: str | None = field(repr=False)
    model: str = DEFAULT_OPENAI_MODEL
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS

    @classmethod
    def from_environment(cls) -> "LLMConfig":
        """Read the only supported configuration sources for the OpenAI client."""
        key = os.getenv("OPENAI_API_KEY")
        model = os.getenv("OPENAI_MODEL", DEFAULT_OPENAI_MODEL).strip() or DEFAULT_OPENAI_MODEL
        timeout_raw = os.getenv("OPENAI_TIMEOUT_SECONDS", str(DEFAULT_TIMEOUT_SECONDS))
        try:
            timeout_seconds = float(timeout_raw)
        except ValueError as error:
            raise ValueError("OPENAI_TIMEOUT_SECONDS must be numeric.") from error
        if timeout_seconds <= 0:
            raise ValueError("OPENAI_TIMEOUT_SECONDS must be positive.")
        return cls(api_key=key, model=model, timeout_seconds=timeout_seconds)


@dataclass(frozen=True)
class LLMClientResponse:
    """Sanitized raw structured output and non-sensitive latency telemetry."""

    output_text: str
    latency_ms: float


class OpenAIResponsesClient:
    """Call the official OpenAI Python SDK without coupling it to engine logic."""

    def __init__(self, config: LLMConfig | None = None, sdk_client: Any | None = None) -> None:
        self._client = sdk_client
        self._unavailable_reason: str | None = None
        if config is None:
            try:
                config = LLMConfig.from_environment()
            except ValueError:
                # Configuration errors affect only the optional enhancement.
                config = LLMConfig(api_key=None)
                self._unavailable_reason = "invalid_llm_configuration"
        self.config = config
        if self._client is None:
            if self._unavailable_reason is not None:
                pass
            elif not self.config.api_key:
                self._unavailable_reason = "missing_api_key"
            else:
                try:
                    from openai import OpenAI
                except ImportError:
                    self._unavailable_reason = "openai_sdk_not_installed"
                else:
                    try:
                        self._client = OpenAI(
                            api_key=self.config.api_key,
                            timeout=self.config.timeout_seconds,
                        )
                    except Exception:
                        self._unavailable_reason = "openai_client_initialization_failed"

    @property
    def is_configured(self) -> bool:
        """Whether a request can be attempted without exposing configuration data."""
        return self._client is not None

    def request_json(
        self,
        *,
        system_prompt: str,
        context: Mapping[str, Any],
        output_schema: Mapping[str, Any],
    ) -> LLMClientResponse:
        """Request strict JSON Schema output through the Responses API."""
        if self._client is None:
            raise LLMUnavailableError(self._unavailable_reason or "llm_unavailable")
        started_at = time.perf_counter()
        try:
            response = self._client.responses.create(
                model=self.config.model,
                instructions=system_prompt,
                input=json.dumps(context, ensure_ascii=False),
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "career_quest_rerank",
                        "strict": True,
                        "schema": output_schema,
                    }
                },
                store=False,
            )
        except Exception as error:
            latency_ms = (time.perf_counter() - started_at) * 1000
            raise LLMRequestError("OpenAI request failed.", latency_ms=latency_ms) from error

        output_text = getattr(response, "output_text", None)
        if not isinstance(output_text, str) or not output_text.strip():
            latency_ms = (time.perf_counter() - started_at) * 1000
            raise LLMRequestError("OpenAI returned no structured output.", latency_ms=latency_ms)
        return LLMClientResponse(
            output_text=output_text,
            latency_ms=(time.perf_counter() - started_at) * 1000,
        )
