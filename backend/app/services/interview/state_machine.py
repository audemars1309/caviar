"""The interview state machine and adaptive decision engine (Phase 8).

Pure, deterministic functions - no I/O, no AI, no randomness, no clock.
Identical inputs always produce identical decisions (verified by replay
tests). Gemini's ``recommended_action`` is exactly one input among
several; every rule below can override it, and the backend's decision is
final.

Decision order (each rule beats everything after it):
  1. Total question budget exhausted            -> CLOSE_INTERVIEW
  2. In CLOSING with its budget used            -> CLOSE_INTERVIEW
  3. Stage budget exhausted                     -> ADVANCE_STAGE
  4. Follow-up streak at the cap (loop guard)   -> follow-up recommendations
                                                   are coerced to CHANGE_TOPIC
  5. Recommendation valid for the current stage -> accepted
  6. Otherwise                                  -> CHANGE_TOPIC (safe default)

Stage movement is forward-only along STAGE_ORDER, skipping stages whose
allocation for the interview type is zero - backward transitions and
plan-external stages are unrepresentable outputs, not merely forbidden.

Duplicate-question prevention is deterministic: questions are normalized
(casefold, punctuation and whitespace collapsed) and checked against the
already-asked set; the question generator gets ONE regeneration with an
explicit no-repeat notice, after which a deterministic stage-appropriate
fallback question is used. No loops, no unbounded retries.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.services.interview.enums import (
    ALLOWED_ACTIONS_BY_STAGE,
    FOLLOW_UP_ACTIONS,
    STAGE_ALLOCATION,
    STAGE_ORDER,
    InterviewAction,
    InterviewStage,
    InterviewType,
    QuestionType,
)

MAX_FOLLOW_UP_STREAK = 2

_NORMALIZE_PATTERN = re.compile(r"[^a-z0-9 ]+")
_WHITESPACE_PATTERN = re.compile(r"\s+")


def compute_question_budget(duration_minutes: int) -> int:
    """~2 minutes per question, clamped to the schema bounds."""
    return max(3, min(30, duration_minutes // 2))


def allocate_stage_budgets(
    interview_type: InterviewType, question_budget: int
) -> dict[InterviewStage, int]:
    """Deterministic largest-remainder allocation of the total budget
    across the type's stage plan. Every planned stage gets at least 1
    question; zero-allocation stages are skipped entirely; the result
    sums exactly to ``question_budget``.

    When the budget is smaller than the number of planned stages, the
    plan itself shrinks deterministically: INTRODUCTION and CLOSING are
    always kept, and the highest-fraction middle stages fill the
    remaining slots (ties broken by stage order)."""
    fractions = STAGE_ALLOCATION[interview_type]
    planned = [stage for stage in STAGE_ORDER if fractions.get(stage, 0.0) > 0.0]
    if question_budget < len(planned):
        anchors = [
            stage
            for stage in (InterviewStage.INTRODUCTION, InterviewStage.CLOSING)
            if stage in planned
        ]
        middles = [stage for stage in planned if stage not in anchors]
        keep = max(question_budget - len(anchors), 0)
        chosen = sorted(
            middles, key=lambda s: (-fractions[s], STAGE_ORDER.index(s))
        )[:keep]
        planned = [stage for stage in STAGE_ORDER if stage in set(anchors) | set(chosen)]
        planned = planned[:question_budget]  # degenerate budgets < 2
    raw = {stage: question_budget * fractions[stage] for stage in planned}
    budgets = {stage: max(1, int(raw[stage])) for stage in planned}

    def _total() -> int:
        return sum(budgets.values())

    # Largest-remainder top-up / smallest-remainder trim to hit the exact
    # total, never trimming a stage below 1. Ties break by STAGE_ORDER -
    # fully deterministic.
    while _total() < question_budget:
        candidate = max(planned, key=lambda s: (raw[s] - budgets[s], -planned.index(s)))
        budgets[candidate] += 1
    while _total() > question_budget:
        trimmable = [stage for stage in planned if budgets[stage] > 1]
        candidate = min(trimmable, key=lambda s: (raw[s] - budgets[s], planned.index(s)))
        budgets[candidate] -= 1
    return budgets


def planned_stages(interview_type: InterviewType) -> tuple[InterviewStage, ...]:
    fractions = STAGE_ALLOCATION[interview_type]
    return tuple(stage for stage in STAGE_ORDER if fractions.get(stage, 0.0) > 0.0)


def next_stage(
    current: InterviewStage, plan: tuple[InterviewStage, ...]
) -> InterviewStage:
    """The next stage in ``plan`` strictly after ``current`` (forward-only
    by construction: ``plan`` is in STAGE_ORDER and only later entries are
    considered)."""
    current_index = STAGE_ORDER.index(current)
    for stage in plan:
        if STAGE_ORDER.index(stage) > current_index:
            return stage
    return InterviewStage.COMPLETED


@dataclass(frozen=True)
class EngineState:
    """Everything the decision needs, as plain data."""

    stage: InterviewStage
    interview_type: InterviewType
    questions_asked_total: int
    questions_asked_in_stage: int
    question_budget: int
    stage_budgets: dict[InterviewStage, int]
    follow_up_streak: int


@dataclass(frozen=True)
class EngineDecision:
    action: InterviewAction
    next_stage: InterviewStage
    recommendation_overridden: bool
    override_reason: str | None


def decide_next_action(
    state: EngineState, recommended_action: str | None
) -> EngineDecision:
    """The adaptive decision. Pure and total: any recommendation string
    (valid, invalid, or absent) produces exactly one legal decision."""

    def _decision(
        action: InterviewAction, *, overridden: bool, reason: str | None
    ) -> EngineDecision:
        if action is InterviewAction.CLOSE_INTERVIEW:
            target = InterviewStage.COMPLETED
        elif action is InterviewAction.ADVANCE_STAGE:
            # Advance within the ALLOCATED plan (which may have been
            # shrunk for small budgets), not the full type plan.
            plan = tuple(
                stage for stage in STAGE_ORDER if stage in state.stage_budgets
            )
            target = next_stage(state.stage, plan)
        else:
            target = state.stage
        # Advancing out of the last content stage lands on CLOSING per the
        # plan; advancing out of CLOSING closes.
        if target is InterviewStage.COMPLETED and action is InterviewAction.ADVANCE_STAGE:
            action = InterviewAction.CLOSE_INTERVIEW
        return EngineDecision(
            action=action,
            next_stage=target,
            recommendation_overridden=overridden,
            override_reason=reason,
        )

    # Rule 1: total budget.
    if state.questions_asked_total >= state.question_budget:
        return _decision(
            InterviewAction.CLOSE_INTERVIEW,
            overridden=recommended_action != InterviewAction.CLOSE_INTERVIEW,
            reason="Total question budget exhausted.",
        )
    # Rule 2: closing stage complete.
    stage_budget = state.stage_budgets.get(state.stage, 1)
    if (
        state.stage is InterviewStage.CLOSING
        and state.questions_asked_in_stage >= stage_budget
    ):
        return _decision(
            InterviewAction.CLOSE_INTERVIEW,
            overridden=recommended_action != InterviewAction.CLOSE_INTERVIEW,
            reason="Closing stage complete.",
        )
    # Rule 3: stage budget.
    if state.questions_asked_in_stage >= stage_budget:
        return _decision(
            InterviewAction.ADVANCE_STAGE,
            overridden=recommended_action != InterviewAction.ADVANCE_STAGE,
            reason="Stage question budget exhausted.",
        )

    # Parse the recommendation (untrusted model output).
    parsed: InterviewAction | None
    try:
        parsed = InterviewAction(recommended_action) if recommended_action else None
    except ValueError:
        parsed = None

    # Rule 4: follow-up loop guard.
    if parsed in FOLLOW_UP_ACTIONS and state.follow_up_streak >= MAX_FOLLOW_UP_STREAK:
        return _decision(
            InterviewAction.CHANGE_TOPIC,
            overridden=True,
            reason=f"Follow-up streak limit ({MAX_FOLLOW_UP_STREAK}) reached.",
        )
    # Rule 5: valid recommendation for this stage.
    if parsed is not None and parsed in ALLOWED_ACTIONS_BY_STAGE[state.stage]:
        return _decision(parsed, overridden=False, reason=None)
    # Rule 6: safe default.
    return _decision(
        InterviewAction.CHANGE_TOPIC,
        overridden=True,
        reason="Recommendation missing or not allowed in the current stage.",
    )


def normalize_question_text(text: str) -> str:
    """Deterministic normalization for duplicate detection."""
    lowered = _NORMALIZE_PATTERN.sub(" ", text.casefold())
    return _WHITESPACE_PATTERN.sub(" ", lowered).strip()


def is_duplicate_question(text: str, asked_normalized: set[str]) -> bool:
    return normalize_question_text(text) in asked_normalized


# Deterministic per-stage fallback questions - used only when the model
# produced a duplicate twice. Generic by necessity, but stage-appropriate
# and guaranteed loop-free.
FALLBACK_QUESTIONS: dict[InterviewStage, tuple[str, QuestionType]] = {
    InterviewStage.INTRODUCTION: (
        "To begin, could you briefly introduce yourself and your background?",
        QuestionType.INTRODUCTORY,
    ),
    InterviewStage.CANDIDATE_BACKGROUND: (
        "What part of your background are you most proud of, and why?",
        QuestionType.INTRODUCTORY,
    ),
    InterviewStage.RESUME_DISCUSSION: (
        "Walk me through the most significant item on your resume and your role in it.",
        QuestionType.RESUME,
    ),
    InterviewStage.PROJECT_DEEP_DIVE: (
        "Pick one project you built: what problem did it solve, and what did you "
        "personally implement?",
        QuestionType.PROJECT,
    ),
    InterviewStage.ROLE_SPECIFIC: (
        "Describe a technical decision you made recently and the trade-offs you weighed.",
        QuestionType.TECHNICAL,
    ),
    InterviewStage.BEHAVIORAL: (
        "Tell me about a time you received difficult feedback and what you did next.",
        QuestionType.BEHAVIORAL,
    ),
    InterviewStage.ADAPTIVE_PROBING: (
        "Of the topics we discussed, which would you approach differently now, and how?",
        QuestionType.SITUATIONAL,
    ),
    InterviewStage.CLOSING: (
        "Before we wrap up, is there anything important we have not covered that you "
        "would like to add?",
        QuestionType.INTRODUCTORY,
    ),
}
