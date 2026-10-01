"""Interactive Human Review Assessment Barrier."""

from __future__ import annotations

import asyncio
import logging
from typing import List, Tuple
from assessments.models import AssessmentData, QuestionItem
from ai.schemas import QuestionAnalysis, ModelComparisonResult

logger = logging.getLogger(__name__)


class AssessmentSession:
    """Manages the human-in-the-loop review barrier for graded assessments."""

    @staticmethod
    def render_review_screen(
        assessment: AssessmentData,
        analysis_results: List[Tuple[QuestionItem, QuestionAnalysis, ModelComparisonResult]],
    ):
        """Display clear educational analysis to terminal and enforce review boundary."""
        border = "=" * 65
        sub_border = "-" * 65

        print(f"\n{border}")
        print(f"        GRADED ASSESSMENT DETECTED: {assessment.title.upper()[:40]}")
        print(f"{border}\n")

        print("Strict Assessment Boundary Enforced:")
        print("  • The agent will NEVER auto-submit or select answers on graded assessments.")
        print("  • Educational analysis and candidate explanations are provided below.")
        print("  • You must verify and submit the assessment in the browser yourself.\n")

        for q, analysis, comp in analysis_results:
            print(f"{sub_border}")
            print(f"Question {q.question_number}: {q.question_text}")
            if q.options:
                for opt in q.options:
                    print(f"   [{opt.label}] {opt.text}")

            print(f"\nCandidate Answer : {analysis.candidate_answer}")
            print(f"Confidence       : {int(analysis.confidence * 100)}%")

            if comp.gemini:
                print(f"\n--- Gemini Analysis ---")
                print(f"Answer: {comp.gemini.answer} (Confidence: {int(comp.gemini.confidence * 100)}%)")
                print(f"Reasoning:\n{comp.gemini.reasoning.strip()[:400]}")

            if comp.local:
                print(f"\n--- Local Model Analysis ---")
                print(f"Answer: {comp.local.answer} (Confidence: {int(comp.local.confidence * 100)}%)")
                print(f"Reasoning:\n{comp.local.reasoning.strip()[:400]}")

            print(f"\nModel Agreement  : {'YES ✓' if comp.agreement else 'NO ⚠ (DISAGREEMENT DETECTED)'}")
            if not comp.agreement and comp.disagreement_reason:
                print(f"Disagreement Note: {comp.disagreement_reason}")

        print(f"\n{border}")
        print("ACTION REQUIRED:")
        print("1. Review the AI reasoning above.")
        print("2. Make your selections and submit inside the open browser window.")
        print("3. When you have completed and submitted the assessment in the browser,")
        print("   return here and press ENTER to continue automated navigation.")
        print(f"{border}\n")

    async def wait_for_user_review(
        self,
        assessment: AssessmentData,
        analysis_results: List[Tuple[QuestionItem, QuestionAnalysis, ModelComparisonResult]],
    ):
        """Display the review screen and await user confirmation before continuing."""
        self.render_review_screen(assessment, analysis_results)
        logger.info(f"Automation paused for human review on graded assessment: {assessment.title}")

        # Run input prompt in async thread so we don't block the event loop
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, input, "Press ENTER after you have completed and submitted in the browser: ")

        print("\n[✓] User confirmation received. Resuming course navigation...\n")
        logger.info("Human confirmation received. Resuming automation.")
