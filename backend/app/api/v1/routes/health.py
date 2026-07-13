"""System health and readiness routes.

These are the only routes that exist in Phase 1. Health is a pure liveness
check (no external dependency touched); readiness additionally verifies the
database connection is usable, which is the only external dependency that
exists at this phase.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.core.exceptions import UpstreamServiceError
from app.db.session import get_db

router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    app_name: str
    environment: str


class ReadinessResponse(BaseModel):
    status: str
    database: str


@router.get("/health", response_model=HealthResponse, status_code=status.HTTP_200_OK)
async def health_check(settings: Settings = Depends(get_settings)) -> HealthResponse:
    """Liveness check. Does not touch the database or any external service."""
    return HealthResponse(status="ok", app_name=settings.APP_NAME, environment=settings.APP_ENV)


@router.get("/health/ready", response_model=ReadinessResponse, status_code=status.HTTP_200_OK)
async def readiness_check(db: AsyncSession = Depends(get_db)) -> ReadinessResponse:
    """Readiness check. Verifies the database connection is usable.

    Raises ``UpstreamServiceError`` (mapped to HTTP 503 by the centralized
    exception handler) rather than letting a raw connection error surface
    as an unhandled 500, so callers can distinguish "app is broken" from
    "a dependency is unavailable."
    """
    try:
        await db.execute(text("SELECT 1"))
    except (SQLAlchemyError, OSError) as exc:
        # SQLAlchemyError covers DBAPI-level failures (e.g. OperationalError)
        # that SQLAlchemy has already translated. OSError covers lower-level
        # connection failures (e.g. ConnectionRefusedError) that asyncpg can
        # raise directly during initial pool connection, before SQLAlchemy's
        # dialect-level exception translation wraps them - verified against
        # the actual failure mode of an unreachable database in this route.
        raise UpstreamServiceError("Database is not reachable.") from exc
    return ReadinessResponse(status="ok", database="reachable")
