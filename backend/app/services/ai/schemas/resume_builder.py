"""Strict output schemas for the CONTENT_ASSIST task (Phase 6).

``CONTENT_ASSIST_SCHEMA_VERSION`` is returned with every assistance
response so clients (and future stored artifacts) know which contract
produced it.

Factual-integrity structure: every improvement is paired with its source
(``original``) so grounding stays auditable; ``missing_fact_questions``
is the mandated mechanism for absent measurable impact - the model asks
for the fact instead of inventing a number, and rewrites use bracketed
placeholders (e.g. "[add: estimated % latency reduction]") where a metric
would belong. On top of the prompt rules, the backend runs a
deterministic fabrication guard (``fabrication_guard.py``) that flags any
number in improved text that does not appear in the user's source
content.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

CONTENT_ASSIST_SCHEMA_VERSION = "content-assist-1.0.0"


class ImprovedSummaryOutput(BaseModel):
    improved_summary: str = Field(
        description=(
            "The generated or improved professional summary, 2-4 sentences, "
            "grounded ONLY in facts present in the provided resume content."
        )
    )
    changes_explained: list[str] = Field(
        description="1-5 short notes on what was changed or emphasized and why."
    )
    missing_fact_questions: list[str] = Field(
        description=(
            "Questions asking the user for missing facts that would strengthen "
            "the summary (empty list if nothing is missing). NEVER invent the "
            "answer to any of these."
        )
    )
    action_verb_suggestions: list[str] = Field(
        description="0-8 stronger action verbs relevant to this candidate's content."
    )


class ImprovedBullet(BaseModel):
    original: str = Field(description="The user's bullet, copied verbatim.")
    improved: str = Field(
        description=(
            "The rewritten bullet: stronger action verb, concise, professional, "
            "ATS-aware wording, grounded only in the user's stated facts. Where a "
            "metric would strengthen it but none was provided, use a bracketed "
            "placeholder question, never an invented number."
        )
    )
    changes_explained: list[str] = Field(
        description="1-3 short notes on what was improved (verb, structure, wording)."
    )
    missing_fact_questions: list[str] = Field(
        description=(
            "Questions for missing measurable impact relevant to THIS bullet "
            "(empty list if none)."
        )
    )


class ImprovedBulletsOutput(BaseModel):
    bullets: list[ImprovedBullet] = Field(
        description="One entry per input bullet, in the same order."
    )
    action_verb_suggestions: list[str] = Field(
        description="0-8 stronger action verbs relevant to this entry."
    )
