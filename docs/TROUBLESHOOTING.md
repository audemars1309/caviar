# Troubleshooting Guide

## Backend

**App refuses to start in staging/production.**
Startup validation found a missing/unsafe setting. Read the logged
`ConfigurationError` — it names each problem (e.g. missing `GEMINI_API_KEY`,
localhost `DATABASE_URL`, `DEBUG=true`). Fix the environment and redeploy.

**`pytest` fails with connection errors.**
Tests need a reachable Postgres. Start one and set `DATABASE_URL`
(`postgresql+asyncpg://caviar:caviar@localhost:5432/caviar`).

**401 on every authenticated request.**
No JWT mechanism configured, or the wrong one. Set `SUPABASE_JWT_JWKS_URL`
(preferred) or `SUPABASE_JWT_SECRET`, and confirm `SUPABASE_JWT_AUDIENCE`
matches your project (`authenticated`).

**503 from `/api/v1/health/ready`.**
The database is unreachable. Check `DATABASE_URL` and network/firewall.

**Storage calls fail.**
Ensure `SUPABASE_URL` and `SUPABASE_ANON_KEY` are set and the `resumes` /
`generated-resumes` buckets exist and are private. The backend uses the anon
key plus the caller's JWT (RLS) — it does not use a service-role key.

**Resume PDF generation fails.**
Confirm Tectonic is installed (`TECTONIC_BINARY_PATH`). In production set
`TECTONIC_ONLY_CACHED=true` and pre-warm the bundle cache at deploy time.
Compiler/template failures are classified and surfaced; user content is
preserved for retry.

## Frontend

**Build fails with "Cannot find type definition file for 'node'".**
Dependencies aren't installed. Run `npm ci` before `npm run build`.

**"Invalid frontend environment" at startup.**
A `VITE_*` variable is missing or malformed. Compare `.env.local` against
`.env.example`; `VITE_API_BASE_URL` and `VITE_SUPABASE_URL` must be valid URLs.

**CORS errors in the browser.**
Add the frontend origin to the backend `BACKEND_CORS_ORIGINS`.

**Microphone doesn't work in the interview room.**
Browsers require HTTPS (or localhost) for microphone access. The room maps
permission/device errors to clear, retryable messages.

## Docker / Compose

**`docker compose up` can't find `backend/.env`.**
Copy it first: `cp backend/.env.example backend/.env` and fill in values.

**Frontend image shows a stale build.**
`VITE_*` values are baked at build time. Rebuild with the correct
`--build-arg`s (or Compose `args`).
