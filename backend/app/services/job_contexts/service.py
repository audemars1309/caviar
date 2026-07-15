"""Job context CRUD (Phase 4).

Minimal user-owned reference data consumed by resume analyses now and by
interview sessions in later phases. All access goes through the
RLS-bound session; queries also filter by the verified user id explicitly
(defense-in-depth, and existence-hiding 404s for foreign ids).
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import AuthenticatedUser
from app.db.models.job_context import JobContext
from app.services.resume_analysis.service import JobContextNotFoundError


async def create_job_context(
    *,
    db: AsyncSession,
    user: AuthenticatedUser,
    target_role: str,
    company_name: str | None,
    job_description: str | None,
) -> JobContext:
    job_context = JobContext(
        user_id=user.id,
        target_role=target_role.strip(),
        company_name=company_name.strip() if company_name else None,
        job_description=job_description,
    )
    db.add(job_context)
    await db.commit()
    await db.refresh(job_context)
    return job_context


async def list_job_contexts(db: AsyncSession, user: AuthenticatedUser) -> list[JobContext]:
    result = await db.execute(
        select(JobContext)
        .where(JobContext.user_id == user.id)
        .order_by(JobContext.created_at.desc())
    )
    return list(result.scalars().all())


async def get_job_context(
    db: AsyncSession, user: AuthenticatedUser, job_context_id: uuid.UUID
) -> JobContext:
    result = await db.execute(
        select(JobContext).where(JobContext.id == job_context_id, JobContext.user_id == user.id)
    )
    job_context = result.scalar_one_or_none()
    if job_context is None:
        raise JobContextNotFoundError("Job context not found.")
    return job_context


async def delete_job_context(
    db: AsyncSession, user: AuthenticatedUser, job_context_id: uuid.UUID
) -> None:
    job_context = await get_job_context(db, user, job_context_id)
    # resume_analyses.job_context_id is ON DELETE SET NULL (0002); analyses
    # keep their target_role_snapshot for historical display.
    await db.delete(job_context)
    await db.commit()
