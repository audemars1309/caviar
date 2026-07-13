"""The ``resume_extractions`` table - one row per successfully extracted
resume (raw text, normalized text, deterministic parsing output, pipeline
metadata). Created by migration 0005 (Phase 3).

Kept as a separate 1:1 table (rather than TEXT columns on ``resumes``) so
resume list/detail queries stay light; the text payloads are only loaded
by the extraction endpoints that actually need them.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ResumeExtraction(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "resume_extractions"
    __table_args__ = (
        CheckConstraint("page_count > 0", name="ck_resume_extractions_page_count_positive"),
        CheckConstraint("char_count >= 0", name="ck_resume_extractions_char_count_nonneg"),
    )

    resume_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_text: Mapped[str] = mapped_column(Text, nullable=False)
    parsed_sections: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list, server_default="[]"
    )
    contact_info: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}"
    )
    detected_section_types: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list, server_default="[]"
    )
    missing_section_types: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list, server_default="[]"
    )
    page_count: Mapped[int] = mapped_column(Integer, nullable=False)
    char_count: Mapped[int] = mapped_column(Integer, nullable=False)
    extraction_duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pipeline_version: Mapped[str] = mapped_column(String, nullable=False)
