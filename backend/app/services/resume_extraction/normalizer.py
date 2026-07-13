"""Deterministic normalization of extracted resume text.

Pure functions, no I/O, no AI. The goal is a stable, analysis-friendly
text form while remaining conservative: normalization must never alter the
factual content of a resume, only its representation. Every transformation
here is reproducible, which matters because downstream deterministic
parsing (and, in Phase 4, AI analysis and scoring) consumes this output;
the pipeline version stored with each extraction records which behavior
produced it.

Transformations, in order:
  1. Unicode NFKC normalization - folds ligatures (ﬁ -> fi), full-width
     forms, and compatibility variants that PDF extraction commonly emits.
  2. Line-ending normalization (\r\n and \r -> \n).
  3. Control-character removal (everything in Cc/Cf except \n and \t).
  4. Bullet-glyph normalization - the zoo of bullet characters PDF fonts
     produce (•, ●, ▪, ◦, ‣, ...) becomes a uniform "- " at line start so
     the section parser and later bullet-quality analysis see one form.
  5. Whitespace collapsing - tabs and space runs inside a line collapse to
     a single space; trailing spaces are stripped; runs of 3+ blank lines
     collapse to one blank line.
"""

from __future__ import annotations

import re
import unicodedata

_BULLET_PREFIX_PATTERN = re.compile(r"^[\u2022\u25CF\u25AA\u25E6\u2023\u2043\u00B7\u2219*]+\s*")
_INLINE_WHITESPACE_PATTERN = re.compile(r"[ \t]+")
_BLANK_RUN_PATTERN = re.compile(r"\n{3,}")


def _strip_control_characters(text: str) -> str:
    return "".join(
        ch for ch in text if ch in ("\n", "\t") or unicodedata.category(ch) not in ("Cc", "Cf")
    )


def normalize_text(raw_text: str) -> str:
    """Normalize extracted resume text. Pure and deterministic."""
    text = unicodedata.normalize("NFKC", raw_text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _strip_control_characters(text)

    normalized_lines: list[str] = []
    for line in text.split("\n"):
        line = _BULLET_PREFIX_PATTERN.sub("- ", line)
        line = _INLINE_WHITESPACE_PATTERN.sub(" ", line)
        normalized_lines.append(line.rstrip())

    text = "\n".join(normalized_lines)
    text = _BLANK_RUN_PATTERN.sub("\n\n", text)
    return text.strip()
