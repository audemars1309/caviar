"""Interview orchestration (Phase 8).

Owns the session lifecycle and the per-answer cycle:

  transcribe (audio mode) -> deterministic speech metrics -> persist
  answer -> AI evaluation (validated, profile-filtered) -> deterministic
  memory update -> state-machine decision (backend law; the AI
  recommendation is one input) -> next question (AI, with deterministic
  duplicate prevention: one no-repeat regeneration, then a deterministic
  fallback) -> optional TTS -> persist everything.

Resilience policy (per the spec: never lose the session because one
service fails):
  * TTS failure         -> text response still returned, warning attached.
  * Question-generation failure after a successful evaluation -> the
    deterministic stage fallback question is used; the cycle completes.
  * Evaluation failure  -> the answer + transcript are PRESERVED
    (status TRANSCRIBED), the typed error propagates, and resubmitting
    the answer for the same question replaces the unevaluated attempt.
  * Report-narrative failure -> the report still completes with all
    deterministic content; the narrative is marked unavailable.
  * Transcription failure -> typed 4xx/503; nothing persisted.

Status changes go exclusively through ``_transition`` (STATUS_TRANSITIONS
is the law); stage changes go exclusively through the state machine's
decisions. ``current_question_id`` makes interrupted-interview recovery a
read: resume returns the question that was pending.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.core.exceptions import ConflictError, NotFoundError, ValidationFailedError
from app.core.security import AuthenticatedUser
from app.db.enums import ExtractionStatus
from app.db.models.interview import InterviewAnswer, InterviewQuestion, InterviewSession
from app.db.models.job_context import JobContext
from app.db.models.report import InterviewMemory, InterviewReport, InterviewReportCategory
from app.db.models.resume import Resume
from app.db.models.resume_extraction import ResumeExtraction
from app.db.models.speech import AnswerEvaluation, SpeechMetric
from app.services.ai.client import AIRequest, StructuredAIRunner
from app.services.ai.exceptions import AIError
from app.services.ai.prompts.interview import (
    build_evaluation_prompt,
    build_question_prompt,
    build_report_prompt,
)
from app.services.ai.schemas.interview import (
    ANSWER_EVALUATION_SCHEMA_VERSION,
    INTERVIEW_REPORT_SCHEMA_VERSION,
    AnswerEvaluationOutput,
    InterviewQuestionOutput,
    InterviewReportNarrativeOutput,
)
from app.services.ai.tasks import AITask
from app.services.interview.enums import (
    ALL_CRITERIA,
    EVALUATION_PROFILES,
    STATUS_TRANSITIONS,
    Difficulty,
    InterviewAction,
    InterviewStage,
    InterviewStatus,
    InterviewType,
    QuestionType,
)
from app.services.interview.memory import (
    MemoryState,
    apply_evaluation_to_memory,
    memory_context_payload,
)
from app.services.interview.readiness import (
    READINESS_ALGORITHM_VERSION,
    AnswerScores,
    compute_readiness,
)
from app.services.interview.state_machine import (
    FALLBACK_QUESTIONS,
    EngineState,
    allocate_stage_budgets,
    compute_question_budget,
    decide_next_action,
    is_duplicate_question,
    normalize_question_text,
)
from app.services.speech.metrics import TimedWord, compute_speech_metrics
from app.services.speech.transcription import (
    TranscriptionProvider,
    TranscriptionResult,
    validate_answer_audio,
)
from app.services.speech.tts import TTSProvider

logger = logging.getLogger(__name__)

_RESUME_SUMMARY_CHARS = 4_000
_JOB_SUMMARY_CHARS = 2_000
_MAX_TEXT_ANSWER_CHARS = 8_000


class InterviewNotFoundError(NotFoundError):
    error_code = "interview_not_found"


class IllegalInterviewTransitionError(ConflictError):
    error_code = "illegal_interview_transition"


class InterviewNotAnswerableError(ConflictError):
    error_code = "interview_not_answerable"


class InterviewSetupError(ConflictError):
    error_code = "interview_setup_invalid"


class ReportNotAvailableError(NotFoundError):
    error_code = "interview_report_not_available"


# ------------------------------------------------------------- helpers


def _transition(session: InterviewSession, target: InterviewStatus) -> None:
    current = InterviewStatus(session.status)
    if target not in STATUS_TRANSITIONS[current]:
        raise IllegalInterviewTransitionError(
            f"Cannot move an interview from {current} to {target}.",
            details={"from": current, "to": target},
        )
    session.status = target


def _memory_state_from_row(row: InterviewMemory) -> MemoryState:
    return MemoryState(
        candidate_profile_summary=row.candidate_profile_summary,
        resume_evidence_summary=row.resume_evidence_summary,
        job_requirements_summary=row.job_requirements_summary,
        topics_explored=list(row.topics_explored),
        topics_pending=list(row.topics_pending),
        questions_asked=list(row.questions_asked),
        skills_covered=list(row.skills_covered),
        strong_areas=list(row.strong_areas),
        weak_areas=list(row.weak_areas),
        verified_evidence=list(row.verified_evidence),
        contradictions=list(row.contradictions),
        follow_up_opportunities=list(row.follow_up_opportunities),
        user_corrections=list(row.user_corrections),
        confidence_trend=list(row.confidence_trend),
        recent_turns=list(row.recent_turns),
    )


def _write_memory_state(row: InterviewMemory, state: MemoryState) -> None:
    row.topics_explored = state.topics_explored
    row.topics_pending = state.topics_pending
    row.questions_asked = state.questions_asked
    row.skills_covered = state.skills_covered
    row.strong_areas = state.strong_areas
    row.weak_areas = state.weak_areas
    row.verified_evidence = state.verified_evidence
    row.contradictions = state.contradictions
    row.follow_up_opportunities = state.follow_up_opportunities
    row.user_corrections = state.user_corrections
    row.confidence_trend = state.confidence_trend
    row.recent_turns = state.recent_turns


async def _get_session(
    db: AsyncSession, user: AuthenticatedUser, session_id: uuid.UUID
) -> InterviewSession:
    result = await db.execute(
        select(InterviewSession).where(
            InterviewSession.id == session_id, InterviewSession.user_id == user.id
        )
    )
    session = result.scalar_one_or_none()
    if session is None:
        raise InterviewNotFoundError("Interview not found.")
    return session


async def _get_memory_row(db: AsyncSession, session_id: uuid.UUID) -> InterviewMemory:
    result = await db.execute(
        select(InterviewMemory).where(InterviewMemory.session_id == session_id)
    )
    return result.scalar_one()


async def _questions(db: AsyncSession, session_id: uuid.UUID) -> list[InterviewQuestion]:
    result = await db.execute(
        select(InterviewQuestion)
        .where(InterviewQuestion.session_id == session_id)
        .order_by(InterviewQuestion.sequence_number)
    )
    return list(result.scalars().all())


def _follow_up_streak(questions: list[InterviewQuestion], stage: str) -> int:
    streak = 0
    for question in reversed(questions):
        if question.stage != stage:
            break
        if question.question_type in (QuestionType.FOLLOW_UP, QuestionType.CLAIM_VERIFICATION):
            streak += 1
        else:
            break
    return streak


def _coerce_question_type(action: InterviewAction, model_type: str) -> str:
    if action in (
        InterviewAction.ASK_FOLLOW_UP,
        InterviewAction.PROBE_VAGUE_ANSWER,
        InterviewAction.CLARIFY_QUESTION,
    ):
        return QuestionType.FOLLOW_UP
    if action is InterviewAction.VERIFY_CLAIM:
        return QuestionType.CLAIM_VERIFICATION
    return model_type


def _requested_difficulty(session: InterviewSession, action: InterviewAction) -> str:
    order = [Difficulty.EASY, Difficulty.MEDIUM, Difficulty.HARD]
    index = order.index(Difficulty(session.difficulty))
    if action is InterviewAction.INCREASE_DIFFICULTY:
        index = min(index + 1, len(order) - 1)
    elif action is InterviewAction.DECREASE_DIFFICULTY:
        index = max(index - 1, 0)
    return order[index]


async def _generate_question(
    *,
    db: AsyncSession,
    ai_runner: StructuredAIRunner,
    session: InterviewSession,
    memory: MemoryState,
    action: InterviewAction,
    target_topic: str | None,
    stage: InterviewStage,
) -> InterviewQuestion:
    """AI question generation with deterministic duplicate prevention:
    one no-repeat regeneration, then the deterministic stage fallback.
    An AI failure here also falls back deterministically - a completed
    evaluation must never strand the session."""
    asked = set(memory.questions_asked)
    difficulty = _requested_difficulty(session, action)
    question_text: str | None = None
    question_type: str = FALLBACK_QUESTIONS[stage][1]
    topic: str | None = target_topic

    for attempt, no_repeat in ((1, False), (2, True)):
        try:
            run = await ai_runner.run(
                AIRequest(
                    task=AITask.INTERVIEW_QUESTION,
                    **_question_prompt_fields(
                        session=session,
                        memory=memory,
                        action=action,
                        target_topic=target_topic,
                        difficulty=difficulty,
                        stage=stage,
                        no_repeat=no_repeat,
                    ),
                ),
                InterviewQuestionOutput,
            )
        except AIError:
            logger.warning(
                "Question generation failed (attempt %s); using deterministic fallback.",
                attempt,
            )
            break
        output = run.output
        assert isinstance(output, InterviewQuestionOutput)
        if not is_duplicate_question(output.question_text, asked):
            question_text = output.question_text
            question_type = _coerce_question_type(action, output.question_type)
            topic = output.topic or target_topic
            difficulty = output.difficulty
            break

    if question_text is None:
        question_text, fallback_type = FALLBACK_QUESTIONS[stage]
        question_type = fallback_type
        if is_duplicate_question(question_text, asked):
            # Even the fallback was asked (long interviews): make it
            # unique deterministically.
            question_text = f"{question_text} Please add anything new this time."

    sequence = session.question_budget_used + 1
    question = InterviewQuestion(
        id=uuid.uuid4(),
        session_id=session.id,
        stage=stage,
        question_type=question_type,
        question_text=question_text,
        normalized_text=normalize_question_text(question_text),
        sequence_number=sequence,
        difficulty=difficulty,
        topic=topic,
    )
    db.add(question)
    session.question_budget_used = sequence
    session.current_stage = stage
    session.current_question_id = question.id
    return question


def _question_prompt_fields(
    *,
    session: InterviewSession,
    memory: MemoryState,
    action: InterviewAction,
    target_topic: str | None,
    difficulty: str,
    stage: InterviewStage,
    no_repeat: bool,
) -> dict[str, str]:
    prompt = build_question_prompt(
        stage=stage,
        action=action,
        target_topic=target_topic,
        difficulty=difficulty,
        questions_already_asked=memory.questions_asked,
        memory_digest=memory_context_payload(memory),
        resume_summary=memory.resume_evidence_summary,
        job_summary=memory.job_requirements_summary,
        no_repeat_notice=no_repeat,
    )
    return {
        "system_instruction": prompt.system_instruction,
        "user_content": prompt.user_content,
    }


# -------------------------------------------------------------- lifecycle


async def create_interview(
    *,
    db: AsyncSession,
    user: AuthenticatedUser,
    resume_id: uuid.UUID,
    job_context_id: uuid.UUID | None,
    interview_type: InterviewType,
    difficulty: Difficulty,
    duration_minutes: int,
) -> InterviewSession:
    resume_result = await db.execute(
        select(Resume).where(Resume.id == resume_id, Resume.user_id == user.id)
    )
    resume = resume_result.scalar_one_or_none()
    if resume is None:
        raise InterviewNotFoundError("Resume not found.")
    if resume.extraction_status != ExtractionStatus.EXTRACTED:
        raise InterviewSetupError(
            "The selected resume has no successful text extraction."
        )
    extraction_result = await db.execute(
        select(ResumeExtraction).where(ResumeExtraction.resume_id == resume.id)
    )
    extraction = extraction_result.scalar_one_or_none()
    if extraction is None:
        raise InterviewSetupError("The selected resume has no extraction data.")

    job_context: JobContext | None = None
    if job_context_id is not None:
        job_result = await db.execute(
            select(JobContext).where(
                JobContext.id == job_context_id, JobContext.user_id == user.id
            )
        )
        job_context = job_result.scalar_one_or_none()
        if job_context is None:
            raise InterviewNotFoundError("Job context not found.")

    session = InterviewSession(
        id=uuid.uuid4(),
        user_id=user.id,
        resume_id=resume.id,
        job_context_id=job_context.id if job_context else None,
        target_role_snapshot=job_context.target_role if job_context else None,
        status=InterviewStatus.PENDING,
        current_stage=InterviewStage.INTRODUCTION,
        interview_type=interview_type,
        difficulty=difficulty,
        duration_minutes=duration_minutes,
        question_budget=compute_question_budget(duration_minutes),
        question_budget_used=0,
    )
    job_summary = None
    if job_context:
        description = (job_context.job_description or "")[:_JOB_SUMMARY_CHARS]
        job_summary = f"Target role: {job_context.target_role}\n{description}".strip()
    memory = InterviewMemory(
        session_id=session.id,
        resume_evidence_summary=extraction.normalized_text[:_RESUME_SUMMARY_CHARS],
        job_requirements_summary=job_summary,
        topics_pending=list(extraction.detected_section_types),
    )
    db.add(session)
    db.add(memory)
    await db.commit()
    await db.refresh(session)
    return session


async def start_interview(
    *,
    db: AsyncSession,
    ai_runner: StructuredAIRunner,
    user: AuthenticatedUser,
    session_id: uuid.UUID,
) -> tuple[InterviewSession, InterviewQuestion]:
    session = await _get_session(db, user, session_id)
    _transition(session, InterviewStatus.READY)
    memory_row = await _get_memory_row(db, session.id)
    memory = _memory_state_from_row(memory_row)
    try:
        question = await _generate_question(
            db=db,
            ai_runner=ai_runner,
            session=session,
            memory=memory,
            action=InterviewAction.CHANGE_TOPIC,
            target_topic="introduction",
            stage=InterviewStage.INTRODUCTION,
        )
    except Exception:
        session.status = InterviewStatus.FAILED
        session.failure_reason = "START_FAILED: The opening question could not be prepared."
        await db.commit()
        raise
    memory_row.questions_asked = list(
        dict.fromkeys(memory.questions_asked + [question.normalized_text])
    )
    _transition(session, InterviewStatus.RUNNING)
    await db.commit()
    await db.refresh(session)
    await db.refresh(question)
    logger.info(
        "Interview started: session_id=%s type=%s budget=%s",
        session.id,
        session.interview_type,
        session.question_budget,
    )
    return session, question


async def pause_interview(
    db: AsyncSession, user: AuthenticatedUser, session_id: uuid.UUID
) -> InterviewSession:
    session = await _get_session(db, user, session_id)
    _transition(session, InterviewStatus.PAUSED)
    await db.commit()
    await db.refresh(session)
    return session


async def resume_interview(
    db: AsyncSession, user: AuthenticatedUser, session_id: uuid.UUID
) -> tuple[InterviewSession, InterviewQuestion | None]:
    """Interrupted-interview recovery: PAUSED -> RUNNING, returning the
    question that was pending when the interview stopped."""
    session = await _get_session(db, user, session_id)
    _transition(session, InterviewStatus.RUNNING)
    await db.commit()
    await db.refresh(session)
    question: InterviewQuestion | None = None
    if session.current_question_id:
        result = await db.execute(
            select(InterviewQuestion).where(
                InterviewQuestion.id == session.current_question_id
            )
        )
        question = result.scalar_one_or_none()
    return session, question


async def cancel_interview(
    db: AsyncSession, user: AuthenticatedUser, session_id: uuid.UUID
) -> InterviewSession:
    session = await _get_session(db, user, session_id)
    _transition(session, InterviewStatus.CANCELLED)
    await db.commit()
    await db.refresh(session)
    return session


async def list_interviews(
    db: AsyncSession, user: AuthenticatedUser
) -> list[InterviewSession]:
    result = await db.execute(
        select(InterviewSession)
        .where(InterviewSession.user_id == user.id)
        .order_by(InterviewSession.created_at.desc())
    )
    return list(result.scalars().all())


async def get_interview(
    db: AsyncSession, user: AuthenticatedUser, session_id: uuid.UUID
) -> tuple[InterviewSession, InterviewQuestion | None]:
    session = await _get_session(db, user, session_id)
    question: InterviewQuestion | None = None
    if session.current_question_id:
        result = await db.execute(
            select(InterviewQuestion).where(
                InterviewQuestion.id == session.current_question_id
            )
        )
        question = result.scalar_one_or_none()
    return session, question


# ------------------------------------------------------------ answer cycle


async def submit_answer(
    *,
    db: AsyncSession,
    ai_runner: StructuredAIRunner,
    transcription: TranscriptionProvider,
    tts: TTSProvider,
    settings: Settings,
    user: AuthenticatedUser,
    session_id: uuid.UUID,
    text_answer: str | None,
    audio_content: bytes | None,
    include_audio: bool,
) -> dict[str, Any]:
    session = await _get_session(db, user, session_id)
    if session.status != InterviewStatus.RUNNING:
        raise InterviewNotAnswerableError(
            "Answers can only be submitted while the interview is running.",
            details={"status": session.status},
        )
    if not session.current_question_id:
        raise InterviewNotAnswerableError("There is no pending question to answer.")
    question_result = await db.execute(
        select(InterviewQuestion).where(InterviewQuestion.id == session.current_question_id)
    )
    question = question_result.scalar_one()

    # ---- input: exactly one of text / audio -------------------------
    if (text_answer is None) == (audio_content is None):
        raise ValidationFailedError("Provide exactly one of a text answer or an audio file.")

    transcription_result: TranscriptionResult | None = None
    if audio_content is not None:
        validate_answer_audio(audio_content, max_bytes=settings.ANSWER_AUDIO_MAX_BYTES)
        transcription_result = await transcription.transcribe(audio_content)
        transcript = transcription_result.text
    else:
        transcript = (text_answer or "").strip()[:_MAX_TEXT_ANSWER_CHARS]
        if not transcript:
            raise ValidationFailedError("The answer is empty.")

    # Replace a previous unevaluated attempt for this question (resilient
    # retry after an evaluation failure).
    previous = await db.execute(
        select(InterviewAnswer).where(InterviewAnswer.question_id == question.id)
    )
    for stale in previous.scalars().all():
        if stale.status == "EVALUATED":
            raise InterviewNotAnswerableError("This question was already answered.")
        await db.delete(stale)

    answer = InterviewAnswer(
        id=uuid.uuid4(),
        question_id=question.id,
        session_id=session.id,
        transcript=transcript,
        input_mode="AUDIO" if audio_content is not None else "TEXT",
        status="TRANSCRIBED",
    )
    if transcription_result is not None:
        answer.language = transcription_result.language
        answer.audio_duration_seconds = transcription_result.audio_duration_seconds
        answer.transcript_segments = [
            {"word": w.word, "start": w.start, "end": w.end, "probability": w.probability}
            for w in transcription_result.words
        ]
    db.add(answer)

    speech_summary: dict[str, Any] | None = None
    if transcription_result is not None:
        metrics = compute_speech_metrics(
            [
                TimedWord(word=w.word, start=w.start, end=w.end)
                for w in transcription_result.words
            ],
            audio_duration_seconds=transcription_result.audio_duration_seconds,
            transcript=transcript,
        )
        db.add(
            SpeechMetric(
                answer_id=answer.id,
                speaking_duration_seconds=metrics.speaking_duration_seconds,
                word_count=metrics.word_count,
                words_per_minute=metrics.words_per_minute,
                long_pause_count=metrics.long_pause_count,
                avg_pause_duration_seconds=metrics.avg_pause_duration_seconds,
                max_pause_duration_seconds=metrics.max_pause_duration_seconds,
                filler_word_count=metrics.filler_word_count,
                filler_word_frequency=metrics.filler_word_frequency,
                hesitation_count=metrics.hesitation_count,
                silence_duration_seconds=metrics.silence_duration_seconds,
                response_duration_seconds=metrics.response_duration_seconds,
                answer_char_length=metrics.answer_char_length,
                speech_completeness=metrics.speech_completeness,
            )
        )
        speech_summary = {
            "words_per_minute": metrics.words_per_minute,
            "long_pause_count": metrics.long_pause_count,
            "filler_word_count": metrics.filler_word_count,
        }
    await db.commit()  # answer (+metrics) preserved regardless of AI outcome

    # ---- AI evaluation ------------------------------------------------
    memory_row = await _get_memory_row(db, session.id)
    memory = _memory_state_from_row(memory_row)
    prompt = build_evaluation_prompt(
        stage=session.current_stage,
        question_text=question.question_text,
        question_type=question.question_type,
        question_topic=question.topic,
        transcript=transcript,
        memory_digest=memory_context_payload(memory),
        resume_summary=memory.resume_evidence_summary,
        job_summary=memory.job_requirements_summary,
    )
    run = await ai_runner.run(
        AIRequest(
            task=AITask.ANSWER_EVALUATION,
            system_instruction=prompt.system_instruction,
            user_content=prompt.user_content,
        ),
        AnswerEvaluationOutput,
    )  # typed AIError propagates; the answer above is already safe
    output = run.output
    assert isinstance(output, AnswerEvaluationOutput)

    # Profile filter: the BACKEND decides which criteria apply.
    profile = EVALUATION_PROFILES[QuestionType(question.question_type)]
    evaluation = AnswerEvaluation(
        answer_id=answer.id,
        question_type=question.question_type,
        strengths=list(output.strengths),
        weaknesses=list(output.weaknesses),
        supporting_evidence=list(output.supporting_evidence),
        unsupported_claims=list(output.unsupported_claims),
        follow_up_required=output.follow_up_required,
        follow_up_reason=output.follow_up_reason or None,
        recommended_action=output.recommended_action,
        target_topic=output.target_topic or None,
        interviewer_observation=output.interviewer_observation,
    )
    for criterion in ALL_CRITERIA:
        setattr(
            evaluation, criterion, getattr(output, criterion) if criterion in profile else None
        )
    db.add(evaluation)
    answer.status = "EVALUATED"

    # ---- deterministic memory update -----------------------------------
    memory = apply_evaluation_to_memory(
        memory,
        question_text=question.question_text,
        question_normalized=question.normalized_text,
        question_topic=question.topic,
        transcript=transcript,
        evaluation={
            "interviewer_observation": output.interviewer_observation,
            "confidence_estimate": output.confidence_estimate,
            "follow_up_required": output.follow_up_required,
            "follow_up_reason": output.follow_up_reason,
            "new_topics": output.new_topics,
            "skills_covered": output.skills_covered,
            "strengths": output.strengths,
            "weaknesses": output.weaknesses,
            "supporting_evidence": output.supporting_evidence,
            "unsupported_claims": output.unsupported_claims,
            "user_corrections": output.user_corrections,
        },
    )
    _write_memory_state(memory_row, memory)

    # ---- backend decision ----------------------------------------------
    questions = await _questions(db, session.id)
    state = EngineState(
        stage=InterviewStage(session.current_stage),
        interview_type=InterviewType(session.interview_type),
        questions_asked_total=session.question_budget_used,
        questions_asked_in_stage=sum(
            1 for item in questions if item.stage == session.current_stage
        ),
        question_budget=session.question_budget,
        stage_budgets=allocate_stage_budgets(
            InterviewType(session.interview_type), session.question_budget
        ),
        follow_up_streak=_follow_up_streak(questions, session.current_stage),
    )
    decision = decide_next_action(state, output.recommended_action)

    response: dict[str, Any] = {
        "interviewer_observation": output.interviewer_observation,
        "action_taken": decision.action,
        "recommendation_overridden": decision.recommendation_overridden,
        "stage": decision.next_stage,
        "speech_summary": speech_summary,
        "questions_used": session.question_budget_used,
        "question_budget": session.question_budget,
        "next_question": None,
        "interview_completed": False,
        "question_audio_base64": None,
        "tts_warning": None,
    }

    if decision.action is InterviewAction.CLOSE_INTERVIEW:
        session.current_question_id = None
        session.current_stage = InterviewStage.COMPLETED
        _transition(session, InterviewStatus.COMPLETED)
        await db.commit()
        await _generate_report(db=db, ai_runner=ai_runner, session=session)
        response["interview_completed"] = True
        logger.info("Interview completed: session_id=%s", session.id)
        return response

    next_question = await _generate_question(
        db=db,
        ai_runner=ai_runner,
        session=session,
        memory=memory,
        action=decision.action,
        target_topic=output.target_topic or None,
        stage=decision.next_stage,
    )
    memory_row.questions_asked = list(
        dict.fromkeys(memory.questions_asked + [next_question.normalized_text])
    )
    await db.commit()
    await db.refresh(next_question)
    response["questions_used"] = session.question_budget_used  # post-cycle state

    if include_audio:
        try:
            tts_result = await tts.synthesize(next_question.question_text)
            import base64

            response["question_audio_base64"] = base64.b64encode(
                tts_result.audio_wav
            ).decode("ascii")
        except Exception as exc:
            response["tts_warning"] = (
                f"Voice synthesis unavailable ({exc.__class__.__name__}); "
                "text response returned."
            )

    response["next_question"] = {
        "id": str(next_question.id),
        "question_text": next_question.question_text,
        "question_type": next_question.question_type,
        "stage": next_question.stage,
        "difficulty": next_question.difficulty,
        "sequence_number": next_question.sequence_number,
    }
    return response


# ------------------------------------------------------------------ report


async def _generate_report(
    *, db: AsyncSession, ai_runner: StructuredAIRunner, session: InterviewSession
) -> InterviewReport:
    questions = await _questions(db, session.id)
    answers_result = await db.execute(
        select(InterviewAnswer, AnswerEvaluation, InterviewQuestion)
        .join(AnswerEvaluation, AnswerEvaluation.answer_id == InterviewAnswer.id)
        .join(InterviewQuestion, InterviewQuestion.id == InterviewAnswer.question_id)
        .where(InterviewAnswer.session_id == session.id)
        .order_by(InterviewQuestion.sequence_number)
    )
    rows = answers_result.all()
    metrics_result = await db.execute(
        select(SpeechMetric)
        .join(InterviewAnswer, InterviewAnswer.id == SpeechMetric.answer_id)
        .where(InterviewAnswer.session_id == session.id)
    )
    metric_rows = list(metrics_result.scalars().all())
    memory_row = await _get_memory_row(db, session.id)

    # ---- deterministic readiness ---------------------------------------
    readiness = compute_readiness(
        [
            AnswerScores(
                scores={criterion: getattr(evaluation, criterion) for criterion in ALL_CRITERIA},
                difficulty=question.difficulty,
            )
            for _, evaluation, question in rows
        ]
    )

    def _avg(values: list) -> float | None:
        cleaned = [float(v) for v in values if v is not None]
        return round(sum(cleaned) / len(cleaned), 2) if cleaned else None

    speech_summary = {
        "answers_with_audio": len(metric_rows),
        "avg_words_per_minute": _avg([m.words_per_minute for m in metric_rows]),
        "avg_filler_word_count": _avg([m.filler_word_count for m in metric_rows]),
        "total_long_pauses": sum(m.long_pause_count or 0 for m in metric_rows),
        "avg_speech_completeness": _avg([m.speech_completeness for m in metric_rows]),
    }
    timeline = [
        {
            "sequence": q.sequence_number,
            "stage": q.stage,
            "question_type": q.question_type,
            "topic": q.topic,
            "difficulty": q.difficulty,
        }
        for q in questions
    ]
    topic_coverage = sorted(
        {q.topic for q in questions if q.topic} | set(memory_row.topics_explored)
    )
    question_history = [
        {
            "sequence": question.sequence_number,
            "question": question.question_text,
            "observation": evaluation.interviewer_observation,
            "strengths": evaluation.strengths,
            "weaknesses": evaluation.weaknesses,
        }
        for _, evaluation, question in rows
    ]

    # ---- AI narrative (resilient) ---------------------------------------
    narrative: dict[str, Any] | None = None
    narrative_model: str | None = None
    record = {
        "interview_type": session.interview_type,
        "difficulty": session.difficulty,
        "timeline": timeline,
        "question_history": question_history,
        "speech_metrics_summary": speech_summary,
        "strong_areas": memory_row.strong_areas,
        "weak_areas": memory_row.weak_areas,
        "contradictions": memory_row.contradictions,
        "readiness_categories": [
            {"category": c.category, "score": c.score} for c in readiness.categories
        ],
    }
    try:
        prompt = build_report_prompt(interview_record=record)
        run = await ai_runner.run(
            AIRequest(
                task=AITask.INTERVIEW_REPORT,
                system_instruction=prompt.system_instruction,
                user_content=prompt.user_content,
            ),
            InterviewReportNarrativeOutput,
        )
        assert isinstance(run.output, InterviewReportNarrativeOutput)
        narrative = run.output.model_dump()
        narrative_model = run.model
    except AIError:
        logger.warning(
            "Report narrative generation failed; deterministic report persisted "
            "(session_id=%s).",
            session.id,
        )

    report = InterviewReport(
        id=uuid.uuid4(),
        session_id=session.id,
        overall_score=readiness.overall_score,
        scoring_algorithm_version=READINESS_ALGORITHM_VERSION,
        readiness_level=readiness.readiness_level,
        key_strengths=list(memory_row.strong_areas),
        key_weaknesses=list(memory_row.weak_areas),
        improvement_priorities=(narrative or {}).get("improvement_roadmap"),
        narrative_model=narrative_model,
        report_payload={
            "schema_version": INTERVIEW_REPORT_SCHEMA_VERSION,
            "evaluation_schema_version": ANSWER_EVALUATION_SCHEMA_VERSION,
            "timeline": timeline,
            "topic_coverage": topic_coverage,
            "question_history": question_history,
            "speech_metrics_summary": speech_summary,
            "narrative": narrative,
            "narrative_unavailable": narrative is None,
        },
    )
    db.add(report)
    for category in readiness.categories:
        db.add(
            InterviewReportCategory(
                interview_report_id=report.id,
                category=category.category,
                score=category.score,
                weight=category.weight,
                evidence=[f"Aggregated from {category.sample_count} evaluated answers."],
            )
        )
    await db.commit()
    await db.refresh(report)
    return report


async def get_report(
    db: AsyncSession, user: AuthenticatedUser, session_id: uuid.UUID
) -> tuple[InterviewReport, list[InterviewReportCategory]]:
    session = await _get_session(db, user, session_id)
    result = await db.execute(
        select(InterviewReport).where(InterviewReport.session_id == session.id)
    )
    report = result.scalar_one_or_none()
    if report is None:
        raise ReportNotAvailableError(
            "No report is available for this interview.",
            details={"status": session.status},
        )
    categories_result = await db.execute(
        select(InterviewReportCategory)
        .where(InterviewReportCategory.interview_report_id == report.id)
        .order_by(InterviewReportCategory.category)
    )
    return report, list(categories_result.scalars().all())
