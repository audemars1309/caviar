# Caviar Backend

FastAPI backend for Caviar — AI-powered career intelligence and candidate
performance platform. Python 3.12 · async SQLAlchemy · Alembic · Pydantic ·
Supabase (Postgres/Auth/Storage) · Google Gemini · faster-whisper · Kokoro ·
Tectonic.

**Version 1.0.0.**

## Run locally

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"          # add ",speech,tts" for local STT/TTS
cp .env.example .env             # fill in real values
alembic upgrade head
uvicorn app.main:app --reload
```

- API base: `/api/v1`  ·  Health: `/api/v1/health`  ·  Docs (non-prod): `/api/v1/docs`

## Checks

```bash
ruff check .
alembic heads      # exactly one head
pytest -q
```

## Key invariants

- The backend owns all deterministic logic (scores, weights, decisions, state,
  authorization); Gemini analyzes evidence and drafts language only.
- All AI output consumed by backend logic is Pydantic-validated with one
  bounded repair; every deterministic algorithm is versioned.
- Storage uses the Supabase anon key + the caller's verified JWT (RLS); no
  service-role key is used. All domain tables use `FORCE ROW LEVEL SECURITY`.

Full documentation: see the repository [`docs/`](../docs) directory
(Architecture, API, Resume System, Interview System, Environment, Deployment).
