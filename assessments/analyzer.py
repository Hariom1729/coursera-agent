"""Assessment analysis coordinator sending questions to AI Router and persisting results."""

from __future__ import annotations

import logging
from typing import List, Tuple
from assessments.models import AssessmentData, QuestionItem
from ai.router import AIRouter
from ai.schemas import QuestionAnalysis, ModelComparisonResult
from database.database import DatabaseSessionManager
from database.repositories import AssessmentRepository

logger = logging.getLogger(__name__)


class AssessmentAnalyzer:
    """Coordinates AI analysis and dual-model verification for all questions in an assessment."""

    def __init__(self, ai_router: AIRouter, db_manager: DatabaseSessionManager):
        self.ai_router = ai_router
        self.db_manager = db_manager

    def format_question_for_ai(self, question: QuestionItem) -> str:
        """Format question text and options into clean prompt text."""
        lines = [f"Question {question.question_number}: {question.question_text}"]
        if question.options:
            lines.append("Options:")
            for opt in question.options:
                lines.append(f"  {opt.label}. {opt.text}")
        else:
            lines.append("(No explicit multiple-choice options visible. Analyze as short-answer/conceptual question.)")

        return "\n".join(lines)

    async def analyze_assessment(
        self,
        assessment: AssessmentData,
    ) -> List[Tuple[QuestionItem, QuestionAnalysis, ModelComparisonResult]]:
        """Run AI analysis and verification on every question in the assessment."""
        logger.info(f"Analyzing {len(assessment.questions)} questions for assessment: '{assessment.title}'")

        # 1. Upsert assessment in database
        async with self.db_manager.session() as session:
            repo = AssessmentRepository(session)
            await repo.upsert_assessment(
                assessment_id=assessment.id,
                lesson_id=assessment.lesson_id,
                title=assessment.title,
                assessment_type=assessment.assessment_type,
                is_graded=assessment.is_graded,
                total_questions=assessment.total_questions,
                confidence=assessment.confidence,
                requires_review=assessment.requires_review,
            )

        results: List[Tuple[QuestionItem, QuestionAnalysis, ModelComparisonResult]] = []

        # 2. Analyze each question
        for q in assessment.questions:
            logger.info(f"Analyzing Question #{q.question_number}...")

            # Persist question record
            async with self.db_manager.session() as session:
                repo = AssessmentRepository(session)
                opts_dict = [{"label": o.label, "text": o.text} for o in q.options]
                await repo.save_question(
                    question_id=q.id,
                    assessment_id=q.assessment_id,
                    question_number=q.question_number,
                    question_text=q.question_text,
                    question_type=q.question_type.value,
                    options=opts_dict,
                    screenshot_path=q.screenshot_path,
                )

            prompt = self.format_question_for_ai(q)
            analysis, comparison = await self.ai_router.analyze_and_verify_question(
                question_prompt=prompt,
                screenshot_path=q.screenshot_path,
            )

            results.append((q, analysis, comparison))

        return results
