# Caviar Backend

Current phase: **Phase 7 complete** - the controlled LaTeX Resume
Generation Engine: Caviar-owned versioned templates (registry-validated
metadata; arbitrary user templates impossible by construction), Jinja2
rendering with remapped delimiters behind a single deterministic
escaping/normalization boundary (all ten LaTeX specials, Unicode
preserved for XeTeX, control characters removed, command injection
structurally impossible, no double escaping by construction), sandboxed
Tectonic compilation (pinned binary, argument arrays, never shell=True,
randomized isolated temp dirs, timeout, exit-code validation, capped
stdout/stderr capture, sanitized failure hints, guaranteed cleanup), PDF
validation (header, non-empty, size cap, page count) with structured
PAGE_OVERFLOW and UNSUPPORTED_GLYPHS warnings (content is never silently
deleted), private generated-resumes Storage upload via the Storage REST
client under the caller's JWT, full lifecycle persistence
(PENDING/RENDERING/COMPILING/VALIDATING/UPLOADING/COMPLETED/FAILED) with
failure classification (TEMPLATE/RENDERING/INPUT_NORMALIZATION/COMPILER/
VALIDATION/STORAGE), and recoverable failures that never touch structured
resume data. No AI participates in generation. Migration head:
`0009_generation_warnings`.

**Tectonic deployment (validated against Tectonic 0.15.0):** vendor the
pinned release binary with the deploy, pre-warm its bundle cache once at
deploy/build time by compiling a warm-up document with network access,
then run with `TECTONIC_ONLY_CACHED=true` so production compiles are
offline, deterministic, and reproducible.

Built on: Phase 6 (Resume Builder), Phase 5 (scoring engine), Phase 4
(Gemini integration), Phase 3 (upload/extraction), Phase 2 (schema,
auth, RLS), Phase 1 (foundation).

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
