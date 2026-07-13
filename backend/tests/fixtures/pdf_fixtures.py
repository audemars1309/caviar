"""Test-only PDF fixture builders (reportlab is a dev dependency only).

Real generated PDFs - not hand-crafted byte blobs - so pdfplumber
exercises its actual parsing path in tests.
"""

from __future__ import annotations

import io

from reportlab.lib.pagesizes import LETTER
from reportlab.pdfgen import canvas

RESUME_LINES = [
    "Dharun Raj Gupta",
    "dharun@example.com | +91 98765 43210",
    "linkedin.com/in/dharunraj | github.com/audemars1309",
    "",
    "PROFESSIONAL SUMMARY",
    "Backend engineer focused on Python, FastAPI, and PostgreSQL.",
    "",
    "EDUCATION",
    "B.Tech in Computer Science, Example University, 2021 - 2025",
    "",
    "SKILLS",
    "Python, FastAPI, SQLAlchemy, PostgreSQL, Supabase, C++, R&D tooling",
    "",
    "EXPERIENCE",
    "Software Engineering Intern - Example Corp (2024)",
    "\u2022 Built an async ingestion service handling 500 requests per minute",
    "\u2022 Reduced p95 latency by tuning connection pooling",
    "",
    "PROJECTS",
    "Caviar - AI career intelligence platform",
    "\u2022 Designed RLS-backed multi-tenant schema on Supabase",
]


def build_pdf(lines: list[str], *, pages: int = 1) -> bytes:
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=LETTER)
    for _ in range(pages):
        y = 750
        for line in lines:
            pdf.drawString(72, y, line)
            y -= 18
        pdf.showPage()
    pdf.save()
    return buffer.getvalue()


def build_resume_pdf() -> bytes:
    return build_pdf(RESUME_LINES)


def build_textless_pdf() -> bytes:
    """A structurally valid one-page PDF containing no text objects."""
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=LETTER)
    pdf.rect(100, 100, 200, 200)
    pdf.showPage()
    pdf.save()
    return buffer.getvalue()
