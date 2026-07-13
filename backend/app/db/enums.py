"""Canonical string enum values used by application code.

These mirror the CHECK-constraint value lists hardcoded into the Alembic
migrations that created each column. Migrations intentionally do NOT
import this module - migration scripts must remain stable and reproducible
independent of application code that will keep changing - so if a value
set changes here, the corresponding migration's CHECK constraint (and a
new migration to alter it in already-deployed databases) must be updated
by hand. This module is the single source of truth for application code;
the migration is the single source of truth for what the database
currently enforces.
"""

from __future__ import annotations

import enum


class ExtractionStatus(enum.StrEnum):
    PENDING = "PENDING"
    EXTRACTED = "EXTRACTED"
    FAILED = "FAILED"


class AnalysisStatus(enum.StrEnum):
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    AI_ANALYSIS_FAILED = "AI_ANALYSIS_FAILED"


class ResumeAnalysisCategoryName(enum.StrEnum):
    CONTENT_QUALITY = "CONTENT_QUALITY"
    EXPERIENCE_IMPACT = "EXPERIENCE_IMPACT"
    SKILLS_RELEVANCE = "SKILLS_RELEVANCE"
    PROJECT_QUALITY = "PROJECT_QUALITY"
    RESUME_STRUCTURE = "RESUME_STRUCTURE"
    ATS_COMPATIBILITY = "ATS_COMPATIBILITY"
    EVIDENCE_QUANTIFICATION = "EVIDENCE_QUANTIFICATION"


class BuilderSectionType(enum.StrEnum):
    PERSONAL_INFO = "PERSONAL_INFO"
    SUMMARY = "SUMMARY"
    EDUCATION = "EDUCATION"
    SKILLS = "SKILLS"
    EXPERIENCE = "EXPERIENCE"
    INTERNSHIPS = "INTERNSHIPS"
    PROJECTS = "PROJECTS"
    CERTIFICATIONS = "CERTIFICATIONS"
    ACHIEVEMENTS = "ACHIEVEMENTS"


class BuilderProjectStatus(enum.StrEnum):
    DRAFT = "DRAFT"
    FINALIZED = "FINALIZED"


class GenerationStatus(enum.StrEnum):
    PENDING = "PENDING"
    RENDERING = "RENDERING"
    COMPILING = "COMPILING"
    VALIDATING = "VALIDATING"
    UPLOADING = "UPLOADING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class InterviewStage(enum.StrEnum):
    INTRODUCTION = "INTRODUCTION"
    CANDIDATE_BACKGROUND = "CANDIDATE_BACKGROUND"
    RESUME_DISCUSSION = "RESUME_DISCUSSION"
    PROJECT_DEEP_DIVE = "PROJECT_DEEP_DIVE"
    ROLE_SPECIFIC = "ROLE_SPECIFIC"
    BEHAVIORAL = "BEHAVIORAL"
    ADAPTIVE_PROBING = "ADAPTIVE_PROBING"
    CLOSING = "CLOSING"
    COMPLETED = "COMPLETED"


class InterviewSessionStatus(enum.StrEnum):
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    ABANDONED = "ABANDONED"


class QuestionType(enum.StrEnum):
    INTRODUCTORY = "INTRODUCTORY"
    RESUME = "RESUME"
    PROJECT = "PROJECT"
    TECHNICAL = "TECHNICAL"
    BEHAVIORAL = "BEHAVIORAL"
    SITUATIONAL = "SITUATIONAL"
    FOLLOW_UP = "FOLLOW_UP"
    CLAIM_VERIFICATION = "CLAIM_VERIFICATION"


class AnswerStatus(enum.StrEnum):
    PENDING = "PENDING"
    TRANSCRIBED = "TRANSCRIBED"
    EVALUATED = "EVALUATED"
    FAILED = "FAILED"


class InterviewReportCategoryName(enum.StrEnum):
    COMMUNICATION = "COMMUNICATION"
    TECHNICAL_DEPTH = "TECHNICAL_DEPTH"
    RELEVANCE = "RELEVANCE"
    SPECIFICITY = "SPECIFICITY"
    EVIDENCE = "EVIDENCE"
    PROBLEM_SOLVING = "PROBLEM_SOLVING"
    ANSWER_STRUCTURE = "ANSWER_STRUCTURE"


class ReadinessLevel(enum.StrEnum):
    NOT_READY = "NOT_READY"
    DEVELOPING = "DEVELOPING"
    READY = "READY"
    STRONG = "STRONG"
