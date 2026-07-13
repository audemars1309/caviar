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

    # --- Phase 3: Supabase Storage + resume upload pipeline -------------
    # Public (publishable) anon key. Required by the Storage REST API as
    # the `apikey` header on every request; authorization itself is the
    # caller's own verified JWT, so Storage RLS (migration 0004) applies.
    # This is NOT the service-role key - the service-role key is
    # deliberately not a setting in this phase at all.
    SUPABASE_ANON_KEY: str | None = Field(default=None)

    # Must match the bucket provisioned by migration 0004.
    RESUMES_BUCKET: str = Field(default="resumes")

    # Must not exceed the resumes.file_size_bytes CHECK constraint
    # (10485760 = 10 MiB) established in migration 0002.
    RESUME_MAX_FILE_SIZE_BYTES: int = Field(default=10_485_760, gt=0, le=10_485_760)

    # Structural sanity cap - a "resume" with more pages than this is
    # rejected before storage. Generous by design; typical resumes are 1-3.
    RESUME_MAX_PAGE_COUNT: int = Field(default=15, gt=0)

    # Seconds a single Storage REST call may take before timing out.
    STORAGE_TIMEOUT_SECONDS: float = Field(default=30.0, gt=0)

    # Lifetime of signed download URLs returned to the frontend.
    STORAGE_SIGNED_URL_EXPIRES_SECONDS: int = Field(default=300, gt=0)

    # In-process upload rate limit (per authenticated user).
    RESUME_UPLOAD_RATE_LIMIT_MAX: int = Field(default=10, gt=0)
    RESUME_UPLOAD_RATE_LIMIT_WINDOW_SECONDS: int = Field(default=3600, gt=0)

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
