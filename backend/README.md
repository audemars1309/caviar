# Caviar Backend

Current phase: **Phase 3 complete** - resume upload, Supabase Storage
integration (Storage REST API, caller-JWT authorized), PDF validation,
text extraction (pdfplumber), deterministic normalization, and
deterministic section parsing, on top of the Phase 1 foundation (app
factory, structured logging, correlation IDs, exception hierarchy) and
Phase 2 (full domain schema, migrations 0001-0004, Supabase JWT auth,
RLS-bound sessions). Migration head: `0005_resume_extractions`.

No Gemini/AI functionality exists yet - Resume Intelligence and scoring
begin in Phase 4.

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
