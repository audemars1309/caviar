"""Response schemas for the resume domain (Phase 3).

Deliberate shape decisions:

  * ``ResumeResponse`` (list/detail/upload) carries metadata and extraction
    *status* only - never the extracted text - so listing resumes stays a
    lightweight query.
  * ``ResumeExtractionResponse`` is the heavy payload (raw + normalized
    text, parsed sections) and is served only by the dedicated extraction
    endpoint.
  * ``storage_path`` is intentionally NOT exposed in any response: it is a
    backend implementation detail. Clients download via the signed-URL
    endpoint.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class ParsedSectionResponse(BaseModel):
    section_type: str
    heading_text: str | None
    start_line: int
    end_line: int
    content: str


class ResumeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    original_filename: str
    file_size_bytes: int
    mime_type: str
    extraction_status: str
    extraction_failure_reason: str | None
    created_at: datetime
    updated_at: datetime


class ResumeListResponse(BaseModel):
    resumes: list[ResumeResponse]


class ResumeExtractionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    resume_id: uuid.UUID
    raw_text: str
    normalized_text: str
    parsed_sections: list[ParsedSectionResponse]
    contact_info: dict[str, Any]
    detected_section_types: list[str]
    missing_section_types: list[str]
    page_count: int
    char_count: int
    extraction_duration_ms: int | None
    pipeline_version: str
    created_at: datetime
    updated_at: datetime


class ResumeUploadResponse(BaseModel):
    """Upload result: resume metadata plus an extraction summary. The full
    extracted text is deliberately not included - fetch it from
    ``GET /resumes/{id}/extraction``."""

    resume: ResumeResponse
    detected_section_types: list[str]
    missing_section_types: list[str]
    page_count: int | None


class ResumeDownloadResponse(BaseModel):
    url: str
    expires_in_seconds: int
