# Developer Setup

From a clean machine to a running local stack.

## Prerequisites

- **Python 3.12+**
- **Node.js 22+** and npm
- **PostgreSQL 16** (local) or a Supabase project
- **Tectonic** (only needed to exercise real resume PDF generation)
- Optional: **Docker** + Docker Compose for local production simulation

## 1. Clone

```bash
git clone https://github.com/audemars1309/caviar.git
cd caviar
```

## 2. Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev]"            # add ",speech,tts" for local STT/TTS
cp .env.example .env               # then edit with real values
```

Point `DATABASE_URL` at a local Postgres or your Supabase connection string,
then apply migrations and run:

```bash
alembic upgrade head
uvicorn app.main:app --reload
```

- API: `http://localhost:8000/api/v1`
- Interactive docs (non-production only): `http://localhost:8000/api/v1/docs`
- Health: `http://localhost:8000/api/v1/health`

### Backend checks

```bash
ruff check .        # lint
pytest -q           # tests (needs a reachable Postgres)
alembic heads       # should print exactly one head
```

## 3. Frontend

```bash
cd frontend
npm ci
cp .env.example .env.local         # then edit with real values
npm run dev                        # http://localhost:5173
```

### Frontend checks

```bash
npx tsc -b          # type-check
npm run lint        # ESLint
npx vitest run      # tests
npm run build       # production build
```

## 4. Supabase (auth, storage, RLS)

Caviar expects a Supabase project providing Auth (JWT), Postgres, and two
**private** Storage buckets: `resumes` and `generated-resumes`. Configure
JWT verification in exactly one mode (JWKS preferred). See
[Environment](ENVIRONMENT.md) for the exact variables.

## 5. Local production simulation (optional)

```bash
cp backend/.env.example backend/.env    # fill in real values
docker compose up --build
# SPA: http://localhost:8080   API: http://localhost:8000/api/v1
```

If something fails, see [Troubleshooting](TROUBLESHOOTING.md).
