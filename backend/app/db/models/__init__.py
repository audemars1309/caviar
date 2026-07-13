"""Importing this module registers every ORM model on Base.metadata.

Alembic's env.py imports this module so that the migration environment has
the full schema picture. Application code should import specific model
classes from their own modules rather than relying on wildcard imports
from this package.
"""

from app.db.models.interview import InterviewAnswer, InterviewQuestion, InterviewSession
from app.db.models.job_context import JobContext
from app.db.models.profile import Profile
from app.db.models.report import InterviewMemory, InterviewReport, InterviewReportCategory
from app.db.models.resume import Resume
from app.db.models.resume_analysis import ResumeAnalysis, ResumeAnalysisCategory
from app.db.models.resume_builder import (
    ResumeBuilderProject,
    ResumeBuilderSection,
    ResumeGeneration,
)
from app.db.models.resume_extraction import ResumeExtraction
from app.db.models.speech import AnswerEvaluation, SpeechMetric

__all__ = [
    "Profile",
    "JobContext",
    "Resume",
    "ResumeExtraction",
    "ResumeAnalysis",
    "ResumeAnalysisCategory",
    "ResumeBuilderProject",
    "ResumeBuilderSection",
    "ResumeGeneration",
    "InterviewSession",
    "InterviewQuestion",
    "InterviewAnswer",
    "SpeechMetric",
    "AnswerEvaluation",
    "InterviewMemory",
    "InterviewReport",
    "InterviewReportCategory",
]
