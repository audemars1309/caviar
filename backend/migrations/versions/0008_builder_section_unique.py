"""Phase 6: Resume Builder structural integrity.

Adds UNIQUE (project_id, section_type) to ``resume_builder_sections``.

The approved data model stores exactly one structured content document
per section type per builder project (the Phase 7 LaTeX pipeline renders
one EXPERIENCE section, one SKILLS section, and so on). Phase 2 created
the table with only UNIQUE (project_id, sort_order); enforcing the
one-per-type invariant in the database - not just in application code -
makes duplicate-section corruption impossible regardless of future code
paths, and gives the section upsert a race-safe anchor.

Safe to apply: no production data exists, and the invariant already holds
vacuously (the table has never been written to before Phase 6).
"""

from __future__ import annotations

from alembic import op

revision = "0008_builder_section_unique"
down_revision = "0007_scoring_engine"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE resume_builder_sections "
        "ADD CONSTRAINT uq_resume_builder_sections_type UNIQUE (project_id, section_type);"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE resume_builder_sections "
        "DROP CONSTRAINT IF EXISTS uq_resume_builder_sections_type;"
    )
