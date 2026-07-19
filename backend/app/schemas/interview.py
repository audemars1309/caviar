"""Request/response schemas for the Interview Intelligence API (Phase 8).

The answer-cycle response deliberately excludes numeric evaluation
scores: during a live interview the candidate sees the professional
``interviewer_observation`` and flow state only; full scoring arrives in
the final report. Raw AI reasoning never exists anywhere to expose.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.services.interview.enums import Difficulty, InterviewType


class InterviewCreateRequest(BaseModel):
    resume_id: uuid.UUID
    job_context_id: uuid.UUID | None = None
    interview_type: InterviewType = InterviewType.MIXED
    difficulty: Difficulty = Difficulty.MEDIUM
    duration_minutes: int = Field(default=20, ge=5, le=60)


class InterviewQuestionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    stage: str
    question_type: str
    question_text: str
    sequence_number: int
    difficulty: str
    topic: str | None


class InterviewSessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    resume_id: uuid.UUID | None
    job_context_id: uuid.UUID | None
    target_role_snapshot: str | None
    status: str
    current_stage: str
    interview_type: str
    difficulty: str
    duration_minutes: int
    question_budget: int
    question_budget_used: int
    failure_reason: str | None
    created_at: datetime
    updated_at: datetime


class InterviewSessionDetailResponse(InterviewSessionResponse):
    current_question: InterviewQuestionResponse | None


class InterviewListResponse(BaseModel):
    interviews: list[InterviewSessionResponse]


class NextQuestionPayload(BaseModel):
    id: uuid.UUID
    question_text: str
    question_type: str
    stage: str
    difficulty: str
    sequence_number: int


class AnswerCycleResponse(BaseModel):
    interviewer_observation: str
    action_taken: str
    recommendation_overridden: bool
    stage: str
    speech_summary: dict[str, Any] | None
    questions_used: int
    question_budget: int
    next_question: NextQuestionPayload | None
    interview_completed: bool
    question_audio_base64: str | None
    tts_warning: str | None


class ReportCategoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    category: str
    score: int | None
    weight: float
    evidence: list[str]


class InterviewReportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    session_id: uuid.UUID
    overall_score: int | None
    readiness_level: str | None
    scoring_algorithm_version: str
    key_strengths: list[str] | None
    key_weaknesses: list[str] | None
    improvement_priorities: list[str] | None
    narrative_model: str | None
    report_payload: dict[str, Any] | None
    created_at: datetime


class InterviewReportDetailResponse(InterviewReportResponse):
    categories: list[ReportCategoryResponse]
