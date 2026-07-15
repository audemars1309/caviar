"""Generated-PDF validation (Phase 7).

A zero exit code is not proof of a usable document. This module verifies
the actual output: non-empty, real PDF header, within the size cap, and
structurally parseable with a countable page count (pdfplumber - already
a project dependency).

Page overflow is a WARNING, never a failure, and never triggers content
removal: the spec forbids silently deleting user content to force a page
target. The structured ``PAGE_OVERFLOW`` warning carries the counts and
concrete recommendations (shorten bullets, remove low-priority content,
reorder sections, try another template) for the user to act on.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from typing import Any

import pdfplumber


class PdfValidationError(Exception):
    """The compiled output is not a usable PDF. ``code`` classifies."""

    def __init__(self, code: str, hint: str) -> None:
        super().__init__(f"{code}: {hint}")
        self.code = code
        self.hint = hint


@dataclass(frozen=True)
class PdfValidationResult:
    page_count: int
    file_size_bytes: int
    warnings: tuple[dict[str, Any], ...]


def validate_generated_pdf(
    pdf_bytes: bytes, *, max_bytes: int, max_pages: int
) -> PdfValidationResult:
    if not pdf_bytes:
        raise PdfValidationError("EMPTY_OUTPUT", "The compiled document is empty.")
    if not pdf_bytes.startswith(b"%PDF-"):
        raise PdfValidationError(
            "INVALID_PDF_HEADER", "The compiled output is not a valid PDF document."
        )
    if len(pdf_bytes) > max_bytes:
        raise PdfValidationError(
            "OUTPUT_TOO_LARGE",
            f"The generated PDF ({len(pdf_bytes)} bytes) exceeds the {max_bytes}-byte limit.",
        )
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            page_count = len(pdf.pages)
    except Exception as exc:
        raise PdfValidationError(
            "UNPARSEABLE_PDF", "The compiled output could not be parsed as a PDF."
        ) from exc
    if page_count == 0:
        raise PdfValidationError("ZERO_PAGES", "The compiled PDF contains no pages.")

    warnings: list[dict[str, Any]] = []
    if page_count > max_pages:
        warnings.append(
            {
                "code": "PAGE_OVERFLOW",
                "message": (
                    f"The resume compiled to {page_count} pages; this template targets "
                    f"{max_pages}. No content was removed."
                ),
                "page_count": page_count,
                "max_pages": max_pages,
                "recommendations": [
                    "Shorten long bullet points.",
                    "Remove low-priority entries or sections.",
                    "Reorder sections so the most relevant content leads.",
                    "Try a more compact template.",
                ],
            }
        )
    return PdfValidationResult(
        page_count=page_count,
        file_size_bytes=len(pdf_bytes),
        warnings=tuple(warnings),
    )
