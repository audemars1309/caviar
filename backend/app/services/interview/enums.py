"""Interview engine enums and deterministic rule tables (Phase 8).

Everything here is backend-owned application law: statuses, the stage
graph, allowed actions per stage, stage question-budget allocation by
interview type, difficulty weights, and the question-type evaluation
profiles that decide which criteria apply to which answers. Gemini can
recommend; only these tables decide.

Stage taxonomy note: the approved Phase 0/2 stage enum is kept
unchanged. Phase 8's requested names map onto it directly -
Warmup=CANDIDATE_BACKGROUND, Technical Round=ROLE_SPECIFIC,
Problem Solving=ADAPTIVE_PROBING.
"""

from __future__ import annotations

import enum


class InterviewStatus(enum.StrEnum):
    PENDING = "PENDING"
    READY = "READY"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


# Legal status transitions - the ONLY way a session status may change.
STATUS_TRANSITIONS: dict[InterviewStatus, frozenset[InterviewStatus]] = {
    InterviewStatus.PENDING: frozenset(
        {InterviewStatus.READY, InterviewStatus.FAILED, InterviewStatus.CANCELLED}
    ),
    InterviewStatus.READY: frozenset(
        {InterviewStatus.RUNNING, InterviewStatus.FAILED, InterviewStatus.CANCELLED}
    ),
    InterviewStatus.RUNNING: frozenset(
        {
            InterviewStatus.PAUSED,
            InterviewStatus.COMPLETED,
            InterviewStatus.FAILED,
            InterviewStatus.CANCELLED,
        }
    ),
    InterviewStatus.PAUSED: frozenset(
        {InterviewStatus.RUNNING, InterviewStatus.CANCELLED}
    ),
    InterviewStatus.FAILED: frozenset(
        {InterviewStatus.READY, InterviewStatus.CANCELLED}  # start is retryable
    ),
    InterviewStatus.COMPLETED: frozenset(),
    InterviewStatus.CANCELLED: frozenset(),
}


class InterviewStage(enum.StrEnum):
    INTRODUCTION = "INTRODUCTION"
    CANDIDATE_BACKGROUND = "CANDIDATE_BACKGROUND"
    RESUME_DISCUSSION = "RESUME_DISCUSSION"
    PROJECT_DEEP_DIVE = "PROJECT_DEEP_DIVE"
    ROLE_SPECIFIC = "ROLE_SPECIFIC"
    BEHAVIORAL = "BEHAVIORAL"
    ADAPTIVE_PROBING = "ADAPTIVE_PROBING"
    CLOSING = "CLOSING"
    COMPLETED = "COMPLETED"


# Document order. Stages may only move FORWARD along this list (skipping
# is allowed - a type-specific plan omits stages); backward transitions
# are illegal.
STAGE_ORDER: tuple[InterviewStage, ...] = (
    InterviewStage.INTRODUCTION,
    InterviewStage.CANDIDATE_BACKGROUND,
    InterviewStage.RESUME_DISCUSSION,
    InterviewStage.PROJECT_DEEP_DIVE,
    InterviewStage.ROLE_SPECIFIC,
    InterviewStage.BEHAVIORAL,
    InterviewStage.ADAPTIVE_PROBING,
    InterviewStage.CLOSING,
    InterviewStage.COMPLETED,
)


class InterviewType(enum.StrEnum):
    MIXED = "MIXED"
    TECHNICAL = "TECHNICAL"
    BEHAVIORAL = "BEHAVIORAL"


class Difficulty(enum.StrEnum):
    EASY = "EASY"
    MEDIUM = "MEDIUM"
    HARD = "HARD"


DIFFICULTY_WEIGHTS: dict[str, float] = {"EASY": 0.8, "MEDIUM": 1.0, "HARD": 1.2}


class InterviewAction(enum.StrEnum):
    ASK_FOLLOW_UP = "ASK_FOLLOW_UP"
    PROBE_VAGUE_ANSWER = "PROBE_VAGUE_ANSWER"
    VERIFY_CLAIM = "VERIFY_CLAIM"
    EXPLORE_PROJECT = "EXPLORE_PROJECT"
    INCREASE_DIFFICULTY = "INCREASE_DIFFICULTY"
    DECREASE_DIFFICULTY = "DECREASE_DIFFICULTY"
    CHANGE_TOPIC = "CHANGE_TOPIC"
    ADVANCE_STAGE = "ADVANCE_STAGE"
    CLARIFY_QUESTION = "CLARIFY_QUESTION"
    CLOSE_INTERVIEW = "CLOSE_INTERVIEW"


# Actions that continue probing the same thread (loop-prevention target).
FOLLOW_UP_ACTIONS: frozenset[InterviewAction] = frozenset(
    {
        InterviewAction.ASK_FOLLOW_UP,
        InterviewAction.PROBE_VAGUE_ANSWER,
        InterviewAction.VERIFY_CLAIM,
        InterviewAction.CLARIFY_QUESTION,
    }
)

# Which actions Gemini may validly recommend in each stage. CLOSING only
# closes; INTRODUCTION never probes.
ALLOWED_ACTIONS_BY_STAGE: dict[InterviewStage, frozenset[InterviewAction]] = {
    InterviewStage.INTRODUCTION: frozenset(
        {InterviewAction.ADVANCE_STAGE, InterviewAction.CHANGE_TOPIC}
    ),
    InterviewStage.CANDIDATE_BACKGROUND: frozenset(
        {
            InterviewAction.ASK_FOLLOW_UP,
            InterviewAction.CLARIFY_QUESTION,
            InterviewAction.CHANGE_TOPIC,
            InterviewAction.ADVANCE_STAGE,
        }
    ),
    InterviewStage.RESUME_DISCUSSION: frozenset(
        {
            InterviewAction.ASK_FOLLOW_UP,
            InterviewAction.PROBE_VAGUE_ANSWER,
            InterviewAction.VERIFY_CLAIM,
            InterviewAction.EXPLORE_PROJECT,
            InterviewAction.CHANGE_TOPIC,
            InterviewAction.ADVANCE_STAGE,
        }
    ),
    InterviewStage.PROJECT_DEEP_DIVE: frozenset(
        {
            InterviewAction.ASK_FOLLOW_UP,
            InterviewAction.PROBE_VAGUE_ANSWER,
            InterviewAction.VERIFY_CLAIM,
            InterviewAction.EXPLORE_PROJECT,
            InterviewAction.INCREASE_DIFFICULTY,
            InterviewAction.DECREASE_DIFFICULTY,
            InterviewAction.CHANGE_TOPIC,
            InterviewAction.ADVANCE_STAGE,
        }
    ),
    InterviewStage.ROLE_SPECIFIC: frozenset(
        {
            InterviewAction.ASK_FOLLOW_UP,
            InterviewAction.PROBE_VAGUE_ANSWER,
            InterviewAction.VERIFY_CLAIM,
            InterviewAction.INCREASE_DIFFICULTY,
            InterviewAction.DECREASE_DIFFICULTY,
            InterviewAction.CHANGE_TOPIC,
            InterviewAction.ADVANCE_STAGE,
        }
    ),
    InterviewStage.BEHAVIORAL: frozenset(
        {
            InterviewAction.ASK_FOLLOW_UP,
            InterviewAction.PROBE_VAGUE_ANSWER,
            InterviewAction.CHANGE_TOPIC,
            InterviewAction.ADVANCE_STAGE,
        }
    ),
    InterviewStage.ADAPTIVE_PROBING: frozenset(
        {
            InterviewAction.ASK_FOLLOW_UP,
            InterviewAction.PROBE_VAGUE_ANSWER,
            InterviewAction.VERIFY_CLAIM,
            InterviewAction.INCREASE_DIFFICULTY,
            InterviewAction.DECREASE_DIFFICULTY,
            InterviewAction.CHANGE_TOPIC,
            InterviewAction.ADVANCE_STAGE,
        }
    ),
    InterviewStage.CLOSING: frozenset({InterviewAction.CLOSE_INTERVIEW}),
    InterviewStage.COMPLETED: frozenset(),
}


class QuestionType(enum.StrEnum):
    INTRODUCTORY = "INTRODUCTORY"
    RESUME = "RESUME"
    PROJECT = "PROJECT"
    TECHNICAL = "TECHNICAL"
    BEHAVIORAL = "BEHAVIORAL"
    SITUATIONAL = "SITUATIONAL"
    FOLLOW_UP = "FOLLOW_UP"
    CLAIM_VERIFICATION = "CLAIM_VERIFICATION"


# Stage budget allocation (fractions of the total question budget) per
# interview type. Zero-fraction stages are SKIPPED for that type. Each
# row sums to 1.0; INTRODUCTION and CLOSING get fixed single questions
# via minimums in the allocator.
STAGE_ALLOCATION: dict[InterviewType, dict[InterviewStage, float]] = {
    InterviewType.MIXED: {
        InterviewStage.INTRODUCTION: 0.08,
        InterviewStage.CANDIDATE_BACKGROUND: 0.10,
        InterviewStage.RESUME_DISCUSSION: 0.15,
        InterviewStage.PROJECT_DEEP_DIVE: 0.17,
        InterviewStage.ROLE_SPECIFIC: 0.20,
        InterviewStage.BEHAVIORAL: 0.15,
        InterviewStage.ADAPTIVE_PROBING: 0.07,
        InterviewStage.CLOSING: 0.08,
    },
    InterviewType.TECHNICAL: {
        InterviewStage.INTRODUCTION: 0.08,
        InterviewStage.CANDIDATE_BACKGROUND: 0.0,
        InterviewStage.RESUME_DISCUSSION: 0.12,
        InterviewStage.PROJECT_DEEP_DIVE: 0.25,
        InterviewStage.ROLE_SPECIFIC: 0.32,
        InterviewStage.BEHAVIORAL: 0.0,
        InterviewStage.ADAPTIVE_PROBING: 0.15,
        InterviewStage.CLOSING: 0.08,
    },
    InterviewType.BEHAVIORAL: {
        InterviewStage.INTRODUCTION: 0.08,
        InterviewStage.CANDIDATE_BACKGROUND: 0.17,
        InterviewStage.RESUME_DISCUSSION: 0.15,
        InterviewStage.PROJECT_DEEP_DIVE: 0.0,
        InterviewStage.ROLE_SPECIFIC: 0.0,
        InterviewStage.BEHAVIORAL: 0.42,
        InterviewStage.ADAPTIVE_PROBING: 0.10,
        InterviewStage.CLOSING: 0.08,
    },
}

# Which evaluation criteria apply per question type. Criteria absent for
# a type are stored as NULL and excluded from readiness aggregation -
# never zero-filled, never guessed.
EVALUATION_PROFILES: dict[QuestionType, frozenset[str]] = {
    QuestionType.INTRODUCTORY: frozenset(
        {"relevance_score", "clarity_score", "communication_score", "answer_structure_score"}
    ),
    QuestionType.RESUME: frozenset(
        {
            "relevance_score",
            "clarity_score",
            "specificity_score",
            "evidence_score",
            "communication_score",
            "answer_structure_score",
        }
    ),
    QuestionType.PROJECT: frozenset(
        {
            "relevance_score",
            "clarity_score",
            "technical_depth_score",
            "specificity_score",
            "evidence_score",
            "problem_solving_score",
            "communication_score",
            "answer_structure_score",
        }
    ),
    QuestionType.TECHNICAL: frozenset(
        {
            "relevance_score",
            "clarity_score",
            "technical_depth_score",
            "specificity_score",
            "problem_solving_score",
            "communication_score",
        }
    ),
    QuestionType.BEHAVIORAL: frozenset(
        {
            "relevance_score",
            "clarity_score",
            "specificity_score",
            "evidence_score",
            "communication_score",
            "answer_structure_score",
        }
    ),
    QuestionType.SITUATIONAL: frozenset(
        {
            "relevance_score",
            "clarity_score",
            "problem_solving_score",
            "communication_score",
            "answer_structure_score",
        }
    ),
    QuestionType.FOLLOW_UP: frozenset(
        {
            "relevance_score",
            "clarity_score",
            "specificity_score",
            "evidence_score",
            "communication_score",
        }
    ),
    QuestionType.CLAIM_VERIFICATION: frozenset(
        {
            "relevance_score",
            "clarity_score",
            "technical_depth_score",
            "specificity_score",
            "evidence_score",
        }
    ),
}

ALL_CRITERIA: tuple[str, ...] = (
    "relevance_score",
    "clarity_score",
    "technical_depth_score",
    "specificity_score",
    "evidence_score",
    "problem_solving_score",
    "communication_score",
    "answer_structure_score",
)
