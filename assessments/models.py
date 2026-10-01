"""Data models for assessments, questions, and options."""

from __future__ import annotations

from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class QuestionType(str, Enum):
    MULTIPLE_CHOICE = "multiple_choice"
    MULTIPLE_SELECT = "multiple_select"
    TRUE_FALSE = "true_false"
    SHORT_TEXT = "short_text"
    MATCHING = "matching"
    IMAGE_BASED = "image_based"
    UNKNOWN = "unknown"


class OptionItem(BaseModel):
    label: str = Field(..., description="Option indicator, e.g. A, B, C, D")
    text: str = Field(..., description="Visible text of option")


class QuestionItem(BaseModel):
    id: str
    assessment_id: str
    question_number: int
    question_text: str
    question_type: QuestionType = QuestionType.MULTIPLE_CHOICE
    options: List[OptionItem] = Field(default_factory=list)
    has_diagram_or_canvas: bool = False
    screenshot_path: Optional[str] = None


class AssessmentData(BaseModel):
    id: str
    lesson_id: Optional[str] = None
    title: str
    assessment_type: str = "quiz"
    is_graded: bool = False
    total_questions: int = 0
    questions: List[QuestionItem] = Field(default_factory=list)
    confidence: float = 1.0
    requires_review: bool = False
