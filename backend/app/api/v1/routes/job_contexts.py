"""Job context routes (Phase 4). Thin wiring only; RLS-bound sessions and
verified identity throughout."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import AuthenticatedUser, get_current_user
from app.db.rls import get_authenticated_db
from app.schemas.resume_analysis import (
    JobContextCreateRequest,
    JobContextListResponse,
    JobContextResponse,
)
from app.services.job_contexts import service as job_context_service

router = APIRouter()


@router.post(
    "/job-contexts", response_model=JobContextResponse, status_code=status.HTTP_201_CREATED
)
async def create_job_context(
    payload: JobContextCreateRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_authenticated_db),
) -> JobContextResponse:
    job_context = await job_context_service.create_job_context(
        db=db,
        user=user,
        target_role=payload.target_role,
        company_name=payload.company_name,
        job_description=payload.job_description,
    )
    return JobContextResponse.model_validate(job_context)


@router.get("/job-contexts", response_model=JobContextListResponse)
async def list_job_contexts(
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_authenticated_db),
) -> JobContextListResponse:
    job_contexts = await job_context_service.list_job_contexts(db, user)
    return JobContextListResponse(
        job_contexts=[JobContextResponse.model_validate(item) for item in job_contexts]
    )


@router.get("/job-contexts/{job_context_id}", response_model=JobContextResponse)
async def get_job_context(
    job_context_id: uuid.UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_authenticated_db),
) -> JobContextResponse:
    job_context = await job_context_service.get_job_context(db, user, job_context_id)
    return JobContextResponse.model_validate(job_context)


@router.delete("/job-contexts/{job_context_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_job_context(
    job_context_id: uuid.UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_authenticated_db),
) -> None:
    await job_context_service.delete_job_context(db, user, job_context_id)
