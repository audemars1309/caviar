"""Resume Intelligence orchestration (Phase 4).

Pipeline per analysis request:

  load resume + Phase 3 extraction (RLS-bound session) -> load optional
  job context (RLS-bound) -> build trust-bounded prompt from the
  deterministic extraction facts and the untrusted resume/job text ->
  run the structured AI task (strict validation, single bounded repair)
  -> deterministically verify evidence quotes -> persist the analysis
  and its seven category rows with backend-owned weights.

Persistence policy per AI failure class (see ai/exceptions.py):

  * ``AIConfigurationError`` - propagate (500); nothing persisted.
  * ``AIRateLimitedError`` / ``AIProviderUnavailableError`` - propagate
    (503); nothing persisted. Purely transient: no state changed, and
    recording a row per throttled attempt would only accumulate noise.
  * ``AIInvalidOutputError`` - persist a controlled failure state
    (``status=AI_ANALYSIS_FAILED``, sanitized ``failure_reason``) and
    return it. The pipeline genuinely ran and the model's output was
    unusable after the single repair; that is a real, reportable outcome.
    No fake analysis data is ever stored. Retrying is creating a new
    analysis - failed rows are immutable history.

Score ownership: ``overall_score`` remains NULL and
``scoring_algorithm_version`` holds the ``unscored`` sentinel. The AI's
category scores are stored as validated inputs; the deterministic
weighted final score is computed exclusively by the Phase 5 scoring
engine. Nothing in this module lets model output become a final score.
"""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.core.exceptions import ConflictError, NotFoundError
from app.core.security import AuthenticatedUser
from app.db.enums import AnalysisStatus, ExtractionStatus
from app.db.models.job_context import JobContext
from app.db.models.resume import Resume
from app.db.models.resume_analysis import ResumeAnalysis, ResumeAnalysisCategory
from app.db.models.resume_extraction import ResumeExtraction
from app.services.ai.client import AIRequest, StructuredAIRunner
from app.services.ai.exceptions import AIInvalidOutputError
from app.services.ai.prompts.resume_analysis import (
    ResumeAnalysisInput,
    build_resume_analysis_prompt,
)
from app.services.ai.schemas.resume_analysis import (
    RESUME_ANALYSIS_SCHEMA_VERSION,
    ResumeAnalysisOutput,
)
from app.services.ai.tasks import AITask
from app.services.resume_analysis.scoring_constants import (
    CATEGORY_WEIGHTS,
    UNSCORED_SENTINEL,
    verify_evidence_quotes,
)
from app.services.resumes.service import get_resume

logger = logging.getLogger(__name__)


class AnalysisNotFoundError(NotFoundError):
    error_code = "analysis_not_found"


class ResumeNotAnalyzableError(ConflictError):
    error_code = "resume_not_analyzable"


class JobContextNotFoundError(NotFoundError):
    error_code = "job_context_not_found"


async def _load_extraction_for_analysis(
    db: AsyncSession, resume: Resume
) -> ResumeExtraction:
    if resume.extraction_status != ExtractionStatus.EXTRACTED:
        raise ResumeNotAnalyzableError(
            "This resume has no successful text extraction to analyze.",
            details={
                "extraction_status": resume.extraction_status,
                "extraction_failure_reason": resume.extraction_failure_reason,
            },
        )
    result = await db.execute(
        select(ResumeExtraction).where(ResumeExtraction.resume_id == resume.id)
    )
    extraction = result.scalar_one_or_none()
    if extraction is None:  # defensive: status says EXTRACTED but row missing
        raise ResumeNotAnalyzableError(
            "This resume has no successful text extraction to analyze."
        )
    return extraction


async def _load_job_context(
    db: AsyncSession, user: AuthenticatedUser, job_context_id: uuid.UUID
) -> JobContext:
    result = await db.execute(
        select(JobContext).where(JobContext.id == job_context_id, JobContext.user_id == user.id)
    )
    job_context = result.scalar_one_or_none()
    if job_context is None:
        raise JobContextNotFoundError("Job context not found.")
    return job_context


def _apply_output_to_analysis(
    analysis: ResumeAnalysis, output: ResumeAnalysisOutput, resume_text: str
) -> list[ResumeAnalysisCategory]:
    analysis.status = AnalysisStatus.COMPLETED
    analysis.strengths = list(output.strengths)
    analysis.weaknesses = list(output.weaknesses)
    analysis.missing_sections = list(output.missing_content_observations)
    analysis.critical_issues = list(output.critical_issues)
    analysis.ats_observations = list(output.ats_observations)
    analysis.section_feedback = [item.model_dump() for item in output.section_feedback]
    analysis.bullet_improvements = [item.model_dump() for item in output.bullet_improvements]
    analysis.priority_improvements = list(output.priority_improvements)
    analysis.role_relevance = {
        "applicable": output.role_relevance.applicable,
        "matched_requirements": verify_evidence_quotes(
            output.role_relevance.matched_requirements, resume_text
        ),
        "missing_requirements": list(output.role_relevance.missing_requirements),
        "relevance_summary": output.role_relevance.relevance_summary,
    }
    return [
        ResumeAnalysisCategory(
            resume_analysis_id=analysis.id,
            category=assessment.category,
            score=assessment.score,
            weight=CATEGORY_WEIGHTS[assessment.category],
            evidence=verify_evidence_quotes(assessment.evidence, resume_text),
            penalties=list(assessment.penalties),
        )
        for assessment in output.categories
    ]


async def create_resume_analysis(
    *,
    db: AsyncSession,
    ai_runner: StructuredAIRunner,
    settings: Settings,
    user: AuthenticatedUser,
    resume_id: uuid.UUID,
    job_context_id: uuid.UUID | None,
) -> tuple[ResumeAnalysis, list[ResumeAnalysisCategory]]:
    resume = await get_resume(db, user, resume_id)
    extraction = await _load_extraction_for_analysis(db, resume)
    job_context = (
        await _load_job_context(db, user, job_context_id) if job_context_id else None
    )

    prompt = build_resume_analysis_prompt(
        ResumeAnalysisInput(
            normalized_resume_text=extraction.normalized_text,
            page_count=extraction.page_count,
            detected_section_types=list(extraction.detected_section_types),
            missing_section_types=list(extraction.missing_section_types),
            target_role=job_context.target_role if job_context else None,
            job_description=job_context.job_description if job_context else None,
        ),
        max_resume_chars=settings.AI_MAX_RESUME_CHARS,
        max_job_description_chars=settings.AI_MAX_JOB_DESCRIPTION_CHARS,
    )
    if prompt.resume_truncated or prompt.job_description_truncated:
        logger.info(
            "AI input truncated: resume=%s job_description=%s resume_id=%s",
            prompt.resume_truncated,
            prompt.job_description_truncated,
            resume_id,
        )

    analysis = ResumeAnalysis(
        id=uuid.uuid4(),
        resume_id=resume.id,
        user_id=user.id,
        job_context_id=job_context.id if job_context else None,
        target_role_snapshot=job_context.target_role if job_context else None,
        scoring_algorithm_version=UNSCORED_SENTINEL,
        analysis_schema_version=RESUME_ANALYSIS_SCHEMA_VERSION,
    )
    categories: list[ResumeAnalysisCategory] = []

    try:
        run_result = await ai_runner.run(
            AIRequest(
                task=AITask.RESUME_ANALYSIS,
                system_instruction=prompt.system_instruction,
                user_content=prompt.user_content,
            ),
            ResumeAnalysisOutput,
        )
    except AIInvalidOutputError:
        analysis.status = AnalysisStatus.AI_ANALYSIS_FAILED
        analysis.failure_reason = "INVALID_AI_OUTPUT"
        db.add(analysis)
        await db.commit()
        await db.refresh(analysis)
        logger.warning("Resume analysis failed (invalid AI output): analysis_id=%s", analysis.id)
        return analysis, []
    # AIConfigurationError / AIRateLimitedError / AIProviderUnavailableError
    # propagate to the API layer; nothing is persisted for transient failures.

    output = run_result.output
    assert isinstance(output, ResumeAnalysisOutput)
    analysis.ai_model = run_result.model
    categories = _apply_output_to_analysis(analysis, output, extraction.normalized_text)

    db.add(analysis)
    for category in categories:
        db.add(category)
    await db.commit()
    await db.refresh(analysis)
    for category in categories:
        await db.refresh(category)

    logger.info(
        "Resume analysis completed: analysis_id=%s model=%s duration_ms=%s repair_used=%s",
        analysis.id,
        run_result.model,
        run_result.duration_ms,
        run_result.repair_used,
    )
    return analysis, categories


async def list_resume_analyses(
    db: AsyncSession, user: AuthenticatedUser, resume_id: uuid.UUID
) -> list[ResumeAnalysis]:
    await get_resume(db, user, resume_id)  # 404 (existence-hiding) if not owned
    result = await db.execute(
        select(ResumeAnalysis)
        .where(ResumeAnalysis.resume_id == resume_id, ResumeAnalysis.user_id == user.id)
        .order_by(ResumeAnalysis.created_at.desc())
    )
    return list(result.scalars().all())


async def get_resume_analysis(
    db: AsyncSession, user: AuthenticatedUser, analysis_id: uuid.UUID
) -> tuple[ResumeAnalysis, list[ResumeAnalysisCategory]]:
    result = await db.execute(
        select(ResumeAnalysis).where(
            ResumeAnalysis.id == analysis_id, ResumeAnalysis.user_id == user.id
        )
    )
    analysis = result.scalar_one_or_none()
    if analysis is None:
        raise AnalysisNotFoundError("Resume analysis not found.")
    categories_result = await db.execute(
        select(ResumeAnalysisCategory)
        .where(ResumeAnalysisCategory.resume_analysis_id == analysis.id)
        .order_by(ResumeAnalysisCategory.category)
    )
    return analysis, list(categories_result.scalars().all())
