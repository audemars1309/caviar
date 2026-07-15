"""The ``resume_analyses`` and ``resume_analysis_categories`` tables.

``resume_analyses`` links to an optional ``job_contexts`` row via
``job_context_id`` (nullable, ``SET NULL`` on delete) rather than storing
the job description itself; ``target_role_snapshot`` is a small immutable
copy of the role name only, kept for historical display even if the
linked job context is later edited or deleted.
"""

from __future__ import annotations

import uuid

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ResumeAnalysis(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "resume_analyses"
    __table_args__ = (
        CheckConstraint(
            "overall_score IS NULL OR (overall_score BETWEEN 0 AND 100)",
            name="ck_resume_analyses_overall_score_range",
        ),
        CheckConstraint(
            "status IN ('PENDING','COMPLETED','AI_ANALYSIS_FAILED')",
            name="ck_resume_analyses_status_valid",
        ),
        Index("ix_resume_analyses_user_id_created_at", "user_id", "created_at"),
    )

    resume_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False
    )
    job_context_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("job_contexts.id", ondelete="SET NULL"), nullable=True
    )
    target_role_snapshot: Mapped[str | None] = mapped_column(String, nullable=True)
    overall_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, server_default="PENDING")
    scoring_algorithm_version: Mapped[str] = mapped_column(String, nullable=False)
    strengths: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    weaknesses: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    missing_sections: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    # --- Phase 4 (migration 0006): validated AI analysis output groups ---
    critical_issues: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    ats_observations: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    section_feedback: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    bullet_improvements: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    priority_improvements: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    role_relevance: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    ai_model: Mapped[str | None] = mapped_column(String, nullable=True)
    analysis_schema_version: Mapped[str | None] = mapped_column(String, nullable=True)


class ResumeAnalysisCategory(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "resume_analysis_categories"
    __table_args__ = (
        CheckConstraint(
            "score IS NULL OR (score BETWEEN 0 AND 100)",
            name="ck_resume_analysis_categories_score_range",
        ),
        CheckConstraint(
            "adjusted_score IS NULL OR (adjusted_score BETWEEN 0 AND 100)",
            name="ck_resume_analysis_categories_adjusted_score_range",
        ),
        CheckConstraint(
            "category IN ("
            "'CONTENT_QUALITY','EXPERIENCE_IMPACT','SKILLS_RELEVANCE',"
            "'PROJECT_QUALITY','RESUME_STRUCTURE','ATS_COMPATIBILITY',"
            "'EVIDENCE_QUANTIFICATION')",
            name="ck_resume_analysis_categories_category_valid",
        ),
        UniqueConstraint("resume_analysis_id", "category", name="uq_resume_analysis_category"),
    )

    resume_analysis_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("resume_analyses.id", ondelete="CASCADE"), nullable=False
    )
    category: Mapped[str] = mapped_column(String, nullable=False)
    # Raw validated AI category assessment (Phase 4), stored unchanged.
    score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    weight: Mapped[float] = mapped_column(Numeric(4, 3), nullable=False)
    evidence: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    # AI qualitative penalties (Phase 4) - stored, never re-deducted.
    penalties: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    # --- Phase 5 (migration 0007): deterministic scoring engine output ---
    # Backend-computed score after evidence caps / structural deductions;
    # NULL when the engine marked the category non-applicable.
    adjusted_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    adjustments: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
