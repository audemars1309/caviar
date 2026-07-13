"""The ``resumes`` table - uploaded candidate resume files (metadata only;
the file itself lives in Supabase Storage under the ``resumes`` bucket)."""

from __future__ import annotations

import uuid

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Resume(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "resumes"
    __table_args__ = (
        CheckConstraint(
            "file_size_bytes > 0 AND file_size_bytes <= 10485760",
            name="ck_resumes_file_size_bytes_range",
        ),
        CheckConstraint(
            "extraction_status IN ('PENDING','EXTRACTED','FAILED')",
            name="ck_resumes_extraction_status_valid",
        ),
        Index("ix_resumes_user_id", "user_id"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False
    )
    storage_path: Mapped[str] = mapped_column(String, nullable=False)
    original_filename: Mapped[str] = mapped_column(String, nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    mime_type: Mapped[str] = mapped_column(String, nullable=False)
    extraction_status: Mapped[str] = mapped_column(
        String, nullable=False, server_default="PENDING"
    )
    # Short, sanitized, machine-classifiable reason recorded when extraction
    # fails (e.g. "NO_TEXT_LAYER"). Lives here rather than on
    # resume_extractions because a failed extraction produces no extraction
    # row. Added by migration 0005 (Phase 3).
    extraction_failure_reason: Mapped[str | None] = mapped_column(String, nullable=True)
