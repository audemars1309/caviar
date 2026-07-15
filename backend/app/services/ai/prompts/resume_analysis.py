"""Prompt construction for the RESUME_ANALYSIS task.

Structure (trust order matters - trusted instructions first, then
application-controlled context, then clearly delimited untrusted data):

  system instruction : Caviar-owned rules - analyst role, evidence
                       requirements, factual-integrity rules, injection
                       resistance, fact/interpretation/recommendation
                       separation.
  user content       : application-controlled context (deterministic
                       facts from the Phase 3 pipeline: page count,
                       detected/missing sections), then the untrusted
                       resume text and optional untrusted job description,
                       each wrapped in trust-boundary markers.

The prompt never asks for an overall resume score - scoring rules and the
final score are owned by the backend (weights now, deterministic
aggregation in Phase 5). The model produces category-level, evidence-
grounded assessments only.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.services.ai.prompts.trust import UNTRUSTED_RULES, truncate_untrusted, wrap_untrusted

SYSTEM_INSTRUCTION = f"""You are the resume analysis engine of Caviar, an AI career \
intelligence platform. You analyze one candidate resume and produce a rigorous, \
evidence-grounded structured assessment.

TRUST BOUNDARY
{UNTRUSTED_RULES}

EVIDENCE RULES
- Every category assessment must rest on evidence items whose `quote` field is a \
short excerpt copied VERBATIM from the resume text. Never paraphrase inside `quote`; \
paraphrase belongs in `observation`.
- Distinguish rigorously between: facts extracted from the resume (verbatim quotes), \
your interpretation of those facts (observations, assessments, weaknesses), and your \
recommendations (improvement advice). Never present an interpretation as if it were \
stated in the resume.
- If the resume does not contain evidence for a judgment, do not invent any - state \
the absence as the finding.

FACTUAL INTEGRITY (ABSOLUTE)
- Never fabricate metrics, percentages, user counts, revenue figures, company names, \
technologies, skills, certifications, job titles, or achievements.
- In `improved_suggestion` rewrites, use only facts present in the resume. Where a \
quantified metric would strengthen a bullet but none exists, insert a bracketed \
placeholder question (e.g. "[add: estimated % latency reduction]") instead of a number.

CATEGORY ASSESSMENTS
- Assess all seven categories, each exactly once: CONTENT_QUALITY, EXPERIENCE_IMPACT, \
SKILLS_RELEVANCE, PROJECT_QUALITY, RESUME_STRUCTURE, ATS_COMPATIBILITY, \
EVIDENCE_QUANTIFICATION.
- Each `score` is a 0-100 assessment of that category alone, grounded in the evidence \
you cite. You are NOT producing an overall resume score; final scoring is computed \
separately by the application from your category assessments and is not your concern.
- List concrete `penalties` for specific deficiencies that lowered a category.

SCOPE AND TONE
- Analyze only what the extracted text supports. Formatting/ATS observations must be \
limited to what is detectable from extracted text (you cannot see the visual layout).
- If no job description is provided, set role_relevance.applicable to false with empty \
lists and an empty summary; never guess a target role.
- Be specific and professional. No praise padding, no generic advice like "add more \
detail" without saying what and where.
- Keep every list within the size guidance in the field descriptions."""


@dataclass(frozen=True)
class ResumeAnalysisInput:
    """Application-assembled input. ``normalized_resume_text`` and the job
    description fields are UNTRUSTED; everything else is deterministic
    output of Caviar's own Phase 3 pipeline."""

    normalized_resume_text: str
    page_count: int
    detected_section_types: list[str]
    missing_section_types: list[str]
    target_role: str | None = None
    job_description: str | None = None


@dataclass(frozen=True)
class BuiltPrompt:
    system_instruction: str
    user_content: str
    resume_truncated: bool
    job_description_truncated: bool


def build_resume_analysis_prompt(
    data: ResumeAnalysisInput, *, max_resume_chars: int, max_job_description_chars: int
) -> BuiltPrompt:
    resume_text, resume_truncated = truncate_untrusted(
        data.normalized_resume_text, max_resume_chars
    )

    parts: list[str] = [
        "Analyze the following candidate resume and produce the structured assessment.",
        "",
        "DETERMINISTIC EXTRACTION FACTS (computed by the application, trusted):",
        f"- PDF page count: {data.page_count}",
        f"- Sections detected by the parser: {', '.join(data.detected_section_types) or 'none'}",
        (
            "- Standard sections NOT detected by the parser: "
            f"{', '.join(data.missing_section_types) or 'none'}"
        ),
    ]
    if resume_truncated:
        parts.append(
            f"- NOTE: the resume text below was truncated to {max_resume_chars} characters."
        )

    job_description_truncated = False
    if data.target_role:
        # target_role is user input too - it rides inside an untrusted block.
        parts += ["", wrap_untrusted("target_role", data.target_role.strip())]
    if data.job_description:
        job_description, job_description_truncated = truncate_untrusted(
            data.job_description, max_job_description_chars
        )
        parts += ["", wrap_untrusted("job_description", job_description)]

    parts += ["", wrap_untrusted("resume", resume_text)]

    return BuiltPrompt(
        system_instruction=SYSTEM_INSTRUCTION,
        user_content="\n".join(parts),
        resume_truncated=resume_truncated,
        job_description_truncated=job_description_truncated,
    )
