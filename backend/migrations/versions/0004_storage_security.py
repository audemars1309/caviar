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

`storage.objects` RLS is enabled but deliberately NOT forced here: on a
real Supabase project, `storage.objects` is managed by Supabase's own
storage-api service, which already does not run as the table owner, so
FORCE is unnecessary there and could interfere with Supabase-internal
operations. Locally (against the Phase 2 dev-shim `storage.objects`),
ownership does mean our connection could bypass RLS without FORCE - this
is a known, acceptable local-only limitation: the storage bucket/policy
*definitions* are still fully created and validated here; full enforcement
against local direct queries is not exercised, only against a real
Supabase project's storage-api layer, which is the actual code path that
matters for production.
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
            f"VALUES ('{bucket_id}', '{bucket_id}', false) ON CONFLICT (id) DO NOTHING;"
        )

    op.execute("ALTER TABLE storage.objects ENABLE ROW LEVEL SECURITY;")

    for bucket_id in _BUCKETS:
        policy_prefix = bucket_id.replace("-", "_")
        ownership_check = (
            f"bucket_id = '{bucket_id}' AND (storage.foldername(name))[1] = auth.uid()::text"
        )
        op.execute(
            f"CREATE POLICY {policy_prefix}_select_own ON storage.objects "
            f"FOR SELECT USING ({ownership_check});"
        )
        op.execute(
            f"CREATE POLICY {policy_prefix}_insert_own ON storage.objects "
            f"FOR INSERT WITH CHECK ({ownership_check});"
        )
        op.execute(
            f"CREATE POLICY {policy_prefix}_update_own ON storage.objects "
            f"FOR UPDATE USING ({ownership_check});"
        )
        op.execute(
            f"CREATE POLICY {policy_prefix}_delete_own ON storage.objects "
            f"FOR DELETE USING ({ownership_check});"
        )


def downgrade() -> None:
    for bucket_id in _BUCKETS:
        policy_prefix = bucket_id.replace("-", "_")
        op.execute(f"DROP POLICY IF EXISTS {policy_prefix}_select_own ON storage.objects;")
        op.execute(f"DROP POLICY IF EXISTS {policy_prefix}_insert_own ON storage.objects;")
        op.execute(f"DROP POLICY IF EXISTS {policy_prefix}_update_own ON storage.objects;")
        op.execute(f"DROP POLICY IF EXISTS {policy_prefix}_delete_own ON storage.objects;")
    for bucket_id in _BUCKETS:
        op.execute(f"DELETE FROM storage.buckets WHERE id = '{bucket_id}';")
