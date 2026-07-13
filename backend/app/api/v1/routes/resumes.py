"""Resume routes (Phase 3): upload, list, detail, extraction, extraction
retry, signed download URL, delete.

Routes contain no business logic - they wire dependencies (verified user,
RLS-bound DB session, storage client, settings), apply the upload rate
limit, and translate service results into response schemas. All error
translation is centralized in ``app.core.exceptions``.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.core.rate_limit import SlidingWindowRateLimiter
from app.core.security import AuthenticatedUser, get_current_user
from app.db.rls import get_authenticated_db
from app.schemas.resume import (
    ResumeDownloadResponse,
    ResumeExtractionResponse,
    ResumeListResponse,
    ResumeResponse,
    ResumeUploadResponse,
)
from app.services.resumes import service as resume_service
from app.services.resumes.validation import read_upload_bounded
from app.services.storage.supabase_storage import StorageClient, get_storage_client

router = APIRouter()

_upload_rate_limiter: SlidingWindowRateLimiter | None = None


def _get_upload_rate_limiter(
    settings: Settings = Depends(get_settings),
) -> SlidingWindowRateLimiter:
    # Lazily constructed from settings on first use; module import must not
    # trigger settings resolution.
    global _upload_rate_limiter
    if _upload_rate_limiter is None:
        _upload_rate_limiter = SlidingWindowRateLimiter(
            max_events=settings.RESUME_UPLOAD_RATE_LIMIT_MAX,
            window_seconds=settings.RESUME_UPLOAD_RATE_LIMIT_WINDOW_SECONDS,
        )
    return _upload_rate_limiter


@router.post(
    "/resumes",
    response_model=ResumeUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_resume(
    file: UploadFile = File(...),
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_authenticated_db),
    storage: StorageClient = Depends(get_storage_client),
    settings: Settings = Depends(get_settings),
    rate_limiter: SlidingWindowRateLimiter = Depends(_get_upload_rate_limiter),
) -> ResumeUploadResponse:
    rate_limiter.check(user.id)
    content = await read_upload_bounded(file, settings.RESUME_MAX_FILE_SIZE_BYTES)
    resume, extraction = await resume_service.upload_resume(
        db=db,
        storage=storage,
        settings=settings,
        user=user,
        content=content,
        original_filename=file.filename,
        declared_content_type=file.content_type,
    )
    return ResumeUploadResponse(
        resume=ResumeResponse.model_validate(resume),
        detected_section_types=list(extraction.detected_section_types) if extraction else [],
        missing_section_types=list(extraction.missing_section_types) if extraction else [],
        page_count=extraction.page_count if extraction else None,
    )


@router.get("/resumes", response_model=ResumeListResponse)
async def list_resumes(
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_authenticated_db),
) -> ResumeListResponse:
    resumes = await resume_service.list_resumes(db, user)
    return ResumeListResponse(
        resumes=[ResumeResponse.model_validate(resume) for resume in resumes]
    )


@router.get("/resumes/{resume_id}", response_model=ResumeResponse)
async def get_resume(
    resume_id: uuid.UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_authenticated_db),
) -> ResumeResponse:
    resume = await resume_service.get_resume(db, user, resume_id)
    return ResumeResponse.model_validate(resume)


@router.get("/resumes/{resume_id}/extraction", response_model=ResumeExtractionResponse)
async def get_resume_extraction(
    resume_id: uuid.UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_authenticated_db),
) -> ResumeExtractionResponse:
    extraction = await resume_service.get_extraction(db, user, resume_id)
    return ResumeExtractionResponse.model_validate(extraction)


@router.post("/resumes/{resume_id}/extraction/retry", response_model=ResumeUploadResponse)
async def retry_resume_extraction(
    resume_id: uuid.UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_authenticated_db),
    storage: StorageClient = Depends(get_storage_client),
    settings: Settings = Depends(get_settings),
) -> ResumeUploadResponse:
    resume, extraction = await resume_service.retry_extraction(
        db=db, storage=storage, settings=settings, user=user, resume_id=resume_id
    )
    return ResumeUploadResponse(
        resume=ResumeResponse.model_validate(resume),
        detected_section_types=list(extraction.detected_section_types) if extraction else [],
        missing_section_types=list(extraction.missing_section_types) if extraction else [],
        page_count=extraction.page_count if extraction else None,
    )


@router.get("/resumes/{resume_id}/download", response_model=ResumeDownloadResponse)
async def download_resume(
    resume_id: uuid.UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_authenticated_db),
    storage: StorageClient = Depends(get_storage_client),
    settings: Settings = Depends(get_settings),
) -> ResumeDownloadResponse:
    url = await resume_service.create_download_url(
        db=db, storage=storage, settings=settings, user=user, resume_id=resume_id
    )
    return ResumeDownloadResponse(
        url=url, expires_in_seconds=settings.STORAGE_SIGNED_URL_EXPIRES_SECONDS
    )


@router.delete("/resumes/{resume_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_resume(
    resume_id: uuid.UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_authenticated_db),
    storage: StorageClient = Depends(get_storage_client),
    settings: Settings = Depends(get_settings),
) -> None:
    await resume_service.delete_resume(
        db=db, storage=storage, settings=settings, user=user, resume_id=resume_id
    )
