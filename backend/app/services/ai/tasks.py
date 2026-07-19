"""AI task registry and configuration-driven model routing.

Per the approved Phase 0 architecture, every AI task resolves its model
from its own environment variable so tasks can be independently routed
between models (quality / cost / free-tier tradeoffs) with zero code
changes. Only tasks that exist are registered; later phases extend the
enum and mapping together with the settings they introduce
(ANSWER_EVALUATION_MODEL, INTERVIEW_MODEL, CONTENT_ASSIST_MODEL,
REPORT_GENERATION_MODEL).
"""

from __future__ import annotations

import enum

from app.config import Settings
from app.services.ai.exceptions import AIConfigurationError


class AITask(enum.StrEnum):
    RESUME_ANALYSIS = "RESUME_ANALYSIS"
    CONTENT_ASSIST = "CONTENT_ASSIST"
    ANSWER_EVALUATION = "ANSWER_EVALUATION"
    INTERVIEW_QUESTION = "INTERVIEW_QUESTION"
    INTERVIEW_REPORT = "INTERVIEW_REPORT"


def resolve_model_for_task(task: AITask, settings: Settings) -> str:
    if task is AITask.RESUME_ANALYSIS:
        return settings.RESUME_ANALYSIS_MODEL
    if task is AITask.CONTENT_ASSIST:
        return settings.CONTENT_ASSIST_MODEL
    if task is AITask.ANSWER_EVALUATION:
        return settings.ANSWER_EVALUATION_MODEL
    if task is AITask.INTERVIEW_QUESTION:
        return settings.INTERVIEW_QUESTION_MODEL
    if task is AITask.INTERVIEW_REPORT:
        return settings.INTERVIEW_REPORT_MODEL
    raise AIConfigurationError(f"No model routing configured for AI task '{task}'.")
