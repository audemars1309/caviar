"""Request/response schemas for the Resume Builder API (Phase 6).

Section content in requests is accepted as a raw dict and validated by
the service against the per-type structured schema
(``section_schemas.py``) so error responses can carry precise per-field
details; responses return the normalized stored content.

Assist responses carry ``schema_version`` (the CONTENT_ASSIST output
contract version) and the deterministic ``unsupported_numbers`` warnings
computed by the backend fabrication guard.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.services.resume_builder.section_schemas import BuilderSectionType


class BuilderProjectCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)


class BuilderProjectUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    status: Literal["DRAFT", "FINALIZED"] | None = None


class BuilderSectionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    section_type: str
    sort_order: int
    content: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class BuilderProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    status: str
    created_at: datetime
    updated_at: datetime


class BuilderProjectDetailResponse(BuilderProjectResponse):
    sections: list[BuilderSectionResponse]


class BuilderProjectListResponse(BaseModel):
    projects: list[BuilderProjectResponse]


class SectionUpsertRequest(BaseModel):
    content: dict[str, Any]


class AssistType(enum.StrEnum):
    GENERATE_SUMMARY = "GENERATE_SUMMARY"
    IMPROVE_SUMMARY = "IMPROVE_SUMMARY"
    IMPROVE_BULLETS = "IMPROVE_BULLETS"


class AssistRequest(BaseModel):
    assist_type: AssistType
    # IMPROVE_BULLETS only:
    section_type: BuilderSectionType | None = None
    entry_index: int | None = Field(default=None, ge=0)
    # Optional targeting for ATS-aware wording (untrusted input; wrapped
    # in trust markers before reaching the model):
    target_role: str | None = Field(default=None, max_length=200)


class ImprovedBulletResponse(BaseModel):
    original: str
    improved: str
    changes_explained: list[str]
    missing_fact_questions: list[str]
    unsupported_numbers: list[str]


class SummaryAssistResponse(BaseModel):
    assist_type: AssistType
    schema_version: str
    ai_model: str
    improved_summary: str
    changes_explained: list[str]
    missing_fact_questions: list[str]
    action_verb_suggestions: list[str]
    unsupported_numbers: list[str]


class BulletsAssistResponse(BaseModel):
    assist_type: AssistType
    schema_version: str
    ai_model: str
    bullets: list[ImprovedBulletResponse]
    action_verb_suggestions: list[str]
