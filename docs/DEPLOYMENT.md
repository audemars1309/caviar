# Deployment Guide

Production topology: **Frontend → Vercel**, **Backend → Railway**,
**Database/Auth/Storage → Supabase**. No URLs are hardcoded; everything is
environment-driven.

## 1. Supabase

- Create a project; note the project URL and **anon** key.
- Enable Auth (email to start; OAuth can be added later).
- Create two **private** Storage buckets: `resumes`, `generated-resumes`.
- Apply RLS. Caviar's migrations create `FORCE ROW LEVEL SECURITY` on all
  domain tables; run them against the Supabase database (see step 2 release
  command). Prefer asymmetric JWT signing and use the JWKS URL.

## 2. Backend → Railway

The backend ships a production `Dockerfile` and `railway.json`. Railway builds
the image and runs the release + start command:

```
release: alembic upgrade head
web:     uvicorn app.main:app --host 0.0.0.0 --port ${PORT}
```

Configure environment variables (see [Environment](ENVIRONMENT.md)); at
minimum: `APP_ENV=production`, `DEBUG=false`, `DATABASE_URL` (Supabase),
`SUPABASE_URL`, `SUPABASE_ANON_KEY`, one JWT mode, `GEMINI_API_KEY`,
`BACKEND_CORS_ORIGINS` (your frontend domain), `ALLOWED_HOSTS` (your API
domain), and `TECTONIC_ONLY_CACHED=true`. The app **validates configuration
at startup and refuses to boot if anything required is missing.**

Health check path: `/api/v1/health`. Custom domain: add it in Railway and
include it in `ALLOWED_HOSTS`.

> Local STT/TTS: build with `--build-arg INSTALL_SPEECH=1` if you run
> faster-whisper/Kokoro in-container. Otherwise those extras are omitted to
> keep the image small (they are lazy-loaded only when interview audio runs).

## 3. Frontend → Vercel

The frontend ships `vercel.json` (Vite framework preset, SPA rewrites, asset
caching, security headers). Set the three public build-time variables in
Vercel's Environment Variables: `VITE_API_BASE_URL` (your Railway API URL +
`/api/v1`), `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`. Add your custom
domain in Vercel.

## 4. Wire the two together

- Set the frontend's `VITE_API_BASE_URL` to the backend's public URL.
- Add the frontend's domain to the backend's `BACKEND_CORS_ORIGINS`.
- Add the backend's domain to `ALLOWED_HOSTS`.

## 5. Local production simulation

`docker compose up --build` runs Postgres + backend + nginx-served frontend
in production images. This is a rehearsal, not the production deployment.

Before going live, complete the [Production Checklist](PRODUCTION_CHECKLIST.md).
