"""Controlled server-side template rendering (Phase 7).

``build_render_context`` IS the escaping boundary: it walks the validated
structured section content and calls ``prepare_for_latex`` on every
string exactly once while assembling a template-shaped context. Templates
receive only pre-escaped strings and simple presence flags/lists -
content and presentation stay fully separated, and no raw user or AI
text can ever reach LaTeX.

Jinja environment: custom delimiters ``(((...)))`` / ``((*...*))`` /
``((=...=))`` so LaTeX's braces and percent signs never collide with
template syntax; ``StrictUndefined`` so a template/context mismatch is a
loud RENDERING failure, never silently empty output; autoescape off
(that machinery is HTML-specific - LaTeX safety is owned entirely by the
escaping boundary).
"""

from __future__ import annotations

from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined
from jinja2 import TemplateError as JinjaTemplateError

from app.core.exceptions import AppError
from app.services.resume_builder.section_schemas import BuilderSectionType
from app.services.resume_generation.latex_escape import prepare_for_latex
from app.services.resume_generation.templates_registry import (
    TemplateMetadata,
    template_source_dir,
    template_source_filename,
)


class RenderingError(AppError):
    """Template rendering failed (template/context defect, not user
    error). Sanitized; carries no user content."""

    status_code = 500
    error_code = "template_rendering_failed"


def _esc(value: str | None) -> str:
    return prepare_for_latex(value) if value else ""


def _join_present(parts: list[str | None], separator: str) -> str:
    return separator.join(_esc(part) for part in parts if part)


def _date_range(start: str | None, end: str | None) -> str:
    if start and end:
        return f"{_esc(start)} -- {_esc(end)}"
    return _esc(start or end)


def _experience_block(heading: str, content: dict[str, Any]) -> dict[str, Any]:
    return {
        "heading": prepare_for_latex(heading),
        "entries": [
            {
                "primary": _esc(entry.get("title")),
                "secondary": _esc(entry.get("company")),
                "location": _esc(entry.get("location")),
                "dates": _date_range(entry.get("start_date"), entry.get("end_date")),
                "description": "",
                "bullets": [_esc(bullet) for bullet in entry.get("bullets", []) if bullet],
            }
            for entry in content.get("entries", [])
        ],
    }


def _projects_block(content: dict[str, Any]) -> dict[str, Any]:
    entries = []
    for entry in content.get("entries", []):
        technologies = _join_present(entry.get("technologies", []), ", ")
        entries.append(
            {
                "primary": _esc(entry.get("name")),
                "secondary": technologies,
                "location": _esc(entry.get("url")),
                "dates": "",
                "description": _esc(entry.get("description")),
                "bullets": [_esc(bullet) for bullet in entry.get("bullets", []) if bullet],
            }
        )
    return {"heading": "Projects", "entries": entries}


def _education_block(content: dict[str, Any]) -> dict[str, Any]:
    entries = []
    for entry in content.get("entries", []):
        degree_line = _join_present([entry.get("degree"), entry.get("field_of_study")], ", ")
        institution = _join_present([entry.get("institution"), entry.get("location")], ", ")
        gpa = entry.get("gpa")
        bullets = [_esc(item) for item in entry.get("highlights", []) if item]
        if gpa:
            bullets.insert(0, f"GPA: {_esc(gpa)}")
        entries.append(
            {
                "primary": degree_line,
                "secondary": institution,
                "location": "",
                "dates": _date_range(entry.get("start_date"), entry.get("end_date")),
                "description": "",
                "bullets": bullets,
            }
        )
    return {"heading": "Education", "entries": entries}


def build_render_context(
    sections: dict[str, dict[str, Any]], template: TemplateMetadata
) -> dict[str, Any]:
    """Structured section content -> template-shaped, fully escaped
    context. The ONLY place ``prepare_for_latex`` is invoked."""
    context: dict[str, Any] = {
        "personal_info": None,
        "summary": None,
        "entry_blocks": [],
        "skills": None,
        "certifications": None,
        "achievements": None,
    }

    personal = sections.get(BuilderSectionType.PERSONAL_INFO)
    if personal:
        contact_line = _join_present(
            [
                personal.get("email"),
                personal.get("phone"),
                personal.get("location"),
                personal.get("linkedin_url"),
                personal.get("github_url"),
                personal.get("website_url"),
            ],
            r" \textbar{} ",
        )
        context["personal_info"] = {
            "full_name": _esc(personal.get("full_name")),
            "contact_line": contact_line,
        }

    summary = sections.get(BuilderSectionType.SUMMARY)
    if summary and summary.get("text"):
        context["summary"] = {"text": _esc(summary["text"])}

    # Entry blocks follow the template's default section order for the
    # experience-shaped sections it declares.
    block_builders = {
        BuilderSectionType.EXPERIENCE: lambda c: _experience_block("Experience", c),
        BuilderSectionType.INTERNSHIPS: lambda c: _experience_block("Internships", c),
        BuilderSectionType.PROJECTS: _projects_block,
        BuilderSectionType.EDUCATION: _education_block,
    }
    for section_name in template.default_section_order:
        try:
            section_type = BuilderSectionType(section_name)
        except ValueError:
            continue
        content = sections.get(section_type)
        if content and section_type in block_builders:
            context["entry_blocks"].append(block_builders[section_type](content))

    skills = sections.get(BuilderSectionType.SKILLS)
    if skills:
        context["skills"] = {
            "groups": [
                {
                    "name": _esc(group.get("name")),
                    "skills_line": _join_present(group.get("skills", []), ", "),
                }
                for group in skills.get("groups", [])
            ]
        }

    certifications = sections.get(BuilderSectionType.CERTIFICATIONS)
    if certifications:
        context["certifications"] = {
            "entries": [
                {
                    "line": _join_present(
                        [entry.get("name"), entry.get("issuer"), entry.get("date")], " -- "
                    )
                }
                for entry in certifications.get("entries", [])
            ]
        }

    achievements = sections.get(BuilderSectionType.ACHIEVEMENTS)
    if achievements:
        context["achievements"] = {
            "entries": [
                {"line": _join_present([entry.get("text"), entry.get("date")], " -- ")}
                for entry in achievements.get("entries", [])
            ]
        }

    return context


def render_latex(template: TemplateMetadata, context: dict[str, Any]) -> str:
    """Render the approved template with a fully escaped context."""
    environment = Environment(
        loader=FileSystemLoader(template_source_dir(template.template_id)),
        block_start_string="((*",
        block_end_string="*))",
        variable_start_string="(((",
        variable_end_string=")))",
        comment_start_string="((=",
        comment_end_string="=))",
        undefined=StrictUndefined,
        autoescape=False,
        keep_trailing_newline=True,
    )
    try:
        return environment.get_template(template_source_filename()).render(**context)
    except JinjaTemplateError as exc:
        # Sanitized: class name only - Jinja messages can echo context
        # fragments, and this is an operator-facing defect signal anyway.
        raise RenderingError(
            f"Template rendering failed ({exc.__class__.__name__})."
        ) from exc
