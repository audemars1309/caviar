"""Phase 3: resume text extraction storage.

Adds:

1. ``resumes.extraction_failure_reason`` - a short, sanitized,
   machine-classifiable reason recorded when extraction fails (e.g.
   ``NO_TEXT_LAYER``). Lives on ``resumes`` (not the extraction table)
   because a failed extraction produces no ``resume_extractions`` row.

2. ``resume_extractions`` - exactly one row per successfully extracted
   resume, holding the raw extracted text, the normalized text, the
   deterministically parsed sections, deterministic contact facts, and
   pipeline metadata. This is a separate 1:1 table rather than columns on
   ``resumes`` so that resume list queries never drag multi-kilobyte text
   payloads through the ORM, and so re-extraction is a clean row replace.

   ``pipeline_version`` records which version of the deterministic
   extraction/normalization/parsing pipeline produced the row, per the
   spec's requirement that deterministic algorithms be versioned so
   historical data remains interpretable.

3. RLS for ``resume_extractions`` using the established one-hop ownership
   pattern (child -> resumes.user_id), including FORCE ROW LEVEL SECURITY
   for the reasons documented in migration 0003.

Implementation note: each ``op.execute()`` call contains exactly one
top-level SQL statement (see 0002's note on asyncpg's prepared-statement
protocol).
"""

from __future__ import annotations

from alembic import op

revision = "0005_resume_extractions"
down_revision = "0004_storage_security"
branch_labels = None
depends_on = None

_UPGRADE_STATEMENTS = [
    "ALTER TABLE resumes ADD COLUMN extraction_failure_reason TEXT;",
    """
    CREATE TABLE resume_extractions (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        resume_id UUID NOT NULL UNIQUE REFERENCES resumes(id) ON DELETE CASCADE,
        raw_text TEXT NOT NULL,
        normalized_text TEXT NOT NULL,
        parsed_sections JSONB NOT NULL DEFAULT '[]',
        contact_info JSONB NOT NULL DEFAULT '{}',
        detected_section_types JSONB NOT NULL DEFAULT '[]',
        missing_section_types JSONB NOT NULL DEFAULT '[]',
        page_count INTEGER NOT NULL CHECK (page_count > 0),
        char_count INTEGER NOT NULL CHECK (char_count >= 0),
        extraction_duration_ms INTEGER,
        pipeline_version TEXT NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    """,
    """
    CREATE TRIGGER trg_resume_extractions_set_updated_at
        BEFORE UPDATE ON resume_extractions
        FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
    """,
    "ALTER TABLE resume_extractions ENABLE ROW LEVEL SECURITY;",
    "ALTER TABLE resume_extractions FORCE ROW LEVEL SECURITY;",
    """
    CREATE POLICY resume_extractions_select_own ON resume_extractions
    FOR SELECT USING (EXISTS (
        SELECT 1 FROM resumes r
        WHERE r.id = resume_extractions.resume_id AND r.user_id = auth.uid()
    ));
    """,
    """
    CREATE POLICY resume_extractions_insert_own ON resume_extractions
    FOR INSERT WITH CHECK (EXISTS (
        SELECT 1 FROM resumes r
        WHERE r.id = resume_extractions.resume_id AND r.user_id = auth.uid()
    ));
    """,
    """
    CREATE POLICY resume_extractions_update_own ON resume_extractions
    FOR UPDATE USING (EXISTS (
        SELECT 1 FROM resumes r
        WHERE r.id = resume_extractions.resume_id AND r.user_id = auth.uid()
    ));
    """,
    """
    CREATE POLICY resume_extractions_delete_own ON resume_extractions
    FOR DELETE USING (EXISTS (
        SELECT 1 FROM resumes r
        WHERE r.id = resume_extractions.resume_id AND r.user_id = auth.uid()
    ));
    """,
]

_DOWNGRADE_STATEMENTS = [
    "DROP TABLE IF EXISTS resume_extractions;",
    "ALTER TABLE resumes DROP COLUMN IF EXISTS extraction_failure_reason;",
]


def upgrade() -> None:
    for statement in _UPGRADE_STATEMENTS:
        op.execute(statement)


def downgrade() -> None:
    for statement in _DOWNGRADE_STATEMENTS:
        op.execute(statement)
