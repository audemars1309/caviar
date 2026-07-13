"""Unit tests for PDF structural validation and text extraction, using
real reportlab-generated PDFs so pdfplumber's actual parsing path runs."""

from __future__ import annotations

import pytest

from app.services.resume_extraction.pdf_extractor import (
    PdfNoTextError,
    PdfStructureError,
    extract_pdf_text,
)
from tests.fixtures.pdf_fixtures import build_pdf, build_resume_pdf, build_textless_pdf


class TestExtractPdfText:
    async def test_valid_resume_extracts_text_and_page_count(self) -> None:
        result = await extract_pdf_text(build_resume_pdf(), max_page_count=15)
        assert result.page_count == 1
        assert "Dharun Raj Gupta" in result.raw_text
        assert "EXPERIENCE" in result.raw_text
        assert len(result.page_texts) == 1

    async def test_multipage_pdf_within_cap(self) -> None:
        result = await extract_pdf_text(build_pdf(["Page content"], pages=3), max_page_count=15)
        assert result.page_count == 3

    async def test_page_count_cap_enforced(self) -> None:
        content = build_pdf(["Page content"], pages=4)
        with pytest.raises(PdfStructureError) as excinfo:
            await extract_pdf_text(content, max_page_count=3)
        assert excinfo.value.reason == "PAGE_COUNT_EXCEEDED"

    async def test_textless_pdf_raises_no_text(self) -> None:
        with pytest.raises(PdfNoTextError):
            await extract_pdf_text(build_textless_pdf(), max_page_count=15)

    async def test_garbage_bytes_rejected_as_unreadable(self) -> None:
        with pytest.raises(PdfStructureError) as excinfo:
            await extract_pdf_text(b"%PDF-1.7 then complete garbage", max_page_count=15)
        assert excinfo.value.reason in ("UNREADABLE_OR_ENCRYPTED", "ZERO_PAGES")

    async def test_truncated_pdf_rejected(self) -> None:
        content = build_resume_pdf()[:200]
        with pytest.raises(PdfStructureError):
            await extract_pdf_text(content, max_page_count=15)
