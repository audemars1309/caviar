"""The ``profiles`` table.

Mirrors ``auth.users``: the primary key is the Supabase Auth user id
itself (not a separately generated UUID), since this table exists purely
to hold application-specific profile data keyed 1:1 to a Supabase Auth
user. Rows are created on first authenticated request via
``app.services.profiles.service.get_or_create_profile`` - there is no
"sign up" endpoint in this backend; Supabase Auth owns sign-up/sign-in.
"""

from __future__ import annotations

import uuid

from sqlalchemy import String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class Profile(Base, TimestampMixin):
    __tablename__ = "profiles"

    # The database-level FK `profiles.id -> auth.users.id ON DELETE CASCADE`
    # is created by migration 0002 and remains fully enforced by Postgres.
    # It is intentionally NOT redeclared here as a SQLAlchemy ForeignKey:
    # `auth.users` is a Supabase-owned table with no ORM model in this
    # codebase, and SQLAlchemy cannot resolve an ORM-level FK to a table
    # absent from its metadata (raises NoReferencedTableError at mapper
    # configuration time). The ORM treats `id` as a plain UUID PK; the
    # referential integrity guarantee lives where it must anyway - in the
    # database.
    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    full_name: Mapped[str | None] = mapped_column(String, nullable=True)
    target_role: Mapped[str | None] = mapped_column(String, nullable=True)
