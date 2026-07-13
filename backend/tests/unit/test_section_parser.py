"""Unit tests for deterministic section parsing and contact extraction."""

from __future__ import annotations

from app.services.resume_extraction.section_parser import (
    ParsedSectionType,
    classify_heading,
    extract_contact_info,
    parse_sections,
)

_SAMPLE = """Dharun Raj Gupta
dharun@example.com | +91 98765 43210
linkedin.com/in/dharunraj | github.com/audemars1309

Professional Summary
Backend engineer focused on Python and PostgreSQL.

EDUCATION
B.Tech in Computer Science, Example University, 2021 - 2025

Technical Skills
Python, FastAPI, SQLAlchemy, C++, AWS LAMBDA

Work Experience
Software Engineering Intern - Example Corp (2024)
- Built an async ingestion service

Projects
Caviar - AI career intelligence platform"""


class TestClassifyHeading:
    def test_known_aliases_match_case_insensitively(self) -> None:
        assert classify_heading("EDUCATION") is ParsedSectionType.EDUCATION
        assert classify_heading("Work Experience") is ParsedSectionType.EXPERIENCE
        assert classify_heading("technical skills:") is ParsedSectionType.SKILLS
        assert classify_heading("Awards & Achievements") is ParsedSectionType.ACHIEVEMENTS

    def test_unknown_lines_are_not_headings(self) -> None:
        assert classify_heading("AWS LAMBDA") is None
        assert classify_heading("Built an async ingestion service") is None
        assert classify_heading("") is None

    def test_sentences_containing_keywords_are_not_headings(self) -> None:
        assert classify_heading("My experience with distributed systems spans five years") is None


class TestParseSections:
    def test_header_holds_preamble(self) -> None:
        result = parse_sections(_SAMPLE)
        header = result.sections[0]
        assert header.section_type is ParsedSectionType.HEADER
        assert header.heading_text is None
        assert "Dharun Raj Gupta" in header.content

    def test_all_expected_sections_detected_in_order(self) -> None:
        result = parse_sections(_SAMPLE)
        assert result.detected_section_types == (
            "SUMMARY",
            "EDUCATION",
            "SKILLS",
            "EXPERIENCE",
            "PROJECTS",
        )

    def test_missing_sections_reported(self) -> None:
        result = parse_sections(_SAMPLE)
        assert set(result.missing_section_types) == {"CERTIFICATIONS", "ACHIEVEMENTS"}

    def test_section_content_and_line_ranges(self) -> None:
        result = parse_sections(_SAMPLE)
        skills = next(s for s in result.sections if s.section_type is ParsedSectionType.SKILLS)
        assert "AWS LAMBDA" in skills.content  # short caps line NOT treated as a heading
        assert skills.heading_text == "Technical Skills"
        lines = _SAMPLE.split("\n")
        assert lines[skills.start_line] == "Technical Skills"
        assert skills.end_line >= skills.start_line

    def test_no_headings_means_header_only(self) -> None:
        result = parse_sections("Just a paragraph of text\nwith no recognized headings.")
        assert len(result.sections) == 1
        assert result.sections[0].section_type is ParsedSectionType.HEADER
        assert result.detected_section_types == ()

    def test_duplicate_section_types_preserved_in_document_order(self) -> None:
        text = "EXPERIENCE\nJob A\n\nPROJECTS\nProject X\n\nEXPERIENCE\nJob B"
        result = parse_sections(text)
        types = [s.section_type for s in result.sections]
        assert types == [
            ParsedSectionType.EXPERIENCE,
            ParsedSectionType.PROJECTS,
            ParsedSectionType.EXPERIENCE,
        ]
        assert result.detected_section_types == ("EXPERIENCE", "PROJECTS")

    def test_deterministic(self) -> None:
        assert parse_sections(_SAMPLE) == parse_sections(_SAMPLE)

    def test_sections_serialize_to_plain_dicts(self) -> None:
        payload = [s.to_dict() for s in parse_sections(_SAMPLE).sections]
        assert payload[0]["section_type"] == "HEADER"
        assert {"section_type", "heading_text", "start_line", "end_line", "content"} == set(
            payload[0]
        )


class TestExtractContactInfo:
    def test_extracts_email_phone_and_urls(self) -> None:
        contact = extract_contact_info(_SAMPLE)
        assert contact["emails"] == ["dharun@example.com"]
        assert contact["phones"] == ["+91 98765 43210"]
        assert contact["linkedin_urls"] == ["linkedin.com/in/dharunraj"]
        assert contact["github_urls"] == ["github.com/audemars1309"]

    def test_no_false_positives_on_plain_text(self) -> None:
        contact = extract_contact_info("Improved throughput by 40% in 2024.")
        assert contact["emails"] == []
        assert contact["phones"] == []
        assert contact["urls"] == []
