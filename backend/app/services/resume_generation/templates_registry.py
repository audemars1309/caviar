"""Caviar-owned LaTeX template registry (Phase 7).

Templates live in the application tree (``app/templates/resumes/<id>/``)
as a ``template.tex.j2`` plus a validated ``metadata.json``. They are
code: versioned, reviewed, and shipped with the application. There is no
mechanism - deliberately - for loading a template from user input, the
database, storage, or any request-supplied path: arbitrary user-uploaded
``.tex`` execution is impossible because the only template source is
this directory and the only lookup key is a registry-validated id.

Every generation stores the template id AND version it used, so
historical PDFs stay traceable to the exact template that produced them
after templates evolve.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.core.exceptions import NotFoundError

_TEMPLATES_ROOT = Path(__file__).resolve().parent.parent.parent / "templates" / "resumes"
_TEMPLATE_SOURCE_FILENAME = "template.tex.j2"


class TemplateNotFoundError(NotFoundError):
    error_code = "template_not_found"


class TemplateMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    template_id: str = Field(pattern=r"^[a-z0-9_]{1,64}$")
    name: str
    template_version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    description: str
    engine: Literal["tectonic-xetex"]
    ats_classification: Literal["ATS_SAFE", "ATS_MODERATE"]
    supported_sections: list[str]
    default_section_order: list[str]
    max_pages: int = Field(gt=0)
    status: Literal["APPROVED", "DRAFT", "RETIRED"]


@lru_cache
def load_registry() -> dict[str, TemplateMetadata]:
    """All templates shipped with this build, validated at first use. A
    malformed shipped template is a build defect and fails loudly."""
    registry: dict[str, TemplateMetadata] = {}
    for metadata_path in sorted(_TEMPLATES_ROOT.glob("*/metadata.json")):
        metadata = TemplateMetadata.model_validate(
            json.loads(metadata_path.read_text(encoding="utf-8"))
        )
        directory_name = metadata_path.parent.name
        if metadata.template_id != directory_name:
            raise RuntimeError(
                f"Template metadata id '{metadata.template_id}' does not match its "
                f"directory '{directory_name}'."
            )
        if not (metadata_path.parent / _TEMPLATE_SOURCE_FILENAME).is_file():
            raise RuntimeError(f"Template '{metadata.template_id}' is missing its source.")
        registry[metadata.template_id] = metadata
    if not registry:
        raise RuntimeError(f"No resume templates found under {_TEMPLATES_ROOT}.")
    return registry


def list_approved_templates() -> list[TemplateMetadata]:
    return [item for item in load_registry().values() if item.status == "APPROVED"]


def get_approved_template(template_id: str) -> TemplateMetadata:
    """Registry-validated lookup - the ONLY way a template is selected."""
    template = load_registry().get(template_id)
    if template is None or template.status != "APPROVED":
        raise TemplateNotFoundError(f"Unknown resume template '{template_id}'.")
    return template


def template_source_dir(template_id: str) -> Path:
    return _TEMPLATES_ROOT / template_id


def template_source_filename() -> str:
    return _TEMPLATE_SOURCE_FILENAME
