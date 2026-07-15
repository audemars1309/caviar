"""Phase 7: LaTeX generation warnings and failure classification.

Adds to ``resume_generations``:

  * ``warnings`` - JSONB list of structured, non-fatal generation
    warnings, each ``{code, message, ...extras}``. Two codes exist in
    pipeline v1: ``PAGE_OVERFLOW`` (the document exceeded the template's
    intended page target - the spec forbids silently deleting content, so
    the overflow is reported with recommendations instead) and
    ``UNSUPPORTED_GLYPHS`` (characters the compiler/font stack could not
    render, parsed from the engine log and preserved).
  * ``failure_category`` - machine classification recorded when
    ``status = 'FAILED'``: TEMPLATE, RENDERING, INPUT_NORMALIZATION,
    COMPILER, VALIDATION, or STORAGE. Deterministic failures are fixed
    deterministically; classification is what routes them.

All other lifecycle columns (status states, template id/version, storage
path, page count, file size, compiler metadata, timestamps) have existed
on this table since migration 0002.
"""

from __future__ import annotations

from alembic import op

revision = "0009_generation_warnings"
down_revision = "0008_builder_section_unique"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE resume_generations ADD COLUMN warnings JSONB NOT NULL DEFAULT '[]';"
    )
    op.execute("ALTER TABLE resume_generations ADD COLUMN failure_category TEXT;")


def downgrade() -> None:
    op.execute("ALTER TABLE resume_generations DROP COLUMN IF EXISTS failure_category;")
    op.execute("ALTER TABLE resume_generations DROP COLUMN IF EXISTS warnings;")
