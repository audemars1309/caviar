"""Unit tests for StructuredAIRunner - the bounded-retry and single-repair
guarantees, tested with a fake raw client (no SDK, no network)."""

from __future__ import annotations

import json

import pytest
from pydantic import BaseModel

from app.config import Settings
from app.services.ai.client import AIRequest, StructuredAIRunner
from app.services.ai.exceptions import (
    AIConfigurationError,
    AIInvalidOutputError,
    AIProviderUnavailableError,
    AIRateLimitedError,
)
from app.services.ai.tasks import AITask


class DemoOutput(BaseModel):
    verdict: str
    confidence: int


VALID_RAW = json.dumps({"verdict": "ok", "confidence": 3})
INVALID_RAW = json.dumps({"verdict": "ok"})  # missing confidence
GARBAGE_RAW = "not json at all"


class FakeRawClient:
    """Scripted raw client: pops one behavior per call. A behavior is
    either a string (returned) or an exception instance (raised)."""

    def __init__(self, script: list) -> None:
        self.script = list(script)
        self.calls: list[dict] = []

    async def generate_raw(self, **kwargs) -> str:
        self.calls.append(kwargs)
        behavior = self.script.pop(0)
        if isinstance(behavior, Exception):
            raise behavior
        return behavior


def make_settings(**overrides) -> Settings:
    values = dict(
        DATABASE_URL="postgresql+asyncpg://x:x@localhost/x",
        OPENAI_API_KEY="test-key",
        _env_file=None,
    )
    values.update(overrides)
    return Settings(**values)


def make_request() -> AIRequest:
    return AIRequest(
        task=AITask.RESUME_ANALYSIS,
        system_instruction="system rules",
        user_content="analyze this",
    )


class TestStructuredAIRunner:
    async def test_valid_first_response_no_repair(self) -> None:
        client = FakeRawClient([VALID_RAW])
        runner = StructuredAIRunner(client, make_settings())
        result = await runner.run(make_request(), DemoOutput)
        assert isinstance(result.output, DemoOutput)
        assert result.output.verdict == "ok"
        assert result.repair_used is False
        assert len(client.calls) == 1

    async def test_invalid_then_repaired(self) -> None:
        client = FakeRawClient([INVALID_RAW, VALID_RAW])
        runner = StructuredAIRunner(client, make_settings())
        result = await runner.run(make_request(), DemoOutput)
        assert result.repair_used is True
        assert len(client.calls) == 2
        repair_call = client.calls[1]
        # The repair call carries the invalid output and the validation
        # errors - and does NOT re-send the original untrusted content.
        assert INVALID_RAW in repair_call["user_content"]
        assert "confidence" in repair_call["user_content"]
        assert "analyze this" not in repair_call["user_content"]

    async def test_exactly_one_repair_never_a_loop(self) -> None:
        client = FakeRawClient([INVALID_RAW, GARBAGE_RAW, VALID_RAW])
        runner = StructuredAIRunner(client, make_settings())
        with pytest.raises(AIInvalidOutputError):
            await runner.run(make_request(), DemoOutput)
        # The third scripted response (which WOULD have validated) was
        # never requested: two calls total, hard stop.
        assert len(client.calls) == 2
        assert client.script == [VALID_RAW]

    async def test_transient_failure_retried_once(self) -> None:
        client = FakeRawClient([AIProviderUnavailableError("down"), VALID_RAW])
        runner = StructuredAIRunner(client, make_settings())
        result = await runner.run(make_request(), DemoOutput)
        assert result.output.verdict == "ok"
        assert len(client.calls) == 2

    async def test_transient_failure_not_retried_twice(self) -> None:
        client = FakeRawClient(
            [AIProviderUnavailableError("down"), AIProviderUnavailableError("down"), VALID_RAW]
        )
        runner = StructuredAIRunner(client, make_settings())
        with pytest.raises(AIProviderUnavailableError):
            await runner.run(make_request(), DemoOutput)
        assert len(client.calls) == 2

    async def test_rate_limit_never_retried(self) -> None:
        client = FakeRawClient([AIRateLimitedError("throttled"), VALID_RAW])
        runner = StructuredAIRunner(client, make_settings())
        with pytest.raises(AIRateLimitedError):
            await runner.run(make_request(), DemoOutput)
        assert len(client.calls) == 1

    async def test_missing_api_key_is_configuration_error(self) -> None:
        client = FakeRawClient([VALID_RAW])
        runner = StructuredAIRunner(client, make_settings(OPENAI_API_KEY=None))
        with pytest.raises(AIConfigurationError):
            await runner.run(make_request(), DemoOutput)
        assert client.calls == []  # provider never contacted

    async def test_model_routed_from_task_setting(self) -> None:
        client = FakeRawClient([VALID_RAW])
        settings = make_settings(RESUME_ANALYSIS_MODEL="custom-model-id")
        runner = StructuredAIRunner(client, settings)
        result = await runner.run(make_request(), DemoOutput)
        assert result.model == "custom-model-id"
        assert client.calls[0]["model"] == "custom-model-id"
