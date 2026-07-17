"""Strict output schemas for the interview AI tasks (Phase 8).

Versioned contracts:
  * ``ANSWER_EVALUATION_SCHEMA_VERSION``  - per-answer evaluation
  * ``INTERVIEW_QUESTION_SCHEMA_VERSION`` - next-question generation
  * ``INTERVIEW_REPORT_SCHEMA_VERSION``   - report narrative

Design rules (same as Phase 4): required fields with simple types
(structured-output reliability), score ranges enforced by the schema,
enums as Literals so an out-of-vocabulary action/type fails validation
rather than reaching the state machine, and NO free-form reasoning
fields - ``interviewer_observation`` is the short, professional,
user-facing product observation defined by the spec, never hidden
chain-of-thought (the prompt forbids revealing reasoning, and no schema
field exists to carry it).

All eight criterion scores are required ints 0-100; the BACKEND decides
which apply to the question type (EVALUATION_PROFILES) and stores the
rest as NULL - the model never decides applicability.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

ANSWER_EVALUATION_SCHEMA_VERSION = "answer-evaluation-1.0.0"
INTERVIEW_QUESTION_SCHEMA_VERSION = "interview-question-1.0.0"
INTERVIEW_REPORT_SCHEMA_VERSION = "interview-report-1.0.0"

ActionLiteral = Literal[
    "ASK_FOLLOW_UP",
    "PROBE_VAGUE_ANSWER",
    "VERIFY_CLAIM",
    "EXPLORE_PROJECT",
    "INCREASE_DIFFICULTY",
    "DECREASE_DIFFICULTY",
    "CHANGE_TOPIC",
    "ADVANCE_STAGE",
    "CLARIFY_QUESTION",
    "CLOSE_INTERVIEW",
]

QuestionTypeLiteral = Literal[
    "INTRODUCTORY",
    "RESUME",
    "PROJECT",
    "TECHNICAL",
    "BEHAVIORAL",
    "SITUATIONAL",
    "FOLLOW_UP",
    "CLAIM_VERIFICATION",
]

DifficultyLiteral = Literal["EASY", "MEDIUM", "HARD"]


class AnswerEvaluationOutput(BaseModel):
    relevance_score: int = Field(ge=0, le=100)
    clarity_score: int = Field(ge=0, le=100)
    technical_depth_score: int = Field(ge=0, le=100)
    specificity_score: int = Field(ge=0, le=100)
    evidence_score: int = Field(ge=0, le=100)
    problem_solving_score: int = Field(ge=0, le=100)
    communication_score: int = Field(ge=0, le=100)
    answer_structure_score: int = Field(ge=0, le=100)
    confidence_estimate: int = Field(
        ge=0,
        le=100,
        description=(
            "How well-supported and self-consistent the ANSWER CONTENT is - an "
            "assessment of the answer, never a psychological claim about the person."
        ),
    )
    strengths: list[str] = Field(description="1-4 specific strengths of this answer.")
    weaknesses: list[str] = Field(description="1-4 specific weaknesses of this answer.")
    supporting_evidence: list[str] = Field(
        description=(
            "Short verbatim excerpts from the candidate's answer that support "
            "your assessment (empty list if none)."
        )
    )
    unsupported_claims: list[str] = Field(
        description="Claims made without support or contradicting earlier answers."
    )
    missing_concepts: list[str] = Field(
        description="Concepts a strong answer would have covered but this one did not."
    )
    improvement_suggestions: list[str] = Field(
        description="1-3 concrete ways this specific answer could be improved."
    )
    follow_up_required: bool
    follow_up_reason: str = Field(
        description="Why a follow-up is (or is not) warranted; empty string if none."
    )
    recommended_action: ActionLiteral
    target_topic: str = Field(
        description="Topic the recommended action should address; empty string if N/A."
    )
    interviewer_observation: str = Field(
        description=(
            "A short, professional, evidence-based observation safe to show the "
            "candidate (1-2 sentences)."
        )
    )
    new_topics: list[str] = Field(
        description="Topics the answer opened that were not previously discussed."
    )
    skills_covered: list[str] = Field(
        description="Concrete skills this answer demonstrated or claimed."
    )
    user_corrections: list[str] = Field(
        description=(
            "Statements where the candidate corrected or amended something they "
            "said earlier (empty list if none)."
        )
    )


class InterviewQuestionOutput(BaseModel):
    question_text: str = Field(
        description=(
            "Exactly ONE clear interview question (may include one short lead-in "
            "sentence referencing an earlier answer). Professional, neutral tone."
        )
    )
    question_type: QuestionTypeLiteral
    topic: str = Field(description="The topic this question explores, 1-5 words.")
    difficulty: DifficultyLiteral


class ReportHighlight(BaseModel):
    question: str = Field(description="The question, verbatim or lightly shortened.")
    reason: str = Field(description="Why this answer stood out (evidence-based).")


class InterviewReportNarrativeOutput(BaseModel):
    overview: str = Field(
        description="4-7 sentence professional overview of the interview performance."
    )
    technical_observations: list[str] = Field(
        description="2-6 evidence-based observations about technical performance."
    )
    behavioral_observations: list[str] = Field(
        description="2-6 evidence-based observations about behavioral/communication performance."
    )
    strongest_answers: list[ReportHighlight] = Field(description="1-3 strongest answers.")
    weakest_answers: list[ReportHighlight] = Field(description="1-3 weakest answers.")
    improvement_roadmap: list[str] = Field(
        description=(
            "3-6 prioritized, evidence-referencing improvement steps - each must "
            "say WHY it matters, citing patterns from this interview. Never "
            "generic advice like 'practice more'."
        )
    )
    recommendations: list[str] = Field(
        description="2-5 concrete practice recommendations for the next interview."
    )
