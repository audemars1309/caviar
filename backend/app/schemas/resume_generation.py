"""Request/response schemas for resume generation (Phase 7).

``storage_path`` is deliberately not exposed (backend detail; downloads
go through the signed-URL endpoint). Warnings are surfaced verbatim as
the structured objects the pipeline recorded.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ResumeTemplateResponse(BaseModel):
    template_id: str
    name: str
    template_version: str
    description: str
    engine: str
    ats_classification: str
    supported_sections: list[str]
    max_pages: int


class ResumeTemplateListResponse(BaseModel):
    templates: list[ResumeTemplateResponse]


class GenerationCreateRequest(BaseModel):
    template_id: str = Field(min_length=1, max_length=64)


class GenerationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    template_id: str
    template_version: str
    status: str
    page_count: int | None
    file_size_bytes: int | None
    compiler_version: str | None
    compilation_duration_ms: int | None
    warnings: list[dict[str, Any]]
    failure_category: str | None
    failure_reason: str | None
    created_at: datetime
    updated_at: datetime


class GenerationListResponse(BaseModel):
    generations: list[GenerationResponse]


class GenerationDownloadResponse(BaseModel):
    url: str
    expires_in_seconds: int
