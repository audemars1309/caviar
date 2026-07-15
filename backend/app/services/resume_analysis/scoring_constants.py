"""Backend-owned scoring constants and deterministic evidence checks.

The category WEIGHTS live here, in application code - never in prompts,
never influenced by model output, never accepted from a client. They are
persisted onto every ``resume_analysis_categories`` row at analysis time
so each historical analysis permanently records the weights that applied
when it was created. The Phase 5 deterministic scoring engine consumes
these stored per-row weights (not this module's current values) so old
analyses stay reproducible after weights evolve.

``verify_evidence_quotes`` is Caviar's deterministic integrity check on
the fact/interpretation boundary: the AI claims its ``quote`` fields are
verbatim resume excerpts, and the backend verifies that claim against the
actual normalized resume text (whitespace-insensitively, since model
output may fold line breaks that normalization preserved). The resulting
``verified`` flag is computed by the backend and cannot be influenced by
the model - an unverified quote is displayed as AI interpretation, never
as an extracted fact.
"""

from __future__ import annotations

import re
from typing import Any

from app.services.ai.schemas.resume_analysis import EvidenceItem

# Sentinel stored in resume_analyses.scoring_algorithm_version (NOT NULL)
# until the Phase 5 deterministic scoring engine computes overall_score
# and replaces it with its real algorithm version.
UNSCORED_SENTINEL = "unscored"

# Must contain exactly the seven categories enforced by the
# resume_analysis_categories CHECK constraint, and sum to 1.0.
CATEGORY_WEIGHTS: dict[str, float] = {
    "CONTENT_QUALITY": 0.20,
    "EXPERIENCE_IMPACT": 0.20,
    "SKILLS_RELEVANCE": 0.15,
    "PROJECT_QUALITY": 0.15,
    "RESUME_STRUCTURE": 0.10,
    "ATS_COMPATIBILITY": 0.10,
    "EVIDENCE_QUANTIFICATION": 0.10,
}

assert abs(sum(CATEGORY_WEIGHTS.values()) - 1.0) < 1e-9, "Category weights must sum to 1.0"

_WHITESPACE = re.compile(r"\s+")


def _fold(text: str) -> str:
    return _WHITESPACE.sub(" ", text).strip().lower()


def verify_evidence_quotes(
    evidence: list[EvidenceItem], resume_text: str
) -> list[dict[str, Any]]:
    """Return JSON-ready evidence dicts with a backend-computed
    ``verified`` flag: True iff the quote actually appears in the resume
    text (whitespace-folded, case-insensitive substring match)."""
    haystack = _fold(resume_text)
    verified_items: list[dict[str, Any]] = []
    for item in evidence:
        needle = _fold(item.quote)
        verified_items.append(
            {
                "quote": item.quote,
                "observation": item.observation,
                "verified": bool(needle) and needle in haystack,
            }
        )
    return verified_items
