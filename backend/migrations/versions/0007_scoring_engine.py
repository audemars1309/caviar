"""Phase 5: deterministic Resume Scoring Engine storage.

Adds to ``resume_analysis_categories``:

  * ``adjusted_score`` - the deterministic, backend-computed score for the
    category after evidence caps and structural deductions, 0-100, NULL
    for categories the engine marked non-applicable. Kept SEPARATE from
    ``score`` (the raw validated AI category assessment, unchanged) so
    every stored analysis permanently shows both the AI input and the
    deterministic output - full explainability and reproducibility.
  * ``adjustments`` - JSONB list of the deterministic adjustments the
    engine applied to this category, each ``{code, points, reason}``
    (points 0 for pure markers such as NON_APPLICABLE). Distinct from
    ``penalties``, which remains the AI's qualitative penalty list from
    Phase 4.

``resume_analyses`` needs no new columns: ``overall_score`` and
``scoring_algorithm_version`` have existed since 0002 and are now
populated by the engine (replacing the Phase 4 ``'unscored'`` sentinel on
newly created, successfully analyzed rows). Rows created before Phase 5
keep the sentinel and NULL score - historical analyses stay exactly as
they were, interpretable via their stored version string.
"""

from __future__ import annotations

from alembic import op

revision = "0007_scoring_engine"
down_revision = "0006_resume_analysis_ai"
branch_labels = None
depends_on = None

_UPGRADE_STATEMENTS = [
    """
    ALTER TABLE resume_analysis_categories
        ADD COLUMN adjusted_score INTEGER
        CHECK (adjusted_score IS NULL OR (adjusted_score BETWEEN 0 AND 100));
    """,
    """
    ALTER TABLE resume_analysis_categories
        ADD COLUMN adjustments JSONB NOT NULL DEFAULT '[]';
    """,
]

_DOWNGRADE_STATEMENTS = [
    "ALTER TABLE resume_analysis_categories DROP COLUMN IF EXISTS adjustments;",
    "ALTER TABLE resume_analysis_categories DROP COLUMN IF EXISTS adjusted_score;",
]


def upgrade() -> None:
    for statement in _UPGRADE_STATEMENTS:
        op.execute(statement)


def downgrade() -> None:
    for statement in _DOWNGRADE_STATEMENTS:
        op.execute(statement)
