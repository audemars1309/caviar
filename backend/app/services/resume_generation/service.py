"""Resume generation lifecycle orchestration (Phase 7).

Pipeline: PENDING -> RENDERING -> COMPILING -> VALIDATING -> UPLOADING ->
COMPLETED, or FAILED at any stage. The status is persisted at every
transition, so an interrupted process leaves an honest record of where it
stopped.

Failure taxonomy (persisted as ``failure_category`` + a sanitized
``failure_reason`` code/hint):

  TEMPLATE             unknown/unapproved template (rejected pre-row)
  RENDERING            Jinja rendering defect
  INPUT_NORMALIZATION  escaping-boundary defect (defensive; unreached
                       through validated content)
  COMPILER             COMPILER_NOT_FOUND / COMPILER_TIMEOUT /
                       COMPILER_FAILED / NO_PDF_OUTPUT / OUTPUT_TOO_LARGE
  VALIDATION           EMPTY_OUTPUT / INVALID_PDF_HEADER / UNPARSEABLE_PDF
                       / ZERO_PAGES / OUTPUT_TOO_LARGE
  STORAGE              upload failure via the Storage REST client

Recoverability: generation failure NEVER touches the structured resume
data - sections are read, not written. A failed generation row is
immutable history; retrying is POSTing a new generation. Deterministic
failures are fixed deterministically (template fix, content edit,
operator action per the category) - the pipeline never asks Gemini to
"repair" LaTeX source, and no AI participates in generation at all.

Storage: PDFs go to the private ``generated-resumes`` bucket via the
Phase 3 Storage REST client under the caller's own JWT (Storage RLS
enforced; ``storage.objects`` rows never touched), at the canonical
server-generated path ``{user_id}/{generation_id}.pdf``.
"""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.core.exceptions import ConflictError, NotFoundError
from app.core.security import AuthenticatedUser
from app.db.models.resume_builder import (
    ResumeBuilderProject,
    ResumeBuilderSection,
    ResumeGeneration,
)
from app.services.resume_builder.section_schemas import BuilderSectionType
from app.services.resume_builder.service import get_project
from app.services.resume_generation.compiler import CompilationFailedError, compile_latex
from app.services.resume_generation.pdf_validator import (
    PdfValidationError,
    validate_generated_pdf,
)
from app.services.resume_generation.renderer import (
    RenderingError,
    build_render_context,
    render_latex,
)
from app.services.resume_generation.templates_registry import get_approved_template
from app.services.resumes.service import _require_access_token
from app.services.storage.supabase_storage import StorageClient

logger = logging.getLogger(__name__)


class GenerationNotFoundError(NotFoundError):
    error_code = "generation_not_found"


class GenerationNotPossibleError(ConflictError):
    error_code = "generation_not_possible"


async def _load_sections_map(
    db: AsyncSession, project_id: uuid.UUID
) -> dict[BuilderSectionType, dict]:
    result = await db.execute(
        select(ResumeBuilderSection).where(ResumeBuilderSection.project_id == project_id)
    )
    return {
        BuilderSectionType(section.section_type): section.content
        for section in result.scalars().all()
    }


async def _set_status(db: AsyncSession, generation: ResumeGeneration, status: str) -> None:
    generation.status = status
    await db.commit()


async def _fail(
    db: AsyncSession,
    generation: ResumeGeneration,
    *,
    category: str,
    reason: str,
) -> ResumeGeneration:
    generation.status = "FAILED"
    generation.failure_category = category
    generation.failure_reason = reason[:500]
    await db.commit()
    await db.refresh(generation)
    logger.warning(
        "Resume generation failed: generation_id=%s category=%s reason=%s",
        generation.id,
        category,
        generation.failure_reason,
    )
    return generation


async def create_generation(
    *,
    db: AsyncSession,
    storage: StorageClient,
    settings: Settings,
    user: AuthenticatedUser,
    project_id: uuid.UUID,
    template_id: str,
) -> ResumeGeneration:
    access_token = _require_access_token(user)
    project = await get_project(db, user, project_id)
    template = get_approved_template(template_id)  # TEMPLATE failures reject pre-row (404)

    sections = await _load_sections_map(db, project.id)
    if BuilderSectionType.PERSONAL_INFO not in sections:
        raise GenerationNotPossibleError(
            "Add a PERSONAL_INFO section before generating - a resume needs at least "
            "a name and contact details."
        )
    if len(sections) < 2:
        raise GenerationNotPossibleError(
            "Add at least one content section (experience, education, skills, or "
            "projects) before generating."
        )

    generation = ResumeGeneration(
        id=uuid.uuid4(),
        project_id=project.id,
        template_id=template.template_id,
        template_version=template.template_version,
        status="PENDING",
    )
    db.add(generation)
    await db.commit()
    await db.refresh(generation)

    # ---- RENDERING ----------------------------------------------------
    await _set_status(db, generation, "RENDERING")
    try:
        context = build_render_context(sections, template)
        latex_source = render_latex(template, context)
    except RenderingError as exc:
        return await _fail(db, generation, category="RENDERING", reason=str(exc))
    except (UnicodeError, ValueError) as exc:
        return await _fail(
            db,
            generation,
            category="INPUT_NORMALIZATION",
            reason=f"Content normalization failed ({exc.__class__.__name__}).",
        )

    # ---- COMPILING ----------------------------------------------------
    await _set_status(db, generation, "COMPILING")
    try:
        compiled = await compile_latex(
            latex_source,
            binary_path=settings.TECTONIC_BINARY_PATH,
            timeout_seconds=settings.LATEX_COMPILE_TIMEOUT_SECONDS,
            only_cached=settings.TECTONIC_ONLY_CACHED,
            max_pdf_bytes=settings.RESUME_PDF_MAX_BYTES,
        )
    except CompilationFailedError as exc:
        return await _fail(
            db, generation, category="COMPILER", reason=f"{exc.code}: {exc.hint}"
        )
    generation.compilation_duration_ms = compiled.duration_ms
    generation.compiler_version = compiled.compiler_version
    warnings: list[dict] = []
    if compiled.unsupported_glyphs:
        warnings.append(
            {
                "code": "UNSUPPORTED_GLYPHS",
                "message": (
                    "Some characters could not be rendered by the template's font "
                    "stack and may be missing from the PDF."
                ),
                "glyphs": list(compiled.unsupported_glyphs),
            }
        )

    # ---- VALIDATING ---------------------------------------------------
    await _set_status(db, generation, "VALIDATING")
    try:
        validation = validate_generated_pdf(
            compiled.pdf_bytes,
            max_bytes=settings.RESUME_PDF_MAX_BYTES,
            max_pages=template.max_pages,
        )
    except PdfValidationError as exc:
        return await _fail(
            db, generation, category="VALIDATION", reason=f"{exc.code}: {exc.hint}"
        )
    generation.page_count = validation.page_count
    generation.file_size_bytes = validation.file_size_bytes
    warnings.extend(dict(item) for item in validation.warnings)
    generation.warnings = warnings

    # ---- UPLOADING ----------------------------------------------------
    await _set_status(db, generation, "UPLOADING")
    storage_path = f"{user.id}/{generation.id}.pdf"
    try:
        await storage.upload_object(
            bucket=settings.GENERATED_RESUMES_BUCKET,
            path=storage_path,
            content=compiled.pdf_bytes,
            content_type="application/pdf",
            access_token=access_token,
        )
    except Exception:
        return await _fail(
            db,
            generation,
            category="STORAGE",
            reason="UPLOAD_FAILED: The generated PDF could not be stored.",
        )
    generation.storage_path = storage_path

    # ---- COMPLETED ----------------------------------------------------
    generation.status = "COMPLETED"
    await db.commit()
    await db.refresh(generation)
    logger.info(
        "Resume generated: generation_id=%s template=%s@%s pages=%s bytes=%s "
        "duration_ms=%s warnings=%s",
        generation.id,
        generation.template_id,
        generation.template_version,
        generation.page_count,
        generation.file_size_bytes,
        generation.compilation_duration_ms,
        [item["code"] for item in warnings],
    )
    return generation


async def list_generations(
    db: AsyncSession, user: AuthenticatedUser, project_id: uuid.UUID
) -> list[ResumeGeneration]:
    project = await get_project(db, user, project_id)
    result = await db.execute(
        select(ResumeGeneration)
        .where(ResumeGeneration.project_id == project.id)
        .order_by(ResumeGeneration.created_at.desc())
    )
    return list(result.scalars().all())


async def get_generation(
    db: AsyncSession, user: AuthenticatedUser, generation_id: uuid.UUID
) -> ResumeGeneration:
    # One-hop ownership: the generation is reachable only through a
    # project owned by the caller (RLS enforces the same shape).
    result = await db.execute(
        select(ResumeGeneration)
        .join(ResumeBuilderProject, ResumeGeneration.project_id == ResumeBuilderProject.id)
        .where(
            ResumeGeneration.id == generation_id,
            ResumeBuilderProject.user_id == user.id,
        )
    )
    generation = result.scalar_one_or_none()
    if generation is None:
        raise GenerationNotFoundError("Resume generation not found.")
    return generation


async def create_generation_download_url(
    *,
    db: AsyncSession,
    storage: StorageClient,
    settings: Settings,
    user: AuthenticatedUser,
    generation_id: uuid.UUID,
) -> str:
    access_token = _require_access_token(user)
    generation = await get_generation(db, user, generation_id)
    if generation.status != "COMPLETED" or not generation.storage_path:
        raise GenerationNotPossibleError(
            "This generation has no downloadable PDF.",
            details={"status": generation.status},
        )
    return await storage.create_signed_url(
        bucket=settings.GENERATED_RESUMES_BUCKET,
        path=generation.storage_path,
        expires_in_seconds=settings.STORAGE_SIGNED_URL_EXPIRES_SECONDS,
        access_token=access_token,
    )
