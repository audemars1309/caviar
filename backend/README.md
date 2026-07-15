# Caviar Backend

Current phase: **Phase 6 complete** - the AI Resume Builder:
structured, presentation-independent resume data (one strictly validated
JSONB content document per section type per project - PERSONAL_INFO,
SUMMARY, EDUCATION, SKILLS, EXPERIENCE, INTERNSHIPS, PROJECTS,
CERTIFICATIONS, ACHIEVEMENTS - never one big text field; DB-enforced
one-section-per-type via migration 0008), full project/section CRUD under
JWT + RLS ownership, and Gemini content assistance (summary
generation/improvement, bullet improvement with grammar, conciseness,
action-verb, and ATS-aware wording rules) through the existing
centralized AI architecture (CONTENT_ASSIST task routing, structured
outputs, single bounded repair, typed failures, trust-boundary wrapping
of all user content). Factual integrity is layered: prompt rules forbid
fabrication, rewrites use bracketed placeholders plus
missing-fact questions instead of invented metrics, a deterministic
backend fabrication guard flags any number not present in the user's own
content, and assistance is persistence-free - only the user's explicit
section upsert writes content. Migration head:
`0008_builder_section_unique`.

No LaTeX/PDF generation exists yet - the controlled template rendering
and compilation pipeline is Phase 7, consuming this phase's structured
data unchanged.

Built on: Phase 5 (deterministic scoring engine), Phase 4 (centralized
Gemini integration), Phase 3 (upload/storage/extraction/parsing),
Phase 2 (schema, auth, RLS), Phase 1 (application foundation).

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
