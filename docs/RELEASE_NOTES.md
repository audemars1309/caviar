# Release Notes

## v1.0.0

First production-ready release of Caviar — an AI-powered career intelligence
and candidate performance platform.

### Product
- **Resume Intelligence** — PDF upload, extraction, and structured
  evidence-based analysis with deterministic, versioned category scoring
  (`resume-scoring-1.0.0`) and role-relevance analysis.
- **AI Resume Builder** — nine structured section types with schema-validated
  editing, persistence-free AI content assistance (fabrication-guarded), and a
  controlled Jinja2 + LaTeX (Tectonic) PDF generation pipeline with versioned
  templates.
- **Adaptive AI Interviewer** — stateful engine over a fixed stage machine;
  voice or text answers, faster-whisper transcription, deterministic speech
  metrics (`speech-metrics-1.0.0`), backend-owned answer evaluation
  (`answer-evaluation-1.0.0`) and readiness aggregation
  (`interview-readiness-1.0.0`), optional Kokoro TTS, and a resilient report
  with browser print-to-PDF export.

### Architecture
- Modular monolith: FastAPI backend + React/Vite frontend.
- Supabase Postgres/Auth/Storage with `FORCE ROW LEVEL SECURITY` on all
  domain tables.
- Strict deterministic boundary: Gemini never owns scores, weights, decisions,
  state, or authorization; all AI output validated (one bounded repair).

### Production engineering (this release)
- Multi-stage production Dockerfiles (backend non-root + healthcheck;
  frontend nginx) and `docker-compose.yml` for local production simulation.
- GitHub Actions CI for backend (ruff, migration validation, pytest) and
  frontend (type-check, ESLint, Vitest, build).
- Startup configuration validation that refuses to boot a misconfigured
  staging/production process.
- Security hardening: response security headers (incl. production HSTS),
  Trusted-Host support, CORS review, per-user rate limits.
- Deployment configs for Vercel (frontend) and Railway (backend, migrate on
  release).
- Health/readiness endpoints reporting version and database reachability.
- Comprehensive external-developer documentation suite.

### Known limitations
- Interview transcript streaming/partial results are not exposed (no
  WebSocket path in v1); typed answers render verbatim and audio answers show
  the backend speech summary.
- Restore/compare of prior resume/interview versions is not offered (no
  backend endpoints); history provides view + download.
- DOCX resume upload is not supported (PDF only).
