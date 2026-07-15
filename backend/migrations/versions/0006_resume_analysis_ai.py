"""Phase 4: Gemini Resume Intelligence result storage.

Extends ``resume_analyses`` with the structured, validated AI analysis
output groups and provenance metadata:

  * ``critical_issues``, ``ats_observations``, ``section_feedback``,
    ``bullet_improvements``, ``priority_improvements``, ``role_relevance``
    - JSONB payload groups mirroring the strict Pydantic output schema
    (``resume-analysis`` schema family). These are genuinely nested,
    per-analysis document data - the JSONB-appropriate case - while the
    scoreable category data remains relational in
    ``resume_analysis_categories``.
  * ``failure_reason`` - short sanitized machine code recorded when
    ``status = 'AI_ANALYSIS_FAILED'`` (e.g. ``INVALID_AI_OUTPUT``).
  * ``ai_model`` and ``analysis_schema_version`` - which Gemini model and
    which output-schema version produced the stored analysis, so
    historical analyses stay interpretable as models and schemas evolve
    (same versioning principle as the extraction pipeline and the future
    scoring algorithm).

No changes to ``resume_analysis_categories`` are needed: it already holds
category, score (nullable), weight, evidence, penalties. RLS for both
tables was established in migration 0003 and is unaffected by ADD COLUMN.

``scoring_algorithm_version`` (NOT NULL, created in 0002) is populated
with the sentinel ``'unscored'`` by Phase 4 application code: the
deterministic scoring engine that computes ``overall_score`` from the
stored category scores and weights is Phase 5, and its version string
replaces the sentinel when it runs.
"""

from __future__ import annotations

from alembic import op

revision = "0006_resume_analysis_ai"
down_revision = "0005_resume_extractions"
branch_labels = None
depends_on = None

_COLUMNS = [
    ("critical_issues", "JSONB"),
    ("ats_observations", "JSONB"),
    ("section_feedback", "JSONB"),
    ("bullet_improvements", "JSONB"),
    ("priority_improvements", "JSONB"),
    ("role_relevance", "JSONB"),
    ("failure_reason", "TEXT"),
    ("ai_model", "TEXT"),
    ("analysis_schema_version", "TEXT"),
]


def upgrade() -> None:
    for name, sql_type in _COLUMNS:
        op.execute(f"ALTER TABLE resume_analyses ADD COLUMN {name} {sql_type};")


def downgrade() -> None:
    for name, _ in reversed(_COLUMNS):
        op.execute(f"ALTER TABLE resume_analyses DROP COLUMN IF EXISTS {name};")
