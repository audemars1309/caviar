"""Unit tests for JWT verification and the authentication dependency.

Tests use the shared-secret (HS256) mode because it needs no network
access. The JWKS path shares all claim-validation logic (audience,
issuer, sub extraction) with this path - the only untested-here difference
is signature-key retrieval, which is pyjwt's own well-tested machinery.
"""

from __future__ import annotations

import time
import uuid

import jwt as pyjwt
import pytest

from app.config import Settings
from app.core.exceptions import AuthenticationError
from app.core.security import AuthConfigurationError, decode_supabase_jwt

_SECRET = "test-secret-for-unit-tests-only-0123456789"


def _make_settings(**overrides) -> Settings:
    base = {
        "APP_ENV": "test",
        "SUPABASE_URL": "https://example-project.supabase.co",
        "SUPABASE_JWT_SECRET": _SECRET,
        "SUPABASE_JWT_JWKS_URL": None,
        # _env_file=None prevents the developer's local .env from leaking
        # into unit tests and changing their behavior.
    }
    base.update(overrides)
    return Settings(_env_file=None, **base)


def _make_token(
    *,
    sub: str | None = None,
    audience: str = "authenticated",
    issuer: str = "https://example-project.supabase.co/auth/v1",
    secret: str = _SECRET,
    expired: bool = False,
) -> str:
    now = int(time.time())
    claims: dict = {
        "aud": audience,
        "iss": issuer,
        "iat": now - 60,
        "exp": now - 30 if expired else now + 3600,
        "email": "candidate@example.com",
    }
    if sub is not None:
        claims["sub"] = sub
    return pyjwt.encode(claims, secret, algorithm="HS256")


class TestDecodeSupabaseJwt:
    def test_valid_token_decodes(self) -> None:
        user_id = str(uuid.uuid4())
        claims = decode_supabase_jwt(_make_token(sub=user_id), _make_settings())
        assert claims["sub"] == user_id
        assert claims["email"] == "candidate@example.com"

    def test_wrong_secret_rejected(self) -> None:
        token = _make_token(sub=str(uuid.uuid4()), secret="wrong-secret-that-is-long-enough-32b")
        with pytest.raises(AuthenticationError):
            decode_supabase_jwt(token, _make_settings())

    def test_expired_token_rejected(self) -> None:
        token = _make_token(sub=str(uuid.uuid4()), expired=True)
        with pytest.raises(AuthenticationError):
            decode_supabase_jwt(token, _make_settings())

    def test_wrong_audience_rejected(self) -> None:
        token = _make_token(sub=str(uuid.uuid4()), audience="anon")
        with pytest.raises(AuthenticationError):
            decode_supabase_jwt(token, _make_settings())

    def test_wrong_issuer_rejected(self) -> None:
        token = _make_token(sub=str(uuid.uuid4()), issuer="https://attacker.example.com/auth/v1")
        with pytest.raises(AuthenticationError):
            decode_supabase_jwt(token, _make_settings())

    def test_garbage_token_rejected(self) -> None:
        with pytest.raises(AuthenticationError):
            decode_supabase_jwt("not-a-jwt-at-all", _make_settings())

    def test_no_verification_method_is_config_error_not_401(self) -> None:
        settings = _make_settings(SUPABASE_JWT_SECRET=None, SUPABASE_JWT_JWKS_URL=None)
        with pytest.raises(AuthConfigurationError):
            decode_supabase_jwt(_make_token(sub=str(uuid.uuid4())), settings)

    def test_issuer_derived_from_supabase_url(self) -> None:
        settings = _make_settings(SUPABASE_JWT_ISSUER=None)
        assert settings.resolved_jwt_issuer == "https://example-project.supabase.co/auth/v1"

    def test_explicit_issuer_overrides_derivation(self) -> None:
        settings = _make_settings(SUPABASE_JWT_ISSUER="https://custom.example.com/auth/v1")
        assert settings.resolved_jwt_issuer == "https://custom.example.com/auth/v1"
