"""AI Verification and Confidence engine."""

from __future__ import annotations

import logging
from typing import Optional
from ai.schemas import (
    ModelOpinion,
    ModelComparisonResult,
    QuestionAnalysis,
)

logger = logging.getLogger(__name__)


class AIVerifier:
    """Compares opinions from multiple AI models to compute agreement, confidence, and review flags."""

    def __init__(self, confidence_threshold: float = 0.80):
        self.confidence_threshold = confidence_threshold

    def normalize_answer(self, ans: Optional[str]) -> str:
        """Normalize answer string (trim, uppercase, remove punctuation) for comparison."""
        if not ans:
            return ""
        clean = ans.strip().upper()
        # If answering like 'Option A' or 'A.', simplify to 'A'
        if clean.startswith("OPTION "):
            clean = clean[7:].strip()
        if len(clean) > 1 and clean[1] in (".", ")", ":", "-"):
            clean = clean[0]
        return clean.strip()

    def verify(
        self,
        gemini_result: Optional[QuestionAnalysis | ModelOpinion],
        local_result: Optional[QuestionAnalysis | ModelOpinion],
    ) -> ModelComparisonResult:
        """Compare Gemini analysis and Local model analysis."""
        gemini_op: Optional[ModelOpinion] = None
        local_op: Optional[ModelOpinion] = None

        if gemini_result is not None:
            if isinstance(gemini_result, QuestionAnalysis):
                gemini_op = ModelOpinion(
                    provider="gemini",
                    model="gemini",
                    answer=gemini_result.candidate_answer,
                    confidence=gemini_result.confidence,
                    reasoning=gemini_result.reasoning,
                )
            else:
                gemini_op = gemini_result

        if local_result is not None:
            if isinstance(local_result, QuestionAnalysis):
                local_op = ModelOpinion(
                    provider="local",
                    model="local-llm",
                    answer=local_result.candidate_answer,
                    confidence=local_result.confidence,
                    reasoning=local_result.reasoning,
                )
            else:
                local_op = local_result

        # Scenario 1: Only Gemini is available
        if gemini_op and not local_op:
            final_conf = gemini_op.confidence
            req_review = final_conf < self.confidence_threshold
            return ModelComparisonResult(
                gemini=gemini_op,
                local=None,
                agreement=True,
                final_confidence=final_conf,
                requires_review=req_review,
                consensus_answer=gemini_op.answer,
            )

        # Scenario 2: Only Local model is available
        if local_op and not gemini_op:
            final_conf = local_op.confidence * 0.85  # Slight discount for unverified local model
            return ModelComparisonResult(
                gemini=None,
                local=local_op,
                agreement=True,
                final_confidence=final_conf,
                requires_review=True,  # Always review single local model
                consensus_answer=local_op.answer,
            )

        # Scenario 3: Neither available
        if not gemini_op and not local_op:
            return ModelComparisonResult(
                gemini=None,
                local=None,
                agreement=False,
                final_confidence=0.0,
                requires_review=True,
                disagreement_reason="No AI model responded successfully.",
            )

        # Scenario 4: Both answered -> compare
        norm_gemini = self.normalize_answer(gemini_op.answer)
        norm_local = self.normalize_answer(local_op.answer)
        agreement = (norm_gemini == norm_local) and bool(norm_gemini)

        if agreement:
            # High confidence when both agree
            final_conf = min(0.99, max(gemini_op.confidence, local_op.confidence) + 0.05)
            req_review = final_conf < self.confidence_threshold
            return ModelComparisonResult(
                gemini=gemini_op,
                local=local_op,
                agreement=True,
                final_confidence=round(final_conf, 2),
                requires_review=req_review,
                consensus_answer=gemini_op.answer,
            )
        else:
            # Disagreement -> lower confidence and mandate human review
            final_conf = round(min(gemini_op.confidence, local_op.confidence) * 0.5, 2)
            disagree_msg = f"Gemini suggested '{gemini_op.answer}', while Local LLM suggested '{local_op.answer}'."
            logger.warning(f"⚠ AI MODEL DISAGREEMENT: {disagree_msg}")
            return ModelComparisonResult(
                gemini=gemini_op,
                local=local_op,
                agreement=False,
                final_confidence=final_conf,
                requires_review=True,
                consensus_answer=gemini_op.answer,  # Primary default
                disagreement_reason=disagree_msg,
            )
