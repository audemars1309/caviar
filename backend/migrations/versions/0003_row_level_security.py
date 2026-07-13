"""Row Level Security for every Caviar domain table.

Two things make this RLS actually protective rather than decorative SQL:

1. `FORCE ROW LEVEL SECURITY` is applied to every table. By default,
   Postgres RLS does not apply to a table's owner - and the role that runs
   these migrations *is* the owner of every table it creates. Without
   FORCE, our own backend's database connection (which uses that same
   role) would silently bypass every policy below. FORCE closes that gap.

2. Every policy checks `auth.uid()` against the row's ownership chain.
   `auth.uid()` reads the `request.jwt.claims` Postgres session setting -
   the same mechanism Supabase's real `auth.uid()` uses. The application
   sets that setting per request via `app.db.rls.get_authenticated_db`
   (Phase 2), so RLS is enforced for the backend's own queries, not only
   for a hypothetical future direct-client access path.

Ownership pattern:
  - Tables with a direct `user_id` column: policy compares `auth.uid()`
    directly to `user_id` (or, for `profiles`, to `id`).
  - Child tables without their own `user_id`: policy uses an `EXISTS`
    subquery walking up to the owning row's `user_id`, one or two joins
    deep as the schema requires.

Implementation note: each statement executed is a single top-level SQL
statement (see 0002's note on asyncpg's prepared-statement protocol).
"""

from __future__ import annotations

from alembic import op

revision = "0003_row_level_security"
down_revision = "0002_domain_schema"
branch_labels = None
depends_on = None

_DIRECT_OWNER_TABLES_BY_ID = [
    ("profiles", "id"),
]

_DIRECT_OWNER_TABLES_BY_USER_ID = [
    "job_contexts",
    "resumes",
    "resume_analyses",
    "resume_builder_projects",
    "interview_sessions",
]

# (child_table, fk_column, parent_table) - parent has user_id directly.
_ONE_HOP = [
    ("resume_analysis_categories", "resume_analysis_id", "resume_analyses"),
    ("resume_builder_sections", "project_id", "resume_builder_projects"),
    ("resume_generations", "project_id", "resume_builder_projects"),
    ("interview_questions", "session_id", "interview_sessions"),
    ("interview_answers", "session_id", "interview_sessions"),
    ("interview_memories", "session_id", "interview_sessions"),
    ("interview_reports", "session_id", "interview_sessions"),
]

# (child_table, fk_column, mid_table, mid_fk_column, root_table) -
# root has user_id directly, two joins away from child.
_TWO_HOP = [
    ("speech_metrics", "answer_id", "interview_answers", "session_id", "interview_sessions"),
    ("answer_evaluations", "answer_id", "interview_answers", "session_id", "interview_sessions"),
    (
        "interview_report_categories",
        "interview_report_id",
        "interview_reports",
        "session_id",
        "interview_sessions",
    ),
]


def _direct_statements(table: str, owner_column: str) -> list[str]:
    return [
        f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;",
        f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY;",
        f"CREATE POLICY {table}_select_own ON {table} "
        f"FOR SELECT USING (auth.uid() = {owner_column});",
        f"CREATE POLICY {table}_insert_own ON {table} "
        f"FOR INSERT WITH CHECK (auth.uid() = {owner_column});",
        f"CREATE POLICY {table}_update_own ON {table} "
        f"FOR UPDATE USING (auth.uid() = {owner_column});",
        f"CREATE POLICY {table}_delete_own ON {table} "
        f"FOR DELETE USING (auth.uid() = {owner_column});",
    ]


def _one_hop_statements(table: str, fk_column: str, parent_table: str) -> list[str]:
    exists_clause = (
        f"EXISTS (SELECT 1 FROM {parent_table} p "
        f"WHERE p.id = {table}.{fk_column} AND p.user_id = auth.uid())"
    )
    return [
        f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;",
        f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY;",
        f"CREATE POLICY {table}_select_own ON {table} FOR SELECT USING ({exists_clause});",
        f"CREATE POLICY {table}_insert_own ON {table} FOR INSERT WITH CHECK ({exists_clause});",
        f"CREATE POLICY {table}_update_own ON {table} FOR UPDATE USING ({exists_clause});",
        f"CREATE POLICY {table}_delete_own ON {table} FOR DELETE USING ({exists_clause});",
    ]


def _two_hop_statements(
    table: str, fk_column: str, mid_table: str, mid_fk_column: str, root_table: str
) -> list[str]:
    exists_clause = (
        f"EXISTS (SELECT 1 FROM {mid_table} m "
        f"JOIN {root_table} r ON r.id = m.{mid_fk_column} "
        f"WHERE m.id = {table}.{fk_column} AND r.user_id = auth.uid())"
    )
    return [
        f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;",
        f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY;",
        f"CREATE POLICY {table}_select_own ON {table} FOR SELECT USING ({exists_clause});",
        f"CREATE POLICY {table}_insert_own ON {table} FOR INSERT WITH CHECK ({exists_clause});",
        f"CREATE POLICY {table}_update_own ON {table} FOR UPDATE USING ({exists_clause});",
        f"CREATE POLICY {table}_delete_own ON {table} FOR DELETE USING ({exists_clause});",
    ]


def upgrade() -> None:
    for table, column in _DIRECT_OWNER_TABLES_BY_ID:
        for statement in _direct_statements(table, column):
            op.execute(statement)

    for table in _DIRECT_OWNER_TABLES_BY_USER_ID:
        for statement in _direct_statements(table, "user_id"):
            op.execute(statement)

    for table, fk_column, parent_table in _ONE_HOP:
        for statement in _one_hop_statements(table, fk_column, parent_table):
            op.execute(statement)

    for table, fk_column, mid_table, mid_fk_column, root_table in _TWO_HOP:
        for statement in _two_hop_statements(table, fk_column, mid_table, mid_fk_column, root_table):
            op.execute(statement)


def downgrade() -> None:
    all_tables = (
        [t for t, _ in _DIRECT_OWNER_TABLES_BY_ID]
        + _DIRECT_OWNER_TABLES_BY_USER_ID
        + [t for t, _, _ in _ONE_HOP]
        + [t for t, _, _, _, _ in _TWO_HOP]
    )
    for table in all_tables:
        op.execute(f"DROP POLICY IF EXISTS {table}_select_own ON {table};")
        op.execute(f"DROP POLICY IF EXISTS {table}_insert_own ON {table};")
        op.execute(f"DROP POLICY IF EXISTS {table}_update_own ON {table};")
        op.execute(f"DROP POLICY IF EXISTS {table}_delete_own ON {table};")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY;")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY;")
