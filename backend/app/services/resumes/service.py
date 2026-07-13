"""Resume domain orchestration (Phase 3).

Owns the upload pipeline mandated by the master spec, in this exact order:

  authenticate (route dependency) -> validate file -> structural PDF
  validation + text extraction (in memory) -> upload to Supabase Storage
  via the Storage REST API -> persist resume + extraction rows -> return
  structured results.

Pipeline-order rationale:

  * Structural validation and extraction run BEFORE the storage upload, so
    junk bytes are rejected without ever being stored, and a valid file is
    read exactly once (no post-upload re-download).
  * A structurally valid PDF with no text layer (scanned resume) is still
    stored - the user's file is preserved, the resume is marked
    ``FAILED / NO_TEXT_LAYER``, and extraction is retryable (a future OCR
    path can succeed where this one cannot).
  * Storage upload happens before the DB insert; if the insert then fails,
    the uploaded object is deleted best-effort so storage does not
    accumulate orphans. The opposite order would be worse: a DB row
    pointing at a nonexistent object is user-visible breakage, while an
    orphaned object is invisible cost.

Ownership: every function takes the ``AuthenticatedUser`` derived from the
verified JWT. Database access goes through the RLS-bound session
(``get_authenticated_db``), so even these first-party queries cannot cross
user boundaries; storage access forwards the caller's own JWT so Storage
RLS applies equally. Storage paths are always the canonical
``{user_id}/{resume_id}.pdf`` - server-generated, never client input.
"""

from __future__ import annotations

import logging
import time
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.core.exceptions import AuthenticationError, ConflictError, NotFoundError
from app.core.security import AuthenticatedUser
from app.db.enums import ExtractionStatus
from app.db.models.resume import Resume
from app.db.models.resume_extraction import ResumeExtraction
from app.services.resume_extraction.normalizer import normalize_text
from app.services.resume_extraction.pdf_extractor import (
    PdfExtractionResult,
    PdfNoTextError,
    extract_pdf_text,
)
from app.services.resume_extraction.section_parser import PIPELINE_VERSION, parse_sections
from app.services.resumes.validation import sanitize_filename, validate_resume_upload
from app.services.storage.supabase_storage import StorageClient, StorageObjectNotFoundError

logger = logging.getLogger(__name__)

_STORED_MIME_TYPE = "application/pdf"


class ResumeNotFoundError(NotFoundError):
    error_code = "resume_not_found"


class ExtractionNotAvailableError(NotFoundError):
    error_code = "extraction_not_available"


class ExtractionNotRetryableError(ConflictError):
    error_code = "extraction_not_retryable"


def _require_access_token(user: AuthenticatedUser) -> str:
    if not user.access_token:
        # Cannot occur through get_current_user; guards direct/incorrect
        # service invocation.
        raise AuthenticationError("Missing credentials for storage access.")
    return user.access_token


def _storage_path(user_id: uuid.UUID, resume_id: uuid.UUID) -> str:
    return f"{user_id}/{resume_id}.pdf"


def _build_extraction_row(
    resume_id: uuid.UUID, extraction: PdfExtractionResult, duration_ms: int
) -> ResumeExtraction:
    normalized = normalize_text(extraction.raw_text)
    parse_result = parse_sections(normalized)
    return ResumeExtraction(
        resume_id=resume_id,
        raw_text=extraction.raw_text,
        normalized_text=normalized,
        parsed_sections=[section.to_dict() for section in parse_result.sections],
        contact_info=parse_result.contact_info,
        detected_section_types=list(parse_result.detected_section_types),
        missing_section_types=list(parse_result.missing_section_types),
        page_count=extraction.page_count,
        char_count=len(normalized),
        extraction_duration_ms=duration_ms,
        pipeline_version=PIPELINE_VERSION,
    )


async def upload_resume(
    *,
    db: AsyncSession,
    storage: StorageClient,
    settings: Settings,
    user: AuthenticatedUser,
    content: bytes,
    original_filename: str | None,
    declared_content_type: str | None,
) -> tuple[Resume, ResumeExtraction | None]:
    """Run the full upload pipeline. Returns the persisted resume and, on
    successful extraction, its extraction row (None when the file was
    stored but had no extractable text)."""
    access_token = _require_access_token(user)
    filename = sanitize_filename(original_filename)
    validate_resume_upload(
        content=content, filename=filename, declared_content_type=declared_content_type
    )

    # Structural validation + extraction, in memory, before any side effect.
    started = time.monotonic()
    extraction_result: PdfExtractionResult | None
    try:
        extraction_result = await extract_pdf_text(
            content, max_page_count=settings.RESUME_MAX_PAGE_COUNT
        )
    except PdfNoTextError:
        extraction_result = None  # valid PDF, no text layer - store anyway
    duration_ms = int((time.monotonic() - started) * 1000)

    resume_id = uuid.uuid4()
    path = _storage_path(user.id, resume_id)

    await storage.upload_object(
        bucket=settings.RESUMES_BUCKET,
        path=path,
        content=content,
        content_type=_STORED_MIME_TYPE,
        access_token=access_token,
    )

    resume = Resume(
        id=resume_id,
        user_id=user.id,
        storage_path=path,
        original_filename=filename,
        file_size_bytes=len(content),
        mime_type=_STORED_MIME_TYPE,
        extraction_status=(
            ExtractionStatus.EXTRACTED if extraction_result else ExtractionStatus.FAILED
        ),
        extraction_failure_reason=None if extraction_result else PdfNoTextError.reason,
    )
    extraction_row: ResumeExtraction | None = None

    try:
        db.add(resume)
        if extraction_result is not None:
            extraction_row = _build_extraction_row(resume_id, extraction_result, duration_ms)
            db.add(extraction_row)
        await db.commit()
    except Exception:
        await db.rollback()
        # Best-effort orphan cleanup; the original failure is what matters.
        try:
            await storage.delete_object(
                bucket=settings.RESUMES_BUCKET, path=path, access_token=access_token
            )
        except Exception:
            logger.warning("Orphan cleanup failed for a stored object after DB failure.")
        raise

    await db.refresh(resume)
    if extraction_row is not None:
        await db.refresh(extraction_row)
    logger.info(
        "Resume uploaded: resume_id=%s status=%s pages=%s duration_ms=%s pipeline=%s",
        resume_id,
        resume.extraction_status,
        extraction_result.page_count if extraction_result else None,
        duration_ms,
        PIPELINE_VERSION,
    )
    return resume, extraction_row


async def list_resumes(db: AsyncSession, user: AuthenticatedUser) -> list[Resume]:
    result = await db.execute(
        select(Resume)
        .where(Resume.user_id == user.id)  # explicit filter; RLS enforces it regardless
        .order_by(Resume.created_at.desc())
    )
    return list(result.scalars().all())


async def get_resume(db: AsyncSession, user: AuthenticatedUser, resume_id: uuid.UUID) -> Resume:
    result = await db.execute(
        select(Resume).where(Resume.id == resume_id, Resume.user_id == user.id)
    )
    resume = result.scalar_one_or_none()
    if resume is None:
        # RLS makes another user's resume indistinguishable from a
        # nonexistent one - deliberately, so ids don't leak existence.
        raise ResumeNotFoundError("Resume not found.")
    return resume


async def get_extraction(
    db: AsyncSession, user: AuthenticatedUser, resume_id: uuid.UUID
) -> ResumeExtraction:
    resume = await get_resume(db, user, resume_id)
    result = await db.execute(
        select(ResumeExtraction).where(ResumeExtraction.resume_id == resume.id)
    )
    extraction = result.scalar_one_or_none()
    if extraction is None:
        raise ExtractionNotAvailableError(
            "No extraction is available for this resume.",
            details={
                "extraction_status": resume.extraction_status,
                "extraction_failure_reason": resume.extraction_failure_reason,
            },
        )
    return extraction


async def retry_extraction(
    *,
    db: AsyncSession,
    storage: StorageClient,
    settings: Settings,
    user: AuthenticatedUser,
    resume_id: uuid.UUID,
) -> tuple[Resume, ResumeExtraction | None]:
    """Re-run the extraction pipeline for an already-stored resume by
    re-downloading its bytes from Storage. Allowed only for resumes whose
    extraction previously FAILED (or is inexplicably PENDING); re-running a
    successful extraction would silently rewrite analysis inputs."""
    access_token = _require_access_token(user)
    resume = await get_resume(db, user, resume_id)
    if resume.extraction_status == ExtractionStatus.EXTRACTED:
        raise ExtractionNotRetryableError(
            "Extraction already succeeded for this resume.",
            details={"extraction_status": resume.extraction_status},
        )

    try:
        content = await storage.download_object(
            bucket=settings.RESUMES_BUCKET, path=resume.storage_path, access_token=access_token
        )
    except StorageObjectNotFoundError:
        raise ExtractionNotRetryableError(
            "The stored file for this resume is no longer available."
        ) from None

    started = time.monotonic()
    try:
        extraction_result = await extract_pdf_text(
            content, max_page_count=settings.RESUME_MAX_PAGE_COUNT
        )
    except PdfNoTextError:
        resume.extraction_status = ExtractionStatus.FAILED
        resume.extraction_failure_reason = PdfNoTextError.reason
        await db.commit()
        await db.refresh(resume)
        return resume, None
    duration_ms = int((time.monotonic() - started) * 1000)

    extraction_row = _build_extraction_row(resume.id, extraction_result, duration_ms)
    resume.extraction_status = ExtractionStatus.EXTRACTED
    resume.extraction_failure_reason = None
    db.add(extraction_row)
    await db.commit()
    await db.refresh(resume)
    await db.refresh(extraction_row)
    logger.info(
        "Resume extraction retried: resume_id=%s status=%s duration_ms=%s pipeline=%s",
        resume.id,
        resume.extraction_status,
        duration_ms,
        PIPELINE_VERSION,
    )
    return resume, extraction_row


async def create_download_url(
    *,
    db: AsyncSession,
    storage: StorageClient,
    settings: Settings,
    user: AuthenticatedUser,
    resume_id: uuid.UUID,
) -> str:
    access_token = _require_access_token(user)
    resume = await get_resume(db, user, resume_id)
    return await storage.create_signed_url(
        bucket=settings.RESUMES_BUCKET,
        path=resume.storage_path,
        expires_in_seconds=settings.STORAGE_SIGNED_URL_EXPIRES_SECONDS,
        access_token=access_token,
    )


async def delete_resume(
    *,
    db: AsyncSession,
    storage: StorageClient,
    settings: Settings,
    user: AuthenticatedUser,
    resume_id: uuid.UUID,
) -> None:
    """Delete the stored object first, then the row (the extraction row
    cascades). A missing object is tolerated so a half-deleted resume can
    always be fully removed."""
    access_token = _require_access_token(user)
    resume = await get_resume(db, user, resume_id)
    await storage.delete_object(
        bucket=settings.RESUMES_BUCKET, path=resume.storage_path, access_token=access_token
    )
    await db.delete(resume)
    await db.commit()
    logger.info("Resume deleted: resume_id=%s", resume_id)
