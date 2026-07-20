# Contributing Guide

## Workflow

1. Branch from `main`.
2. Make focused changes within the existing modular-monolith architecture.
3. Run the full local gate (below) — it mirrors CI.
4. Open a PR. CI (backend + frontend workflows) must pass before merge.

## Local gate (must pass before a PR)

**Backend** (from `backend/`):
```bash
ruff check .
alembic heads      # exactly one head
pytest -q
```

**Frontend** (from `frontend/`):
```bash
npx tsc -b
npm run lint
npx vitest run
npm run build
```

## Standards

- **Deterministic boundary is sacred.** Never let Gemini own a score, weight,
  final decision, state transition, or authorization. If you add an AI output
  consumed by backend logic, validate it with a strict Pydantic schema and a
  single bounded repair.
- **Version deterministic algorithms.** Store the version alongside results.
- **Types everywhere.** No `any` in the frontend; typed Python throughout.
- **Security first.** Never trust a client `user_id`; never expose a secret to
  the frontend; treat all user content (resumes, answers, filenames) as
  untrusted; never build shell strings from user input.
- **Provide complete files/tests.** No placeholders or TODOs for core logic.
- **New env var?** Add it to the relevant `.env.example` with a comment and,
  if required in production, to `app/core/startup.py`.

## Migrations

Alembic history is linear. Add the next `NNNN_*` revision with the correct
`down_revision`; never create a branch or a second head.
