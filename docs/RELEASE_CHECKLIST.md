# Release Checklist

Steps to cut a versioned release.

1. **Version.** Update `backend/app/version.py`, `backend/pyproject.toml`
   (`version`), and `frontend/package.json` (`version`) to the target version.
   These are the three sources of truth.
2. **Changelog.** Add an entry to `docs/RELEASE_NOTES.md`.
3. **Gate.** Run the full local gate (see [Contributing](CONTRIBUTING.md));
   both CI workflows must be green on `main`.
4. **Migrations.** `alembic heads` reports exactly one head; the chain is
   linear.
5. **Production checklist.** Complete [Production Checklist](PRODUCTION_CHECKLIST.md).
6. **Tag.** Create the annotated tag (e.g. `v1.0.0`) on the release commit.
7. **Deploy.** Backend → Railway (release runs migrations), frontend → Vercel.
8. **Smoke test.** `/api/v1/health` returns the new version; sign in; run one
   resume analysis and one short interview end to end.
9. **Rollback plan.** Keep the previous image/deploy available; migrations in
   this release are additive.
