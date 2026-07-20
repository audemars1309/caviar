# Production Checklist

Complete before serving real users.

## Configuration
- [ ] `APP_ENV=production`, `DEBUG=false`.
- [ ] All required vars set (startup validation passes — the app boots).
- [ ] `DATABASE_URL` points at the production/Supabase database (not localhost).
- [ ] JWT verification configured (JWKS preferred); `SUPABASE_JWT_AUDIENCE` correct.
- [ ] `BACKEND_CORS_ORIGINS` = exact frontend origin(s), no wildcard.
- [ ] `ALLOWED_HOSTS` = API domain(s).
- [ ] `TECTONIC_ONLY_CACHED=true` and bundle cache pre-warmed.

## Security
- [ ] No secrets in the repository (`.env` files git-ignored; only `.env.example` committed).
- [ ] Service-role key **not** present in the backend (storage uses anon key + caller JWT).
- [ ] Frontend bundle contains only public values (API URL, Supabase URL, anon key).
- [ ] Security headers present on responses (verified: nosniff, DENY, CSP, HSTS in prod).
- [ ] RLS FORCE-enabled on all domain tables; RLS policy tests pass.
- [ ] Rate limits reviewed for expected load.
- [ ] API docs (`/docs`, `openapi.json`) disabled in production (automatic when `APP_ENV=production`).

## Data & migrations
- [ ] `alembic upgrade head` applied to the production database.
- [ ] `alembic heads` reports exactly one head.
- [ ] Private storage buckets exist: `resumes`, `generated-resumes`.

## Observability
- [ ] Structured logs shipping to your platform; `X-Request-ID` correlation confirmed.
- [ ] `/api/v1/health` and `/api/v1/health/ready` wired to platform health checks.
- [ ] No sensitive data (resumes, answers, tokens, keys) in logs.

## Validation
- [ ] Backend: `ruff check .` clean, `pytest -q` green.
- [ ] Frontend: `tsc -b` clean, `npm run lint` clean, `vitest run` green, `npm run build` succeeds.
- [ ] Both CI workflows green on `main`.
