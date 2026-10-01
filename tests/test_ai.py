"""Unit tests for AI schemas and prompt generation."""

import pytest
from ai.schemas import (
    OptionModel,
    QuestionAnalysis,
    AssessmentAnalysis,
    GeneralAnalysis,
    ModelOpinion,
    ModelComparisonResult,
)
from ai.verifier import AIVerifier


def test_question_analysis_schema_valid():
    """Verify structured QuestionAnalysis model serialization and validation."""
    data = {
        "question": "What does SQL stand for?",
        "question_type": "multiple_choice",
        "options": [
            {"label": "A", "text": "Structured Query Language"},
            {"label": "B", "text": "Simple Query Logic"},
        ],
        "analysis": "SQL is standard domain-specific language for relational databases.",
        "candidate_answer": "A",
        "confidence": 0.95,
        "reasoning": "Option A is the universally accepted expansion.",
        "uncertainties": [],
        "requires_review": True,
    }
    model = QuestionAnalysis.model_validate(data)
    assert model.candidate_answer == "A"
    assert model.confidence == 0.95
    assert len(model.options) == 2
    assert model.options[0].label == "A"


def test_general_analysis_schema():
    """Verify GeneralAnalysis schema for reading lessons."""
    data = {
        "understanding": "The module teaches basic loop structures.",
        "key_points": ["for loops", "while loops"],
        "answer": "Summary complete",
        "reasoning": "Clear pedagogical narrative",
        "confidence": 0.9,
    }
    analysis = GeneralAnalysis.model_validate(data)
    assert len(analysis.key_points) == 2
    assert analysis.confidence == 0.9


def test_verifier_agreement():
    """Verify agreement calculation when Gemini and Local model agree."""
    verifier = AIVerifier(confidence_threshold=0.80)

    gemini_op = ModelOpinion(
        provider="gemini",
        model="gemini-2.5-flash",
        answer="B",
        confidence=0.94,
        reasoning="Option B is direct definition.",
    )
    local_op = ModelOpinion(
        provider="local",
        model="qwen3.5-4b",
        answer="Option B",
        confidence=0.80,
        reasoning="Option B is standard.",
    )

    result = verifier.verify(gemini_op, local_op)
    assert result.agreement is True
    assert result.final_confidence >= 0.85
    assert result.consensus_answer == "B"
    assert result.requires_review is False


def test_verifier_disagreement():
    """Verify disagreement detection flags mandatory human review."""
    verifier = AIVerifier(confidence_threshold=0.80)

    gemini_op = ModelOpinion(
        provider="gemini",
        model="gemini-2.5-flash",
        answer="B",
        confidence=0.90,
        reasoning="B is correct.",
    )
    local_op = ModelOpinion(
        provider="local",
        model="qwen3.5-4b",
        answer="C",
        confidence=0.75,
        reasoning="C seems right.",
    )

    result = verifier.verify(gemini_op, local_op)
    assert result.agreement is False
    assert result.requires_review is True
    assert "disagreed" in result.disagreement_reason.lower() or "suggested" in result.disagreement_reason.lower()
