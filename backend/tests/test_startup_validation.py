"""Tests for startup configuration validation."""

from __future__ import annotations

import pytest

from app.config import Settings
from app.core.startup import (
    ConfigurationError,
    enforce_startup_configuration,
    validate_settings,
)


def _production_settings(**overrides: object) -> Settings:
    base: dict[str, object] = {
        "APP_ENV": "production",
        "DEBUG": False,
        "DATABASE_URL": "postgresql+asyncpg://user:pw@db.example.com:5432/caviar",
        "SUPABASE_URL": "https://proj.supabase.co",
        "SUPABASE_ANON_KEY": "anon-key",
        "OPENAI_API_KEY": "openai-key",
        "BACKEND_CORS_ORIGINS": "https://app.example.com",
        "SUPABASE_JWT_JWKS_URL": "https://proj.supabase.co/auth/v1/.well-known/jwks.json",
    }
    base.update(overrides)
    return Settings(**base)  # type: ignore[arg-type]


def test_valid_production_settings_have_no_problems() -> None:
    assert validate_settings(_production_settings()) == []


def test_missing_openai_key_is_flagged() -> None:
    problems = validate_settings(_production_settings(OPENAI_API_KEY=None))
    assert any("OPENAI_API_KEY" in p for p in problems)


def test_localhost_database_is_flagged_in_production() -> None:
    problems = validate_settings(
        _production_settings(
            DATABASE_URL="postgresql+asyncpg://caviar:caviar@localhost:5432/caviar"
        )
    )
    assert any("localhost" in p for p in problems)


def test_missing_jwt_mechanism_is_flagged() -> None:
    problems = validate_settings(
        _production_settings(SUPABASE_JWT_JWKS_URL=None, SUPABASE_JWT_SECRET=None)
    )
    assert any("JWT" in p for p in problems)


def test_debug_true_is_flagged() -> None:
    problems = validate_settings(_production_settings(DEBUG=True))
    assert any("DEBUG" in p for p in problems)


def test_enforce_raises_in_production_when_invalid() -> None:
    with pytest.raises(ConfigurationError):
        enforce_startup_configuration(_production_settings(OPENAI_API_KEY=None))


def test_enforce_is_advisory_in_development() -> None:
    # Development must never raise, even with an empty configuration.
    dev = Settings(APP_ENV="development", OPENAI_API_KEY=None)  # type: ignore[arg-type]
    enforce_startup_configuration(dev)  # no exception


def test_enforce_passes_in_production_when_valid() -> None:
    enforce_startup_configuration(_production_settings())  # no exception
