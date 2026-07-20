# Architecture Guide

Caviar is a **modular monolith**: one deployable backend, one deployable
frontend, organized into clear feature modules with strong boundaries.

## High-level topology

```
Browser (React SPA)
   │  HTTPS, Supabase JWT in Authorization header
   ▼
FastAPI backend  ──►  Google Gemini (task-routed AI)
   │                  faster-whisper (STT, lazy)
   │                  Kokoro (TTS, lazy)
   │                  Tectonic (LaTeX compile)
   ▼
Supabase: PostgreSQL (FORCE RLS) · Auth (JWT) · Storage (private buckets)
```

The frontend never talks to Gemini, Whisper, Kokoro, or Tectonic. It never
holds a backend secret. It authenticates with Supabase, sends the resulting
JWT to the backend, and renders backend-computed results.

## The deterministic boundary (the central invariant)

Gemini **analyzes evidence and drafts language**. It never owns:

- numerical scores, category weights, or final decisions,
- interview state transitions,
- authorization.

Every AI output consumed by backend logic is validated against a strict
Pydantic schema with exactly one bounded repair attempt before falling back.
Every deterministic algorithm is **versioned**, and the version is stored
alongside each persisted result so historical rows stay interpretable:

- `resume-scoring-1.0.0` — resume category scoring
- `content-assist-1.0.0` — resume builder assistance schema
- `speech-metrics-1.0.0` — speech metric calculation
- `answer-evaluation-1.0.0` — interview answer evaluation schema
- `interview-readiness-1.0.0` — interview readiness aggregation

## Backend module map

```
backend/app/
  main.py                 # app factory, middleware, lifespan, startup validation
  config.py               # all settings (pydantic-settings), env-driven
  version.py              # single source of truth for the version
  core/                   # cross-cutting: logging, middleware, security headers,
                          #   startup validation, exceptions, rate limiting
  db/                     # async engine/session, RLS GUC arming
  api/v1/                 # routers (health, profiles, resumes, resume_analyses,
                          #   resume_builder, resume_generations, job_contexts,
                          #   interviews)
  services/               # business logic, isolated by domain:
    ai/                   #   centralized Gemini client, prompts, schemas
    resume_analysis/      #   deterministic scoring
    resume_builder/       #   section schemas, content assist
    resume_generation/    #   renderer, latex escaping, compiler, validator
    storage/              #   Supabase Storage REST (anon key + caller JWT)
    speech/               #   faster-whisper transcription, metrics
    interview/            #   state machine, memory, readiness, orchestration
  schemas/                # request/response Pydantic models
migrations/               # Alembic (linear 0001 → 0010)
tests/                    # pytest
```

## Frontend module map

```
frontend/src/
  app/ providers/         # app shell, query client, auth provider
  routes/                 # lazy route table, path constants, guards
  layouts/                # Public / Auth / Dashboard shells
  pages/                  # route entry points (lazy-loaded)
  features/               # feature-isolated logic + components + hooks:
    auth/  resumes/  builder/  interviews/
  components/ui/          # vendored design-system primitives
  components/common/      # shared app components
  services/api/           # single axios client, typed helpers, error model
  store/                  # Zustand stores (client state only)
  lib/ utils/ hooks/      # shared helpers, validated env loader
```

## Request & data flow (representative)

**Resume analysis:** upload PDF → validate (type/size) → store in private
bucket → extract + normalize text → Gemini structured analysis (validated) →
**backend computes deterministic scores** → persist with algorithm version →
return structured result the SPA renders read-only.

**Interview answer cycle:** record audio in browser → POST to backend →
faster-whisper transcribes → **backend computes speech metrics** → answer
persisted before any AI call → Gemini evaluates (validated) → **backend
orchestration decides the next action** (can override the AI) → Gemini drafts
the next question → optional Kokoro TTS → response returned. A failure in TTS
or evaluation never loses the session.

## State management

- **Server state** lives in TanStack Query (never duplicated into Zustand).
- **Client state** (auth session, theme, UI, notifications) lives in Zustand.
- The backend is the single source of truth for all domain data.

## Security posture (summary)

FORCE RLS on all domain tables with `auth.uid()` as the identity anchor; the
backend never trusts a frontend-supplied `user_id`; storage uses the anon key
plus the caller's own verified JWT (no service-role key in the backend);
JWT verification pins algorithms and enforces audience. See
[Production Checklist](PRODUCTION_CHECKLIST.md) for the full list.
