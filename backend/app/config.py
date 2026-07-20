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

    # Comma-separated Host header allowlist for TrustedHostMiddleware.
    # Empty (the development default) allows any host. In production this
    # should list the API's own domain(s) to block Host-header spoofing.
    ALLOWED_HOSTS: str = Field(default="")

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

    # --- Phase 4: Gemini AI (Resume Intelligence) ------------------------
    # Google AI Studio API key for the Gemini Developer API. Backend-only;
    # never exposed to the frontend.
    GEMINI_API_KEY: str | None = Field(default=None)

    # Task-based model routing (approved Phase 0 architecture): each AI
    # task resolves its model from its own environment variable, so tasks
    # can be moved between models (cost/quality/free-tier routing) without
    # code changes. Only the tasks that exist so far have settings here;
    # later phases add ANSWER_EVALUATION_MODEL, INTERVIEW_MODEL, etc. with
    # the subsystems that use them. Default validated against the Gemini
    # pricing/rate-limit docs (July 2026): gemini-3.5-flash is current,
    # free-tier eligible, and supports structured outputs.
    RESUME_ANALYSIS_MODEL: str = Field(default="gemini-3.5-flash")
    # Phase 6: Resume Builder content assistance (summary/bullet
    # improvement). Same free-tier-eligible default; independently
    # routable (e.g. to a Flash-Lite model) without code changes.
    CONTENT_ASSIST_MODEL: str = Field(default="gemini-3.5-flash")

    # One outbound Gemini call may take this long before timing out.
    AI_TIMEOUT_SECONDS: float = Field(default=90.0, gt=0)
    AI_MAX_OUTPUT_TOKENS: int = Field(default=8192, gt=0)
    # Low temperature: analysis should be evidence-bound, not creative.
    AI_TEMPERATURE: float = Field(default=0.2, ge=0.0, le=2.0)

    # Untrusted-content size caps forwarded to the model (characters).
    # Oversized content is truncated (and the truncation logged), never
    # rejected - a long resume is still analyzable from its first N chars.
    AI_MAX_RESUME_CHARS: int = Field(default=40_000, gt=0)
    AI_MAX_JOB_DESCRIPTION_CHARS: int = Field(default=20_000, gt=0)

    # In-process rate limit for analysis creation (per authenticated
    # user). AI calls are the most expensive operation in the system.
    RESUME_ANALYSIS_RATE_LIMIT_MAX: int = Field(default=10, gt=0)
    RESUME_ANALYSIS_RATE_LIMIT_WINDOW_SECONDS: int = Field(default=3600, gt=0)

    # --- Phase 6: Resume Builder content assistance -----------------
    CONTENT_ASSIST_RATE_LIMIT_MAX: int = Field(default=20, gt=0)
    CONTENT_ASSIST_RATE_LIMIT_WINDOW_SECONDS: int = Field(default=3600, gt=0)

    # --- Phase 7: LaTeX resume generation ----------------------------
    # Path to the pinned Tectonic executable. Production deploys vendor a
    # specific release binary and pre-warm its bundle cache at deploy
    # time; see backend/README.md.
    TECTONIC_BINARY_PATH: str = Field(default="tectonic")
    # When true, Tectonic runs with --only-cached: compiles never touch
    # the network and use only the pre-warmed local bundle cache. Enable
    # in production for deterministic, offline, reproducible compiles.
    TECTONIC_ONLY_CACHED: bool = Field(default=False)
    LATEX_COMPILE_TIMEOUT_SECONDS: float = Field(default=60.0, gt=0)
    # Hard cap on generated PDF size (bytes).
    RESUME_PDF_MAX_BYTES: int = Field(default=5_242_880, gt=0)
    GENERATED_RESUMES_BUCKET: str = Field(default="generated-resumes")
    GENERATION_RATE_LIMIT_MAX: int = Field(default=10, gt=0)
    GENERATION_RATE_LIMIT_WINDOW_SECONDS: int = Field(default=3600, gt=0)

    # --- Phase 8: Interview Intelligence ------------------------------
    # Task-based model routing (per-task env vars, per Phase 0).
    ANSWER_EVALUATION_MODEL: str = Field(default="gemini-3.5-flash")
    INTERVIEW_QUESTION_MODEL: str = Field(default="gemini-3.5-flash")
    INTERVIEW_REPORT_MODEL: str = Field(default="gemini-3.5-flash")

    # faster-whisper (optional [speech] extra; lazy-loaded).
    WHISPER_MODEL_SIZE: str = Field(default="base")
    WHISPER_DEVICE: str = Field(default="cpu")  # cpu | cuda | auto
    WHISPER_COMPUTE_TYPE: str | None = Field(default=None)
    TRANSCRIPTION_TIMEOUT_SECONDS: float = Field(default=120.0, gt=0)
    ANSWER_AUDIO_MAX_BYTES: int = Field(default=26_214_400, gt=0)  # 25 MiB

    # Kokoro TTS (optional [tts] extra; lazy-loaded).
    KOKORO_VOICE: str = Field(default="af_heart")
    KOKORO_LANG_CODE: str = Field(default="a")
    TTS_TIMEOUT_SECONDS: float = Field(default=60.0, gt=0)

    # In-process rate limit for answer submission (transcription + up to
    # three AI calls per cycle make it the most expensive endpoint).
    INTERVIEW_ANSWER_RATE_LIMIT_MAX: int = Field(default=60, gt=0)
    INTERVIEW_ANSWER_RATE_LIMIT_WINDOW_SECONDS: int = Field(default=3600, gt=0)

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
