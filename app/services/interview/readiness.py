"""Deterministic interview readiness calculation (Phase 8).

Algorithm version: ``interview-readiness-1.0.0``. Pure functions; no AI.
Gemini's per-answer criterion scores are validated INPUTS; the backend
computes every number here, exactly as the resume scoring engine does
for resumes (Phase 5).

ALGORITHM:

1. Inputs: one record per evaluated answer - the eight criterion scores
   (a criterion is None when the question type's evaluation profile
   excluded it; None is EXCLUDED from aggregation, never zero-filled -
   missing evidence is never treated as evidence) plus the question
   difficulty.

2. Category scores: each report category maps 1:1 to its criterion
   (COMMUNICATION<-communication_score, TECHNICAL_DEPTH<-
   technical_depth_score, RELEVANCE, SPECIFICITY, EVIDENCE,
   PROBLEM_SOLVING, ANSWER_STRUCTURE). Per category, take the answers
   where the criterion applies, weight each by question difficulty
   (EASY 0.8 / MEDIUM 1.0 / HARD 1.2), and compute the weighted mean -
   with an outlier guard: when a category has >= 4 samples, the single
   lowest and single highest scores are dropped first (ties broken by
   answer order - deterministic), so one anomalous answer cannot distort
   the category. Categories with zero samples get score None and are
   excluded from the overall (their weight is redistributed).

3. Overall: weighted mean of scored categories using the backend-owned
   category weights below (sum 1.0), renormalized over scored
   categories, rounded, bounds-checked. With zero scored categories the
   overall and readiness level are None - an honest "not assessable",
   never a guess.

4. Readiness level thresholds on the overall score:
   < 45 NOT_READY, < 60 DEVELOPING, < 75 READY, else STRONG.

Malformed inputs (unknown criteria keys, out-of-range scores, unknown
difficulty) raise ``ReadinessInputError`` - never a silently wrong score.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.core.exceptions import AppError
from app.services.interview.enums import ALL_CRITERIA, DIFFICULTY_WEIGHTS

READINESS_ALGORITHM_VERSION = "interview-readiness-1.0.0"

_OUTLIER_TRIM_MIN_SAMPLES = 4

CATEGORY_TO_CRITERION: dict[str, str] = {
    "COMMUNICATION": "communication_score",
    "TECHNICAL_DEPTH": "technical_depth_score",
    "RELEVANCE": "relevance_score",
    "SPECIFICITY": "specificity_score",
    "EVIDENCE": "evidence_score",
    "PROBLEM_SOLVING": "problem_solving_score",
    "ANSWER_STRUCTURE": "answer_structure_score",
}

READINESS_CATEGORY_WEIGHTS: dict[str, float] = {
    "TECHNICAL_DEPTH": 0.20,
    "COMMUNICATION": 0.20,
    "RELEVANCE": 0.15,
    "PROBLEM_SOLVING": 0.15,
    "SPECIFICITY": 0.125,
    "EVIDENCE": 0.125,
    "ANSWER_STRUCTURE": 0.05,
}

assert abs(sum(READINESS_CATEGORY_WEIGHTS.values()) - 1.0) < 1e-9

_LEVEL_THRESHOLDS: tuple[tuple[int, str], ...] = (
    (45, "NOT_READY"),
    (60, "DEVELOPING"),
    (75, "READY"),
    (101, "STRONG"),
)


class ReadinessInputError(AppError):
    status_code = 500
    error_code = "readiness_input_invalid"


@dataclass(frozen=True)
class AnswerScores:
    """One evaluated answer's validated criterion scores. ``scores`` maps
    criterion name -> int 0-100, or None where the question type's
    profile excluded the criterion."""

    scores: dict[str, int | None]
    difficulty: str


@dataclass(frozen=True)
class CategoryReadiness:
    category: str
    score: int | None
    weight: float
    sample_count: int


@dataclass(frozen=True)
class ReadinessResult:
    overall_score: int | None
    readiness_level: str | None
    algorithm_version: str
    categories: tuple[CategoryReadiness, ...]


def _validate(answers: list[AnswerScores]) -> None:
    for index, answer in enumerate(answers):
        if answer.difficulty not in DIFFICULTY_WEIGHTS:
            raise ReadinessInputError(f"Answer {index}: unknown difficulty.")
        for criterion, value in answer.scores.items():
            if criterion not in ALL_CRITERIA:
                raise ReadinessInputError(f"Answer {index}: unknown criterion '{criterion}'.")
            if value is None:
                continue
            if not isinstance(value, int) or isinstance(value, bool):
                raise ReadinessInputError(f"Answer {index}: '{criterion}' must be an integer.")
            if not 0 <= value <= 100:
                raise ReadinessInputError(
                    f"Answer {index}: '{criterion}'={value} outside [0, 100]."
                )


def readiness_level_for(score: int) -> str:
    for threshold, level in _LEVEL_THRESHOLDS:
        if score < threshold:
            return level
    return "STRONG"  # unreachable; defensive


def compute_readiness(answers: list[AnswerScores]) -> ReadinessResult:
    """Deterministic readiness over validated evaluations. Pure."""
    _validate(answers)

    categories: list[CategoryReadiness] = []
    for category, criterion in CATEGORY_TO_CRITERION.items():
        samples: list[tuple[int, float]] = [
            (answer.scores[criterion], DIFFICULTY_WEIGHTS[answer.difficulty])
            for answer in answers
            if answer.scores.get(criterion) is not None
        ]
        if len(samples) >= _OUTLIER_TRIM_MIN_SAMPLES:
            ordered = sorted(range(len(samples)), key=lambda i: (samples[i][0], i))
            drop = {ordered[0], ordered[-1]}
            samples = [item for i, item in enumerate(samples) if i not in drop]
        if samples:
            weight_sum = sum(weight for _, weight in samples)
            score = round(sum(value * weight for value, weight in samples) / weight_sum)
        else:
            score = None
        categories.append(
            CategoryReadiness(
                category=category,
                score=score,
                weight=READINESS_CATEGORY_WEIGHTS[category],
                sample_count=len(samples),
            )
        )

    scored = [item for item in categories if item.score is not None]
    if scored:
        weight_sum = sum(item.weight for item in scored)
        overall = round(sum(item.score * item.weight for item in scored) / weight_sum)
        if not 0 <= overall <= 100:  # structurally impossible; defensive
            raise ReadinessInputError(f"Computed overall {overall} outside [0, 100].")
        level = readiness_level_for(overall)
    else:
        overall, level = None, None

    return ReadinessResult(
        overall_score=overall,
        readiness_level=level,
        algorithm_version=READINESS_ALGORITHM_VERSION,
        categories=tuple(categories),
    )


def answer_scores_from_evaluation_row(row: Any) -> AnswerScores:
    """Adapter: an answer_evaluations ORM row (+ its question difficulty
    attached as ``difficulty``) -> plain AnswerScores."""
    return AnswerScores(
        scores={criterion: getattr(row, criterion) for criterion in ALL_CRITERIA},
        difficulty=row.difficulty,
    )
