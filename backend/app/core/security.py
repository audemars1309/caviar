"""Supabase JWT verification and the reusable authentication dependency.

Supports two verification modes, chosen by configuration:

1. Asymmetric (JWKS) verification - the current recommended Supabase mode.
   Configure ``SUPABASE_JWT_JWKS_URL``.
2. Legacy shared-secret (HS256) verification - configure
   ``SUPABASE_JWT_SECRET``.

If ``SUPABASE_JWT_JWKS_URL`` is configured, JWKS verification is used;
otherwise the shared secret is used. If neither is configured, requests
fail with a sanitized 500 (misconfiguration), not a misleading 401 - a
missing verification method is an operator error, not a bad credential.

This module never trusts a user id supplied by the client in any form
other than the verified JWT's ``sub`` claim. No route or service may
accept a user_id from a request body/query/path and treat it as the
acting user's identity.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient

from app.config import Settings, get_settings
from app.core.exceptions import AppError, AuthenticationError

logger = logging.getLogger(__name__)

_bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class AuthenticatedUser:
    """The authenticated caller, derived exclusively from a verified JWT."""

    id: uuid.UUID
    email: str | None


class AuthConfigurationError(AppError):
    """Raised when no valid JWT verification method is configured. This is
    an operator/configuration error (HTTP 500), not a bad-credential error
    (HTTP 401) - the distinction matters for alerting."""

    status_code = 500
    error_code = "auth_misconfigured"


@lru_cache
def _get_jwk_client(jwks_url: str) -> PyJWKClient:
    return PyJWKClient(jwks_url)


def _decode_kwargs(settings: Settings) -> dict[str, Any]:
    kwargs: dict[str, Any] = {"audience": settings.SUPABASE_JWT_AUDIENCE}
    if settings.resolved_jwt_issuer:
        kwargs["issuer"] = settings.resolved_jwt_issuer
    return kwargs


def _decode_with_jwks(token: str, settings: Settings) -> dict[str, Any]:
    jwks_url = settings.resolved_jwt_jwks_url
    assert jwks_url is not None  # guarded by caller
    signing_key = _get_jwk_client(jwks_url).get_signing_key_from_jwt(token)
    return jwt.decode(
        token,
        signing_key.key,
        algorithms=["ES256", "RS256"],
        **_decode_kwargs(settings),
    )


def _decode_with_shared_secret(token: str, settings: Settings) -> dict[str, Any]:
    assert settings.SUPABASE_JWT_SECRET is not None  # guarded by caller
    return jwt.decode(
        token,
        settings.SUPABASE_JWT_SECRET,
        algorithms=["HS256"],
        **_decode_kwargs(settings),
    )


def decode_supabase_jwt(token: str, settings: Settings) -> dict[str, Any]:
    """Decode and verify a Supabase-issued JWT, returning its claims.

    Raises ``AuthenticationError`` (401) for any verification failure
    (bad signature, expired, wrong audience/issuer, malformed), and
    ``AuthConfigurationError`` (500) if no verification method is
    configured at all.
    """
    if settings.resolved_jwt_jwks_url:
        try:
            return _decode_with_jwks(token, settings)
        except Exception as exc:  # noqa: BLE001 - re-raised as AuthenticationError
            logger.info("JWKS verification failed: %s", exc.__class__.__name__)
            raise AuthenticationError("Invalid or expired credentials.") from exc

    if settings.SUPABASE_JWT_SECRET:
        try:
            return _decode_with_shared_secret(token, settings)
        except Exception as exc:  # noqa: BLE001
            logger.info("Shared-secret verification failed: %s", exc.__class__.__name__)
            raise AuthenticationError("Invalid or expired credentials.") from exc

    raise AuthConfigurationError(
        "No Supabase JWT verification method is configured "
        "(set SUPABASE_JWT_JWKS_URL or SUPABASE_JWT_SECRET)."
    )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    settings: Settings = Depends(get_settings),
) -> AuthenticatedUser:
    """FastAPI dependency: verifies the bearer token and returns the caller's
    identity. This is the ONLY sanctioned source of the acting user's id
    anywhere in the codebase - never a path/query/body parameter."""
    if credentials is None:
        raise AuthenticationError("Missing bearer credentials.")

    claims = decode_supabase_jwt(credentials.credentials, settings)

    sub = claims.get("sub")
    if not sub:
        raise AuthenticationError("Token is missing a subject claim.")
    try:
        user_id = uuid.UUID(str(sub))
    except ValueError as exc:
        raise AuthenticationError("Token subject is not a valid user id.") from exc

    return AuthenticatedUser(id=user_id, email=claims.get("email"))
