# Environment Guide

Caviar separates configuration across **development**, **staging**, and
**production**. No secrets are committed; every variable ships as a documented
placeholder in `.env.example` (backend) and `frontend/.env.example`.

In **staging** and **production**, the backend validates configuration at
startup and **refuses to boot** if required values are missing or unsafe
(`app/core/startup.py`). In **development** and **test**, the same checks are
advisory warnings only, so local work and CI are never blocked.

## Backend variables

### Required in production
| Variable | Purpose |
|---|---|
| `DATABASE_URL` | Async Postgres URL (`postgresql+asyncpg://…`, Supabase). Must not point at localhost in prod. |
| `SUPABASE_URL` | Supabase project URL (auth + storage). |
| `SUPABASE_ANON_KEY` | Anon/publishable key for Storage REST calls. **Not** the service-role key. |
| `GEMINI_API_KEY` | Google Gemini key for all AI tasks. Backend-only. |
| `BACKEND_CORS_ORIGINS` | Comma-separated allowed browser origins. Empty blocks the SPA. |
| **One JWT mode** | `SUPABASE_JWT_JWKS_URL` (preferred) **or** `SUPABASE_JWT_SECRET`. |

### Application & safety
`APP_ENV` (development/staging/production/test), `DEBUG` (must be false in
prod), `LOG_LEVEL`, `API_V1_PREFIX`, `ALLOWED_HOSTS` (Host allowlist; set to
your API domain in prod).

### AI, storage, LaTeX, speech, TTS, rate limits
Task model routing (`RESUME_ANALYSIS_MODEL`, `CONTENT_ASSIST_MODEL`,
`ANSWER_EVALUATION_MODEL`, `INTERVIEW_QUESTION_MODEL`, `INTERVIEW_REPORT_MODEL`),
AI tuning (`AI_TIMEOUT_SECONDS`, `AI_TEMPERATURE`, char caps), storage
(`RESUMES_BUCKET`, `GENERATED_RESUMES_BUCKET`, signed-URL TTL), Tectonic
(`TECTONIC_BINARY_PATH`, `TECTONIC_ONLY_CACHED`), Whisper/Kokoro tuning, and
per-user rate limits. **Every one has a safe default and is fully documented
in `backend/.env.example`.**

## Frontend variables

Every frontend variable is **public by design** (inlined into the browser
bundle by Vite at build time). Never place a secret here.

| Variable | Purpose |
|---|---|
| `VITE_API_BASE_URL` | Backend API base, including `/api/v1`. |
| `VITE_SUPABASE_URL` | Supabase project URL. |
| `VITE_SUPABASE_ANON_KEY` | Supabase anon (publishable) key. |

## Per-tier guidance

| | Development | Staging | Production |
|---|---|---|---|
| `APP_ENV` | development | staging | production |
| `DEBUG` | may be true | false | **false** |
| Startup validation | advisory | **strict** | **strict** |
| API docs (`/docs`) | on | on | **off** |
| `TECTONIC_ONLY_CACHED` | false | true | **true** |
| CORS / `ALLOWED_HOSTS` | localhost | staging domains | prod domains |
| HSTS header | off | off | **on** |
