"""Prompt construction for the CONTENT_ASSIST task (Phase 6).

Same trust architecture as resume analysis: Caviar-owned system rules
first; the user's structured resume content (and optional target role)
is untrusted data inside neutralized trust-boundary markers. The builder
sends structured content as compact JSON - the model improves DATA, and
presentation stays out of scope by instruction (Phase 7 owns rendering).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from app.services.ai.prompts.trust import UNTRUSTED_RULES, wrap_untrusted

SYSTEM_INSTRUCTION = f"""You are the resume content assistant of Caviar, an AI career \
intelligence platform. You improve or generate structured resume content for a candidate.

TRUST BOUNDARY
{UNTRUSTED_RULES}

FACTUAL INTEGRITY (ABSOLUTE)
- Work ONLY with facts the candidate provided. Never fabricate or embellish metrics, \
percentages, user counts, revenue figures, performance improvements, technologies, \
tools, companies, employment, job titles, dates, skills, certifications, or \
achievements. Rewording is allowed; adding facts is not.
- If a quantified metric would strengthen the content but none was provided, do NOT \
invent one: insert a bracketed placeholder (e.g. "[add: estimated % latency \
reduction]") in the rewrite AND add a corresponding question to \
missing_fact_questions so the candidate can supply the real number.
- Do not upgrade weak claims into strong ones the content does not support (e.g. \
"helped with" must not become "led" unless leadership is stated).

WRITING RULES
- One clear idea per bullet; start bullets with a strong action verb; no first-person \
pronouns; concise, professional phrasing; correct grammar; remove filler and \
repetition; prefer ATS-friendly standard terminology over decorative wording; keep \
bullets under about 30 words.
- Improve content only. Never add formatting, layout, LaTeX, markdown, or styling - \
presentation is handled elsewhere.
- Keep every list within the size guidance in the field descriptions."""


@dataclass(frozen=True)
class AssistPrompt:
    system_instruction: str
    user_content: str


def _compact_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _target_role_block(target_role: str | None) -> list[str]:
    if not target_role:
        return []
    return [
        "",
        "Tailor wording toward the target role below where the candidate's facts "
        "genuinely support it (never by inventing experience):",
        wrap_untrusted("target_role", target_role.strip()),
    ]


def build_summary_assist_prompt(
    *,
    existing_summary: str | None,
    resume_content: dict[str, Any],
    target_role: str | None,
) -> AssistPrompt:
    """GENERATE_SUMMARY (no existing summary) or IMPROVE_SUMMARY."""
    action = (
        "Improve the candidate's existing professional summary."
        if existing_summary
        else "Generate a professional summary for the candidate."
    )
    parts: list[str] = [
        action,
        "Ground every statement in the structured resume content provided. "
        "2-4 sentences, third person implied (no pronouns), specific, no cliches.",
        *_target_role_block(target_role),
        "",
        "Structured resume content (JSON):",
        wrap_untrusted("resume_content", _compact_json(resume_content)),
    ]
    if existing_summary:
        parts += ["", wrap_untrusted("existing_summary", existing_summary)]
    return AssistPrompt(system_instruction=SYSTEM_INSTRUCTION, user_content="\n".join(parts))


def build_bullets_assist_prompt(
    *,
    section_type: str,
    entry_context: dict[str, Any],
    bullets: list[str],
    target_role: str | None,
) -> AssistPrompt:
    """IMPROVE_BULLETS for one experience/internship/project entry."""
    parts: list[str] = [
        f"Improve the bullet points of one {section_type} entry. Return exactly one "
        "improved version per input bullet, in the same order.",
        *_target_role_block(target_role),
        "",
        "Entry context (JSON - the entry these bullets belong to):",
        wrap_untrusted("entry_context", _compact_json(entry_context)),
        "",
        "Bullets to improve (JSON array, in order):",
        wrap_untrusted("bullets", _compact_json(bullets)),
    ]
    return AssistPrompt(system_instruction=SYSTEM_INSTRUCTION, user_content="\n".join(parts))
