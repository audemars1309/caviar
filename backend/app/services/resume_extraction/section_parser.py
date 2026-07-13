"""Deterministic resume section parsing.

Pure functions, no I/O, no AI. Splits normalized resume text into the
canonical Caviar section types by recognizing section headings, and
extracts simple contact facts (email, phone, URLs) by regex.

Design constraints:

  * Conservative by construction. A line only becomes a section boundary
    if it canonicalizes to a *known alias* of a section type. There is no
    "looks like a heading" heuristic (all-caps, short, etc.) - such
    heuristics misfire on short technical lines ("AWS LAMBDA") and would
    silently shred content. Unrecognized headings simply remain inside the
    surrounding section's content; downstream analysis still sees them.
  * Everything the parser outputs is a FACT about the document's text
    (this heading text appeared at this line; this email string appeared),
    never an interpretation. Interpretation is Phase 4's job, and the spec
    requires the two never be conflated.
  * Versioned: ``PIPELINE_VERSION`` covers the extractor + normalizer +
    parser behavior as a unit and is stored with every extraction row so
    historical rows remain interpretable after the pipeline evolves.

The section immediately at the top of the document, before any recognized
heading, is emitted as ``HEADER`` - resumes conventionally open with the
candidate's name and contact block, which has no heading.
"""

from __future__ import annotations

import enum
import re
from dataclasses import dataclass
from typing import Any

PIPELINE_VERSION = "extraction-1.0.0"


class ParsedSectionType(enum.StrEnum):
    HEADER = "HEADER"
    SUMMARY = "SUMMARY"
    EDUCATION = "EDUCATION"
    SKILLS = "SKILLS"
    EXPERIENCE = "EXPERIENCE"
    INTERNSHIPS = "INTERNSHIPS"
    PROJECTS = "PROJECTS"
    CERTIFICATIONS = "CERTIFICATIONS"
    ACHIEVEMENTS = "ACHIEVEMENTS"


# Section types whose absence is worth reporting to later pipeline stages.
# HEADER and INTERNSHIPS are excluded: HEADER is positional (not a real
# heading), and internships are commonly folded into EXPERIENCE.
_REPORTABLE_TYPES: tuple[ParsedSectionType, ...] = (
    ParsedSectionType.SUMMARY,
    ParsedSectionType.EDUCATION,
    ParsedSectionType.SKILLS,
    ParsedSectionType.EXPERIENCE,
    ParsedSectionType.PROJECTS,
    ParsedSectionType.CERTIFICATIONS,
    ParsedSectionType.ACHIEVEMENTS,
)

_HEADING_ALIASES: dict[str, ParsedSectionType] = {
    # SUMMARY
    "summary": ParsedSectionType.SUMMARY,
    "professional summary": ParsedSectionType.SUMMARY,
    "career summary": ParsedSectionType.SUMMARY,
    "executive summary": ParsedSectionType.SUMMARY,
    "profile": ParsedSectionType.SUMMARY,
    "professional profile": ParsedSectionType.SUMMARY,
    "about": ParsedSectionType.SUMMARY,
    "about me": ParsedSectionType.SUMMARY,
    "objective": ParsedSectionType.SUMMARY,
    "career objective": ParsedSectionType.SUMMARY,
    # EDUCATION
    "education": ParsedSectionType.EDUCATION,
    "educational background": ParsedSectionType.EDUCATION,
    "academic background": ParsedSectionType.EDUCATION,
    "academics": ParsedSectionType.EDUCATION,
    "academic qualifications": ParsedSectionType.EDUCATION,
    "qualifications": ParsedSectionType.EDUCATION,
    # SKILLS
    "skills": ParsedSectionType.SKILLS,
    "technical skills": ParsedSectionType.SKILLS,
    "key skills": ParsedSectionType.SKILLS,
    "core skills": ParsedSectionType.SKILLS,
    "core competencies": ParsedSectionType.SKILLS,
    "skills & abilities": ParsedSectionType.SKILLS,
    "skills and abilities": ParsedSectionType.SKILLS,
    "technologies": ParsedSectionType.SKILLS,
    "technical proficiencies": ParsedSectionType.SKILLS,
    "tools & technologies": ParsedSectionType.SKILLS,
    "tools and technologies": ParsedSectionType.SKILLS,
    # EXPERIENCE
    "experience": ParsedSectionType.EXPERIENCE,
    "work experience": ParsedSectionType.EXPERIENCE,
    "professional experience": ParsedSectionType.EXPERIENCE,
    "employment": ParsedSectionType.EXPERIENCE,
    "employment history": ParsedSectionType.EXPERIENCE,
    "work history": ParsedSectionType.EXPERIENCE,
    "relevant experience": ParsedSectionType.EXPERIENCE,
    "career history": ParsedSectionType.EXPERIENCE,
    # INTERNSHIPS
    "internships": ParsedSectionType.INTERNSHIPS,
    "internship": ParsedSectionType.INTERNSHIPS,
    "internship experience": ParsedSectionType.INTERNSHIPS,
    # PROJECTS
    "projects": ParsedSectionType.PROJECTS,
    "personal projects": ParsedSectionType.PROJECTS,
    "academic projects": ParsedSectionType.PROJECTS,
    "key projects": ParsedSectionType.PROJECTS,
    "selected projects": ParsedSectionType.PROJECTS,
    "side projects": ParsedSectionType.PROJECTS,
    # CERTIFICATIONS
    "certifications": ParsedSectionType.CERTIFICATIONS,
    "certificates": ParsedSectionType.CERTIFICATIONS,
    "certifications & licenses": ParsedSectionType.CERTIFICATIONS,
    "certifications and licenses": ParsedSectionType.CERTIFICATIONS,
    "licenses & certifications": ParsedSectionType.CERTIFICATIONS,
    "licenses and certifications": ParsedSectionType.CERTIFICATIONS,
    "courses & certifications": ParsedSectionType.CERTIFICATIONS,
    "courses and certifications": ParsedSectionType.CERTIFICATIONS,
    # ACHIEVEMENTS
    "achievements": ParsedSectionType.ACHIEVEMENTS,
    "accomplishments": ParsedSectionType.ACHIEVEMENTS,
    "awards": ParsedSectionType.ACHIEVEMENTS,
    "honors": ParsedSectionType.ACHIEVEMENTS,
    "honours": ParsedSectionType.ACHIEVEMENTS,
    "awards & achievements": ParsedSectionType.ACHIEVEMENTS,
    "awards and achievements": ParsedSectionType.ACHIEVEMENTS,
    "honors & awards": ParsedSectionType.ACHIEVEMENTS,
    "honors and awards": ParsedSectionType.ACHIEVEMENTS,
}

# A heading line, after canonicalization, must be short - real section
# headings are; sentences that merely *contain* a keyword are not.
_MAX_HEADING_LENGTH = 48

_EMAIL_PATTERN = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PHONE_PATTERN = re.compile(r"(?<![\w/])\+?\d[\d\s().-]{8,16}\d(?![\w/])")
_URL_PATTERN = re.compile(r"(?:https?://|www\.)[^\s|,;]+", re.IGNORECASE)
_LINKEDIN_PATTERN = re.compile(r"(?:www\.)?linkedin\.com/[^\s|,;]+", re.IGNORECASE)
_GITHUB_PATTERN = re.compile(r"(?:www\.)?github\.com/[^\s|,;]+", re.IGNORECASE)


@dataclass(frozen=True)
class ParsedSection:
    section_type: ParsedSectionType
    heading_text: str | None
    start_line: int
    end_line: int
    content: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "section_type": self.section_type.value,
            "heading_text": self.heading_text,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "content": self.content,
        }


@dataclass(frozen=True)
class SectionParseResult:
    sections: tuple[ParsedSection, ...]
    detected_section_types: tuple[str, ...]
    missing_section_types: tuple[str, ...]
    contact_info: dict[str, Any]


def _canonicalize_heading(line: str) -> str:
    text = line.strip().strip(":").strip()
    # Strip decorative leaders sometimes surviving normalization (e.g.
    # "— Experience —", "- Skills").
    text = text.strip("—–-•|· ").strip()
    return re.sub(r"\s+", " ", text).lower()


def classify_heading(line: str) -> ParsedSectionType | None:
    """Return the section type if this line is a recognized heading,
    otherwise None. Deliberately alias-exact: no fuzzy matching."""
    stripped = line.strip()
    if not stripped or len(stripped) > _MAX_HEADING_LENGTH:
        return None
    return _HEADING_ALIASES.get(_canonicalize_heading(stripped))


def extract_contact_info(text: str) -> dict[str, Any]:
    """Extract literal contact facts by regex. These are extracted facts
    (strings that appear in the document), never inferences."""
    emails = sorted(set(_EMAIL_PATTERN.findall(text)))
    phones = sorted(
        {
            re.sub(r"\s+", " ", match).strip()
            for match in _PHONE_PATTERN.findall(text)
            # Real phone numbers carry >= 10 digits; this filter rejects
            # date/year ranges like "2021 - 2025" (8 digits) that the
            # pattern's shape alone cannot distinguish.
            if sum(ch.isdigit() for ch in match) >= 10
        }
    )
    urls = sorted(set(_URL_PATTERN.findall(text)))
    linkedin = sorted(set(_LINKEDIN_PATTERN.findall(text)))
    github = sorted(set(_GITHUB_PATTERN.findall(text)))
    return {
        "emails": emails,
        "phones": phones,
        "urls": urls,
        "linkedin_urls": linkedin,
        "github_urls": github,
    }


def parse_sections(normalized_text: str) -> SectionParseResult:
    """Split normalized resume text into sections at recognized headings.

    Content before the first recognized heading becomes the ``HEADER``
    section (candidate name / contact block). If the same section type
    appears more than once (multi-column or multi-page artifacts), each
    occurrence is preserved as its own section, in document order.
    """
    lines = normalized_text.split("\n")

    boundaries: list[tuple[int, ParsedSectionType, str]] = []
    for index, line in enumerate(lines):
        section_type = classify_heading(line)
        if section_type is not None:
            boundaries.append((index, section_type, line.strip()))

    sections: list[ParsedSection] = []

    def _emit(
        section_type: ParsedSectionType,
        heading_text: str | None,
        start_line: int,
        end_line: int,
        content_lines: list[str],
    ) -> None:
        content = "\n".join(content_lines).strip()
        if not content and section_type is ParsedSectionType.HEADER:
            return
        sections.append(
            ParsedSection(
                section_type=section_type,
                heading_text=heading_text,
                start_line=start_line,
                end_line=end_line,
                content=content,
            )
        )

    first_heading_line = boundaries[0][0] if boundaries else len(lines)
    _emit(
        ParsedSectionType.HEADER,
        None,
        0,
        max(first_heading_line - 1, 0),
        lines[:first_heading_line],
    )

    for position, (heading_line, section_type, heading_text) in enumerate(boundaries):
        next_start = (
            boundaries[position + 1][0] if position + 1 < len(boundaries) else len(lines)
        )
        _emit(
            section_type,
            heading_text,
            heading_line,
            next_start - 1,
            lines[heading_line + 1 : next_start],
        )

    detected = tuple(
        dict.fromkeys(
            section.section_type.value
            for section in sections
            if section.section_type is not ParsedSectionType.HEADER
        )
    )
    missing = tuple(
        section_type.value
        for section_type in _REPORTABLE_TYPES
        if section_type.value not in detected
    )

    return SectionParseResult(
        sections=tuple(sections),
        detected_section_types=detected,
        missing_section_types=missing,
        contact_info=extract_contact_info(normalized_text),
    )
