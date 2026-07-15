"""Structured Resume Builder section content schemas (Phase 6).

Every ``resume_builder_sections.content`` JSONB document is validated
against the schema for its section type before persistence - the builder
never stores free-form blobs, and never stores the whole resume as one
text field. Content is pure DATA, deliberately free of any presentation
concern (no fonts, layouts, template hints): presentation is owned by the
versioned Phase 7 LaTeX template system, so the same stored content can
render through any future template.

Validation posture: ``extra="forbid"`` everywhere (this is client input -
unknown keys are mistakes or probing, not flexibility), tight length and
list-size caps (also serving as prompt-size protection when content later
feeds AI assistance or LaTeX rendering), and dates as bounded free text
(resumes legitimately use "2021 - 2025", "Expected May 2026"; forcing ISO
dates would corrupt real-world content).
"""

from __future__ import annotations

import enum

from pydantic import BaseModel, ConfigDict, Field


class BuilderSectionType(enum.StrEnum):
    """Mirrors the resume_builder_sections.section_type CHECK constraint."""

    PERSONAL_INFO = "PERSONAL_INFO"
    SUMMARY = "SUMMARY"
    EDUCATION = "EDUCATION"
    SKILLS = "SKILLS"
    EXPERIENCE = "EXPERIENCE"
    INTERNSHIPS = "INTERNSHIPS"
    PROJECTS = "PROJECTS"
    CERTIFICATIONS = "CERTIFICATIONS"
    ACHIEVEMENTS = "ACHIEVEMENTS"


# Canonical storage order per type. sort_order is deliberately not
# client-settable in v1: display order is a presentation concern owned by
# Phase 7 templates, and fixed values keep UNIQUE (project_id, sort_order)
# conflict-free by construction.
SECTION_SORT_ORDER: dict[BuilderSectionType, int] = {
    BuilderSectionType.PERSONAL_INFO: 0,
    BuilderSectionType.SUMMARY: 1,
    BuilderSectionType.EDUCATION: 2,
    BuilderSectionType.SKILLS: 3,
    BuilderSectionType.EXPERIENCE: 4,
    BuilderSectionType.INTERNSHIPS: 5,
    BuilderSectionType.PROJECTS: 6,
    BuilderSectionType.CERTIFICATIONS: 7,
    BuilderSectionType.ACHIEVEMENTS: 8,
}


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


_SHORT = Field(max_length=200)
_SHORT_OPT = Field(default=None, max_length=200)
_DATE_OPT = Field(default=None, max_length=50)
_BULLETS = Field(default_factory=list, max_length=20)


class PersonalInfoContent(_StrictModel):
    full_name: str = Field(min_length=1, max_length=200)
    email: str | None = Field(default=None, max_length=320)
    phone: str | None = Field(default=None, max_length=50)
    location: str | None = _SHORT_OPT
    linkedin_url: str | None = Field(default=None, max_length=500)
    github_url: str | None = Field(default=None, max_length=500)
    website_url: str | None = Field(default=None, max_length=500)


class SummaryContent(_StrictModel):
    text: str = Field(min_length=1, max_length=2_000)


class EducationEntry(_StrictModel):
    institution: str = Field(min_length=1, max_length=200)
    degree: str = Field(min_length=1, max_length=200)
    field_of_study: str | None = _SHORT_OPT
    location: str | None = _SHORT_OPT
    start_date: str | None = _DATE_OPT
    end_date: str | None = _DATE_OPT
    gpa: str | None = Field(default=None, max_length=20)
    highlights: list[str] = Field(default_factory=list, max_length=10)


class EducationContent(_StrictModel):
    entries: list[EducationEntry] = Field(min_length=1, max_length=10)


class SkillGroup(_StrictModel):
    name: str = Field(min_length=1, max_length=100)
    skills: list[str] = Field(min_length=1, max_length=40)


class SkillsContent(_StrictModel):
    groups: list[SkillGroup] = Field(min_length=1, max_length=15)


class ExperienceEntry(_StrictModel):
    company: str = Field(min_length=1, max_length=200)
    title: str = Field(min_length=1, max_length=200)
    location: str | None = _SHORT_OPT
    start_date: str | None = _DATE_OPT
    end_date: str | None = _DATE_OPT
    bullets: list[str] = _BULLETS


class ExperienceContent(_StrictModel):
    entries: list[ExperienceEntry] = Field(min_length=1, max_length=20)


class ProjectEntry(_StrictModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=1_000)
    technologies: list[str] = Field(default_factory=list, max_length=30)
    url: str | None = Field(default=None, max_length=500)
    bullets: list[str] = _BULLETS


class ProjectsContent(_StrictModel):
    entries: list[ProjectEntry] = Field(min_length=1, max_length=20)


class CertificationEntry(_StrictModel):
    name: str = Field(min_length=1, max_length=200)
    issuer: str | None = _SHORT_OPT
    date: str | None = _DATE_OPT
    credential_url: str | None = Field(default=None, max_length=500)


class CertificationsContent(_StrictModel):
    entries: list[CertificationEntry] = Field(min_length=1, max_length=20)


class AchievementEntry(_StrictModel):
    text: str = Field(min_length=1, max_length=500)
    date: str | None = _DATE_OPT


class AchievementsContent(_StrictModel):
    entries: list[AchievementEntry] = Field(min_length=1, max_length=20)


SECTION_CONTENT_SCHEMAS: dict[BuilderSectionType, type[BaseModel]] = {
    BuilderSectionType.PERSONAL_INFO: PersonalInfoContent,
    BuilderSectionType.SUMMARY: SummaryContent,
    BuilderSectionType.EDUCATION: EducationContent,
    BuilderSectionType.SKILLS: SkillsContent,
    BuilderSectionType.EXPERIENCE: ExperienceContent,
    BuilderSectionType.INTERNSHIPS: ExperienceContent,  # same shape by design
    BuilderSectionType.PROJECTS: ProjectsContent,
    BuilderSectionType.CERTIFICATIONS: CertificationsContent,
    BuilderSectionType.ACHIEVEMENTS: AchievementsContent,
}

# Bullet-bearing section types eligible for IMPROVE_BULLETS assistance.
BULLET_SECTION_TYPES: frozenset[BuilderSectionType] = frozenset(
    {
        BuilderSectionType.EXPERIENCE,
        BuilderSectionType.INTERNSHIPS,
        BuilderSectionType.PROJECTS,
    }
)


def validate_section_content(section_type: BuilderSectionType, content: dict) -> dict:
    """Validate raw content against the section type's schema; returns the
    normalized dict for storage. Raises pydantic.ValidationError."""
    schema = SECTION_CONTENT_SCHEMAS[section_type]
    return schema.model_validate(content).model_dump(mode="json")
