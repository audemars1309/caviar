"""Aggregates all v1 route modules into a single router mounted by
``app.main`` under the configured API prefix.

Phase 1 registered the system health routes; Phase 2 adds the profile
routes (the first authenticated resource). Remaining domain routers
(job-contexts, resumes, resume-analyses, resume-builder, interviews,
interview-answers, interview-report) are added by the phases that
introduce those domains.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.routes import health, profiles

api_router = APIRouter()
api_router.include_router(health.router, tags=["system"])
api_router.include_router(profiles.router, tags=["profiles"])
