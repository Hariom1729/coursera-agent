"""Unit tests for AI Router and caching logic."""

import pytest
from unittest.mock import AsyncMock, patch
from config import AIConfig, GeminiConfig, LocalLLMConfig, VerificationConfig
from ai.router import AIRouter
from ai.schemas import QuestionAnalysis


@pytest.mark.asyncio
async def test_router_fallback_to_local_when_gemini_fails():
    """Verify router automatically engages local LLM fallback if Gemini raises error."""
    config = AIConfig(
        primary_provider="gemini",
        gemini=GeminiConfig(enabled=True),
        local=LocalLLMConfig(enabled=True),
        verification=VerificationConfig(enabled=False),
    )
    router = AIRouter(config=config)

    # Mock gemini to fail and local to succeed
    mock_gemini = AsyncMock()
    mock_gemini.analyze.side_effect = RuntimeError("Gemini 429 Resource Exhausted")
    router.gemini = mock_gemini

    expected_qa = QuestionAnalysis(
        question="What is 2+2?",
        candidate_answer="4",
        confidence=0.99,
        reasoning="Arithmetic",
    )
    mock_local = AsyncMock()
    mock_local.analyze.return_value = expected_qa
    router.local = mock_local

    res = await router.analyze("What is 2+2?", schema=QuestionAnalysis, use_cache=False)
    assert res.candidate_answer == "4"
    mock_gemini.analyze.assert_called_once()
    mock_local.analyze.assert_called_once()


@pytest.mark.asyncio
async def test_router_cross_verification_agreement():
    """Verify dual analysis queries both providers and computes consensus."""
    config = AIConfig(
        primary_provider="gemini",
        gemini=GeminiConfig(enabled=True),
        local=LocalLLMConfig(enabled=True),
        verification=VerificationConfig(enabled=True, confidence_threshold=0.80),
    )
    router = AIRouter(config=config)

    qa1 = QuestionAnalysis(
        question="Select the mutable type:",
        candidate_answer="A",
        confidence=0.92,
        reasoning="List is mutable",
    )
    qa2 = QuestionAnalysis(
        question="Select the mutable type:",
        candidate_answer="A",
        confidence=0.85,
        reasoning="Lists can be modified",
    )

    router.gemini = AsyncMock()
    router.gemini.analyze.return_value = qa1
    router.local = AsyncMock()
    router.local.analyze.return_value = qa2

    analysis, comp = await router.analyze_and_verify_question("Select the mutable type:")
    assert comp.agreement is True
    assert analysis.candidate_answer == "A"
    assert comp.final_confidence >= 0.85
