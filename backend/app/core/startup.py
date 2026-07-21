"""Startup configuration validation.

Fail fast: when the app boots in staging or production, verify that the
settings the app genuinely cannot run without are present, instead of
letting the first request fail deep inside a handler. In development and
test the check is advisory (logged, not fatal) so local work and the test
suite never require real credentials.

This module owns no business logic; it only inspects ``Settings``.
"""

from __future__ import annotations

import logging

from app.config import Settings

logger = logging.getLogger("caviar.startup")


class ConfigurationError(RuntimeError):
    """Raised at startup when required production settings are missing."""


# Settings the app cannot function without in a real deployment. Each entry
# is (attribute name, human explanation). These have safe local defaults or
# are optional in the Settings model (so imports and tests never break), but
# a real staging/production boot without them is a misconfiguration.
_REQUIRED_IN_PRODUCTION: tuple[tuple[str, str], ...] = (
    ("DATABASE_URL", "Postgres connection string (Supabase)."),
    ("SUPABASE_URL", "Supabase project URL, used for auth and storage."),
    ("SUPABASE_ANON_KEY", "Supabase anon key, used for Storage REST calls."),
    ("OPENAI_API_KEY", "OpenAI API key for all AI tasks."),
    ("BACKEND_CORS_ORIGINS", "Allowed browser origins; empty blocks the SPA."),
)

# At least one JWT verification mechanism must be configured, or every
# authenticated request will fail. JWKS (asymmetric) is preferred.
_JWT_MECHANISMS: tuple[str, ...] = ("SUPABASE_JWT_JWKS_URL", "SUPABASE_JWT_SECRET")

# The local-dev DATABASE_URL default must never be used in production.
_LOCAL_DB_SENTINEL = "@localhost:"


def _is_blank(value: object) -> bool:
    return value is None or (isinstance(value, str) and value.strip() == "")


def validate_settings(settings: Settings) -> list[str]:
    """Return a list of human-readable configuration problems.

    Empty list means the configuration is valid for the current environment.
    """
    problems: list[str] = []

    for attr, explanation in _REQUIRED_IN_PRODUCTION:
        if _is_blank(getattr(settings, attr, None)):
            problems.append(f"{attr} is required ({explanation})")

    if all(_is_blank(getattr(settings, attr, None)) for attr in _JWT_MECHANISMS):
        problems.append(
            "No JWT verification configured: set SUPABASE_JWT_JWKS_URL "
            "(preferred) or SUPABASE_JWT_SECRET, or authenticated requests "
            "will all fail."
        )

    if _LOCAL_DB_SENTINEL in (settings.DATABASE_URL or ""):
        problems.append(
            "DATABASE_URL points at localhost - this looks like the local "
            "development default, not a production database."
        )

    if settings.DEBUG:
        problems.append("DEBUG must be false in production.")

    return problems


def enforce_startup_configuration(settings: Settings) -> None:
    """Validate settings for the active environment.

    Production/staging: raise ``ConfigurationError`` on any problem so the
    process refuses to start misconfigured. Development/test: log warnings
    only, so local iteration and the test suite are never blocked.
    """
    problems = validate_settings(settings)
    is_strict = settings.APP_ENV in ("production", "staging")

    if not problems:
        logger.info(
            "Configuration validated for environment=%s (strict=%s).",
            settings.APP_ENV,
            is_strict,
        )
        return

    if is_strict:
        joined = "; ".join(problems)
        raise ConfigurationError(
            f"Refusing to start in {settings.APP_ENV}: {joined}"
        )

    for problem in problems:
        logger.warning("Configuration advisory (%s): %s", settings.APP_ENV, problem)
