# Caviar Frontend

React 19 · TypeScript · Vite 8 SPA for Caviar. TanStack Query (server state) ·
Zustand (client state) · Tailwind 4 · Supabase Auth.

**Version 1.0.0.**

## Run locally

```bash
npm ci
cp .env.example .env.local       # fill in real values
npm run dev                      # http://localhost:5173
```

All `VITE_*` variables are **public** (inlined at build time): the API base
URL and the Supabase URL + anon key. No secrets belong here.

## Checks

```bash
npx tsc -b          # type-check
npm run lint        # ESLint
npx vitest run      # tests
npm run build       # production build
```

Full documentation: see the repository [`docs/`](../docs) directory
(Architecture, Developer Setup, Deployment).
