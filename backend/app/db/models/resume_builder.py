"""The ``resume_builder_projects``, ``resume_builder_sections``, and
``resume_generations`` tables."""

from __future__ import annotations

import uuid

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ResumeBuilderProject(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "resume_builder_projects"
    __table_args__ = (
        CheckConstraint(
            "status IN ('DRAFT','FINALIZED')", name="ck_resume_builder_projects_status_valid"
        ),
        Index("ix_resume_builder_projects_user_id", "user_id"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, server_default="DRAFT")


class ResumeBuilderSection(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "resume_builder_sections"
    __table_args__ = (
        CheckConstraint(
            "section_type IN ("
            "'PERSONAL_INFO','SUMMARY','EDUCATION','SKILLS','EXPERIENCE',"
            "'INTERNSHIPS','PROJECTS','CERTIFICATIONS','ACHIEVEMENTS')",
            name="ck_resume_builder_sections_section_type_valid",
        ),
        UniqueConstraint("project_id", "sort_order", name="uq_resume_builder_sections_order"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("resume_builder_projects.id", ondelete="CASCADE"), nullable=False
    )
    section_type: Mapped[str] = mapped_column(String, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[dict] = mapped_column(JSONB, nullable=False)


class ResumeGeneration(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "resume_generations"
    __table_args__ = (
        CheckConstraint(
            "status IN ('PENDING','RENDERING','COMPILING','VALIDATING','UPLOADING',"
            "'COMPLETED','FAILED')",
            name="ck_resume_generations_status_valid",
        ),
        Index("ix_resume_generations_project_id", "project_id"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("resume_builder_projects.id", ondelete="CASCADE"), nullable=False
    )
    template_id: Mapped[str] = mapped_column(String, nullable=False)
    template_version: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, server_default="PENDING")
    storage_path: Mapped[str | None] = mapped_column(String, nullable=True)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    file_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    compiler_version: Mapped[str | None] = mapped_column(String, nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    compilation_duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
