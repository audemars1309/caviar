"""The ``job_contexts`` table.

Reusable, user-owned reference data (target role, company, job
description) that resume analyses and interview sessions link to via a
nullable ``job_context_id`` FK rather than duplicating the job
description text. See Phase 0 Draft 2, Section 6, for the full rationale
and deletion-behavior discussion (``ON DELETE SET NULL``, immutable
``target_role_snapshot`` on the referencing tables).
"""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class JobContext(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "job_contexts"
    __table_args__ = (Index("ix_job_contexts_user_id", "user_id"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False
    )
    target_role: Mapped[str] = mapped_column(String, nullable=False)
    company_name: Mapped[str | None] = mapped_column(String, nullable=True)
    job_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    requirements_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
