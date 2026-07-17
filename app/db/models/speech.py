"""The ``speech_metrics`` and ``answer_evaluations`` tables."""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class SpeechMetric(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "speech_metrics"

    answer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("interview_answers.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    speaking_duration_seconds: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    word_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    words_per_minute: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    long_pause_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    avg_pause_duration_seconds: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    max_pause_duration_seconds: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    filler_word_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    filler_word_frequency: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    # --- Phase 8 (migration 0010) ---
    hesitation_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    silence_duration_seconds: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    response_duration_seconds: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    answer_char_length: Mapped[int | None] = mapped_column(Integer, nullable=True)
    speech_completeness: Mapped[float | None] = mapped_column(Numeric, nullable=True)


class AnswerEvaluation(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "answer_evaluations"
    __table_args__ = (
        CheckConstraint(
            "relevance_score IS NULL OR (relevance_score BETWEEN 0 AND 100)",
            name="ck_answer_evaluations_relevance_score_range",
        ),
        CheckConstraint(
            "clarity_score IS NULL OR (clarity_score BETWEEN 0 AND 100)",
            name="ck_answer_evaluations_clarity_score_range",
        ),
        CheckConstraint(
            "technical_depth_score IS NULL OR (technical_depth_score BETWEEN 0 AND 100)",
            name="ck_answer_evaluations_technical_depth_score_range",
        ),
        CheckConstraint(
            "specificity_score IS NULL OR (specificity_score BETWEEN 0 AND 100)",
            name="ck_answer_evaluations_specificity_score_range",
        ),
        CheckConstraint(
            "evidence_score IS NULL OR (evidence_score BETWEEN 0 AND 100)",
            name="ck_answer_evaluations_evidence_score_range",
        ),
        CheckConstraint(
            "problem_solving_score IS NULL OR (problem_solving_score BETWEEN 0 AND 100)",
            name="ck_answer_evaluations_problem_solving_score_range",
        ),
        CheckConstraint(
            "communication_score IS NULL OR (communication_score BETWEEN 0 AND 100)",
            name="ck_answer_evaluations_communication_score_range",
        ),
        CheckConstraint(
            "answer_structure_score IS NULL OR (answer_structure_score BETWEEN 0 AND 100)",
            name="ck_answer_evaluations_answer_structure_score_range",
        ),
    )

    answer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("interview_answers.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    question_type: Mapped[str] = mapped_column(String, nullable=False)
    relevance_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    clarity_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    technical_depth_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    specificity_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    evidence_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    problem_solving_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    communication_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    answer_structure_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    strengths: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    weaknesses: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    supporting_evidence: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    unsupported_claims: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    follow_up_required: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    follow_up_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    recommended_action: Mapped[str | None] = mapped_column(String, nullable=True)
    target_topic: Mapped[str | None] = mapped_column(String, nullable=True)
    interviewer_observation: Mapped[str | None] = mapped_column(Text, nullable=True)
