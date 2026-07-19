# Caviar Frontend

React 19 + TypeScript + Vite frontend for Caviar (Phase 9A foundation).

## Stack
React 19, TypeScript (strict), Vite 8, React Router 7, TanStack Query 5,
Zustand 5, React Hook Form + Zod, Tailwind CSS 4, shadcn-style UI
components (vendored), Axios, Supabase Auth (`@supabase/supabase-js`).

## Setup
Run from `frontend/`:

    npm install
    cp .env.example .env.local   # fill in Supabase URL + anon key
    npm run dev

## Commands (run from `frontend/`)
    npm run dev        # start the dev server
    npm run build      # typecheck + production build
    npm run typecheck  # tsc -b
    npm run lint       # eslint (typed rules)
    npm run lint:oxlint# oxlint (fast secondary linter from the Vite template)
    npm run test       # vitest

## Architecture (Phase 9A)
- `src/routes/` - lazy route table, guards (ProtectedRoute holds on a
  loading state during session restoration; PublicOnlyRoute keeps
  signed-in users out of login/signup), path constants.
- `src/providers/` - QueryClient, Theme (light/dark/system, persisted),
  Auth (session restoration + onAuthStateChange -> auth store).
- `src/services/api/` - the ONLY API access path: axios instance with
  token injection, single-refresh-then-retry 401 policy, typed ApiError
  normalization, typed request helpers.
- `src/store/` - Zustand for CLIENT state only (auth status, user shell
  prefs, UI, notifications, theme). Server state lives in TanStack Query.
- `src/components/ui` - vendored shadcn-style design system;
  `src/components/common` - error boundary, loading, empty states.
- `src/features/` - feature modules (auth ships in 9A; resume and
  interview features arrive in 9B/9C).
- Pages are layout placeholders only; feature logic lands in later
  phases.

## Security
Only public values belong in frontend env (`VITE_API_BASE_URL`,
`VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`). Never the service-role
key, Gemini key, or any backend secret. All application data flows
through the Caviar backend API - the frontend never queries the
database directly.
