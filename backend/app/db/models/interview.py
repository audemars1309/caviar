"""The ``interview_sessions``, ``interview_questions``, and
``interview_answers`` tables."""

from __future__ import annotations

import uuid

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class InterviewSession(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "interview_sessions"
    __table_args__ = (
        CheckConstraint(
            "current_stage IN ("
            "'INTRODUCTION','CANDIDATE_BACKGROUND','RESUME_DISCUSSION',"
            "'PROJECT_DEEP_DIVE','ROLE_SPECIFIC','BEHAVIORAL','ADAPTIVE_PROBING',"
            "'CLOSING','COMPLETED')",
            name="ck_interview_sessions_current_stage_valid",
        ),
        CheckConstraint(
            "status IN ('IN_PROGRESS','COMPLETED','ABANDONED')",
            name="ck_interview_sessions_status_valid",
        ),
        Index("ix_interview_sessions_user_id", "user_id"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False
    )
    resume_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("resumes.id", ondelete="SET NULL"), nullable=True
    )
    job_context_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("job_contexts.id", ondelete="SET NULL"), nullable=True
    )
    target_role_snapshot: Mapped[str | None] = mapped_column(String, nullable=True)
    current_stage: Mapped[str] = mapped_column(
        String, nullable=False, server_default="INTRODUCTION"
    )
    status: Mapped[str] = mapped_column(String, nullable=False, server_default="IN_PROGRESS")
    question_budget_used: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )


class InterviewQuestion(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "interview_questions"
    __table_args__ = (
        CheckConstraint(
            "question_type IN ("
            "'INTRODUCTORY','RESUME','PROJECT','TECHNICAL','BEHAVIORAL',"
            "'SITUATIONAL','FOLLOW_UP','CLAIM_VERIFICATION')",
            name="ck_interview_questions_question_type_valid",
        ),
        UniqueConstraint("session_id", "sequence_number", name="uq_interview_questions_sequence"),
    )

    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("interview_sessions.id", ondelete="CASCADE"), nullable=False
    )
    stage: Mapped[str] = mapped_column(String, nullable=False)
    question_type: Mapped[str] = mapped_column(String, nullable=False)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)


class InterviewAnswer(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "interview_answers"
    __table_args__ = (
        CheckConstraint(
            "status IN ('PENDING','TRANSCRIBED','EVALUATED','FAILED')",
            name="ck_interview_answers_status_valid",
        ),
        Index("ix_interview_answers_session_id", "session_id"),
    )

    question_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("interview_questions.id", ondelete="CASCADE"), nullable=False
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("interview_sessions.id", ondelete="CASCADE"), nullable=False
    )
    audio_storage_path: Mapped[str | None] = mapped_column(String, nullable=True)
    transcript: Mapped[str | None] = mapped_column(Text, nullable=True)
    transcript_segments: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, server_default="PENDING")
