"""Request/response schemas for job contexts and resume analyses (Phase 4).

Response shape decisions:

  * ``ResumeAnalysisResponse`` (detail) carries the full validated AI
    output groups plus per-category rows; the list endpoint returns
    ``ResumeAnalysisSummaryResponse`` without the heavy JSONB payloads.
  * ``overall_score`` is present and null in Phase 4 responses - it is
    populated only by the Phase 5 deterministic scoring engine. Exposing
    the field now keeps the response contract stable across phases.
  * Evidence items include the backend-computed ``verified`` flag so the
    frontend can visually separate verified extracted facts from
    unverified AI claims.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class JobContextCreateRequest(BaseModel):
    target_role: str = Field(min_length=2, max_length=200)
    company_name: str | None = Field(default=None, max_length=200)
    job_description: str | None = Field(default=None, max_length=50_000)


class JobContextResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    target_role: str
    company_name: str | None
    job_description: str | None
    created_at: datetime
    updated_at: datetime


class JobContextListResponse(BaseModel):
    job_contexts: list[JobContextResponse]


class ResumeAnalysisCreateRequest(BaseModel):
    job_context_id: uuid.UUID | None = None


class AnalysisCategoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    category: str
    score: int | None  # raw validated AI assessment (scoring input)
    weight: float
    evidence: list[dict[str, Any]]
    penalties: list[str]
    # Deterministic engine output (Phase 5): None when non-applicable.
    adjusted_score: int | None
    adjustments: list[dict[str, Any]]


class ResumeAnalysisSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    resume_id: uuid.UUID
    job_context_id: uuid.UUID | None
    target_role_snapshot: str | None
    status: str
    overall_score: int | None
    scoring_algorithm_version: str
    analysis_schema_version: str | None
    ai_model: str | None
    failure_reason: str | None
    created_at: datetime
    updated_at: datetime


class ResumeAnalysisResponse(ResumeAnalysisSummaryResponse):
    strengths: list[str] | None
    weaknesses: list[str] | None
    missing_sections: list[str] | None
    critical_issues: list[str] | None
    ats_observations: list[str] | None
    section_feedback: list[dict[str, Any]] | None
    bullet_improvements: list[dict[str, Any]] | None
    priority_improvements: list[str] | None
    role_relevance: dict[str, Any] | None
    categories: list[AnalysisCategoryResponse]


class ResumeAnalysisListResponse(BaseModel):
    analyses: list[ResumeAnalysisSummaryResponse]
