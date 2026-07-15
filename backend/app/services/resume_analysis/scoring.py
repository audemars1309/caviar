"""The deterministic Resume Scoring Engine (Phase 5).

Algorithm version: ``resume-scoring-1.0.0``.

Pure functions over already-validated inputs. No AI calls, no I/O, no
randomness, no clock: identical inputs always produce identical outputs.
Gemini's role ended in Phase 4 - its validated category assessments and
backend-verified evidence are INPUTS here; nothing the model emits can
choose, override, or directly become the final score.

INPUTS (all previously validated/derived):
  * Seven category assessments: raw AI score (int 0-100, schema-enforced),
    evidence items with the backend-computed ``verified`` flag from
    ``verify_evidence_quotes`` (deterministic substring verification
    against the actual resume text), AI penalty strings (stored, not
    re-deducted - see rationale below), and the backend-owned weight
    persisted on each row at analysis time.
  * The deterministic Phase 3 parser's detected section types.

ALGORITHM (in order):

1. INPUT VALIDATION (reject, never guess):
   - exactly the seven known categories, each exactly once;
   - every raw score an int in [0, 100];
   - stored weights positive and summing to 1.0 (±1e-6).
   Violations raise ``ScoringInputError`` - a malformed analysis is never
   scored, partially scored, or defaulted.

2. APPLICABILITY (explicit handling of non-applicable categories, decided
   only from deterministic parser facts - never from AI output):
   - PROJECT_QUALITY is NON_APPLICABLE when the parser detected no
     PROJECTS section;
   - EXPERIENCE_IMPACT is NON_APPLICABLE when the parser detected neither
     EXPERIENCE nor INTERNSHIPS;
   - all other categories are always applicable.
   Non-applicable categories get ``adjusted_score = None``, a
   ``NON_APPLICABLE`` adjustment marker, and are excluded from
   aggregation with their weight redistributed (see step 4). The absent
   material still costs the candidate exactly once, deterministically,
   via the structural deduction in step 3b - it is neither double-punished
   nor silently ignored.

3. PER-CATEGORY DETERMINISTIC ADJUSTMENTS (each applied adjustment is
   recorded as ``{code, points, reason}``):
   a. EVIDENCE REQUIREMENT CAPS - an assessment is only worth what its
      verified evidence supports; unverified AI claims are never treated
      as positive evidence:
        verified evidence count == 0  ->  score capped at 40
                                          (EVIDENCE_CAP_NO_VERIFIED)
        verified evidence count == 1  ->  score capped at 70
                                          (EVIDENCE_CAP_SINGLE_VERIFIED)
        verified evidence count >= 2  ->  no cap.
   b. STRUCTURAL DEDUCTION (RESUME_STRUCTURE only) - 4 points per core
      section the deterministic parser did not detect, among SUMMARY,
      EDUCATION, SKILLS, EXPERIENCE, PROJECTS, capped at 12 total
      (MISSING_SECTION_DEDUCTION).
   adjusted = clamp(min(raw, cap) - deductions, 0, 100).

   AI penalty strings are deliberately NOT re-deducted: the model already
   reflected them in its raw category score, and deducting again would
   double-count a signal the backend cannot independently verify. They
   remain stored verbatim for explainability. Deterministic deductions
   are applied only for backend-verifiable facts.

4. AGGREGATION over applicable categories with weight renormalization:
       effective_weight(c) = weight(c) / sum(weight(a) for applicable a)
       overall = round(sum(adjusted(c) * effective_weight(c)))
   Result is bounds-checked to [0, 100]. At least four categories must be
   applicable (structurally guaranteed at five by step 2's rules; the
   check is defense-in-depth for future rule changes).

REPRODUCIBILITY & VERSIONING: the exact weights used live on each stored
category row (not read back from current constants), both raw and
adjusted scores are stored, every adjustment is stored, and
``scoring_algorithm_version`` records which algorithm produced
``overall_score``. Re-running this module's ``score_analysis`` on a stored
row's data reproduces its stored result exactly; rows scored by older
algorithm versions (or the Phase 4 ``unscored`` sentinel) remain valid
historical records and are never silently rescored.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.core.exceptions import AppError
from app.services.ai.schemas.resume_analysis import ALL_CATEGORY_NAMES

SCORING_ALGORITHM_VERSION = "resume-scoring-1.0.0"

_WEIGHT_SUM_TOLERANCE = 1e-6
_MIN_APPLICABLE_CATEGORIES = 4

_EVIDENCE_CAP_NO_VERIFIED = 40
_EVIDENCE_CAP_SINGLE_VERIFIED = 70

_STRUCTURE_CORE_SECTIONS = ("SUMMARY", "EDUCATION", "SKILLS", "EXPERIENCE", "PROJECTS")
_MISSING_SECTION_POINTS = 4
_MISSING_SECTION_DEDUCTION_MAX = 12


class ScoringInputError(AppError):
    """The validated-analysis inputs handed to the scoring engine are
    malformed or incomplete. Operator/pipeline defect (HTTP 500): Phase 4
    validation should make this unreachable through the API."""

    status_code = 500
    error_code = "scoring_input_invalid"


@dataclass(frozen=True)
class CategoryScoringInput:
    category: str
    raw_score: int
    weight: float
    verified_evidence_count: int


@dataclass(frozen=True)
class CategoryScoringResult:
    category: str
    raw_score: int
    weight: float
    applicable: bool
    adjusted_score: int | None
    adjustments: tuple[dict[str, Any], ...]


@dataclass(frozen=True)
class ScoringResult:
    overall_score: int
    algorithm_version: str
    categories: tuple[CategoryScoringResult, ...]


def _validate_inputs(categories: list[CategoryScoringInput]) -> None:
    names = [item.category for item in categories]
    if sorted(names) != sorted(ALL_CATEGORY_NAMES):
        missing = set(ALL_CATEGORY_NAMES) - set(names)
        unknown_or_duplicated = sorted(
            set(name for name in names if names.count(name) > 1 or name not in ALL_CATEGORY_NAMES)
        )
        raise ScoringInputError(
            "Scoring requires exactly one assessment per category; "
            f"missing={sorted(missing)} invalid={unknown_or_duplicated}"
        )
    for item in categories:
        if not isinstance(item.raw_score, int) or isinstance(item.raw_score, bool):
            raise ScoringInputError(
                f"Category {item.category} raw score must be an integer."
            )
        if not 0 <= item.raw_score <= 100:
            raise ScoringInputError(
                f"Category {item.category} raw score {item.raw_score} outside [0, 100]."
            )
        if item.weight <= 0:
            raise ScoringInputError(f"Category {item.category} weight must be positive.")
        if item.verified_evidence_count < 0:
            raise ScoringInputError(
                f"Category {item.category} verified evidence count cannot be negative."
            )
    weight_sum = sum(item.weight for item in categories)
    if abs(weight_sum - 1.0) > _WEIGHT_SUM_TOLERANCE:
        raise ScoringInputError(
            f"Category weights must sum to 1.0 (got {weight_sum!r})."
        )


def _is_applicable(category: str, detected_sections: frozenset[str]) -> bool:
    if category == "PROJECT_QUALITY":
        return "PROJECTS" in detected_sections
    if category == "EXPERIENCE_IMPACT":
        return bool({"EXPERIENCE", "INTERNSHIPS"} & detected_sections)
    return True


def _score_category(
    item: CategoryScoringInput, detected_sections: frozenset[str]
) -> CategoryScoringResult:
    if not _is_applicable(item.category, detected_sections):
        return CategoryScoringResult(
            category=item.category,
            raw_score=item.raw_score,
            weight=item.weight,
            applicable=False,
            adjusted_score=None,
            adjustments=(
                {
                    "code": "NON_APPLICABLE",
                    "points": 0,
                    "reason": (
                        "Excluded from aggregation: the deterministic parser found no "
                        "section supporting this category; its weight was redistributed."
                    ),
                },
            ),
        )

    adjustments: list[dict[str, Any]] = []
    adjusted = item.raw_score

    if item.verified_evidence_count == 0 and adjusted > _EVIDENCE_CAP_NO_VERIFIED:
        adjustments.append(
            {
                "code": "EVIDENCE_CAP_NO_VERIFIED",
                "points": adjusted - _EVIDENCE_CAP_NO_VERIFIED,
                "reason": (
                    "No evidence quote for this category was verified against the "
                    f"resume text; score capped at {_EVIDENCE_CAP_NO_VERIFIED}."
                ),
            }
        )
        adjusted = _EVIDENCE_CAP_NO_VERIFIED
    elif item.verified_evidence_count == 1 and adjusted > _EVIDENCE_CAP_SINGLE_VERIFIED:
        adjustments.append(
            {
                "code": "EVIDENCE_CAP_SINGLE_VERIFIED",
                "points": adjusted - _EVIDENCE_CAP_SINGLE_VERIFIED,
                "reason": (
                    "Only one evidence quote for this category was verified against "
                    f"the resume text; score capped at {_EVIDENCE_CAP_SINGLE_VERIFIED}."
                ),
            }
        )
        adjusted = _EVIDENCE_CAP_SINGLE_VERIFIED

    if item.category == "RESUME_STRUCTURE":
        missing = [
            section
            for section in _STRUCTURE_CORE_SECTIONS
            if section not in detected_sections
        ]
        if missing:
            deduction = min(
                _MISSING_SECTION_POINTS * len(missing), _MISSING_SECTION_DEDUCTION_MAX
            )
            adjustments.append(
                {
                    "code": "MISSING_SECTION_DEDUCTION",
                    "points": deduction,
                    "reason": (
                        "Core sections not detected by the deterministic parser: "
                        f"{', '.join(missing)} "
                        f"({_MISSING_SECTION_POINTS} points each, "
                        f"max {_MISSING_SECTION_DEDUCTION_MAX})."
                    ),
                }
            )
            adjusted -= deduction

    adjusted = max(0, min(100, adjusted))
    return CategoryScoringResult(
        category=item.category,
        raw_score=item.raw_score,
        weight=item.weight,
        applicable=True,
        adjusted_score=adjusted,
        adjustments=tuple(adjustments),
    )


def score_analysis(
    categories: list[CategoryScoringInput], detected_section_types: list[str]
) -> ScoringResult:
    """Compute the deterministic overall resume score. Pure; raises
    ``ScoringInputError`` on malformed inputs, never guesses."""
    _validate_inputs(categories)
    detected = frozenset(detected_section_types)

    results = tuple(
        _score_category(item, detected)
        for item in sorted(categories, key=lambda item: item.category)
    )

    applicable = [result for result in results if result.applicable]
    if len(applicable) < _MIN_APPLICABLE_CATEGORIES:
        raise ScoringInputError(
            f"Only {len(applicable)} categories applicable; at least "
            f"{_MIN_APPLICABLE_CATEGORIES} required to compute a score."
        )

    applicable_weight_sum = sum(result.weight for result in applicable)
    overall = round(
        sum(
            result.adjusted_score * (result.weight / applicable_weight_sum)
            for result in applicable
        )
    )
    if not 0 <= overall <= 100:  # structurally impossible; defense-in-depth
        raise ScoringInputError(f"Computed overall score {overall} outside [0, 100].")

    return ScoringResult(
        overall_score=overall,
        algorithm_version=SCORING_ALGORITHM_VERSION,
        categories=results,
    )


def count_verified_evidence(evidence: list[dict[str, Any]]) -> int:
    """Count backend-verified evidence items in the JSON-ready evidence
    shape produced by ``verify_evidence_quotes``."""
    return sum(1 for item in evidence if item.get("verified") is True)
