"""Resume Intelligence routes (Phase 4): create analyses (the AI call),
list per resume, fetch detail with category assessments.

The creation endpoint is rate limited per user independently of the
upload limiter - AI calls are the most expensive operation in the system
and (on the free tier) the scarcest.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.core.rate_limit import SlidingWindowRateLimiter
from app.core.security import AuthenticatedUser, get_current_user
from app.db.rls import get_authenticated_db
from app.schemas.resume_analysis import (
    AnalysisCategoryResponse,
    ResumeAnalysisCreateRequest,
    ResumeAnalysisListResponse,
    ResumeAnalysisResponse,
    ResumeAnalysisSummaryResponse,
)
from app.services.ai.client import StructuredAIRunner, get_ai_runner
from app.services.resume_analysis import service as analysis_service

router = APIRouter()

_analysis_rate_limiter: SlidingWindowRateLimiter | None = None


def _get_analysis_rate_limiter(
    settings: Settings = Depends(get_settings),
) -> SlidingWindowRateLimiter:
    global _analysis_rate_limiter
    if _analysis_rate_limiter is None:
        _analysis_rate_limiter = SlidingWindowRateLimiter(
            max_events=settings.RESUME_ANALYSIS_RATE_LIMIT_MAX,
            window_seconds=settings.RESUME_ANALYSIS_RATE_LIMIT_WINDOW_SECONDS,
        )
    return _analysis_rate_limiter


def _to_detail_response(analysis, categories) -> ResumeAnalysisResponse:
    return ResumeAnalysisResponse(
        **ResumeAnalysisSummaryResponse.model_validate(analysis).model_dump(),
        strengths=analysis.strengths,
        weaknesses=analysis.weaknesses,
        missing_sections=analysis.missing_sections,
        critical_issues=analysis.critical_issues,
        ats_observations=analysis.ats_observations,
        section_feedback=analysis.section_feedback,
        bullet_improvements=analysis.bullet_improvements,
        priority_improvements=analysis.priority_improvements,
        role_relevance=analysis.role_relevance,
        categories=[AnalysisCategoryResponse.model_validate(c) for c in categories],
    )


@router.post(
    "/resumes/{resume_id}/analyses",
    response_model=ResumeAnalysisResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_resume_analysis(
    resume_id: uuid.UUID,
    payload: ResumeAnalysisCreateRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_authenticated_db),
    ai_runner: StructuredAIRunner = Depends(get_ai_runner),
    settings: Settings = Depends(get_settings),
    rate_limiter: SlidingWindowRateLimiter = Depends(_get_analysis_rate_limiter),
) -> ResumeAnalysisResponse:
    rate_limiter.check(user.id)
    analysis, categories = await analysis_service.create_resume_analysis(
        db=db,
        ai_runner=ai_runner,
        settings=settings,
        user=user,
        resume_id=resume_id,
        job_context_id=payload.job_context_id,
    )
    return _to_detail_response(analysis, categories)


@router.get("/resumes/{resume_id}/analyses", response_model=ResumeAnalysisListResponse)
async def list_resume_analyses(
    resume_id: uuid.UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_authenticated_db),
) -> ResumeAnalysisListResponse:
    analyses = await analysis_service.list_resume_analyses(db, user, resume_id)
    return ResumeAnalysisListResponse(
        analyses=[ResumeAnalysisSummaryResponse.model_validate(item) for item in analyses]
    )


@router.get("/resume-analyses/{analysis_id}", response_model=ResumeAnalysisResponse)
async def get_resume_analysis(
    analysis_id: uuid.UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_authenticated_db),
) -> ResumeAnalysisResponse:
    analysis, categories = await analysis_service.get_resume_analysis(db, user, analysis_id)
    return _to_detail_response(analysis, categories)
