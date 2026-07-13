"""Local development compatibility shims for Supabase-provided schemas.

Real Supabase Postgres projects already provide the `auth` schema (with
`auth.users` and `auth.uid()`) and the `storage` schema (with
`storage.buckets`, `storage.objects`, and `storage.foldername()`) as part
of the platform itself. This migration creates minimal, guarded stand-ins
for those ONLY when they do not already exist, so that:

  1. `alembic upgrade head` can run end-to-end against a plain local/dev
     Postgres instance (for testing schema + RLS + storage-policy SQL
     without a live Supabase project), and
  2. this migration is a complete no-op against a real Supabase project,
     since Supabase already provides these schemas and this migration
     checks for their existence before creating anything.

The `auth.uid()` stub below reads the `request.jwt.claims` Postgres
session setting and extracts the `sub` claim - this is the exact
convention Supabase's real `auth.uid()` uses (documented in Supabase's own
schema), not a Caviar-specific convention. That matters: it means the
application's `get_authenticated_db` dependency (app/db/rls.py), which
sets `request.jwt.claims` per request, works identically whether the
database is this local shim or a real Supabase project that already
enforces RLS through the same mechanism.
"""

from __future__ import annotations

from alembic import op

revision = "0001_local_dev_compat"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_namespace WHERE nspname = 'auth') THEN
                CREATE SCHEMA auth;

                CREATE TABLE auth.users (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    email TEXT
                );

                CREATE FUNCTION auth.uid() RETURNS UUID
                LANGUAGE sql STABLE
                AS $fn$
                    SELECT (NULLIF(current_setting('request.jwt.claims', true), '')::json ->> 'sub')::uuid;
                $fn$;
            END IF;
        END
        $$;
        """
    )

    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_namespace WHERE nspname = 'storage') THEN
                CREATE SCHEMA storage;

                CREATE TABLE storage.buckets (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    public BOOLEAN NOT NULL DEFAULT false
                );

                CREATE TABLE storage.objects (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    bucket_id TEXT REFERENCES storage.buckets(id),
                    name TEXT,
                    owner UUID
                );

                CREATE FUNCTION storage.foldername(name TEXT) RETURNS TEXT[]
                LANGUAGE sql IMMUTABLE
                AS $fn$
                    SELECT string_to_array(name, '/');
                $fn$;
            END IF;
        END
        $$;
        """
    )


def downgrade() -> None:
    raise NotImplementedError(
        "Downgrading the local-dev compatibility shim is not supported. Its "
        "upgrade is guarded against real Supabase schemas already existing, "
        "but it cannot safely distinguish 'schema created by this shim' from "
        "'schema already present' at downgrade time, and dropping a real "
        "Supabase project's auth/storage schemas would be destructive. For "
        "local development, drop and recreate the database instead of "
        "downgrading through this migration."
    )
