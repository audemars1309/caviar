"""Storage security foundation: private buckets and storage.objects RLS.

Buckets are created by inserting into `storage.buckets` directly (a
documented, valid way to provision Supabase Storage buckets via SQL/
migrations, avoiding a manual dashboard step) rather than via the Storage
API, keeping bucket provisioning in version control alongside the schema
that depends on it.

Path convention (per Phase 0 Draft 2): `{bucket}/{user_id}/{resource_id}.{ext}`.
Policies below check that the first path segment -
`(storage.foldername(name))[1]` - equals the caller's `auth.uid()`, so a
user can only read/write objects under their own user-id folder.

On Supabase, `storage.objects` is a platform-managed table. RLS is already
managed by Supabase itself, so this migration does not attempt to enable it.
"""

from __future__ import annotations

from alembic import op

revision = "0004_storage_security"
down_revision = "0003_row_level_security"
branch_labels = None
depends_on = None

_BUCKETS = ["resumes", "generated-resumes"]


def upgrade() -> None:
    for bucket_id in _BUCKETS:
        op.execute(
            f"INSERT INTO storage.buckets (id, name, public) "
            f"VALUES ('{bucket_id}', '{bucket_id}', false) "
            f"ON CONFLICT (id) DO NOTHING;"
        )

    # Supabase already manages RLS on storage.objects.
    # Do NOT attempt:
    # ALTER TABLE storage.objects ENABLE ROW LEVEL SECURITY;

    for bucket_id in _BUCKETS:
        policy_prefix = bucket_id.replace("-", "_")
        ownership_check = (
            f"bucket_id = '{bucket_id}' "
            f"AND (storage.foldername(name))[1] = auth.uid()::text"
        )

        op.execute(
            f"CREATE POLICY {policy_prefix}_select_own "
            f"ON storage.objects "
            f"FOR SELECT USING ({ownership_check});"
        )

        op.execute(
            f"CREATE POLICY {policy_prefix}_insert_own "
            f"ON storage.objects "
            f"FOR INSERT WITH CHECK ({ownership_check});"
        )

        op.execute(
            f"CREATE POLICY {policy_prefix}_update_own "
            f"ON storage.objects "
            f"FOR UPDATE USING ({ownership_check});"
        )

        op.execute(
            f"CREATE POLICY {policy_prefix}_delete_own "
            f"ON storage.objects "
            f"FOR DELETE USING ({ownership_check});"
        )


def downgrade() -> None:
    for bucket_id in _BUCKETS:
        policy_prefix = bucket_id.replace("-", "_")

        op.execute(
            f"DROP POLICY IF EXISTS {policy_prefix}_select_own ON storage.objects;"
        )
        op.execute(
            f"DROP POLICY IF EXISTS {policy_prefix}_insert_own ON storage.objects;"
        )
        op.execute(
            f"DROP POLICY IF EXISTS {policy_prefix}_update_own ON storage.objects;"
        )
        op.execute(
            f"DROP POLICY IF EXISTS {policy_prefix}_delete_own ON storage.objects;"
        )

    for bucket_id in _BUCKETS:
        op.execute(
            f"DELETE FROM storage.buckets WHERE id = '{bucket_id}';"
        )
