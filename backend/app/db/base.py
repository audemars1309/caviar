"""Shared declarative base and reusable ORM mixins.

No domain models (resumes, interviews, job_contexts, etc.) are defined in
Phase 1. Domain models are introduced starting in Phase 2 per the approved
Caviar architecture baseline (Phase 0 Draft 2). This module only provides
the infrastructure every future model will build on: the declarative base
itself, a UUID primary-key mixin, and a created_at/updated_at timestamp
mixin.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Declarative base for all Caviar ORM models."""


class UUIDPrimaryKeyMixin:
    """Adds a UUID primary key, matching the spec's "use UUIDs where
    appropriate" convention for every domain table."""

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )


class TimestampMixin:
    """Adds created_at/updated_at columns.

    Phase 2 review observation #2: ``onupdate=func.now()`` only fires when
    SQLAlchemy itself constructs the UPDATE statement. It does not cover
    direct SQL writes (psql, the Supabase dashboard, other clients), so it
    cannot be the sole mechanism keeping ``updated_at`` correct. Starting
    with the Phase 2 schema migration, a Postgres trigger
    (``public.set_updated_at()``) is attached to every table with this
    mixin and is now the authoritative mechanism, covering every write
    path. The ``onupdate`` below is retained only as a harmless, redundant
    default for ORM-level clarity and for tests that don't touch a real
    trigger-bearing database.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
