"""Resume upload validation.

Everything about an uploaded file is untrusted: its name, its declared
content type, its declared size, and its bytes. This module validates all
of them deterministically before anything is stored.

Validation layers, in order:
  1. Bounded read - the request body is read in chunks and abandoned the
     moment it exceeds the configured maximum, so an oversized upload can
     never be buffered fully into memory.
  2. Extension - the sanitized original filename must end in ``.pdf``.
  3. Declared content type - must be a PDF-plausible declaration. The
     declaration is advisory only (browsers lie; some send
     ``application/octet-stream``), which is why layer 4 exists.
  4. Magic bytes - the file must actually begin with ``%PDF-``. This is
     the authoritative type check.

Structural PDF validation (parseable, not encrypted, page-count cap) is a
separate concern handled by ``pdf_extractor``, which has to open the
document anyway.
"""

from __future__ import annotations

import re
import unicodedata

from fastapi import UploadFile

from app.core.exceptions import ValidationFailedError

_PDF_MAGIC = b"%PDF-"

# Declarations accepted as "plausibly a PDF". Real type enforcement is the
# magic-byte check; this list only rejects obviously-wrong declarations
# (e.g. image/png) early with a clearer error.
_ACCEPTED_DECLARED_TYPES = frozenset(
    {"application/pdf", "application/x-pdf", "application/octet-stream"}
)

_READ_CHUNK_BYTES = 64 * 1024
_MAX_FILENAME_LENGTH = 255


class InvalidResumeFileError(ValidationFailedError):
    error_code = "invalid_resume_file"


def sanitize_filename(raw_name: str | None) -> str:
    """Reduce a client-supplied filename to a safe display string.

    The result is used ONLY as display metadata (``original_filename``);
    storage paths are always server-generated UUIDs and never derived from
    this value.
    """
    if not raw_name:
        return "resume.pdf"
    # Strip any path components regardless of client OS convention.
    name = raw_name.replace("\\", "/").rsplit("/", 1)[-1]
    # Drop control characters and normalize to a sane unicode form.
    name = unicodedata.normalize("NFKC", name)
    name = "".join(ch for ch in name if unicodedata.category(ch)[0] != "C")
    name = re.sub(r"\s+", " ", name).strip()
    if not name or name in {".", ".."}:
        return "resume.pdf"
    if len(name) > _MAX_FILENAME_LENGTH:
        stem, dot, ext = name.rpartition(".")
        if dot and len(ext) <= 10:
            keep = _MAX_FILENAME_LENGTH - len(ext) - 1
            name = f"{stem[:keep]}.{ext}"
        else:
            name = name[:_MAX_FILENAME_LENGTH]
    return name


async def read_upload_bounded(upload: UploadFile, max_bytes: int) -> bytes:
    """Read the upload in chunks, failing fast once it exceeds
    ``max_bytes`` instead of buffering an arbitrarily large body."""
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await upload.read(_READ_CHUNK_BYTES)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise InvalidResumeFileError(
                f"The file exceeds the maximum allowed size of {max_bytes} bytes.",
                details={"max_bytes": max_bytes},
            )
        chunks.append(chunk)
    return b"".join(chunks)


def validate_resume_upload(
    *, content: bytes, filename: str, declared_content_type: str | None
) -> None:
    """Apply the deterministic pre-storage checks. Raises
    ``InvalidResumeFileError`` on the first failure."""
    if not content:
        raise InvalidResumeFileError("The uploaded file is empty.")

    if not filename.lower().endswith(".pdf"):
        raise InvalidResumeFileError("Only PDF resumes are supported (.pdf extension required).")

    declared = (declared_content_type or "").split(";", 1)[0].strip().lower()
    if declared and declared not in _ACCEPTED_DECLARED_TYPES:
        raise InvalidResumeFileError(
            "The uploaded file does not declare a PDF content type.",
            details={"declared_content_type": declared},
        )

    if not content.startswith(_PDF_MAGIC):
        raise InvalidResumeFileError("The uploaded file is not a valid PDF document.")
