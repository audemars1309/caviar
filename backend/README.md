# Caviar Backend

Current phase: **Phase 4 complete** - centralized Gemini AI integration
(google-genai SDK confined to one module, task-based model routing via
per-task env vars, structured outputs with strict Pydantic validation,
exactly one bounded repair attempt, typed AI failure handling) and
Resume Intelligence: evidence-based structured analysis over the Phase 3
deterministic extraction pipeline, with prompt trust boundaries and
injection resistance for untrusted resume/job-description content,
deterministic backend verification of evidence quotes, backend-owned
category weights, and job-context CRUD. Migration head:
`0006_resume_analysis_ai`.

The final numerical resume score is NOT computed yet: `overall_score`
stays NULL with `scoring_algorithm_version='unscored'`. The deterministic
Resume Scoring Engine that aggregates the stored, validated category
scores and weights is Phase 5.

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
