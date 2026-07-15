"""Unit tests for Resume Builder structured section schemas and the
deterministic fabrication guard."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.services.resume_builder.fabrication_guard import (
    extract_numbers,
    find_unsupported_numbers,
    source_numbers_from_content,
)
from app.services.resume_builder.section_schemas import (
    SECTION_CONTENT_SCHEMAS,
    SECTION_SORT_ORDER,
    BuilderSectionType,
    validate_section_content,
)

VALID_CONTENT: dict[BuilderSectionType, dict] = {
    BuilderSectionType.PERSONAL_INFO: {
        "full_name": "Dharun Raj Gupta",
        "email": "dharun@example.com",
        "phone": "+91 98765 43210",
        "github_url": "https://github.com/audemars1309",
    },
    BuilderSectionType.SUMMARY: {"text": "Backend engineer focused on Python and PostgreSQL."},
    BuilderSectionType.EDUCATION: {
        "entries": [
            {
                "institution": "Example University",
                "degree": "B.Tech",
                "field_of_study": "Computer Science",
                "start_date": "2021",
                "end_date": "Expected May 2026",
                "highlights": ["Robotics team president"],
            }
        ]
    },
    BuilderSectionType.SKILLS: {
        "groups": [
            {"name": "Languages", "skills": ["Python", "C++", "TypeScript"]},
            {"name": "Backend", "skills": ["FastAPI", "SQLAlchemy", "PostgreSQL"]},
        ]
    },
    BuilderSectionType.EXPERIENCE: {
        "entries": [
            {
                "company": "Example Corp",
                "title": "Software Engineering Intern",
                "start_date": "May 2024",
                "end_date": "Aug 2024",
                "bullets": ["Built an async ingestion service handling 500 requests per minute"],
            }
        ]
    },
    BuilderSectionType.INTERNSHIPS: {
        "entries": [{"company": "Startup", "title": "Intern", "bullets": ["Wrote tests"]}]
    },
    BuilderSectionType.PROJECTS: {
        "entries": [
            {
                "name": "Caviar",
                "description": "AI career intelligence platform.",
                "technologies": ["FastAPI", "Supabase"],
                "bullets": ["Designed RLS-backed multi-tenant schema"],
            }
        ]
    },
    BuilderSectionType.CERTIFICATIONS: {
        "entries": [{"name": "AWS SAA", "issuer": "Amazon", "date": "2025"}]
    },
    BuilderSectionType.ACHIEVEMENTS: {
        "entries": [{"text": "Won university hackathon", "date": "2024"}]
    },
}


class TestSectionContentSchemas:
    def test_every_section_type_has_schema_and_sort_order(self) -> None:
        assert set(SECTION_CONTENT_SCHEMAS) == set(BuilderSectionType)
        assert set(SECTION_SORT_ORDER) == set(BuilderSectionType)
        assert sorted(SECTION_SORT_ORDER.values()) == list(range(9))

    @pytest.mark.parametrize("section_type", list(BuilderSectionType))
    def test_valid_content_accepted_and_normalized(
        self, section_type: BuilderSectionType
    ) -> None:
        normalized = validate_section_content(section_type, VALID_CONTENT[section_type])
        assert isinstance(normalized, dict)
        # Round-trips through its own schema (normalization is stable).
        assert validate_section_content(section_type, normalized) == normalized

    def test_unknown_keys_rejected(self) -> None:
        with pytest.raises(ValidationError):
            validate_section_content(
                BuilderSectionType.SUMMARY, {"text": "ok", "font": "Comic Sans"}
            )

    def test_required_fields_enforced(self) -> None:
        with pytest.raises(ValidationError):
            validate_section_content(BuilderSectionType.PERSONAL_INFO, {"email": "a@b.co"})
        with pytest.raises(ValidationError):
            validate_section_content(
                BuilderSectionType.EXPERIENCE, {"entries": [{"company": "X"}]}
            )

    def test_empty_entry_lists_rejected(self) -> None:
        for section_type in (
            BuilderSectionType.EDUCATION,
            BuilderSectionType.EXPERIENCE,
            BuilderSectionType.PROJECTS,
        ):
            with pytest.raises(ValidationError):
                validate_section_content(section_type, {"entries": []})

    def test_length_caps_enforced(self) -> None:
        with pytest.raises(ValidationError):
            validate_section_content(BuilderSectionType.SUMMARY, {"text": "x" * 2001})
        entry = dict(VALID_CONTENT[BuilderSectionType.EXPERIENCE]["entries"][0])
        entry["bullets"] = ["b"] * 21
        with pytest.raises(ValidationError):
            validate_section_content(BuilderSectionType.EXPERIENCE, {"entries": [entry]})

    def test_whole_resume_as_single_text_blob_rejected(self) -> None:
        # The structural point of the builder: no giant text field.
        with pytest.raises(ValidationError):
            validate_section_content(
                BuilderSectionType.EXPERIENCE, {"text": "my entire resume..."}
            )

    def test_internships_share_experience_shape(self) -> None:
        assert (
            SECTION_CONTENT_SCHEMAS[BuilderSectionType.INTERNSHIPS]
            is SECTION_CONTENT_SCHEMAS[BuilderSectionType.EXPERIENCE]
        )


class TestFabricationGuard:
    def test_extracts_and_normalizes_numbers(self) -> None:
        assert extract_numbers("Cut costs by 1,200.50 units in 2024") == {"1200.5", "2024"}

    def test_source_numbers_from_nested_content(self) -> None:
        numbers = source_numbers_from_content(
            {"entries": [{"bullets": ["handled 500 requests"], "start_date": "May 2024"}]}
        )
        assert {"500", "2024"} <= numbers

    def test_supported_numbers_not_flagged(self) -> None:
        source = source_numbers_from_content({"bullets": ["handled 500 requests"]})
        assert find_unsupported_numbers("Handled 500 requests per minute", source) == []

    def test_fabricated_number_flagged(self) -> None:
        source = source_numbers_from_content({"bullets": ["improved the service"]})
        assert find_unsupported_numbers("Improved the service by 40%", source) == ["40"]

    def test_bracketed_placeholders_exempt(self) -> None:
        source = source_numbers_from_content({"bullets": ["reduced latency"]})
        improved = "Reduced latency [add: estimated % reduction, e.g. 20-30%]"
        assert find_unsupported_numbers(improved, source) == []

    def test_grouping_and_decimal_variants_match(self) -> None:
        source = source_numbers_from_content({"bullets": ["served 1,200 users"]})
        assert find_unsupported_numbers("Served 1200 users", source) == []
        source = source_numbers_from_content({"bullets": ["uptime 99.90"]})
        assert find_unsupported_numbers("Achieved 99.9 uptime", source) == []

    def test_duplicates_reported_once_in_order(self) -> None:
        source: set[str] = set()
        result = find_unsupported_numbers("Grew 40% then 40% then 15%", source)
        assert result == ["40", "15"]
