# Caviar Backend

Phase 1 (current): repository foundation only - FastAPI application factory,
structured logging, centralized exception handling, request correlation
IDs, database engine/session scaffolding, and an empty Alembic migration
environment. No Supabase schema, authentication, resume, Gemini, interview,
speech, or LaTeX functionality exists yet.

## Setup

Run all commands below from this `backend/` directory.

```
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
cp .env.example .env
python -m uvicorn app.main:app --reload
```

API: `http://127.0.0.1:8000`
Docs (development only): `http://127.0.0.1:8000/api/v1/docs`

## Tests

```
python -m pytest -v
```
