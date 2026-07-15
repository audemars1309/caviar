"""Unit tests for the template registry, the render-context escaping
boundary, and Jinja rendering of caviar_classic."""

from __future__ import annotations

import pytest

from app.services.resume_builder.section_schemas import BuilderSectionType
from app.services.resume_generation.renderer import build_render_context, render_latex
from app.services.resume_generation.templates_registry import (
    TemplateNotFoundError,
    get_approved_template,
    list_approved_templates,
    load_registry,
)

FULL_SECTIONS = {
    BuilderSectionType.PERSONAL_INFO: {
        "full_name": "Dharun Raj Gupta",
        "email": "dharun@example.com",
        "phone": "+91 98765 43210",
        "github_url": "https://github.com/audemars1309",
    },
    BuilderSectionType.SUMMARY: {"text": "Backend engineer: Python, C# & R&D, 100% focus."},
    BuilderSectionType.EXPERIENCE: {
        "entries": [
            {
                "company": "Example Corp",
                "title": "SWE Intern",
                "start_date": "May 2024",
                "end_date": "Aug 2024",
                "bullets": [r"Injected? \input{/etc/passwd} & $500 saved"],
            }
        ]
    },
    BuilderSectionType.SKILLS: {
        "groups": [{"name": "Languages", "skills": ["Python", "C++", "C#"]}]
    },
    BuilderSectionType.EDUCATION: {
        "entries": [
            {
                "institution": "Example University",
                "degree": "B.Tech",
                "field_of_study": "CS",
                "gpa": "9.1/10",
                "start_date": "2021",
                "end_date": "2025",
            }
        ]
    },
    BuilderSectionType.CERTIFICATIONS: {
        "entries": [{"name": "AWS SAA", "issuer": "Amazon", "date": "2025"}]
    },
    BuilderSectionType.ACHIEVEMENTS: {"entries": [{"text": "Won 1st_place", "date": "2024"}]},
}


class TestTemplateRegistry:
    def test_registry_loads_and_validates(self) -> None:
        registry = load_registry()
        assert "caviar_classic" in registry
        metadata = registry["caviar_classic"]
        assert metadata.template_version == "1.0.0"
        assert metadata.status == "APPROVED"
        assert metadata.max_pages == 2

    def test_only_approved_templates_selectable(self) -> None:
        assert get_approved_template("caviar_classic").template_id == "caviar_classic"
        assert [t.template_id for t in list_approved_templates()] == ["caviar_classic"]

    def test_unknown_and_path_traversal_ids_rejected(self) -> None:
        for bad_id in ("nope", "../evil", "/etc/passwd", "caviar_classic/../x"):
            with pytest.raises(TemplateNotFoundError):
                get_approved_template(bad_id)


class TestRenderContextBoundary:
    def test_every_string_is_escaped_exactly_once(self) -> None:
        template = get_approved_template("caviar_classic")
        context = build_render_context(FULL_SECTIONS, template)
        summary = context["summary"]["text"]
        assert summary == r"Backend engineer: Python, C\# \& R\&D, 100\% focus."
        bullet = context["entry_blocks"][0]["entries"][0]["bullets"][0]
        assert r"\textbackslash{}input\{/etc/passwd\}" in bullet
        assert r"\$500" in bullet
        # No double escaping anywhere: an escaped ampersand never becomes \\&.
        assert r"\\&" not in summary

    def test_missing_optional_sections_yield_empty_context(self) -> None:
        template = get_approved_template("caviar_classic")
        context = build_render_context(
            {
                BuilderSectionType.PERSONAL_INFO: FULL_SECTIONS[
                    BuilderSectionType.PERSONAL_INFO
                ],
                BuilderSectionType.SKILLS: FULL_SECTIONS[BuilderSectionType.SKILLS],
            },
            template,
        )
        assert context["summary"] is None
        assert context["entry_blocks"] == []
        assert context["certifications"] is None

    def test_blocks_follow_template_default_order(self) -> None:
        template = get_approved_template("caviar_classic")
        context = build_render_context(FULL_SECTIONS, template)
        assert [block["heading"] for block in context["entry_blocks"]] == [
            "Experience",
            "Education",
        ]


class TestRenderLatex:
    def test_full_render_contains_escaped_content_only(self) -> None:
        template = get_approved_template("caviar_classic")
        source = render_latex(template, build_render_context(FULL_SECTIONS, template))
        # The leading template comment strips to a blank line, which TeX ignores.
        assert source.lstrip().startswith(r"\documentclass")
        assert "Dharun Raj Gupta" in source
        assert r"C\# \& R\&D" in source
        assert r"\textbackslash{}input\{/etc/passwd\}" in source
        assert r"\input{/etc/passwd}" not in source  # injection cannot survive
        assert "1st\\_place" in source
        assert r"\end{document}" in source

    def test_minimal_resume_renders(self) -> None:
        template = get_approved_template("caviar_classic")
        source = render_latex(
            template,
            build_render_context(
                {
                    BuilderSectionType.PERSONAL_INFO: {"full_name": "Zoë Müller"},
                    BuilderSectionType.SKILLS: {
                        "groups": [{"name": "Core", "skills": ["Python"]}]
                    },
                },
                template,
            ),
        )
        assert "Zoë Müller" in source  # unicode preserved for XeTeX
        assert "Experience" not in source

    def test_empty_bullet_lists_render_without_itemize(self) -> None:
        template = get_approved_template("caviar_classic")
        sections = {
            BuilderSectionType.PERSONAL_INFO: {"full_name": "A B"},
            BuilderSectionType.EXPERIENCE: {
                "entries": [{"company": "X", "title": "Y", "bullets": []}]
            },
        }
        source = render_latex(template, build_render_context(sections, template))
        assert r"\begin{itemize}" not in source

    def test_render_is_deterministic(self) -> None:
        template = get_approved_template("caviar_classic")
        first = render_latex(template, build_render_context(FULL_SECTIONS, template))
        second = render_latex(template, build_render_context(FULL_SECTIONS, template))
        assert first == second
