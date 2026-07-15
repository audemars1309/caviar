"""Unit tests for the strict resume-analysis output schema, deterministic
evidence verification, and backend-owned weights."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.services.ai.schemas.resume_analysis import (
    ALL_CATEGORY_NAMES,
    EvidenceItem,
    ResumeAnalysisOutput,
)
from app.services.resume_analysis.scoring_constants import (
    CATEGORY_WEIGHTS,
    verify_evidence_quotes,
)


def make_valid_output_dict(*, score: int = 70) -> dict:
    category = lambda name: {  # noqa: E731
        "category": name,
        "score": score,
        "evidence": [{"quote": "Built an async ingestion service", "observation": "Concrete."}],
        "penalties": [],
    }
    return {
        "categories": [category(name) for name in ALL_CATEGORY_NAMES],
        "strengths": ["Clear technical stack"],
        "weaknesses": ["No quantified outcomes"],
        "critical_issues": [],
        "missing_content_observations": ["No certifications section"],
        "ats_observations": ["Standard section headings detected"],
        "section_feedback": [
            {
                "section_type": "EXPERIENCE",
                "assessment": "Describes work but not outcomes.",
                "recommendations": ["Add measurable results"],
            }
        ],
        "bullet_improvements": [
            {
                "original_bullet": "Built an async ingestion service",
                "issues": ["No outcome stated"],
                "improved_suggestion": (
                    "Built an async ingestion service handling [add: request volume]"
                ),
            }
        ],
        "priority_improvements": ["Quantify experience bullets"],
        "role_relevance": {
            "applicable": False,
            "matched_requirements": [],
            "missing_requirements": [],
            "relevance_summary": "",
        },
    }


class TestResumeAnalysisOutputSchema:
    def test_valid_payload_parses(self) -> None:
        output = ResumeAnalysisOutput.model_validate(make_valid_output_dict())
        assert len(output.categories) == 7

    def test_missing_category_rejected(self) -> None:
        payload = make_valid_output_dict()
        payload["categories"] = payload["categories"][:6]
        with pytest.raises(ValidationError, match="missing"):
            ResumeAnalysisOutput.model_validate(payload)

    def test_duplicate_category_rejected(self) -> None:
        payload = make_valid_output_dict()
        payload["categories"][1]["category"] = payload["categories"][0]["category"]
        with pytest.raises(ValidationError):
            ResumeAnalysisOutput.model_validate(payload)

    def test_unknown_category_rejected(self) -> None:
        payload = make_valid_output_dict()
        payload["categories"][0]["category"] = "VIBES"
        with pytest.raises(ValidationError):
            ResumeAnalysisOutput.model_validate(payload)

    def test_score_range_enforced(self) -> None:
        payload = make_valid_output_dict()
        payload["categories"][0]["score"] = 101
        with pytest.raises(ValidationError):
            ResumeAnalysisOutput.model_validate(payload)
        payload["categories"][0]["score"] = -1
        with pytest.raises(ValidationError):
            ResumeAnalysisOutput.model_validate(payload)


class TestEvidenceVerification:
    RESUME = "Dharun Raj Gupta\nEXPERIENCE\n- Built an async ingestion   service\nPython, C++"

    def test_exact_quote_verified(self) -> None:
        items = verify_evidence_quotes(
            [EvidenceItem(quote="Dharun Raj Gupta", observation="Name present.")], self.RESUME
        )
        assert items[0]["verified"] is True

    def test_whitespace_and_case_folded(self) -> None:
        items = verify_evidence_quotes(
            [EvidenceItem(quote="built an async ingestion service", observation="x")],
            self.RESUME,
        )
        assert items[0]["verified"] is True

    def test_fabricated_quote_not_verified(self) -> None:
        items = verify_evidence_quotes(
            [EvidenceItem(quote="Increased revenue by 40%", observation="x")], self.RESUME
        )
        assert items[0]["verified"] is False

    def test_empty_quote_not_verified(self) -> None:
        items = verify_evidence_quotes([EvidenceItem(quote="  ", observation="x")], self.RESUME)
        assert items[0]["verified"] is False

    def test_output_shape_is_json_ready(self) -> None:
        items = verify_evidence_quotes(
            [EvidenceItem(quote="Python", observation="Listed skill.")], self.RESUME
        )
        assert items == [
            {"quote": "Python", "observation": "Listed skill.", "verified": True}
        ]


class TestBackendOwnedWeights:
    def test_weights_cover_all_categories_and_sum_to_one(self) -> None:
        assert set(CATEGORY_WEIGHTS) == set(ALL_CATEGORY_NAMES)
        assert abs(sum(CATEGORY_WEIGHTS.values()) - 1.0) < 1e-9
