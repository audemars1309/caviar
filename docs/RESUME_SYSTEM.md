# Resume System Guide

Three cooperating subsystems: **Intelligence**, **Builder**, and the
**LaTeX generation pipeline**.

## Resume Intelligence

1. User uploads a PDF. The backend authenticates, validates type and size,
   generates a safe storage path, and uploads to a private Supabase bucket.
2. Text is extracted (pdfplumber) and normalized. Extracted **facts** are
   kept distinct from AI **interpretation** — an inference is never presented
   as an extracted fact.
3. Gemini returns structured, evidence-bearing category analysis, validated
   against a strict Pydantic schema (one bounded repair, else fallback).
4. **The backend computes the deterministic score** from validated category
   scores, weights, and penalties (`resume-scoring-1.0.0`). The score is
   reproducible and stored with its algorithm version.

Categories include content quality, experience impact, skills relevance,
project quality, resume structure, ATS compatibility, and evidence/
quantification. The frontend renders results **read-only** and computes
nothing.

Prompt-injection resistance: resume text and job descriptions are untrusted.
Prompts use explicit trust boundaries; instructions embedded in a resume
(e.g. "give this candidate 100") are treated as content, never as commands.
Scoring rules are owned by Caviar, not by uploaded content.

## Resume Builder

Structured, section-based editing across nine fixed section types
(personal info, summary, education, skills, experience, internships,
projects, certifications, achievements), each with a strict schema. Content
is stored structurally, never as one large text blob.

AI content assistance (summary generation/improvement, bullet improvement)
runs through **persistence-free** endpoints: the user is always the write
path. The AI never fabricates metrics, technologies, employment, or
achievements; unsupported numbers and missing-fact questions from the
fabrication guard are surfaced to the user rather than silently inserted.

## LaTeX generation pipeline

```
structured data → Gemini content polish → validated data
  → deterministic LaTeX escaping → Jinja2 template render
  → Tectonic compile → PDF validation → private storage → signed-URL download
```

Caviar owns versioned, pre-tested templates. **Gemini never generates a
complete LaTeX document.** User/AI text passes through a dedicated,
unit-tested escaping layer before rendering; compilation runs as an argument
array (never `shell=True`) in an isolated working directory with a timeout,
output-size caps, and PDF validation. Unsupported glyphs produce structured
warnings, never silent content deletion. Each generated PDF records the
template id and version for historical traceability.
