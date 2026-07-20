# Caviar

**AI-powered career intelligence and candidate performance platform.**

Caviar helps candidates understand, improve, and objectively evaluate their
readiness for hiring processes. It combines resume intelligence, an AI resume
builder with a controlled LaTeX generation pipeline, and an adaptive AI
interviewer with evidence-based performance reporting.

> **Version:** 1.0.0 &nbsp;·&nbsp; **Status:** production-ready release candidate

Caviar's design philosophy is **Analyze · Simulate · Evaluate · Improve**, with
one hard architectural rule throughout: **the backend owns all deterministic
logic** (scores, weights, state transitions, authorization). Gemini analyzes
evidence and drafts language; it never owns a number or a decision.

---

## Core systems

| System | What it does |
|---|---|
| **Resume Intelligence** | Upload a PDF resume, get structured, evidence-based analysis with deterministic category scoring (`resume-scoring-1.0.0`). |
| **AI Resume Builder** | Structured, section-based editing with AI content assistance and a controlled Jinja2 + LaTeX (Tectonic) PDF pipeline. |
| **Adaptive AI Interviewer** | A stateful interview engine over a fixed stage machine; adaptive questioning, transcription, speech metrics, and a deterministic readiness report (`interview-readiness-1.0.0`). |

## Tech stack

- **Frontend:** React 19 · TypeScript · Vite 8 · TanStack Query · Zustand · Tailwind 4
- **Backend:** Python 3.12 · FastAPI · async SQLAlchemy · Alembic · Pydantic
- **Data & auth:** Supabase (PostgreSQL, Auth, Storage) with FORCE row-level security
- **AI:** Google Gemini (task-routed) · faster-whisper (STT) · Kokoro (TTS) · Tectonic (LaTeX)
- **Architecture:** modular monolith

## Quick start

```bash
# Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env          # fill in real values
alembic upgrade head
uvicorn app.main:app --reload

# Frontend (separate terminal)
cd frontend
npm ci
cp .env.example .env.local    # fill in real values
npm run dev
```

Local production simulation (Postgres + API + nginx-served SPA):

```bash
cp backend/.env.example backend/.env   # fill in real values
docker compose up --build
# SPA: http://localhost:8080   API: http://localhost:8000/api/v1
```

## Documentation

| Guide | Purpose |
|---|---|
| [Architecture](docs/ARCHITECTURE.md) | System design, data flow, module map |
| [Developer Setup](docs/DEVELOPER_SETUP.md) | Local environment from scratch |
| [Environment](docs/ENVIRONMENT.md) | Every environment variable, per tier |
| [API Guide](docs/API.md) | Endpoints, auth, error model |
| [Resume System](docs/RESUME_SYSTEM.md) | Intelligence, builder, LaTeX pipeline |
| [Interview System](docs/INTERVIEW_SYSTEM.md) | Engine, audio flow, reporting |
| [Deployment](docs/DEPLOYMENT.md) | Vercel + Railway + Supabase |
| [Contributing](docs/CONTRIBUTING.md) | Workflow, standards, review |
| [Troubleshooting](docs/TROUBLESHOOTING.md) | Common failures and fixes |
| [Production Checklist](docs/PRODUCTION_CHECKLIST.md) | Go-live verification |
| [Release Checklist](docs/RELEASE_CHECKLIST.md) | Cutting a versioned release |
| [Release Notes](docs/RELEASE_NOTES.md) | Version history |

## License

Proprietary. All rights reserved.
