"""Deterministic tests for interview memory, the readiness engine, and
speech metrics."""

from __future__ import annotations

import pytest

from app.services.interview.memory import (
    RECENT_TURNS_WINDOW,
    MemoryState,
    apply_evaluation_to_memory,
    memory_context_payload,
)
from app.services.interview.readiness import (
    AnswerScores,
    ReadinessInputError,
    compute_readiness,
    readiness_level_for,
)
from app.services.speech.metrics import TimedWord, compute_speech_metrics


def _evaluation(**overrides) -> dict:
    payload = {
        "interviewer_observation": "Clear answer with a concrete example.",
        "confidence_estimate": 72,
        "follow_up_required": True,
        "follow_up_reason": "Quantify the latency claim.",
        "new_topics": ["connection pooling"],
        "skills_covered": ["FastAPI"],
        "strengths": ["Concrete example"],
        "weaknesses": ["No metrics"],
        "supporting_evidence": ["we tuned the pool size"],
        "unsupported_claims": [],
        "user_corrections": [],
    }
    payload.update(overrides)
    return payload


class TestInterviewMemory:
    def test_update_is_deterministic_replay(self) -> None:
        memory = MemoryState(topics_pending=["EXPERIENCE", "PROJECTS"])
        kwargs = dict(
            question_text="Tell me about the ingestion service.",
            question_normalized="tell me about the ingestion service",
            question_topic="EXPERIENCE",
            transcript="We built an async ingestion service...",
            evaluation=_evaluation(),
        )
        first = apply_evaluation_to_memory(memory, **kwargs)
        for _ in range(25):
            assert apply_evaluation_to_memory(memory, **kwargs) == first
        assert "EXPERIENCE" in first.topics_explored
        assert "EXPERIENCE" not in first.topics_pending  # moved, not duplicated
        assert first.questions_asked == ["tell me about the ingestion service"]
        assert first.confidence_trend == [72]
        assert first.follow_up_opportunities == ["Quantify the latency claim."]

    def test_recent_turns_window_is_bounded(self) -> None:
        memory = MemoryState()
        for index in range(RECENT_TURNS_WINDOW + 4):
            memory = apply_evaluation_to_memory(
                memory,
                question_text=f"Question {index}",
                question_normalized=f"question {index}",
                question_topic=None,
                transcript=f"Answer {index}",
                evaluation=_evaluation(),
            )
        assert len(memory.recent_turns) == RECENT_TURNS_WINDOW
        assert memory.recent_turns[-1]["question"] == f"Question {RECENT_TURNS_WINDOW + 3}"
        assert memory.recent_turns[0]["question"] == "Question 4"

    def test_lists_deduplicate_preserving_order(self) -> None:
        memory = MemoryState(strong_areas=["Concrete example"])
        updated = apply_evaluation_to_memory(
            memory,
            question_text="Q",
            question_normalized="q",
            question_topic=None,
            transcript="A",
            evaluation=_evaluation(strengths=["Concrete example", "Good structure"]),
        )
        assert updated.strong_areas == ["Concrete example", "Good structure"]

    def test_context_payload_is_bounded(self) -> None:
        memory = MemoryState(
            topics_explored=[f"topic-{i}" for i in range(50)],
            confidence_trend=list(range(30)),
        )
        payload = memory_context_payload(memory)
        assert len(payload["topics_explored"]) == 20
        assert len(payload["confidence_trend"]) == 8
        assert payload["confidence_trend"][-1] == 29


def _answer(difficulty: str = "MEDIUM", **scores) -> AnswerScores:
    base: dict[str, int | None] = {
        "relevance_score": 70,
        "clarity_score": 70,
        "technical_depth_score": None,
        "specificity_score": 70,
        "evidence_score": 70,
        "problem_solving_score": None,
        "communication_score": 70,
        "answer_structure_score": 70,
    }
    base.update(scores)
    return AnswerScores(scores=base, difficulty=difficulty)


class TestReadiness:
    def test_uniform_scores_and_null_exclusion(self) -> None:
        result = compute_readiness([_answer(), _answer()])
        by_name = {c.category: c for c in result.categories}
        assert by_name["COMMUNICATION"].score == 70
        # No answer carried technical depth: category unscored, excluded.
        assert by_name["TECHNICAL_DEPTH"].score is None
        assert by_name["TECHNICAL_DEPTH"].sample_count == 0
        assert result.overall_score == 70  # renormalized over scored categories
        assert result.readiness_level == "READY"
        assert result.algorithm_version == "interview-readiness-1.0.0"

    def test_difficulty_weighting(self) -> None:
        answers = [
            _answer("EASY", communication_score=60),
            _answer("HARD", communication_score=90),
        ]
        result = compute_readiness(answers)
        communication = next(c for c in result.categories if c.category == "COMMUNICATION")
        # (60*0.8 + 90*1.2) / 2.0 = 78
        assert communication.score == 78

    def test_outlier_trim_at_four_samples(self) -> None:
        answers = [
            _answer(communication_score=score) for score in (10, 70, 72, 95)
        ]
        result = compute_readiness(answers)
        communication = next(c for c in result.categories if c.category == "COMMUNICATION")
        assert communication.score == 71  # 10 and 95 dropped
        assert communication.sample_count == 2

    def test_no_scored_categories_yields_honest_none(self) -> None:
        empty = AnswerScores(
            scores={key: None for key in _answer().scores}, difficulty="MEDIUM"
        )
        result = compute_readiness([empty])
        assert result.overall_score is None
        assert result.readiness_level is None

    def test_thresholds(self) -> None:
        assert readiness_level_for(44) == "NOT_READY"
        assert readiness_level_for(45) == "DEVELOPING"
        assert readiness_level_for(60) == "READY"
        assert readiness_level_for(75) == "STRONG"
        assert readiness_level_for(100) == "STRONG"

    def test_malformed_inputs_rejected(self) -> None:
        with pytest.raises(ReadinessInputError):
            compute_readiness([_answer(communication_score=101)])
        with pytest.raises(ReadinessInputError):
            compute_readiness([_answer("IMPOSSIBLE")])
        with pytest.raises(ReadinessInputError):
            compute_readiness(
                [AnswerScores(scores={"vibes_score": 50}, difficulty="MEDIUM")]
            )

    def test_replay_determinism(self) -> None:
        answers = [
            _answer("EASY", communication_score=61),
            _answer("HARD", technical_depth_score=88, communication_score=79),
            _answer(communication_score=70),
            _answer(communication_score=90),
        ]
        first = compute_readiness(answers)
        for _ in range(50):
            assert compute_readiness(list(answers)) == first


def _word(text: str, start: float, end: float) -> TimedWord:
    return TimedWord(word=text, start=start, end=end)


class TestSpeechMetrics:
    def test_full_metric_computation(self) -> None:
        words = [
            _word("Um,", 0.0, 0.3),
            _word("I", 0.4, 0.5),
            _word("I", 0.6, 0.7),
            _word("built", 0.8, 1.1),
            _word("the", 1.2, 1.4),
            _word("service", 3.2, 3.7),  # 1.8s long pause before
            _word("you", 3.8, 3.9),
            _word("know", 4.0, 4.2),
            _word("quickly", 4.7, 5.1),  # 0.5s pause
        ]
        metrics = compute_speech_metrics(
            words, audio_duration_seconds=6.0, transcript="Um, I I built the service..."
        )
        assert metrics.word_count == 9
        assert metrics.long_pause_count == 1
        assert metrics.max_pause_duration_seconds == 1.8
        assert metrics.filler_word_count == 2  # "um" + "you know"
        assert metrics.hesitation_count == 3  # fillers + "I I" repetition
        assert 0 < metrics.speech_completeness < 1
        assert metrics.silence_duration_seconds > 0
        assert metrics.response_duration_seconds == 6.0
        assert metrics.words_per_minute > 0

    def test_empty_words_yield_zeros(self) -> None:
        metrics = compute_speech_metrics([], audio_duration_seconds=3.0, transcript="")
        assert metrics.word_count == 0
        assert metrics.words_per_minute == 0.0
        assert metrics.speech_completeness == 0.0
        assert metrics.silence_duration_seconds == 3.0

    def test_replay_determinism(self) -> None:
        words = [_word("hello", 0.0, 0.4), _word("world", 0.9, 1.3)]
        first = compute_speech_metrics(words, audio_duration_seconds=2.0, transcript="hello world")
        for _ in range(25):
            assert (
                compute_speech_metrics(
                    list(words), audio_duration_seconds=2.0, transcript="hello world"
                )
                == first
            )
