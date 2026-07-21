"""Strict output schema for the RESUME_ANALYSIS task.

``RESUME_ANALYSIS_SCHEMA_VERSION`` is stored with every persisted analysis
so historical rows remain interpretable as this schema evolves.

Design principles (per the master spec's fact/interpretation/
recommendation separation):

  * Facts are verbatim material from the resume: ``EvidenceItem.quote``
    and ``BulletImprovement.original_bullet``. After validation, the
    backend deterministically verifies each quote against the actual
    resume text and stores a ``verified`` flag the AI cannot influence.
  * Interpretations are the AI's readings of those facts:
    ``EvidenceItem.observation``, ``weaknesses``, ``ats_observations``,
    ``SectionFeedback.assessment``, ``RoleRelevance`` fields.
  * Recommendations are explicit advice fields:
    ``SectionFeedback.recommendations``, ``improved_suggestion``,
    ``priority_improvements``.

Category scores here are the model's evidence-grounded CATEGORY-LEVEL
assessments - inputs to scoring, not the score. The final numerical
resume score is computed deterministically by the backend from these
validated category scores and backend-owned weights in Phase 5; no field
in this schema is, or ever becomes, the final score.

Schema-shape constraints: OpenAI structured output is most reliable with
required fields and simple types. Optionality is expressed with explicit
``applicable`` booleans (``RoleRelevance``) rather than Optional/Union
fields, and every list is bounded via prompt guidance rather than
maxItems (which not all schema conversions honor). Validators enforce
what the model cannot be trusted to: exactly one assessment per category,
all seven categories present.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

RESUME_ANALYSIS_SCHEMA_VERSION = "resume-analysis-1.0.0"

CategoryName = Literal[
    "CONTENT_QUALITY",
    "EXPERIENCE_IMPACT",
    "SKILLS_RELEVANCE",
    "PROJECT_QUALITY",
    "RESUME_STRUCTURE",
    "ATS_COMPATIBILITY",
    "EVIDENCE_QUANTIFICATION",
]

ALL_CATEGORY_NAMES: tuple[str, ...] = (
    "CONTENT_QUALITY",
    "EXPERIENCE_IMPACT",
    "SKILLS_RELEVANCE",
    "PROJECT_QUALITY",
    "RESUME_STRUCTURE",
    "ATS_COMPATIBILITY",
    "EVIDENCE_QUANTIFICATION",
)


class EvidenceItem(BaseModel):
    quote: str = Field(
        description=(
            "A short verbatim excerpt copied exactly from the resume text "
            "(the extracted fact this assessment rests on)."
        )
    )
    observation: str = Field(
        description="What this evidence shows or fails to show (your interpretation)."
    )


class CategoryAssessment(BaseModel):
    category: CategoryName
    score: int = Field(
        ge=0,
        le=100,
        description=(
            "Evidence-grounded assessment for this category only, 0-100. "
            "This is an input to backend scoring, never a final resume score."
        ),
    )
    evidence: list[EvidenceItem] = Field(
        description="2-5 evidence items grounding this category's assessment."
    )
    penalties: list[str] = Field(
        description=(
            "Specific deficiencies that lowered this category's assessment "
            "(empty list if none)."
        )
    )


class SectionFeedback(BaseModel):
    section_type: str = Field(
        description="The resume section this feedback addresses (e.g. EXPERIENCE, SKILLS)."
    )
    assessment: str = Field(description="Evidence-based assessment of this section.")
    recommendations: list[str] = Field(
        description="1-3 concrete, actionable recommendations for this section."
    )


class BulletImprovement(BaseModel):
    original_bullet: str = Field(
        description="A weak bullet point copied verbatim from the resume."
    )
    issues: list[str] = Field(description="What is weak about it (1-3 issues).")
    improved_suggestion: str = Field(
        description=(
            "A rewritten version using only facts present in the resume. Where a "
            "metric would strengthen it but none exists in the resume, include a "
            "bracketed placeholder question such as '[add: estimated % latency "
            "reduction]' - NEVER an invented number."
        )
    )


class RoleRelevance(BaseModel):
    applicable: bool = Field(
        description=(
            "true only when a target role / job description was provided in the "
            "input. When false, leave the lists empty and the summary as an "
            "empty string."
        )
    )
    matched_requirements: list[EvidenceItem] = Field(
        description="Job requirements the resume demonstrably addresses, with evidence."
    )
    missing_requirements: list[str] = Field(
        description="Job requirements the resume does not demonstrate."
    )
    relevance_summary: str = Field(
        description="2-4 sentence assessment of fit between resume and role."
    )


class ResumeAnalysisOutput(BaseModel):
    categories: list[CategoryAssessment] = Field(
        description="Exactly one assessment per category, all seven categories."
    )
    strengths: list[str] = Field(description="3-6 evidence-based strengths.")
    weaknesses: list[str] = Field(description="3-6 evidence-based weaknesses.")
    critical_issues: list[str] = Field(
        description="Issues severe enough to cost interviews (empty list if none)."
    )
    missing_content_observations: list[str] = Field(
        description=(
            "Observations about expected content that is absent (empty list if none)."
        )
    )
    ats_observations: list[str] = Field(
        description=(
            "ATS-compatibility observations detectable from the extracted text "
            "(empty list if none)."
        )
    )
    section_feedback: list[SectionFeedback] = Field(
        description="Feedback for each major section present in the resume."
    )
    bullet_improvements: list[BulletImprovement] = Field(
        description="2-6 of the weakest bullets with improved rewrites."
    )
    priority_improvements: list[str] = Field(
        description="3-5 improvements ordered by impact, most impactful first."
    )
    role_relevance: RoleRelevance

    @field_validator("categories")
    @classmethod
    def _exactly_all_categories_once(
        cls, value: list[CategoryAssessment]
    ) -> list[CategoryAssessment]:
        seen = [item.category for item in value]
        if sorted(seen) != sorted(ALL_CATEGORY_NAMES):
            missing = set(ALL_CATEGORY_NAMES) - set(seen)
            duplicated = {name for name in seen if seen.count(name) > 1}
            raise ValueError(
                "categories must contain exactly one assessment per category; "
                f"missing={sorted(missing)} duplicated={sorted(duplicated)}"
            )
        return value
