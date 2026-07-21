"""Automatic profile creation for Supabase Auth users.

Adds public.handle_new_user() plus an AFTER INSERT trigger on auth.users so
every new Supabase Auth user gets a matching public.profiles row, and
backfills profiles for pre-existing users. Idempotent and compatible with
the project's FORCE ROW LEVEL SECURITY model.

Confirmed against the caviar-production schema (2026-07-20):
  public.profiles(id uuid NOT NULL [no default],
                  full_name text NULL, target_role text NULL,
                  created_at timestamptz NOT NULL default now(),
                  updated_at timestamptz NOT NULL default now())
The only NOT NULL column without a default is id, supplied from NEW.id;
full_name/target_role are nullable and created_at/updated_at default to
now(), so INSERT (id) VALUES (NEW.id) is sufficient and cannot raise.

RLS note: the function is SECURITY DEFINER and runs as the migration/owner
role, not supabase_auth_admin. No additional INSERT policy is added here.
If runtime testing shows the trigger insert is blocked by FORCE RLS
(error: "new row violates row-level security policy for table profiles"),
add a narrow INSERT policy in a follow-up migration (0012) rather than
broadening permissions preemptively.

Revision ID: 0011_auto_profile_creation
Revises: 0010_interview_engine
"""

from __future__ import annotations

from alembic import op

revision = "0011_auto_profile_creation"
down_revision = "0010_interview_engine"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Trigger function. SECURITY DEFINER so it runs as the function
    #    owner (the migration role) rather than supabase_auth_admin, with a
    #    pinned search_path (standard SECURITY DEFINER hardening). The
    #    ON CONFLICT keeps it idempotent per-user and race-safe.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.handle_new_user()
        RETURNS trigger
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = public, pg_temp
        AS $$
        BEGIN
            INSERT INTO public.profiles (id)
            VALUES (NEW.id)
            ON CONFLICT (id) DO NOTHING;
            RETURN NEW;
        END;
        $$;
        """
    )

    # 2. Trigger on auth.users (dropped first for idempotency / re-runs).
    op.execute("DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;")
    op.execute(
        """
        CREATE TRIGGER on_auth_user_created
            AFTER INSERT ON auth.users
            FOR EACH ROW
            EXECUTE FUNCTION public.handle_new_user();
        """
    )

    # 3. One-time backfill: profiles for existing users that lack one.
    #    Same column list as the function. ON CONFLICT keeps it safe to
    #    re-run manually.
    op.execute(
        """
        INSERT INTO public.profiles (id)
        SELECT u.id
        FROM auth.users AS u
        LEFT JOIN public.profiles AS p ON p.id = u.id
        WHERE p.id IS NULL
        ON CONFLICT (id) DO NOTHING;
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;")
    op.execute("DROP FUNCTION IF EXISTS public.handle_new_user();")
