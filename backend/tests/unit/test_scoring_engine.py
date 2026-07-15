"""Comprehensive deterministic tests for the Resume Scoring Engine
(algorithm resume-scoring-1.0.0). Pure unit tests: no DB, no AI, no I/O.
"""

from __future__ import annotations

import pytest

from app.services.ai.schemas.resume_analysis import ALL_CATEGORY_NAMES
from app.services.resume_analysis.scoring import (
    SCORING_ALGORITHM_VERSION,
    CategoryScoringInput,
    ScoringInputError,
    count_verified_evidence,
    score_analysis,
)
from app.services.resume_analysis.scoring_constants import CATEGORY_WEIGHTS

ALL_SECTIONS = ["SUMMARY", "EDUCATION", "SKILLS", "EXPERIENCE", "PROJECTS"]


def make_inputs(
    *, score: int = 60, verified: int = 2, overrides: dict[str, dict] | None = None
) -> list[CategoryScoringInput]:
    overrides = overrides or {}
    inputs = []
    for name in ALL_CATEGORY_NAMES:
        values = {
            "raw_score": score,
            "weight": CATEGORY_WEIGHTS[name],
            "verified_evidence_count": verified,
        }
        values.update(overrides.get(name, {}))
        inputs.append(CategoryScoringInput(category=name, **values))
    return inputs


class TestAggregation:
    def test_uniform_scores_aggregate_to_that_score(self) -> None:
        result = score_analysis(make_inputs(score=64), ALL_SECTIONS)
        assert result.overall_score == 64
        assert result.algorithm_version == SCORING_ALGORITHM_VERSION
        assert all(c.applicable for c in result.categories)
        assert all(c.adjusted_score == 64 for c in result.categories)
        assert all(c.adjustments == () for c in result.categories)

    def test_weighted_mean_exact_value(self) -> None:
        # CONTENT_QUALITY (0.20) at 100, everything else (0.80) at 50 ->
        # 0.20*100 + 0.80*50 = 60.
        result = score_analysis(
            make_inputs(score=50, overrides={"CONTENT_QUALITY": {"raw_score": 100}}),
            ALL_SECTIONS,
        )
        assert result.overall_score == 60

    def test_bounds_extremes(self) -> None:
        assert score_analysis(make_inputs(score=0), ALL_SECTIONS).overall_score == 0
        assert score_analysis(make_inputs(score=100), ALL_SECTIONS).overall_score == 100

    def test_raw_scores_stored_unchanged_alongside_adjusted(self) -> None:
        result = score_analysis(make_inputs(score=90, verified=0), ALL_SECTIONS)
        for category in result.categories:
            assert category.raw_score == 90  # AI input untouched
            assert category.adjusted_score == 40  # deterministic output


class TestEvidenceRequirements:
    def test_no_verified_evidence_caps_at_40(self) -> None:
        result = score_analysis(
            make_inputs(score=85, overrides={"CONTENT_QUALITY": {"verified_evidence_count": 0}}),
            ALL_SECTIONS,
        )
        content = next(c for c in result.categories if c.category == "CONTENT_QUALITY")
        assert content.adjusted_score == 40
        assert content.adjustments[0]["code"] == "EVIDENCE_CAP_NO_VERIFIED"
        assert content.adjustments[0]["points"] == 45

    def test_single_verified_evidence_caps_at_70(self) -> None:
        result = score_analysis(
            make_inputs(score=85, overrides={"SKILLS_RELEVANCE": {"verified_evidence_count": 1}}),
            ALL_SECTIONS,
        )
        skills = next(c for c in result.categories if c.category == "SKILLS_RELEVANCE")
        assert skills.adjusted_score == 70
        assert skills.adjustments[0]["code"] == "EVIDENCE_CAP_SINGLE_VERIFIED"

    def test_caps_do_not_raise_low_scores(self) -> None:
        # Missing evidence is never treated as positive evidence - but a
        # cap is a ceiling, not a floor: a raw 20 stays 20.
        result = score_analysis(make_inputs(score=20, verified=0), ALL_SECTIONS)
        assert all(c.adjusted_score == 20 for c in result.categories)
        assert all(c.adjustments == () for c in result.categories)

    def test_two_verified_items_lift_all_caps(self) -> None:
        result = score_analysis(make_inputs(score=95, verified=2), ALL_SECTIONS)
        assert all(c.adjusted_score == 95 for c in result.categories)


class TestStructuralPenalties:
    def test_missing_core_sections_deduct_from_structure_only(self) -> None:
        sections = ["EDUCATION", "SKILLS", "EXPERIENCE", "PROJECTS"]  # SUMMARY missing
        result = score_analysis(make_inputs(score=80), sections)
        structure = next(c for c in result.categories if c.category == "RESUME_STRUCTURE")
        assert structure.adjusted_score == 76
        assert structure.adjustments[0]["code"] == "MISSING_SECTION_DEDUCTION"
        assert structure.adjustments[0]["points"] == 4
        assert "SUMMARY" in structure.adjustments[0]["reason"]
        others = [c for c in result.categories if c.category != "RESUME_STRUCTURE"]
        assert all(c.adjusted_score == 80 for c in others)

    def test_deduction_capped_at_12(self) -> None:
        sections = ["EXPERIENCE"]  # SUMMARY, EDUCATION, SKILLS, PROJECTS missing (4 x 4 = 16)
        result = score_analysis(make_inputs(score=80), sections)
        structure = next(c for c in result.categories if c.category == "RESUME_STRUCTURE")
        assert structure.adjustments[0]["points"] == 12
        assert structure.adjusted_score == 68

    def test_deduction_floors_at_zero(self) -> None:
        result = score_analysis(
            make_inputs(score=60, overrides={"RESUME_STRUCTURE": {"raw_score": 5}}),
            ["EXPERIENCE"],
        )
        structure = next(c for c in result.categories if c.category == "RESUME_STRUCTURE")
        assert structure.adjusted_score == 0

    def test_cap_and_deduction_compose(self) -> None:
        # raw 90, zero verified evidence -> capped to 40, then -4 for one
        # missing core section -> 36.
        result = score_analysis(
            make_inputs(
                score=90,
                overrides={"RESUME_STRUCTURE": {"verified_evidence_count": 0}},
            ),
            ["EDUCATION", "SKILLS", "EXPERIENCE", "PROJECTS"],
        )
        structure = next(c for c in result.categories if c.category == "RESUME_STRUCTURE")
        assert [a["code"] for a in structure.adjustments] == [
            "EVIDENCE_CAP_NO_VERIFIED",
            "MISSING_SECTION_DEDUCTION",
        ]
        assert structure.adjusted_score == 36


class TestNonApplicableCategories:
    def test_no_projects_section_excludes_project_quality(self) -> None:
        sections = ["SUMMARY", "EDUCATION", "SKILLS", "EXPERIENCE"]
        result = score_analysis(
            make_inputs(score=60, overrides={"PROJECT_QUALITY": {"raw_score": 0}}), sections
        )
        project = next(c for c in result.categories if c.category == "PROJECT_QUALITY")
        assert project.applicable is False
        assert project.adjusted_score is None
        assert project.adjustments[0]["code"] == "NON_APPLICABLE"
        # The excluded category's raw 0 must not drag the mean: remaining
        # categories all sit at 60 except RESUME_STRUCTURE (missing
        # PROJECTS costs 4 -> 56, weight 0.10 of remaining 0.85).
        expected = round((60 * 0.75 + 56 * 0.10) / 0.85)
        assert result.overall_score == expected

    def test_no_experience_or_internships_excludes_experience_impact(self) -> None:
        sections = ["SUMMARY", "EDUCATION", "SKILLS", "PROJECTS"]
        result = score_analysis(make_inputs(score=60), sections)
        experience = next(c for c in result.categories if c.category == "EXPERIENCE_IMPACT")
        assert experience.applicable is False
        assert experience.adjusted_score is None

    def test_internships_section_keeps_experience_impact_applicable(self) -> None:
        sections = ["SUMMARY", "EDUCATION", "SKILLS", "INTERNSHIPS", "PROJECTS"]
        result = score_analysis(make_inputs(score=60), sections)
        experience = next(c for c in result.categories if c.category == "EXPERIENCE_IMPACT")
        assert experience.applicable is True

    def test_weight_renormalization_is_exact(self) -> None:
        # Both PROJECT_QUALITY and EXPERIENCE_IMPACT excluded; the five
        # remaining uniform 80s (with structure deductions for the two
        # missing core sections: 80 - 8 = 72 at weight 0.10 of 0.65).
        sections = ["SUMMARY", "EDUCATION", "SKILLS"]
        result = score_analysis(make_inputs(score=80), sections)
        expected = round((80 * 0.55 + 72 * 0.10) / 0.65)
        assert result.overall_score == expected


class TestInputValidation:
    def test_missing_category_rejected(self) -> None:
        with pytest.raises(ScoringInputError, match="missing"):
            score_analysis(make_inputs()[:6], ALL_SECTIONS)

    def test_duplicate_category_rejected(self) -> None:
        inputs = make_inputs()
        inputs[1] = CategoryScoringInput(
            category=inputs[0].category, raw_score=50, weight=0.2, verified_evidence_count=2
        )
        with pytest.raises(ScoringInputError):
            score_analysis(inputs, ALL_SECTIONS)

    def test_unknown_category_rejected(self) -> None:
        inputs = make_inputs()
        inputs[0] = CategoryScoringInput(
            category="VIBES", raw_score=50, weight=0.2, verified_evidence_count=2
        )
        with pytest.raises(ScoringInputError):
            score_analysis(inputs, ALL_SECTIONS)

    def test_out_of_range_scores_rejected(self) -> None:
        for bad in (-1, 101):
            with pytest.raises(ScoringInputError, match="outside"):
                score_analysis(
                    make_inputs(overrides={"CONTENT_QUALITY": {"raw_score": bad}}),
                    ALL_SECTIONS,
                )

    def test_non_integer_score_rejected(self) -> None:
        with pytest.raises(ScoringInputError, match="integer"):
            score_analysis(
                make_inputs(overrides={"CONTENT_QUALITY": {"raw_score": 61.5}}),
                ALL_SECTIONS,
            )

    def test_weight_sum_must_be_one(self) -> None:
        with pytest.raises(ScoringInputError, match="sum to 1.0"):
            score_analysis(
                make_inputs(overrides={"CONTENT_QUALITY": {"weight": 0.5}}), ALL_SECTIONS
            )

    def test_nonpositive_weight_rejected(self) -> None:
        with pytest.raises(ScoringInputError, match="positive"):
            score_analysis(
                make_inputs(overrides={"CONTENT_QUALITY": {"weight": 0.0}}), ALL_SECTIONS
            )

    def test_negative_evidence_count_rejected(self) -> None:
        with pytest.raises(ScoringInputError, match="negative"):
            score_analysis(
                make_inputs(overrides={"CONTENT_QUALITY": {"verified_evidence_count": -1}}),
                ALL_SECTIONS,
            )


class TestReproducibilityAndVersioning:
    def test_identical_inputs_identical_outputs(self) -> None:
        inputs = make_inputs(
            score=73,
            overrides={
                "CONTENT_QUALITY": {"verified_evidence_count": 1},
                "ATS_COMPATIBILITY": {"verified_evidence_count": 0},
            },
        )
        sections = ["SUMMARY", "SKILLS", "EXPERIENCE", "PROJECTS"]
        first = score_analysis(list(inputs), list(sections))
        for _ in range(50):
            assert score_analysis(list(inputs), list(sections)) == first

    def test_input_order_does_not_matter(self) -> None:
        inputs = make_inputs(score=55)
        forward = score_analysis(inputs, ALL_SECTIONS)
        backward = score_analysis(list(reversed(inputs)), ALL_SECTIONS)
        assert forward == backward

    def test_version_stamped_on_result(self) -> None:
        result = score_analysis(make_inputs(), ALL_SECTIONS)
        assert result.algorithm_version == "resume-scoring-1.0.0"
        assert result.algorithm_version == SCORING_ALGORITHM_VERSION


class TestCountVerifiedEvidence:
    def test_counts_only_backend_verified_true(self) -> None:
        evidence = [
            {"quote": "a", "observation": "x", "verified": True},
            {"quote": "b", "observation": "y", "verified": False},
            {"quote": "c", "observation": "z"},  # missing flag -> not verified
            {"quote": "d", "observation": "w", "verified": "yes"},  # wrong type
        ]
        assert count_verified_evidence(evidence) == 1

    def test_empty_evidence_counts_zero(self) -> None:
        assert count_verified_evidence([]) == 0
