"""The ``interview_memories``, ``interview_reports``, and
``interview_report_categories`` tables."""

from __future__ import annotations

import uuid

from sqlalchemy import CheckConstraint, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class InterviewMemory(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "interview_memories"

    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("interview_sessions.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    candidate_profile_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    resume_evidence_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    job_requirements_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    verified_evidence: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    weak_areas: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    strong_areas: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    contradictions: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    topics_explored: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    topics_pending: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    # --- Phase 8 (migration 0010) ---
    questions_asked: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    skills_covered: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    user_corrections: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default="[]"
    )
    confidence_trend: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default="[]"
    )
    follow_up_opportunities: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default="[]"
    )
    recent_turns: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")


class InterviewReport(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "interview_reports"
    __table_args__ = (
        CheckConstraint(
            "overall_score IS NULL OR (overall_score BETWEEN 0 AND 100)",
            name="ck_interview_reports_overall_score_range",
        ),
        CheckConstraint(
            "readiness_level IS NULL OR readiness_level IN "
            "('NOT_READY','DEVELOPING','READY','STRONG')",
            name="ck_interview_reports_readiness_level_valid",
        ),
    )

    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("interview_sessions.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    overall_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    scoring_algorithm_version: Mapped[str] = mapped_column(String, nullable=False)
    readiness_level: Mapped[str | None] = mapped_column(String, nullable=True)
    key_strengths: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    key_weaknesses: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    improvement_priorities: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    # --- Phase 8 (migration 0010) ---
    report_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    narrative_model: Mapped[str | None] = mapped_column(String, nullable=True)


class InterviewReportCategory(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "interview_report_categories"
    __table_args__ = (
        CheckConstraint(
            "score IS NULL OR (score BETWEEN 0 AND 100)",
            name="ck_interview_report_categories_score_range",
        ),
        CheckConstraint(
            "category IN ("
            "'COMMUNICATION','TECHNICAL_DEPTH','RELEVANCE','SPECIFICITY',"
            "'EVIDENCE','PROBLEM_SOLVING','ANSWER_STRUCTURE')",
            name="ck_interview_report_categories_category_valid",
        ),
        UniqueConstraint(
            "interview_report_id", "category", name="uq_interview_report_category"
        ),
    )

    interview_report_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("interview_reports.id", ondelete="CASCADE"), nullable=False
    )
    category: Mapped[str] = mapped_column(String, nullable=False)
    score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    weight: Mapped[float] = mapped_column(Numeric(4, 3), nullable=False)
    evidence: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
