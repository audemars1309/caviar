"""Sandboxed Tectonic compilation (Phase 7).

Execution model, validated against Tectonic 0.15.0 (pinned release,
verified CLI):

  * subprocess ARGUMENT ARRAYS only - never ``shell=True``, and no
    command string ever contains user-derived text. The rendered source
    is written to a fixed filename (``main.tex``) inside an isolated,
    randomized temporary working directory (``tempfile.mkdtemp``), which
    is removed in a ``finally`` regardless of outcome.
  * ``--outdir`` is the same isolated directory; ``--chatter minimal``
    and ``--keep-logs`` so failures and glyph warnings are diagnosable
    from the captured log; ``--only-cached`` is appended when configured
    (production: pinned binary + pre-warmed bundle cache = deterministic,
    offline, reproducible compiles).
  * Wall-clock timeout enforced via ``subprocess.run(timeout=...)``
    (which kills the process), exit-code validation, stdout/stderr
    captured and length-capped. Compilation is CPU-bound and runs in a
    worker thread off the event loop.

Failure reporting is SANITIZED: callers receive a machine code
(COMPILER_NOT_FOUND / COMPILER_TIMEOUT / COMPILER_FAILED /
OUTPUT_TOO_LARGE / NO_PDF_OUTPUT) plus a scrubbed one-line hint with
temporary paths removed. Raw engine output is never persisted or exposed.

"Missing character" lines in the engine log (XeTeX's report that the
current font stack cannot render a glyph) are parsed into a structured,
de-duplicated UNSUPPORTED_GLYPHS warning - preserved and surfaced, never
a hard failure, per the approved Phase 0 decision.
"""

from __future__ import annotations

import asyncio
import logging
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

_TEX_FILENAME = "main.tex"
_PDF_FILENAME = "main.pdf"
_LOG_FILENAME = "main.log"
_CAPTURE_CAP_BYTES = 20_000

_MISSING_CHARACTER_PATTERN = re.compile(r"Missing character: There is no (.{1,40}?) in font")


class CompilationFailedError(Exception):
    """Compilation did not produce a usable PDF. ``code`` is the machine
    classification; ``hint`` is a sanitized one-liner safe to persist."""

    def __init__(self, code: str, hint: str) -> None:
        super().__init__(f"{code}: {hint}")
        self.code = code
        self.hint = hint


@dataclass(frozen=True)
class CompilationResult:
    pdf_bytes: bytes
    duration_ms: int
    compiler_version: str | None
    unsupported_glyphs: tuple[str, ...] = field(default_factory=tuple)


def _scrub(text: str, workdir: str) -> str:
    first_line = next((line for line in text.splitlines() if line.strip()), "")
    return first_line.replace(workdir, "<workdir>")[:300]


def _parse_unsupported_glyphs(log_text: str) -> tuple[str, ...]:
    seen: dict[str, None] = {}
    for match in _MISSING_CHARACTER_PATTERN.finditer(log_text):
        seen.setdefault(match.group(1).strip(), None)
    return tuple(seen)


def _compile_sync(
    latex_source: str,
    *,
    binary_path: str,
    timeout_seconds: float,
    only_cached: bool,
    max_pdf_bytes: int,
) -> CompilationResult:
    workdir = tempfile.mkdtemp(prefix="caviar-gen-")
    try:
        tex_path = Path(workdir) / _TEX_FILENAME
        tex_path.write_text(latex_source, encoding="utf-8")

        argv = [
            binary_path,
            "--outdir",
            workdir,
            "--chatter",
            "minimal",
            "--keep-logs",
        ]
        if only_cached:
            argv.append("--only-cached")
        argv.append(str(tex_path))

        import time

        started = time.monotonic()
        try:
            completed = subprocess.run(  # noqa: S603 - fixed argv, no shell
                argv,
                capture_output=True,
                timeout=timeout_seconds,
                cwd=workdir,
                shell=False,
            )
        except FileNotFoundError as exc:
            raise CompilationFailedError(
                "COMPILER_NOT_FOUND",
                "The LaTeX compiler binary is not available on this host.",
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise CompilationFailedError(
                "COMPILER_TIMEOUT",
                f"Compilation exceeded the {timeout_seconds:.0f}s limit and was stopped.",
            ) from exc
        duration_ms = int((time.monotonic() - started) * 1000)

        stdout = completed.stdout[:_CAPTURE_CAP_BYTES].decode("utf-8", errors="replace")
        stderr = completed.stderr[:_CAPTURE_CAP_BYTES].decode("utf-8", errors="replace")
        log_path = Path(workdir) / _LOG_FILENAME
        log_text = ""
        if log_path.is_file():
            log_text = log_path.read_text(encoding="utf-8", errors="replace")[
                :_CAPTURE_CAP_BYTES
            ]

        if completed.returncode != 0:
            hint = _scrub(stderr or stdout or "Compiler exited with an error.", workdir)
            logger.error(
                "Tectonic compile failed: exit=%s hint=%s", completed.returncode, hint
            )
            raise CompilationFailedError("COMPILER_FAILED", hint)

        pdf_path = Path(workdir) / _PDF_FILENAME
        if not pdf_path.is_file():
            raise CompilationFailedError(
                "NO_PDF_OUTPUT", "The compiler reported success but produced no PDF."
            )
        pdf_size = pdf_path.stat().st_size
        if pdf_size > max_pdf_bytes:
            raise CompilationFailedError(
                "OUTPUT_TOO_LARGE",
                f"The generated PDF ({pdf_size} bytes) exceeds the {max_pdf_bytes}-byte limit.",
            )

        return CompilationResult(
            pdf_bytes=pdf_path.read_bytes(),
            duration_ms=duration_ms,
            compiler_version=_binary_version(binary_path),
            unsupported_glyphs=_parse_unsupported_glyphs(log_text + "\n" + stderr),
        )
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def _binary_version(binary_path: str) -> str | None:
    try:
        completed = subprocess.run(  # noqa: S603 - fixed argv, no shell
            [binary_path, "--version"], capture_output=True, timeout=10, shell=False
        )
    except Exception:
        return None
    output = (completed.stdout or completed.stderr).decode("utf-8", errors="replace")
    return output.strip().splitlines()[0][:100] if output.strip() else None


async def compile_latex(
    latex_source: str,
    *,
    binary_path: str,
    timeout_seconds: float,
    only_cached: bool,
    max_pdf_bytes: int,
) -> CompilationResult:
    """Compile rendered LaTeX to PDF bytes without blocking the event
    loop. Raises ``CompilationFailedError`` with a sanitized code+hint."""
    return await asyncio.to_thread(
        _compile_sync,
        latex_source,
        binary_path=binary_path,
        timeout_seconds=timeout_seconds,
        only_cached=only_cached,
        max_pdf_bytes=max_pdf_bytes,
    )
