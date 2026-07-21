"""Centralized OpenAI client: SDK adapter + structured-output runner.

Two layers, split for testability and provider isolation:

  * ``RawStructuredAIClient`` (Protocol) / ``OpenAIRawClient`` - the ONLY
    place in the codebase that touches the openai SDK. Sends one
    structured-output request (system instruction + user content +
    response schema) and returns the raw JSON text, mapping every SDK
    failure to the typed exceptions in ``app.services.ai.exceptions``.
  * ``StructuredAIRunner`` - provider-agnostic orchestration: task-based
    model routing, one bounded transient retry, strict Pydantic
    validation, and EXACTLY ONE controlled repair attempt when validation
    fails, per the approved AI failure-handling architecture. No loops,
    no unbounded retries, structurally impossible to retry forever.

Retry policy (deliberate, per failure class):
  * Provider 5xx / transport / timeout -> one retry after a short delay
    (transient by definition).
  * Provider 429 (rate limit) -> NO retry. An immediate retry burns quota
    and usually re-fails; fail fast with a typed error and let the user
    retry later.
  * Validation failure -> one repair call that sends the model its own
    invalid output plus the validation errors and asks for corrected
    JSON. The repair prompt contains no untrusted resume content - the
    model is fixing JSON shape, not re-analyzing.

Logging: task, model, duration, attempt kind, success/failure class.
Never candidate content, never raw model output.

SDK usage validated against openai 2.46.0 (July 2026): async calls via
``AsyncOpenAI().responses.parse`` (the stable Responses API with
Structured Outputs), passing ``instructions`` (system prompt), ``input``
(user content), ``text_format`` (a Pydantic model class), ``temperature``
and ``max_output_tokens``; the raw JSON is read from ``.output_text`` so
the runner's own validation and repair path is preserved byte-for-byte.
Errors surface as ``openai.RateLimitError`` (429), ``openai.APIStatusError``
(other non-2xx, with ``.status_code``), and ``openai.APIConnectionError`` /
``openai.APITimeoutError`` (transport, no status). Confining SDK contact to
this one module makes any future provider migration a single-file change.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from functools import lru_cache
from typing import Protocol, TypeVar

import openai
from fastapi import Depends
from openai import AsyncOpenAI
from pydantic import BaseModel, ValidationError

from app.config import Settings, get_settings
from app.services.ai.exceptions import (
    AIConfigurationError,
    AIInvalidOutputError,
    AIProviderUnavailableError,
    AIRateLimitedError,
)
from app.services.ai.tasks import AITask, resolve_model_for_task

logger = logging.getLogger(__name__)

_TRANSIENT_RETRY_DELAY_SECONDS = 0.5

TSchema = TypeVar("TSchema", bound=BaseModel)


@dataclass(frozen=True)
class AIRequest:
    task: AITask
    system_instruction: str
    user_content: str


class RawStructuredAIClient(Protocol):
    """One structured-output generation call; returns the raw JSON text."""

    async def generate_raw(
        self,
        *,
        model: str,
        system_instruction: str,
        user_content: str,
        schema: type[BaseModel],
        temperature: float,
        max_output_tokens: int,
        timeout_seconds: float,
    ) -> str: ...


@lru_cache
def _openai_client(api_key: str) -> AsyncOpenAI:
    """One SDK client per process per key; AsyncOpenAI is reusable and
    manages its own connection pool."""
    return AsyncOpenAI(api_key=api_key)


# GPT-5-family reasoning models (Luna/Terra/Sol and the o-series) run at a
# fixed internal setting and reject the `temperature` sampling parameter
# with an HTTP 400 invalid_request error. Detect them by model-ID prefix so
# a task routed to a still-sampling model keeps sending temperature.
_TEMPERATURE_UNSUPPORTED_PREFIXES: tuple[str, ...] = ("gpt-5", "o1", "o3", "o4")


def _model_rejects_temperature(model: str) -> bool:
    normalized = model.lower()
    return any(normalized.startswith(prefix) for prefix in _TEMPERATURE_UNSUPPORTED_PREFIXES)


class OpenAIRawClient:
    def __init__(self, *, api_key: str) -> None:
        self._api_key = api_key

    async def generate_raw(
        self,
        *,
        model: str,
        system_instruction: str,
        user_content: str,
        schema: type[BaseModel],
        temperature: float,
        max_output_tokens: int,
        timeout_seconds: float,
    ) -> str:
        # Build request kwargs. GPT-5-family reasoning models reject the
        # `temperature` sampling parameter (HTTP 400 invalid_request);
        # they only run at their fixed internal setting. Omit it for those
        # models and pass it for any model that still supports it. The
        # protocol signature is unchanged - temperature is simply not
        # forwarded when the target model does not accept it.
        request_kwargs: dict[str, object] = dict(
            model=model,
            instructions=system_instruction,
            input=user_content,
            text_format=schema,
            max_output_tokens=max_output_tokens,
            timeout=timeout_seconds,
        )
        if not _model_rejects_temperature(model):
            request_kwargs["temperature"] = temperature

        try:
            response = await _openai_client(self._api_key).responses.parse(
                **request_kwargs
            )
        except openai.RateLimitError as exc:
            # 429 -> NO retry (RateLimitError must be caught before
            # APIStatusError, of which it is a subclass).
            logger.warning("OpenAI rate-limited the project (model=%s).", model)
            raise AIRateLimitedError(
                "The AI provider is rate-limiting requests. Try again later."
            ) from exc
        except openai.APIStatusError as exc:
            # Split by status class. 4xx is a deterministic bad request
            # (unsupported parameter, bad model, malformed input): retrying
            # is pointless, so surface it as a configuration/invalid-request
            # error (NOT the retryable AIProviderUnavailableError). 5xx is a
            # genuine upstream failure and stays retryable.
            if 400 <= exc.status_code < 500:
                logger.error(
                    "OpenAI rejected the request: code=%s model=%s", exc.status_code, model
                )
                raise AIConfigurationError(
                    "The AI provider rejected the request as invalid."
                ) from exc
            logger.error(
                "OpenAI API server error: code=%s model=%s", exc.status_code, model
            )
            raise AIProviderUnavailableError(
                "The AI provider is currently unavailable."
            ) from exc
        except openai.APIConnectionError as exc:
            # Transport failures and timeouts (APITimeoutError subclasses
            # APIConnectionError); no HTTP status.
            logger.error(
                "OpenAI transport failure: %s (model=%s)", exc.__class__.__name__, model
            )
            raise AIProviderUnavailableError(
                "The AI provider could not be reached."
            ) from exc

        text = response.output_text
        if not text:
            logger.error("OpenAI returned an empty response (model=%s).", model)
            raise AIInvalidOutputError("The AI provider returned an empty response.")
        return text


def _build_repair_user_content(invalid_output: str, validation_error: ValidationError) -> str:
    error_lines = "\n".join(
        f"- {'.'.join(str(loc) for loc in err['loc'])}: {err['msg']}"
        for err in validation_error.errors()
    )
    return (
        "The JSON below was produced for a structured-output request but failed "
        "schema validation. Return ONLY the corrected JSON object conforming to "
        "the response schema. Preserve the substantive content; fix structure, "
        "types, ranges, and missing or duplicated fields only. Do not add "
        "commentary or markdown fences.\n\n"
        f"Validation errors:\n{error_lines}\n\n"
        f"Invalid JSON:\n{invalid_output}"
    )


_REPAIR_SYSTEM_INSTRUCTION = (
    "You repair JSON documents so they conform to a provided response schema. "
    "Output only the corrected JSON object."
)


@dataclass(frozen=True)
class AIRunResult:
    """A validated structured output plus provenance for persistence."""

    output: BaseModel
    model: str
    duration_ms: int
    repair_used: bool


class StructuredAIRunner:
    """Provider-agnostic structured generation with strict validation and
    exactly one bounded repair attempt."""

    def __init__(self, raw_client: RawStructuredAIClient, settings: Settings) -> None:
        self._raw_client = raw_client
        self._settings = settings

    async def _generate_with_transient_retry(
        self, *, model: str, system_instruction: str, user_content: str, schema: type[BaseModel]
    ) -> str:
        kwargs = dict(
            model=model,
            system_instruction=system_instruction,
            user_content=user_content,
            schema=schema,
            temperature=self._settings.AI_TEMPERATURE,
            max_output_tokens=self._settings.AI_MAX_OUTPUT_TOKENS,
            timeout_seconds=self._settings.AI_TIMEOUT_SECONDS,
        )
        try:
            return await self._raw_client.generate_raw(**kwargs)
        except AIProviderUnavailableError:
            # One retry for transient provider/transport failures only.
            # AIRateLimitedError is deliberately NOT caught here.
            await asyncio.sleep(_TRANSIENT_RETRY_DELAY_SECONDS)
            return await self._raw_client.generate_raw(**kwargs)

    async def run(self, request: AIRequest, schema: type[TSchema]) -> AIRunResult:
        if not self._settings.OPENAI_API_KEY:
            raise AIConfigurationError("OPENAI_API_KEY is not configured.")
        model = resolve_model_for_task(request.task, self._settings)
        started = time.monotonic()

        raw = await self._generate_with_transient_retry(
            model=model,
            system_instruction=request.system_instruction,
            user_content=request.user_content,
            schema=schema,
        )
        repair_used = False
        try:
            output: BaseModel = schema.model_validate_json(raw)
        except ValidationError as first_error:
            # EXACTLY ONE controlled repair attempt - never a loop.
            repair_used = True
            logger.warning(
                "AI output failed validation; attempting single repair (task=%s model=%s).",
                request.task,
                model,
            )
            repaired_raw = await self._generate_with_transient_retry(
                model=model,
                system_instruction=_REPAIR_SYSTEM_INSTRUCTION,
                user_content=_build_repair_user_content(raw, first_error),
                schema=schema,
            )
            try:
                output = schema.model_validate_json(repaired_raw)
            except ValidationError as second_error:
                logger.error(
                    "AI output invalid after repair (task=%s model=%s).", request.task, model
                )
                raise AIInvalidOutputError(
                    "The AI response did not conform to the required structure."
                ) from second_error

        duration_ms = int((time.monotonic() - started) * 1000)
        logger.info(
            "AI task completed: task=%s model=%s duration_ms=%s repair_used=%s",
            request.task,
            model,
            duration_ms,
            repair_used,
        )
        return AIRunResult(
            output=output, model=model, duration_ms=duration_ms, repair_used=repair_used
        )


def get_ai_runner(settings: Settings = Depends(get_settings)) -> StructuredAIRunner:
    """FastAPI dependency producing the configured runner. Tests override
    this dependency; unit tests construct the runner with a fake raw
    client directly. The missing-key check lives in ``run`` (not here) so
    dependency resolution never fails before request validation does."""
    api_key = settings.OPENAI_API_KEY or ""
    return StructuredAIRunner(OpenAIRawClient(api_key=api_key), settings)
