"""Pydantic schemas for structured AI responses."""

from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field


class OptionModel(BaseModel):
    label: str = Field(..., description="Option letter or indicator, e.g. A, B, C, D")
    text: str = Field(..., description="The visible text of the option")


class QuestionAnalysis(BaseModel):
    question: str = Field(..., description="Full text of the question")
    question_type: str = Field(
        default="multiple_choice",
        description="Type of question: multiple_choice, multiple_select, true_false, short_text, matching, image_based",
    )
    options: List[OptionModel] = Field(default_factory=list, description="Available options if applicable")
    analysis: str = Field(default="", description="Deep conceptual breakdown and clues")
    candidate_answer: str = Field(..., description="Candidate answer(s) or option label(s), e.g. 'A' or 'True'")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Model confidence between 0.0 and 1.0")
    reasoning: str = Field(..., description="Step-by-step reasoning for why the candidate answer is correct")
    uncertainties: List[str] = Field(default_factory=list, description="Any ambiguities or assumptions made")
    requires_review: bool = Field(default=True, description="Always true for graded assessments")


class AssessmentAnalysis(BaseModel):
    assessment_title: str = Field(default="", description="Title of the quiz or assessment")
    is_graded: bool = Field(default=False, description="Whether this is a graded assessment")
    questions: List[QuestionAnalysis] = Field(default_factory=list, description="List of analyzed questions")
    overall_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    requires_review: bool = Field(default=True)


class GeneralAnalysis(BaseModel):
    understanding: str = Field(..., description="Summary of the material or topic understood")
    key_points: List[str] = Field(default_factory=list, description="Key takeaways or points")
    answer: str = Field(default="", description="Direct answer or synthesized conclusion")
    reasoning: str = Field(default="", description="Underlying reasoning and principles")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Confidence between 0.0 and 1.0")
    uncertainties: List[str] = Field(default_factory=list, description="Areas of uncertainty")
    requires_review: bool = Field(default=False, description="Whether human review is advised")


class ModelOpinion(BaseModel):
    provider: str
    model: str
    answer: str
    confidence: float
    reasoning: str


class ModelComparisonResult(BaseModel):
    gemini: Optional[ModelOpinion] = None
    local: Optional[ModelOpinion] = None
    agreement: bool = False
    final_confidence: float = 0.0
    requires_review: bool = True
    consensus_answer: Optional[str] = None
    disagreement_reason: Optional[str] = None
