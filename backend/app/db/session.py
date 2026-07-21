"""Async SQLAlchemy engine and session factory.

Engine construction is lazy (SQLAlchemy does not open a connection until a
session actually executes something), so importing this module - and
therefore importing ``app.main`` - never requires a live database. Only
calling ``get_db`` and executing a statement does.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import get_settings

_settings = get_settings()

engine: AsyncEngine = create_async_engine(
    _settings.DATABASE_URL,
    echo=_settings.DEBUG,
    pool_pre_ping=True,
    connect_args={
        "statement_cache_size": 0,
    },
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding a request-scoped async SQLAlchemy session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
