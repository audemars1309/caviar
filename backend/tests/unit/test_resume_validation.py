"""Unit tests for resume upload validation (filename sanitization,
bounded body reads, and the layered file checks)."""

from __future__ import annotations

import io

import pytest
from fastapi import UploadFile

from app.services.resumes.validation import (
    InvalidResumeFileError,
    read_upload_bounded,
    sanitize_filename,
    validate_resume_upload,
)

_VALID_PDF_PREFIX = b"%PDF-1.7 fake body for validation-layer tests"


class TestSanitizeFilename:
    def test_plain_name_passes_through(self) -> None:
        assert sanitize_filename("resume.pdf") == "resume.pdf"

    def test_path_components_are_stripped(self) -> None:
        assert sanitize_filename("../../etc/passwd.pdf") == "passwd.pdf"
        assert sanitize_filename("C:\\Users\\x\\cv.pdf") == "cv.pdf"

    def test_control_characters_removed(self) -> None:
        assert sanitize_filename("cv\x00\x1b.pdf") == "cv.pdf"

    def test_empty_and_dot_names_fall_back(self) -> None:
        assert sanitize_filename(None) == "resume.pdf"
        assert sanitize_filename("") == "resume.pdf"
        assert sanitize_filename("..") == "resume.pdf"

    def test_overlong_name_truncated_preserving_extension(self) -> None:
        name = sanitize_filename("a" * 400 + ".pdf")
        assert len(name) <= 255
        assert name.endswith(".pdf")

    def test_whitespace_collapsed(self) -> None:
        assert sanitize_filename("  my   resume .pdf ") == "my resume .pdf"


class TestReadUploadBounded:
    async def test_reads_full_content_under_limit(self) -> None:
        upload = UploadFile(file=io.BytesIO(b"x" * 1000), filename="cv.pdf")
        assert await read_upload_bounded(upload, 2000) == b"x" * 1000

    async def test_rejects_oversized_body(self) -> None:
        upload = UploadFile(file=io.BytesIO(b"x" * 3000), filename="cv.pdf")
        with pytest.raises(InvalidResumeFileError):
            await read_upload_bounded(upload, 2000)


class TestValidateResumeUpload:
    def test_valid_pdf_accepted(self) -> None:
        validate_resume_upload(
            content=_VALID_PDF_PREFIX,
            filename="cv.pdf",
            declared_content_type="application/pdf",
        )

    def test_octet_stream_declaration_accepted_when_magic_matches(self) -> None:
        validate_resume_upload(
            content=_VALID_PDF_PREFIX,
            filename="cv.pdf",
            declared_content_type="application/octet-stream",
        )

    def test_empty_content_rejected(self) -> None:
        with pytest.raises(InvalidResumeFileError):
            validate_resume_upload(
                content=b"", filename="cv.pdf", declared_content_type="application/pdf"
            )

    def test_wrong_extension_rejected(self) -> None:
        with pytest.raises(InvalidResumeFileError):
            validate_resume_upload(
                content=_VALID_PDF_PREFIX,
                filename="cv.docx",
                declared_content_type="application/pdf",
            )

    def test_wrong_declared_type_rejected(self) -> None:
        with pytest.raises(InvalidResumeFileError):
            validate_resume_upload(
                content=_VALID_PDF_PREFIX, filename="cv.pdf", declared_content_type="image/png"
            )

    def test_magic_bytes_are_authoritative(self) -> None:
        with pytest.raises(InvalidResumeFileError):
            validate_resume_upload(
                content=b"MZ definitely not a pdf",
                filename="cv.pdf",
                declared_content_type="application/pdf",
            )
