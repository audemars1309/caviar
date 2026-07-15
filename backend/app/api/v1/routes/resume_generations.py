"""Resume generation routes (Phase 7): approved-template listing,
generation creation (the compile pipeline; rate limited), listing,
detail, and signed-URL download. Thin wiring only."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.core.rate_limit import SlidingWindowRateLimiter
from app.core.security import AuthenticatedUser, get_current_user
from app.db.rls import get_authenticated_db
from app.schemas.resume_generation import (
    GenerationCreateRequest,
    GenerationDownloadResponse,
    GenerationListResponse,
    GenerationResponse,
    ResumeTemplateListResponse,
    ResumeTemplateResponse,
)
from app.services.resume_generation import service as generation_service
from app.services.resume_generation.templates_registry import list_approved_templates
from app.services.storage.supabase_storage import StorageClient, get_storage_client

router = APIRouter()

_generation_rate_limiter: SlidingWindowRateLimiter | None = None


def _get_generation_rate_limiter(
    settings: Settings = Depends(get_settings),
) -> SlidingWindowRateLimiter:
    global _generation_rate_limiter
    if _generation_rate_limiter is None:
        _generation_rate_limiter = SlidingWindowRateLimiter(
            max_events=settings.GENERATION_RATE_LIMIT_MAX,
            window_seconds=settings.GENERATION_RATE_LIMIT_WINDOW_SECONDS,
        )
    return _generation_rate_limiter


@router.get("/resume-templates", response_model=ResumeTemplateListResponse)
async def list_templates(
    user: AuthenticatedUser = Depends(get_current_user),
) -> ResumeTemplateListResponse:
    return ResumeTemplateListResponse(
        templates=[
            ResumeTemplateResponse(
                template_id=item.template_id,
                name=item.name,
                template_version=item.template_version,
                description=item.description,
                engine=item.engine,
                ats_classification=item.ats_classification,
                supported_sections=item.supported_sections,
                max_pages=item.max_pages,
            )
            for item in list_approved_templates()
        ]
    )


@router.post(
    "/resume-builder/projects/{project_id}/generations",
    response_model=GenerationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_generation(
    project_id: uuid.UUID,
    payload: GenerationCreateRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_authenticated_db),
    storage: StorageClient = Depends(get_storage_client),
    settings: Settings = Depends(get_settings),
    rate_limiter: SlidingWindowRateLimiter = Depends(_get_generation_rate_limiter),
) -> GenerationResponse:
    rate_limiter.check(user.id)
    generation = await generation_service.create_generation(
        db=db,
        storage=storage,
        settings=settings,
        user=user,
        project_id=project_id,
        template_id=payload.template_id,
    )
    return GenerationResponse.model_validate(generation)


@router.get(
    "/resume-builder/projects/{project_id}/generations",
    response_model=GenerationListResponse,
)
async def list_generations(
    project_id: uuid.UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_authenticated_db),
) -> GenerationListResponse:
    generations = await generation_service.list_generations(db, user, project_id)
    return GenerationListResponse(
        generations=[GenerationResponse.model_validate(item) for item in generations]
    )


@router.get("/resume-generations/{generation_id}", response_model=GenerationResponse)
async def get_generation(
    generation_id: uuid.UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_authenticated_db),
) -> GenerationResponse:
    generation = await generation_service.get_generation(db, user, generation_id)
    return GenerationResponse.model_validate(generation)


@router.get(
    "/resume-generations/{generation_id}/download",
    response_model=GenerationDownloadResponse,
)
async def download_generation(
    generation_id: uuid.UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_authenticated_db),
    storage: StorageClient = Depends(get_storage_client),
    settings: Settings = Depends(get_settings),
) -> GenerationDownloadResponse:
    url = await generation_service.create_generation_download_url(
        db=db, storage=storage, settings=settings, user=user, generation_id=generation_id
    )
    return GenerationDownloadResponse(
        url=url, expires_in_seconds=settings.STORAGE_SIGNED_URL_EXPIRES_SECONDS
    )
