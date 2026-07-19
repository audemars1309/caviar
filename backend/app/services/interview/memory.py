"""Structured interview memory (Phase 8).

The memory is a typed structure persisted on ``interview_memories`` -
never a growing prompt string. Prompt context is assembled fresh each
turn from three bounded pieces: (1) the static candidate/job summaries
captured at session start, (2) compact structured state (topics, skills,
strengths, weaknesses, follow-ups, corrections, confidence trend), and
(3) a bounded recent-turns window (the last ``RECENT_TURNS_WINDOW``
question/answer-summary pairs). Full conversation history lives in the
database, not in prompts.

``apply_evaluation_to_memory`` is deterministic: given the same memory
and the same validated evaluation, it produces the same updated memory
(verified by replay tests). All list fields are de-duplicated
order-preservingly and bounded so memory cannot grow without limit.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any

RECENT_TURNS_WINDOW = 6
_LIST_CAP = 30
_TURN_SUMMARY_CHARS = 400


def _merge(existing: list[str], additions: list[str], cap: int = _LIST_CAP) -> list[str]:
    merged = dict.fromkeys(item.strip() for item in existing if item and item.strip())
    for item in additions:
        cleaned = item.strip()
        if cleaned:
            merged.setdefault(cleaned, None)
    return list(merged)[:cap]


@dataclass(frozen=True)
class MemoryState:
    """Plain-data mirror of the interview_memories row."""

    candidate_profile_summary: str | None = None
    resume_evidence_summary: str | None = None
    job_requirements_summary: str | None = None
    topics_explored: list[str] = field(default_factory=list)
    topics_pending: list[str] = field(default_factory=list)
    questions_asked: list[str] = field(default_factory=list)  # normalized text
    skills_covered: list[str] = field(default_factory=list)
    strong_areas: list[str] = field(default_factory=list)
    weak_areas: list[str] = field(default_factory=list)
    verified_evidence: list[str] = field(default_factory=list)
    contradictions: list[str] = field(default_factory=list)
    follow_up_opportunities: list[str] = field(default_factory=list)
    user_corrections: list[str] = field(default_factory=list)
    confidence_trend: list[int] = field(default_factory=list)
    recent_turns: list[dict[str, Any]] = field(default_factory=list)


def apply_evaluation_to_memory(
    memory: MemoryState,
    *,
    question_text: str,
    question_normalized: str,
    question_topic: str | None,
    transcript: str,
    evaluation: dict[str, Any],
) -> MemoryState:
    """Deterministically fold one evaluated answer into memory.

    ``evaluation`` is the already-validated AI evaluation as a plain dict
    (strengths, weaknesses, supporting_evidence, unsupported_claims,
    confidence_estimate, follow_up_reason, memory topics/skills/
    corrections). Untrusted content stays quoted data inside memory; it
    is re-wrapped in trust markers whenever it later enters a prompt.
    """
    turn = {
        "question": question_text[:_TURN_SUMMARY_CHARS],
        "answer_summary": transcript[:_TURN_SUMMARY_CHARS],
        "observation": (evaluation.get("interviewer_observation") or "")[:_TURN_SUMMARY_CHARS],
    }
    recent = (memory.recent_turns + [turn])[-RECENT_TURNS_WINDOW:]

    confidence = evaluation.get("confidence_estimate")
    trend = list(memory.confidence_trend)
    if isinstance(confidence, int):
        trend = (trend + [confidence])[-_LIST_CAP:]

    follow_ups = []
    if evaluation.get("follow_up_required") and evaluation.get("follow_up_reason"):
        follow_ups.append(str(evaluation["follow_up_reason"]))

    new_topics = [str(item) for item in evaluation.get("new_topics", [])]
    explored = _merge(
        memory.topics_explored, ([question_topic] if question_topic else []) + new_topics
    )

    return replace(
        memory,
        topics_explored=explored,
        topics_pending=[t for t in memory.topics_pending if t not in explored],
        questions_asked=_merge(memory.questions_asked, [question_normalized], cap=60),
        skills_covered=_merge(
            memory.skills_covered,
            [str(item) for item in evaluation.get("skills_covered", [])],
        ),
        strong_areas=_merge(
            memory.strong_areas, [str(item) for item in evaluation.get("strengths", [])]
        ),
        weak_areas=_merge(
            memory.weak_areas, [str(item) for item in evaluation.get("weaknesses", [])]
        ),
        verified_evidence=_merge(
            memory.verified_evidence,
            [str(item) for item in evaluation.get("supporting_evidence", [])],
        ),
        contradictions=_merge(
            memory.contradictions,
            [str(item) for item in evaluation.get("unsupported_claims", [])],
        ),
        follow_up_opportunities=_merge(memory.follow_up_opportunities, follow_ups, cap=10),
        user_corrections=_merge(
            memory.user_corrections,
            [str(item) for item in evaluation.get("user_corrections", [])],
            cap=10,
        ),
        confidence_trend=trend,
        recent_turns=recent,
    )


def memory_context_payload(memory: MemoryState) -> dict[str, Any]:
    """The compact, bounded, structured context sent to the model each
    turn (as JSON inside trust markers) - never a concatenated history."""
    return {
        "topics_explored": memory.topics_explored[:20],
        "topics_pending": memory.topics_pending[:10],
        "skills_covered": memory.skills_covered[:20],
        "strong_areas": memory.strong_areas[:10],
        "weak_areas": memory.weak_areas[:10],
        "follow_up_opportunities": memory.follow_up_opportunities[:5],
        "user_corrections": memory.user_corrections[:5],
        "contradictions": memory.contradictions[:8],
        "confidence_trend": memory.confidence_trend[-8:],
        "recent_turns": memory.recent_turns[-RECENT_TURNS_WINDOW:],
    }
