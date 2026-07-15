"""Resume Builder routes (Phase 6): project CRUD, structured section
upsert/delete, and content assistance. Thin wiring only; assistance is
rate limited per user (AI cost) and never persists content."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.core.rate_limit import SlidingWindowRateLimiter
from app.core.security import AuthenticatedUser, get_current_user
from app.db.rls import get_authenticated_db
from app.schemas.resume_builder import (
    AssistRequest,
    AssistType,
    BuilderProjectCreateRequest,
    BuilderProjectDetailResponse,
    BuilderProjectListResponse,
    BuilderProjectResponse,
    BuilderProjectUpdateRequest,
    BuilderSectionResponse,
    BulletsAssistResponse,
    SectionUpsertRequest,
    SummaryAssistResponse,
)
from app.services.ai.client import StructuredAIRunner, get_ai_runner
from app.services.ai.schemas.resume_builder import CONTENT_ASSIST_SCHEMA_VERSION
from app.services.resume_builder import service as builder_service
from app.services.resume_builder.section_schemas import BuilderSectionType
from app.services.resume_builder.service import AssistRequestInvalidError

router = APIRouter()

_assist_rate_limiter: SlidingWindowRateLimiter | None = None


def _get_assist_rate_limiter(
    settings: Settings = Depends(get_settings),
) -> SlidingWindowRateLimiter:
    global _assist_rate_limiter
    if _assist_rate_limiter is None:
        _assist_rate_limiter = SlidingWindowRateLimiter(
            max_events=settings.CONTENT_ASSIST_RATE_LIMIT_MAX,
            window_seconds=settings.CONTENT_ASSIST_RATE_LIMIT_WINDOW_SECONDS,
        )
    return _assist_rate_limiter


@router.post(
    "/resume-builder/projects",
    response_model=BuilderProjectResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_project(
    payload: BuilderProjectCreateRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_authenticated_db),
) -> BuilderProjectResponse:
    project = await builder_service.create_project(db, user, payload.title)
    return BuilderProjectResponse.model_validate(project)


@router.get("/resume-builder/projects", response_model=BuilderProjectListResponse)
async def list_projects(
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_authenticated_db),
) -> BuilderProjectListResponse:
    projects = await builder_service.list_projects(db, user)
    return BuilderProjectListResponse(
        projects=[BuilderProjectResponse.model_validate(item) for item in projects]
    )


@router.get(
    "/resume-builder/projects/{project_id}", response_model=BuilderProjectDetailResponse
)
async def get_project(
    project_id: uuid.UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_authenticated_db),
) -> BuilderProjectDetailResponse:
    project = await builder_service.get_project(db, user, project_id)
    sections = await builder_service.list_sections(db, user, project_id)
    return BuilderProjectDetailResponse(
        **BuilderProjectResponse.model_validate(project).model_dump(),
        sections=[BuilderSectionResponse.model_validate(item) for item in sections],
    )


@router.patch("/resume-builder/projects/{project_id}", response_model=BuilderProjectResponse)
async def update_project(
    project_id: uuid.UUID,
    payload: BuilderProjectUpdateRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_authenticated_db),
) -> BuilderProjectResponse:
    project = await builder_service.update_project(
        db, user, project_id, title=payload.title, status=payload.status
    )
    return BuilderProjectResponse.model_validate(project)


@router.delete(
    "/resume-builder/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_project(
    project_id: uuid.UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_authenticated_db),
) -> None:
    await builder_service.delete_project(db, user, project_id)


@router.put(
    "/resume-builder/projects/{project_id}/sections/{section_type}",
    response_model=BuilderSectionResponse,
)
async def upsert_section(
    project_id: uuid.UUID,
    section_type: BuilderSectionType,
    payload: SectionUpsertRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_authenticated_db),
) -> BuilderSectionResponse:
    section = await builder_service.upsert_section(
        db, user, project_id, section_type, payload.content
    )
    return BuilderSectionResponse.model_validate(section)


@router.delete(
    "/resume-builder/projects/{project_id}/sections/{section_type}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_section(
    project_id: uuid.UUID,
    section_type: BuilderSectionType,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_authenticated_db),
) -> None:
    await builder_service.delete_section(db, user, project_id, section_type)


@router.post(
    "/resume-builder/projects/{project_id}/assist",
    response_model=SummaryAssistResponse | BulletsAssistResponse,
)
async def assist(
    project_id: uuid.UUID,
    payload: AssistRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_authenticated_db),
    ai_runner: StructuredAIRunner = Depends(get_ai_runner),
    rate_limiter: SlidingWindowRateLimiter = Depends(_get_assist_rate_limiter),
) -> SummaryAssistResponse | BulletsAssistResponse:
    rate_limiter.check(user.id)
    if payload.assist_type in (AssistType.GENERATE_SUMMARY, AssistType.IMPROVE_SUMMARY):
        result = await builder_service.assist_summary(
            db=db,
            ai_runner=ai_runner,
            user=user,
            project_id=project_id,
            target_role=payload.target_role,
        )
        return SummaryAssistResponse(
            assist_type=payload.assist_type,
            schema_version=CONTENT_ASSIST_SCHEMA_VERSION,
            **result,
        )
    if payload.section_type is None or payload.entry_index is None:
        raise AssistRequestInvalidError(
            "IMPROVE_BULLETS requires section_type and entry_index."
        )
    result = await builder_service.assist_bullets(
        db=db,
        ai_runner=ai_runner,
        user=user,
        project_id=project_id,
        section_type=payload.section_type,
        entry_index=payload.entry_index,
        target_role=payload.target_role,
    )
    return BulletsAssistResponse(
        assist_type=payload.assist_type,
        schema_version=CONTENT_ASSIST_SCHEMA_VERSION,
        **result,
    )
