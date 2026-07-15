"""Deterministic fabrication guard (Phase 6).

Prompt rules forbid invented numbers, but prompt rules are not
enforcement. This module is the backend's deterministic check: any
numeric token appearing in AI-improved text that does not appear in the
user's source content is flagged as unsupported. The flag is computed by
the backend and attached to the assistance response
(``unsupported_numbers`` per item) so the frontend can warn the user
before they accept a rewrite - the number may be a hallucination.

Scope and honesty about limits:
  * Numbers inside bracketed placeholders ("[add: estimated 20-30% ...]")
    are exempt - placeholders are the sanctioned way to point at a
    missing metric and are visibly not claims.
  * Comparison is by normalized numeric token (digits with optional
    decimal part; grouping commas removed), against every numeric token
    anywhere in the source material. This catches the dangerous class -
    fabricated quantities ("increased throughput by 40%") - not textual
    embellishment ("helped" -> "led"), which no deterministic check can
    verify; that class is addressed by prompt rules and by keeping
    assistance advisory (nothing is persisted until the user applies it).
"""

from __future__ import annotations

import json
import re
from typing import Any

_NUMBER_PATTERN = re.compile(r"\d[\d,]*(?:\.\d+)?")
_BRACKETED_PLACEHOLDER_PATTERN = re.compile(r"\[[^\[\]]*\]")


def _normalize_number(token: str) -> str:
    normalized = token.replace(",", "")
    if "." in normalized:
        normalized = normalized.rstrip("0").rstrip(".")
    return normalized.lstrip("0") or "0"


def extract_numbers(text: str) -> set[str]:
    return {_normalize_number(match) for match in _NUMBER_PATTERN.findall(text)}


def source_numbers_from_content(source: Any) -> set[str]:
    """All numeric tokens appearing anywhere in the user's source content
    (dict/list/str - serialized deterministically)."""
    if isinstance(source, str):
        haystack = source
    else:
        haystack = json.dumps(source, ensure_ascii=False)
    return extract_numbers(haystack)


def find_unsupported_numbers(improved_text: str, source_numbers: set[str]) -> list[str]:
    """Numbers claimed in improved text (outside bracketed placeholders)
    that the user's source content never stated, in first-appearance
    order."""
    stripped = _BRACKETED_PLACEHOLDER_PATTERN.sub(" ", improved_text)
    unsupported: list[str] = []
    for match in _NUMBER_PATTERN.findall(stripped):
        normalized = _normalize_number(match)
        if normalized not in source_numbers and normalized not in unsupported:
            unsupported.append(normalized)
    return unsupported
