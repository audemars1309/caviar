"""Unit tests for the compilation service (against fake compiler
executables - real subprocess execution, real timeouts, real cleanup,
no TeX required) and the PDF validator.

A real-Tectonic golden compile runs automatically when a working Tectonic
with a usable bundle is present (developer machines / CI with cache), and
skips otherwise (this sandbox blocks the bundle CDN).
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from app.services.resume_generation.compiler import (
    CompilationFailedError,
    compile_latex,
)
from app.services.resume_generation.pdf_validator import (
    PdfValidationError,
    validate_generated_pdf,
)
from tests.fixtures.pdf_fixtures import build_pdf, build_resume_pdf

_MAX_PDF_BYTES = 5_242_880


def _write_fake_compiler(tmp_path: Path, body: str) -> str:
    """A fake 'tectonic' executable. Contract mirrors the real CLI as the
    service invokes it: argv = [bin, --outdir, DIR, --chatter, minimal,
    --keep-logs, (--only-cached,) TEXFILE] so the outdir is $2;
    --version supported."""
    script = tmp_path / "fake-tectonic"
    script.write_text(
        "#!/bin/sh\n"
        'if [ "$1" = "--version" ]; then echo "tectonic 0.15.0-fake"; exit 0; fi\n'
        'OUTDIR="$2"\n' + body,
        encoding="utf-8",
    )
    script.chmod(0o755)
    return str(script)


@pytest.fixture
def fake_pdf_env(tmp_path, monkeypatch):
    pdf_path = tmp_path / "fixture.pdf"
    pdf_path.write_bytes(build_resume_pdf())
    monkeypatch.setenv("CAVIAR_FAKE_PDF", str(pdf_path))
    return pdf_path


async def _compile(binary: str, **overrides) -> object:
    kwargs = dict(
        binary_path=binary,
        timeout_seconds=10.0,
        only_cached=False,
        max_pdf_bytes=_MAX_PDF_BYTES,
    )
    kwargs.update(overrides)
    return await compile_latex(r"\documentclass{article}...", **kwargs)


class TestCompileLatex:
    async def test_successful_compile_returns_pdf_and_metadata(
        self, tmp_path, fake_pdf_env
    ) -> None:
        binary = _write_fake_compiler(
            tmp_path, 'cp "$CAVIAR_FAKE_PDF" "$OUTDIR/main.pdf"\nexit 0\n'
        )
        result = await _compile(binary)
        assert result.pdf_bytes.startswith(b"%PDF-")
        assert result.compiler_version == "tectonic 0.15.0-fake"
        assert result.duration_ms >= 0
        assert result.unsupported_glyphs == ()

    async def test_unsupported_glyphs_parsed_from_log(self, tmp_path, fake_pdf_env) -> None:
        binary = _write_fake_compiler(
            tmp_path,
            'cp "$CAVIAR_FAKE_PDF" "$OUTDIR/main.pdf"\n'
            'printf "Missing character: There is no 東 in font cmr10!\\n'
            "Missing character: There is no 京 in font cmr10!\\n"
            'Missing character: There is no 東 in font cmr10!\\n" > "$OUTDIR/main.log"\n'
            "exit 0\n",
        )
        result = await _compile(binary)
        assert result.unsupported_glyphs == ("東", "京")  # de-duplicated, ordered

    async def test_nonzero_exit_raises_sanitized_failure(self, tmp_path) -> None:
        binary = _write_fake_compiler(
            tmp_path, 'echo "error: something exploded in $OUTDIR/main.tex" >&2\nexit 1\n'
        )
        with pytest.raises(CompilationFailedError) as excinfo:
            await _compile(binary)
        assert excinfo.value.code == "COMPILER_FAILED"
        assert "<workdir>" in excinfo.value.hint  # temp path scrubbed
        assert "caviar-gen-" not in excinfo.value.hint

    async def test_timeout_kills_and_classifies(self, tmp_path) -> None:
        binary = _write_fake_compiler(tmp_path, "sleep 30\n")
        with pytest.raises(CompilationFailedError) as excinfo:
            await _compile(binary, timeout_seconds=0.5)
        assert excinfo.value.code == "COMPILER_TIMEOUT"

    async def test_missing_binary_classified(self) -> None:
        with pytest.raises(CompilationFailedError) as excinfo:
            await _compile("/nonexistent/tectonic-binary")
        assert excinfo.value.code == "COMPILER_NOT_FOUND"

    async def test_success_without_pdf_classified(self, tmp_path) -> None:
        binary = _write_fake_compiler(tmp_path, "exit 0\n")
        with pytest.raises(CompilationFailedError) as excinfo:
            await _compile(binary)
        assert excinfo.value.code == "NO_PDF_OUTPUT"

    async def test_oversized_output_rejected(self, tmp_path) -> None:
        binary = _write_fake_compiler(
            tmp_path,
            'head -c 200000 /dev/zero > "$OUTDIR/main.pdf"\nexit 0\n',
        )
        with pytest.raises(CompilationFailedError) as excinfo:
            await _compile(binary, max_pdf_bytes=100_000)
        assert excinfo.value.code == "OUTPUT_TOO_LARGE"

    async def test_workdir_cleaned_up_on_success_and_failure(
        self, tmp_path, fake_pdf_env
    ) -> None:
        import tempfile

        def _caviar_dirs() -> set[str]:
            return {
                name
                for name in os.listdir(tempfile.gettempdir())
                if name.startswith("caviar-gen-")
            }

        before = _caviar_dirs()
        ok_binary = _write_fake_compiler(
            tmp_path, 'cp "$CAVIAR_FAKE_PDF" "$OUTDIR/main.pdf"\nexit 0\n'
        )
        await _compile(ok_binary)
        fail_binary = _write_fake_compiler(tmp_path, "exit 1\n")
        with pytest.raises(CompilationFailedError):
            await _compile(fail_binary)
        assert _caviar_dirs() == before  # nothing leaked

    async def test_only_cached_flag_passed_through(self, tmp_path, fake_pdf_env) -> None:
        binary = _write_fake_compiler(
            tmp_path,
            'echo "$@" > "$OUTDIR/args.txt"\ncp "$CAVIAR_FAKE_PDF" "$OUTDIR/main.pdf"\n'
            'grep -q -- "--only-cached" "$OUTDIR/args.txt" || exit 7\nexit 0\n',
        )
        result = await _compile(binary, only_cached=True)
        assert result.pdf_bytes.startswith(b"%PDF-")

    async def test_real_tectonic_golden_compile_if_available(self) -> None:
        """Golden test with the real pinned Tectonic. Skips when the
        binary or its bundle is unavailable (e.g. sandboxed networks)."""
        binary = shutil.which("tectonic") or "/tmp/tectonic"
        if not (shutil.which("tectonic") or Path("/tmp/tectonic").is_file()):
            pytest.skip("Tectonic binary not available.")
        probe = subprocess.run(  # noqa: S603
            [binary, "--version"], capture_output=True, timeout=10, shell=False
        )
        if probe.returncode != 0:
            pytest.skip("Tectonic binary not runnable.")
        try:
            result = await compile_latex(
                "\\documentclass{article}\\begin{document}Caviar golden\\end{document}",
                binary_path=binary,
                timeout_seconds=120.0,
                only_cached=False,
                max_pdf_bytes=_MAX_PDF_BYTES,
            )
        except CompilationFailedError as exc:
            pytest.skip(f"Tectonic bundle unavailable in this environment ({exc.code}).")
        assert result.pdf_bytes.startswith(b"%PDF-")


class TestValidateGeneratedPdf:
    def test_valid_single_page_pdf(self) -> None:
        result = validate_generated_pdf(
            build_resume_pdf(), max_bytes=_MAX_PDF_BYTES, max_pages=2
        )
        assert result.page_count == 1
        assert result.warnings == ()
        assert result.file_size_bytes > 0

    def test_empty_output_rejected(self) -> None:
        with pytest.raises(PdfValidationError) as excinfo:
            validate_generated_pdf(b"", max_bytes=_MAX_PDF_BYTES, max_pages=2)
        assert excinfo.value.code == "EMPTY_OUTPUT"

    def test_bad_header_rejected(self) -> None:
        with pytest.raises(PdfValidationError) as excinfo:
            validate_generated_pdf(b"GIF89a not a pdf", max_bytes=_MAX_PDF_BYTES, max_pages=2)
        assert excinfo.value.code == "INVALID_PDF_HEADER"

    def test_truncated_pdf_unparseable(self) -> None:
        with pytest.raises(PdfValidationError) as excinfo:
            validate_generated_pdf(
                build_resume_pdf()[:150], max_bytes=_MAX_PDF_BYTES, max_pages=2
            )
        assert excinfo.value.code == "UNPARSEABLE_PDF"

    def test_size_cap_enforced(self) -> None:
        content = build_resume_pdf()
        with pytest.raises(PdfValidationError) as excinfo:
            validate_generated_pdf(content, max_bytes=len(content) - 1, max_pages=2)
        assert excinfo.value.code == "OUTPUT_TOO_LARGE"

    def test_page_overflow_is_warning_not_failure(self) -> None:
        result = validate_generated_pdf(
            build_pdf(["content"], pages=4), max_bytes=_MAX_PDF_BYTES, max_pages=2
        )
        assert result.page_count == 4
        warning = result.warnings[0]
        assert warning["code"] == "PAGE_OVERFLOW"
        assert warning["page_count"] == 4
        assert warning["max_pages"] == 2
        assert warning["recommendations"]  # advice, never content deletion
