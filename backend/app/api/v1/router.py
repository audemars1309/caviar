"""Aggregates all v1 route modules into a single router mounted by
``app.main`` under the configured API prefix.

Phase 1 registered the system health routes; Phase 2 added the profile
routes (the first authenticated resource); Phase 3 adds the resume
routes. Remaining domain routers (job-contexts, resume-analyses,
resume-builder, interviews, interview-answers, interview-report) are
added by the phases that introduce those domains.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.routes import (
    health,
    job_contexts,
    profiles,
    resume_analyses,
    resume_builder,
    resume_generations,
    resumes,
)

api_router = APIRouter()
api_router.include_router(health.router, tags=["system"])
api_router.include_router(profiles.router, tags=["profiles"])
api_router.include_router(resumes.router, tags=["resumes"])
api_router.include_router(resume_analyses.router, tags=["resume-analyses"])
api_router.include_router(job_contexts.router, tags=["job-contexts"])
api_router.include_router(resume_builder.router, tags=["resume-builder"])
api_router.include_router(resume_generations.router, tags=["resume-generations"])
