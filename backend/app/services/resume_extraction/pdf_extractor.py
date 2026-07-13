"""PDF structural validation and text extraction.

Built on pdfplumber (MIT-licensed, on top of pdfminer.six). PyMuPDF was
deliberately rejected: it is AGPL-licensed, which is incompatible with
Caviar as a proprietary product without a commercial license.

Two distinct outcomes are modeled, because they demand different product
behavior:

  * ``PdfStructureError`` - the bytes are not an acceptable PDF at all
    (unparseable, encrypted, zero pages, over the page cap). The upload is
    REJECTED; storing it would be storing junk.
  * ``PdfNoTextError`` - the PDF is structurally fine but yields no
    extractable text (typically a scanned image resume). The upload is
    still STORED and the resume is marked extraction FAILED with reason
    ``NO_TEXT_LAYER`` - retryable, and a future OCR path can process it.

pdfplumber is synchronous, CPU/IO-bound work; the async entry point runs
it in a worker thread so it never blocks the event loop.
"""

from __future__ import annotations

import asyncio
import io
import logging
from dataclasses import dataclass

import pdfplumber

from app.core.exceptions import ValidationFailedError

logger = logging.getLogger(__name__)


class PdfStructureError(ValidationFailedError):
    """The bytes are not an acceptable PDF (reject the upload)."""

    error_code = "invalid_pdf_structure"

    def __init__(self, message: str, *, reason: str) -> None:
        super().__init__(message, details={"reason": reason})
        self.reason = reason


class PdfNoTextError(Exception):
    """Structurally valid PDF with no extractable text (store the file,
    mark extraction FAILED with a retryable reason)."""

    reason = "NO_TEXT_LAYER"


@dataclass(frozen=True)
class PdfExtractionResult:
    raw_text: str
    page_count: int
    page_texts: tuple[str, ...]


def _extract_sync(content: bytes, max_page_count: int) -> PdfExtractionResult:
    try:
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            page_count = len(pdf.pages)
            if page_count == 0:
                raise PdfStructureError(
                    "The PDF contains no pages.", reason="ZERO_PAGES"
                )
            if page_count > max_page_count:
                raise PdfStructureError(
                    f"The PDF has {page_count} pages, exceeding the maximum of "
                    f"{max_page_count} pages for a resume.",
                    reason="PAGE_COUNT_EXCEEDED",
                )
            page_texts = tuple((page.extract_text() or "") for page in pdf.pages)
    except PdfStructureError:
        raise
    except Exception as exc:
        # pdfminer raises a family of exceptions for password-protected and
        # malformed documents; all of them mean "not an acceptable PDF"
        # from the product's perspective. The class name is logged for
        # operators; the client gets a sanitized message.
        logger.info("PDF parsing failed: %s", exc.__class__.__name__)
        raise PdfStructureError(
            "The PDF could not be read. Encrypted or corrupted files are not supported.",
            reason="UNREADABLE_OR_ENCRYPTED",
        ) from exc

    raw_text = "\n\n".join(text for text in page_texts if text).strip()
    if not raw_text:
        raise PdfNoTextError()

    return PdfExtractionResult(raw_text=raw_text, page_count=page_count, page_texts=page_texts)


async def extract_pdf_text(content: bytes, *, max_page_count: int) -> PdfExtractionResult:
    """Validate PDF structure and extract its text without blocking the
    event loop."""
    return await asyncio.to_thread(_extract_sync, content, max_page_count)
