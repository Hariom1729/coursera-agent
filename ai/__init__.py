"""AI package for Coursera automation agent."""

from ai.base import AIProvider
from ai.schemas import (
    OptionModel,
    QuestionAnalysis,
    AssessmentAnalysis,
    GeneralAnalysis,
    ModelComparisonResult,
)
from ai.prompts import (
    ASSESSMENT_ANALYSIS_PROMPT,
    READING_SUMMARY_PROMPT,
    PRACTICE_ACTIVITY_PROMPT,
    IMAGE_ASSESSMENT_PROMPT,
)

__all__ = [
    "AIProvider",
    "OptionModel",
    "QuestionAnalysis",
    "AssessmentAnalysis",
    "GeneralAnalysis",
    "ModelComparisonResult",
    "ASSESSMENT_ANALYSIS_PROMPT",
    "READING_SUMMARY_PROMPT",
    "PRACTICE_ACTIVITY_PROMPT",
    "IMAGE_ASSESSMENT_PROMPT",
]
