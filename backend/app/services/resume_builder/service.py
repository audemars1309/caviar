"""Resume Builder orchestration (Phase 6).

Two cleanly separated responsibilities:

  * STRUCTURED STORAGE - project and section CRUD. Every section content
    document is validated against its per-type schema before persistence;
    exactly one section per type per project (DB-enforced, migration
    0008); sort_order comes from the canonical constant, never the client.
  * CONTENT ASSISTANCE - Gemini-backed suggestions through the Phase 4
    centralized AI architecture (same runner, routing, single bounded
    repair, typed failures). Assistance is ADVISORY AND PERSISTENCE-FREE:
    it returns suggestions plus deterministic fabrication-guard warnings;
    content changes happen only through the user's explicit section
    upsert. This boundary is what makes "AI never writes facts the user
    didn't state" enforceable - the user is always the write path.

Ownership: RLS-bound sessions plus explicit user filters throughout;
sections are reached only through their owned project (one-hop, matching
the RLS policy shape).
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationFailedError
from app.core.security import AuthenticatedUser
from app.db.models.resume_builder import ResumeBuilderProject, ResumeBuilderSection
from app.services.ai.client import AIRequest, StructuredAIRunner
from app.services.ai.prompts.resume_builder import (
    build_bullets_assist_prompt,
    build_summary_assist_prompt,
)
from app.services.ai.schemas.resume_builder import (
    ImprovedBulletsOutput,
    ImprovedSummaryOutput,
)
from app.services.ai.tasks import AITask
from app.services.resume_builder.fabrication_guard import (
    find_unsupported_numbers,
    source_numbers_from_content,
)
from app.services.resume_builder.section_schemas import (
    BULLET_SECTION_TYPES,
    SECTION_SORT_ORDER,
    BuilderSectionType,
    validate_section_content,
)

logger = logging.getLogger(__name__)


class BuilderProjectNotFoundError(NotFoundError):
    error_code = "builder_project_not_found"


class BuilderSectionNotFoundError(NotFoundError):
    error_code = "builder_section_not_found"


class InvalidSectionContentError(ValidationFailedError):
    error_code = "invalid_section_content"


class AssistRequestInvalidError(ValidationFailedError):
    error_code = "assist_request_invalid"


# ----------------------------------------------------------------- CRUD


async def create_project(
    db: AsyncSession, user: AuthenticatedUser, title: str
) -> ResumeBuilderProject:
    project = ResumeBuilderProject(user_id=user.id, title=title.strip())
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return project


async def list_projects(
    db: AsyncSession, user: AuthenticatedUser
) -> list[ResumeBuilderProject]:
    result = await db.execute(
        select(ResumeBuilderProject)
        .where(ResumeBuilderProject.user_id == user.id)
        .order_by(ResumeBuilderProject.created_at.desc())
    )
    return list(result.scalars().all())


async def get_project(
    db: AsyncSession, user: AuthenticatedUser, project_id: uuid.UUID
) -> ResumeBuilderProject:
    result = await db.execute(
        select(ResumeBuilderProject).where(
            ResumeBuilderProject.id == project_id, ResumeBuilderProject.user_id == user.id
        )
    )
    project = result.scalar_one_or_none()
    if project is None:
        raise BuilderProjectNotFoundError("Resume builder project not found.")
    return project


async def update_project(
    db: AsyncSession,
    user: AuthenticatedUser,
    project_id: uuid.UUID,
    *,
    title: str | None,
    status: str | None,
) -> ResumeBuilderProject:
    project = await get_project(db, user, project_id)
    if title is not None:
        project.title = title.strip()
    if status is not None:
        project.status = status
    await db.commit()
    await db.refresh(project)
    return project


async def delete_project(
    db: AsyncSession, user: AuthenticatedUser, project_id: uuid.UUID
) -> None:
    project = await get_project(db, user, project_id)
    await db.delete(project)  # sections and generations cascade
    await db.commit()


async def list_sections(
    db: AsyncSession, user: AuthenticatedUser, project_id: uuid.UUID
) -> list[ResumeBuilderSection]:
    project = await get_project(db, user, project_id)
    result = await db.execute(
        select(ResumeBuilderSection)
        .where(ResumeBuilderSection.project_id == project.id)
        .order_by(ResumeBuilderSection.sort_order)
    )
    return list(result.scalars().all())


async def _get_section(
    db: AsyncSession, project_id: uuid.UUID, section_type: BuilderSectionType
) -> ResumeBuilderSection | None:
    result = await db.execute(
        select(ResumeBuilderSection).where(
            ResumeBuilderSection.project_id == project_id,
            ResumeBuilderSection.section_type == section_type,
        )
    )
    return result.scalar_one_or_none()


async def upsert_section(
    db: AsyncSession,
    user: AuthenticatedUser,
    project_id: uuid.UUID,
    section_type: BuilderSectionType,
    content: dict[str, Any],
) -> ResumeBuilderSection:
    project = await get_project(db, user, project_id)
    try:
        normalized = validate_section_content(section_type, content)
    except ValidationError as exc:
        raise InvalidSectionContentError(
            f"Content does not match the {section_type} section schema.",
            details={
                "errors": [
                    {
                        "field": ".".join(str(loc) for loc in error["loc"]),
                        "message": error["msg"],
                    }
                    for error in exc.errors()
                ]
            },
        ) from exc

    section = await _get_section(db, project.id, section_type)
    if section is None:
        section = ResumeBuilderSection(
            project_id=project.id,
            section_type=section_type,
            sort_order=SECTION_SORT_ORDER[section_type],
            content=normalized,
        )
        db.add(section)
    else:
        section.content = normalized
    await db.commit()
    await db.refresh(section)
    return section


async def delete_section(
    db: AsyncSession,
    user: AuthenticatedUser,
    project_id: uuid.UUID,
    section_type: BuilderSectionType,
) -> None:
    project = await get_project(db, user, project_id)
    section = await _get_section(db, project.id, section_type)
    if section is None:
        raise BuilderSectionNotFoundError("This project has no such section.")
    await db.delete(section)
    await db.commit()


# ------------------------------------------------------ content assistance


def _sections_as_content_map(
    sections: list[ResumeBuilderSection],
) -> dict[str, dict[str, Any]]:
    return {section.section_type: section.content for section in sections}


async def assist_summary(
    *,
    db: AsyncSession,
    ai_runner: StructuredAIRunner,
    user: AuthenticatedUser,
    project_id: uuid.UUID,
    target_role: str | None,
) -> dict[str, Any]:
    sections = await list_sections(db, user, project_id)
    content_map = _sections_as_content_map(sections)
    substantive = {
        key: value for key, value in content_map.items() if key != BuilderSectionType.SUMMARY
    }
    if not substantive:
        raise AssistRequestInvalidError(
            "Add resume content (experience, education, skills, or projects) before "
            "requesting a summary - there are no facts to ground it in."
        )
    existing_summary = (content_map.get(BuilderSectionType.SUMMARY) or {}).get("text")

    prompt = build_summary_assist_prompt(
        existing_summary=existing_summary,
        resume_content=substantive,
        target_role=target_role,
    )
    run_result = await ai_runner.run(
        AIRequest(
            task=AITask.CONTENT_ASSIST,
            system_instruction=prompt.system_instruction,
            user_content=prompt.user_content,
        ),
        ImprovedSummaryOutput,
    )
    output = run_result.output
    assert isinstance(output, ImprovedSummaryOutput)

    source_numbers = source_numbers_from_content(
        {"content": substantive, "existing_summary": existing_summary or ""}
    )
    logger.info(
        "Content assist completed: kind=summary project_id=%s model=%s duration_ms=%s",
        project_id,
        run_result.model,
        run_result.duration_ms,
    )
    return {
        "improved_summary": output.improved_summary,
        "changes_explained": output.changes_explained,
        "missing_fact_questions": output.missing_fact_questions,
        "action_verb_suggestions": output.action_verb_suggestions,
        "unsupported_numbers": find_unsupported_numbers(
            output.improved_summary, source_numbers
        ),
        "ai_model": run_result.model,
    }


async def assist_bullets(
    *,
    db: AsyncSession,
    ai_runner: StructuredAIRunner,
    user: AuthenticatedUser,
    project_id: uuid.UUID,
    section_type: BuilderSectionType,
    entry_index: int,
    target_role: str | None,
) -> dict[str, Any]:
    if section_type not in BULLET_SECTION_TYPES:
        raise AssistRequestInvalidError(
            "Bullet improvement is available for EXPERIENCE, INTERNSHIPS, and "
            "PROJECTS sections only."
        )
    project = await get_project(db, user, project_id)
    section = await _get_section(db, project.id, section_type)
    if section is None:
        raise BuilderSectionNotFoundError("This project has no such section.")
    entries = section.content.get("entries", [])
    if not 0 <= entry_index < len(entries):
        raise AssistRequestInvalidError(
            f"entry_index {entry_index} is out of range for this section "
            f"({len(entries)} entries)."
        )
    entry = entries[entry_index]
    bullets = entry.get("bullets", [])
    if not bullets:
        raise AssistRequestInvalidError(
            "This entry has no bullets to improve - add bullet points first."
        )

    entry_context = {key: value for key, value in entry.items() if key != "bullets"}
    prompt = build_bullets_assist_prompt(
        section_type=section_type,
        entry_context=entry_context,
        bullets=bullets,
        target_role=target_role,
    )
    run_result = await ai_runner.run(
        AIRequest(
            task=AITask.CONTENT_ASSIST,
            system_instruction=prompt.system_instruction,
            user_content=prompt.user_content,
        ),
        ImprovedBulletsOutput,
    )
    output = run_result.output
    assert isinstance(output, ImprovedBulletsOutput)

    source_numbers = source_numbers_from_content(entry)
    improved_bullets = [
        {
            "original": bullet.original,
            "improved": bullet.improved,
            "changes_explained": bullet.changes_explained,
            "missing_fact_questions": bullet.missing_fact_questions,
            "unsupported_numbers": find_unsupported_numbers(bullet.improved, source_numbers),
        }
        for bullet in output.bullets
    ]
    logger.info(
        "Content assist completed: kind=bullets project_id=%s section=%s model=%s "
        "duration_ms=%s",
        project_id,
        section_type,
        run_result.model,
        run_result.duration_ms,
    )
    return {
        "bullets": improved_bullets,
        "action_verb_suggestions": output.action_verb_suggestions,
        "ai_model": run_result.model,
    }
