"""Interview Intelligence routes (Phase 8). Thin wiring; providers
(transcription, TTS) are FastAPI dependencies constructed from settings
and overridable in tests - the same seam pattern as storage and AI."""

from __future__ import annotations

import uuid
from functools import lru_cache

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.core.rate_limit import SlidingWindowRateLimiter
from app.core.security import AuthenticatedUser, get_current_user
from app.db.rls import get_authenticated_db
from app.schemas.interview import (
    AnswerCycleResponse,
    InterviewCreateRequest,
    InterviewListResponse,
    InterviewQuestionResponse,
    InterviewReportDetailResponse,
    InterviewReportResponse,
    InterviewSessionDetailResponse,
    InterviewSessionResponse,
    ReportCategoryResponse,
)
from app.services.ai.client import StructuredAIRunner, get_ai_runner
from app.services.interview import service as interview_service
from app.services.speech.transcription import FasterWhisperProvider, TranscriptionProvider
from app.services.speech.tts import KokoroTTSProvider, TTSProvider

router = APIRouter()

_answer_rate_limiter: SlidingWindowRateLimiter | None = None


def _get_answer_rate_limiter(
    settings: Settings = Depends(get_settings),
) -> SlidingWindowRateLimiter:
    global _answer_rate_limiter
    if _answer_rate_limiter is None:
        _answer_rate_limiter = SlidingWindowRateLimiter(
            max_events=settings.INTERVIEW_ANSWER_RATE_LIMIT_MAX,
            window_seconds=settings.INTERVIEW_ANSWER_RATE_LIMIT_WINDOW_SECONDS,
        )
    return _answer_rate_limiter


@lru_cache
def _cached_transcription_provider(
    model_size: str, device: str, compute_type: str | None, timeout: float
) -> FasterWhisperProvider:
    return FasterWhisperProvider(
        model_size=model_size, device=device, compute_type=compute_type, timeout_seconds=timeout
    )


def get_transcription_provider(
    settings: Settings = Depends(get_settings),
) -> TranscriptionProvider:
    return _cached_transcription_provider(
        settings.WHISPER_MODEL_SIZE,
        settings.WHISPER_DEVICE,
        settings.WHISPER_COMPUTE_TYPE,
        settings.TRANSCRIPTION_TIMEOUT_SECONDS,
    )


@lru_cache
def _cached_tts_provider(voice: str, lang: str, timeout: float) -> KokoroTTSProvider:
    return KokoroTTSProvider(default_voice=voice, lang_code=lang, timeout_seconds=timeout)


def get_tts_provider(settings: Settings = Depends(get_settings)) -> TTSProvider:
    return _cached_tts_provider(
        settings.KOKORO_VOICE, settings.KOKORO_LANG_CODE, settings.TTS_TIMEOUT_SECONDS
    )


@router.post(
    "/interviews", response_model=InterviewSessionResponse, status_code=status.HTTP_201_CREATED
)
async def create_interview(
    payload: InterviewCreateRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_authenticated_db),
) -> InterviewSessionResponse:
    session = await interview_service.create_interview(
        db=db,
        user=user,
        resume_id=payload.resume_id,
        job_context_id=payload.job_context_id,
        interview_type=payload.interview_type,
        difficulty=payload.difficulty,
        duration_minutes=payload.duration_minutes,
    )
    return InterviewSessionResponse.model_validate(session)


@router.get("/interviews", response_model=InterviewListResponse)
async def list_interviews(
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_authenticated_db),
) -> InterviewListResponse:
    sessions = await interview_service.list_interviews(db, user)
    return InterviewListResponse(
        interviews=[InterviewSessionResponse.model_validate(item) for item in sessions]
    )


@router.get("/interviews/{session_id}", response_model=InterviewSessionDetailResponse)
async def get_interview(
    session_id: uuid.UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_authenticated_db),
) -> InterviewSessionDetailResponse:
    session, question = await interview_service.get_interview(db, user, session_id)
    return InterviewSessionDetailResponse(
        **InterviewSessionResponse.model_validate(session).model_dump(),
        current_question=(
            InterviewQuestionResponse.model_validate(question) if question else None
        ),
    )


@router.post("/interviews/{session_id}/start", response_model=InterviewSessionDetailResponse)
async def start_interview(
    session_id: uuid.UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_authenticated_db),
    ai_runner: StructuredAIRunner = Depends(get_ai_runner),
) -> InterviewSessionDetailResponse:
    session, question = await interview_service.start_interview(
        db=db, ai_runner=ai_runner, user=user, session_id=session_id
    )
    return InterviewSessionDetailResponse(
        **InterviewSessionResponse.model_validate(session).model_dump(),
        current_question=InterviewQuestionResponse.model_validate(question),
    )


@router.post("/interviews/{session_id}/answers", response_model=AnswerCycleResponse)
async def submit_answer(
    session_id: uuid.UUID,
    include_audio: bool = Query(default=False),
    text_answer: str | None = Form(default=None),
    audio: UploadFile | None = File(default=None),
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_authenticated_db),
    ai_runner: StructuredAIRunner = Depends(get_ai_runner),
    transcription: TranscriptionProvider = Depends(get_transcription_provider),
    tts: TTSProvider = Depends(get_tts_provider),
    settings: Settings = Depends(get_settings),
    rate_limiter: SlidingWindowRateLimiter = Depends(_get_answer_rate_limiter),
) -> AnswerCycleResponse:
    rate_limiter.check(user.id)
    audio_content = await audio.read() if audio is not None else None
    result = await interview_service.submit_answer(
        db=db,
        ai_runner=ai_runner,
        transcription=transcription,
        tts=tts,
        settings=settings,
        user=user,
        session_id=session_id,
        text_answer=text_answer,
        audio_content=audio_content,
        include_audio=include_audio,
    )
    return AnswerCycleResponse(**result)


@router.post("/interviews/{session_id}/pause", response_model=InterviewSessionResponse)
async def pause_interview(
    session_id: uuid.UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_authenticated_db),
) -> InterviewSessionResponse:
    session = await interview_service.pause_interview(db, user, session_id)
    return InterviewSessionResponse.model_validate(session)


@router.post("/interviews/{session_id}/resume", response_model=InterviewSessionDetailResponse)
async def resume_interview(
    session_id: uuid.UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_authenticated_db),
) -> InterviewSessionDetailResponse:
    session, question = await interview_service.resume_interview(db, user, session_id)
    return InterviewSessionDetailResponse(
        **InterviewSessionResponse.model_validate(session).model_dump(),
        current_question=(
            InterviewQuestionResponse.model_validate(question) if question else None
        ),
    )


@router.post("/interviews/{session_id}/cancel", response_model=InterviewSessionResponse)
async def cancel_interview(
    session_id: uuid.UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_authenticated_db),
) -> InterviewSessionResponse:
    session = await interview_service.cancel_interview(db, user, session_id)
    return InterviewSessionResponse.model_validate(session)


@router.get("/interviews/{session_id}/report", response_model=InterviewReportDetailResponse)
async def get_interview_report(
    session_id: uuid.UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_authenticated_db),
) -> InterviewReportDetailResponse:
    report, categories = await interview_service.get_report(db, user, session_id)
    return InterviewReportDetailResponse(
        **InterviewReportResponse.model_validate(report).model_dump(),
        categories=[ReportCategoryResponse.model_validate(item) for item in categories],
    )
