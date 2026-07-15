# Caviar Backend

Current phase: **Phase 5 complete** - the deterministic Resume Scoring
Engine (`app/services/resume_analysis/scoring.py`, algorithm
`resume-scoring-1.0.0`): backend-owned, versioned, reproducible scoring
over the validated Phase 4 AI category assessments. Evidence-requirement
caps (unverified AI claims are never positive evidence), deterministic
structural deductions from Phase 3 parser facts, explicit non-applicable
category handling with weight renormalization, strict input validation,
and full explainability (raw AI score, adjusted score, and every applied
adjustment stored per category; `overall_score` +
`scoring_algorithm_version` on the analysis). Gemini cannot generate,
choose, or override the final score. Historical rows keep their stored
version (`unscored` for pre-Phase-5 and failed analyses) and are never
silently rescored. Migration head: `0007_scoring_engine`.

Built on: Phase 4 (centralized Gemini integration, structured outputs,
single bounded repair, trust boundaries, evidence verification), Phase 3
(upload/storage/extraction/parsing), Phase 2 (schema, auth, RLS), and
Phase 1 (application foundation).

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
