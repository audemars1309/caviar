"""Typed AI failure hierarchy.

Every failure mode of the AI layer maps to exactly one exception type, so
orchestration code can make policy decisions ("persist a failed analysis
row" vs "return a retryable 503" vs "surface an operator error") on type
alone, never by parsing provider error strings.

HTTP mapping rationale:

  * ``AIConfigurationError`` -> 500: operator error (missing key), same
    principle as ``AuthConfigurationError`` / ``StorageConfigurationError``.
  * ``AIProviderUnavailableError`` / ``AIRateLimitedError`` -> 503: the
    upstream failed or throttled *us*; the caller did nothing wrong and
    should simply retry later. Deliberately NOT 429: 429 is reserved for
    the caller exceeding Caviar's own per-user limits.
  * ``AIInvalidOutputError`` -> 502: the provider responded, but with
    output that failed strict validation even after the single bounded
    repair attempt. A bad-gateway semantic: the upstream's response was
    unusable.
"""

from __future__ import annotations

from fastapi import status

from app.core.exceptions import AppError


class AIError(AppError):
    """Base class for all AI-layer failures."""

    status_code = status.HTTP_502_BAD_GATEWAY
    error_code = "ai_error"


class AIConfigurationError(AIError):
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    error_code = "ai_misconfigured"


class AIProviderUnavailableError(AIError):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    error_code = "ai_unavailable"


class AIRateLimitedError(AIError):
    """The AI provider rate-limited Caviar's project (upstream 429)."""

    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    error_code = "ai_rate_limited"


class AIInvalidOutputError(AIError):
    """The model's output failed strict schema validation even after the
    single bounded repair attempt."""

    status_code = status.HTTP_502_BAD_GATEWAY
    error_code = "ai_invalid_output"
