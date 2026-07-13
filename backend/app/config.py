"""Application configuration.

Phase 1 scope: settings for the backend foundation (app metadata, CORS,
logging, database connection string).

Phase 2 adds: Supabase JWT authentication settings. Settings required by
later phases - Gemini task-based model routing (RESUME_ANALYSIS_MODEL,
ANSWER_EVALUATION_MODEL, INTERVIEW_MODEL, CONTENT_ASSIST_MODEL,
REPORT_GENERATION_MODEL), STT/TTS configuration, LaTeX compiler
configuration, and Supabase Storage/service-role keys - are intentionally
NOT defined yet. They will be added in the phases that introduce those
subsystems, per the approved Caviar architecture baseline (Phase 0 Draft 2).
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    APP_NAME: str = "Caviar"
    APP_ENV: str = Field(default="development", pattern="^(development|staging|production|test)$")
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api/v1"
    LOG_LEVEL: str = "INFO"

    # Stored as a raw comma-separated string rather than List[str]. Complex
    # (list/dict) fields on pydantic-settings are parsed as JSON by default,
    # which would reject a plain comma-separated value like
    # "http://a,http://b". Parsing it ourselves via `cors_origins_list`
    # avoids that pitfall entirely.
    BACKEND_CORS_ORIGINS: str = Field(default="")

    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://caviar:caviar@localhost:5432/caviar",
        description=(
            "Async SQLAlchemy connection string (must use the postgresql+asyncpg "
            "driver). Will point at the Supabase Postgres connection string "
            "starting in Phase 2."
        ),
    )

    # --- Phase 2: Supabase JWT authentication ---------------------------
    # Base URL of the Supabase project, e.g. https://xxxxx.supabase.co.
    # Used only to derive the expected JWT issuer; does NOT by itself
    # enable JWKS verification (see resolved_jwt_jwks_url below).
    SUPABASE_URL: str | None = Field(default=None)

    # Explicit opt-in only. Not every Supabase project has asymmetric
    # (JWKS) signing keys enabled, so this is never auto-derived from
    # SUPABASE_URL alone - a project using the legacy shared-secret mode
    # would otherwise incorrectly be routed through JWKS verification.
    SUPABASE_JWT_JWKS_URL: str | None = Field(default=None)

    # Legacy shared-secret (HS256) verification mode.
    SUPABASE_JWT_SECRET: str | None = Field(default=None)

    SUPABASE_JWT_AUDIENCE: str = Field(default="authenticated")
    SUPABASE_JWT_ISSUER: str | None = Field(default=None)

    @property
    def cors_origins_list(self) -> list[str]:
        if not self.BACKEND_CORS_ORIGINS:
            return []
        return [origin.strip() for origin in self.BACKEND_CORS_ORIGINS.split(",") if origin.strip()]

    @property
    def resolved_jwt_jwks_url(self) -> str | None:
        """JWKS endpoint used for asymmetric verification, if configured."""
        return self.SUPABASE_JWT_JWKS_URL

    @property
    def resolved_jwt_issuer(self) -> str | None:
        """Expected `iss` claim. Falls back to the standard Supabase Auth
        issuer path derived from SUPABASE_URL if not explicitly set."""
        if self.SUPABASE_JWT_ISSUER:
            return self.SUPABASE_JWT_ISSUER
        if self.SUPABASE_URL:
            return f"{self.SUPABASE_URL.rstrip('/')}/auth/v1"
        return None


@lru_cache
def get_settings() -> Settings:
    return Settings()
