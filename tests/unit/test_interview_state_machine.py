"""Deterministic tests for the interview state machine and adaptive
decision engine - including identical-input replay verification."""

from __future__ import annotations

import pytest

from app.services.interview.enums import (
    STAGE_ORDER,
    InterviewAction,
    InterviewStage,
    InterviewType,
)
from app.services.interview.state_machine import (
    FALLBACK_QUESTIONS,
    MAX_FOLLOW_UP_STREAK,
    EngineState,
    allocate_stage_budgets,
    compute_question_budget,
    decide_next_action,
    is_duplicate_question,
    next_stage,
    normalize_question_text,
    planned_stages,
)


def make_state(**overrides) -> EngineState:
    defaults = dict(
        stage=InterviewStage.ROLE_SPECIFIC,
        interview_type=InterviewType.MIXED,
        questions_asked_total=4,
        questions_asked_in_stage=1,
        question_budget=12,
        stage_budgets=allocate_stage_budgets(InterviewType.MIXED, 12),
        follow_up_streak=0,
    )
    defaults.update(overrides)
    return EngineState(**defaults)


class TestBudgets:
    def test_question_budget_from_duration(self) -> None:
        assert compute_question_budget(5) == 3  # clamped up
        assert compute_question_budget(20) == 10
        assert compute_question_budget(60) == 30

    @pytest.mark.parametrize("interview_type", list(InterviewType))
    @pytest.mark.parametrize("budget", [3, 4, 6, 8, 10, 12, 20, 30])
    def test_allocation_sums_exactly_with_minimums(
        self, interview_type: InterviewType, budget: int
    ) -> None:
        budgets = allocate_stage_budgets(interview_type, budget)
        assert sum(budgets.values()) == budget
        assert all(value >= 1 for value in budgets.values())
        # Zero-fraction stages never appear in the plan.
        assert all(stage in planned_stages(interview_type) for stage in budgets)

    def test_small_budget_keeps_anchors(self) -> None:
        budgets = allocate_stage_budgets(InterviewType.MIXED, 3)
        assert InterviewStage.INTRODUCTION in budgets
        assert InterviewStage.CLOSING in budgets
        assert len(budgets) == 3

    def test_technical_plan_skips_behavioral(self) -> None:
        plan = planned_stages(InterviewType.TECHNICAL)
        assert InterviewStage.BEHAVIORAL not in plan
        assert InterviewStage.CANDIDATE_BACKGROUND not in plan

    def test_allocation_is_deterministic(self) -> None:
        first = allocate_stage_budgets(InterviewType.MIXED, 11)
        for _ in range(20):
            assert allocate_stage_budgets(InterviewType.MIXED, 11) == first


class TestStageMovement:
    def test_next_stage_is_forward_only(self) -> None:
        plan = planned_stages(InterviewType.MIXED)
        assert next_stage(InterviewStage.INTRODUCTION, plan) == (
            InterviewStage.CANDIDATE_BACKGROUND
        )
        assert next_stage(InterviewStage.CLOSING, plan) == InterviewStage.COMPLETED
        # Plans never emit an earlier stage.
        for stage in plan[:-1]:
            successor = next_stage(stage, plan)
            assert STAGE_ORDER.index(successor) > STAGE_ORDER.index(stage)

    def test_next_stage_respects_shrunk_plan(self) -> None:
        budgets = allocate_stage_budgets(InterviewType.MIXED, 3)
        plan = tuple(stage for stage in STAGE_ORDER if stage in budgets)
        middle = [s for s in plan if s not in (InterviewStage.INTRODUCTION, InterviewStage.CLOSING)]
        assert next_stage(InterviewStage.INTRODUCTION, plan) == middle[0]


class TestDecideNextAction:
    def test_total_budget_forces_close(self) -> None:
        decision = decide_next_action(
            make_state(questions_asked_total=12), "ASK_FOLLOW_UP"
        )
        assert decision.action is InterviewAction.CLOSE_INTERVIEW
        assert decision.next_stage is InterviewStage.COMPLETED
        assert decision.recommendation_overridden is True

    def test_closing_stage_completion_forces_close(self) -> None:
        decision = decide_next_action(
            make_state(stage=InterviewStage.CLOSING, questions_asked_in_stage=1),
            "ASK_FOLLOW_UP",
        )
        assert decision.action is InterviewAction.CLOSE_INTERVIEW

    def test_stage_budget_forces_advance(self) -> None:
        stage_budget = allocate_stage_budgets(InterviewType.MIXED, 12)[
            InterviewStage.ROLE_SPECIFIC
        ]
        assert stage_budget >= 1
        state = make_state(questions_asked_in_stage=stage_budget)
        decision = decide_next_action(state, "ASK_FOLLOW_UP")
        assert decision.action is InterviewAction.ADVANCE_STAGE
        assert decision.next_stage is InterviewStage.BEHAVIORAL

    def test_follow_up_streak_coerced_to_change_topic(self) -> None:
        decision = decide_next_action(
            make_state(follow_up_streak=MAX_FOLLOW_UP_STREAK), "PROBE_VAGUE_ANSWER"
        )
        assert decision.action is InterviewAction.CHANGE_TOPIC
        assert decision.recommendation_overridden is True
        assert "streak" in (decision.override_reason or "")

    def test_valid_recommendation_accepted(self) -> None:
        decision = decide_next_action(make_state(), "VERIFY_CLAIM")
        assert decision.action is InterviewAction.VERIFY_CLAIM
        assert decision.recommendation_overridden is False
        assert decision.next_stage is InterviewStage.ROLE_SPECIFIC

    def test_stage_disallowed_recommendation_overridden(self) -> None:
        # EXPLORE_PROJECT is not allowed in ROLE_SPECIFIC.
        decision = decide_next_action(make_state(), "EXPLORE_PROJECT")
        assert decision.action is InterviewAction.CHANGE_TOPIC
        assert decision.recommendation_overridden is True

    @pytest.mark.parametrize("bad", [None, "", "BECOME_SENTIENT", "close_interview", "42"])
    def test_missing_or_garbage_recommendation_safe_default(self, bad) -> None:
        decision = decide_next_action(make_state(), bad)
        assert decision.action is InterviewAction.CHANGE_TOPIC
        assert decision.next_stage is InterviewStage.ROLE_SPECIFIC

    def test_advance_out_of_last_stage_closes(self) -> None:
        state = make_state(stage=InterviewStage.CLOSING, questions_asked_in_stage=0)
        decision = decide_next_action(state, "ADVANCE_STAGE")
        # CLOSING only allows CLOSE_INTERVIEW; ADVANCE is coerced but the
        # target past CLOSING is COMPLETED either way.
        assert decision.next_stage in (InterviewStage.COMPLETED, InterviewStage.CLOSING)

    def test_identical_inputs_identical_decisions_replay(self) -> None:
        state = make_state(follow_up_streak=1, questions_asked_total=7)
        first = decide_next_action(state, "ASK_FOLLOW_UP")
        for _ in range(50):
            assert decide_next_action(state, "ASK_FOLLOW_UP") == first


class TestDuplicatePrevention:
    def test_normalization(self) -> None:
        assert normalize_question_text("  Tell me about C++?! ") == "tell me about c"
        assert normalize_question_text("TELL me   about\tC") == "tell me about c"

    def test_duplicate_detection_ignores_punctuation_and_case(self) -> None:
        asked = {normalize_question_text("What did you build at Example Corp?")}
        assert is_duplicate_question("what did you BUILD at example corp", asked)
        assert not is_duplicate_question("What did you learn at Example Corp?", asked)

    def test_fallback_questions_cover_every_asking_stage(self) -> None:
        asking_stages = [s for s in STAGE_ORDER if s not in (InterviewStage.COMPLETED,)]
        assert set(FALLBACK_QUESTIONS) == set(asking_stages)
