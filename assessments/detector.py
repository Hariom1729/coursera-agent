"""Assessment detection and classification (Graded vs Practice)."""

from __future__ import annotations

import logging
import re
from typing import Optional
from pydantic import BaseModel
from playwright.async_api import Page

logger = logging.getLogger(__name__)


class AssessmentDetectionResult(BaseModel):
    is_assessment: bool = False
    is_graded: bool = False
    assessment_type: str = "quiz"  # quiz, exam, assignment, practice
    confidence: float = 0.0
    requires_review: bool = False
    details: str = ""


class AssessmentDetector:
    """Accurately detects whether a page is an assessment and whether it is graded."""

    GRADED_SIGNALS = [
        r"\bgraded\s+quiz\b",
        r"\bgraded\s+assessment\b",
        r"\bgraded\s+assignment\b",
        r"\bcounts\s+towards\s+your\s+grade\b",
        r"\bpassing\s+grade\b",
        r"\bweight:\s*\d+%\b",
        r"\bgraded\b",
    ]

    PRACTICE_SIGNALS = [
        r"\bpractice\s+quiz\b",
        r"\bungraded\s+quiz\b",
        r"\bpractice\s+exercise\b",
        r"\bdoes\s+not\s+count\s+towards\b",
        r"\bungraded\b",
    ]

    ASSESSMENT_SELECTORS = [
        'div[data-testid="assessment-app"]',
        'div[data-testid="quiz-attempt"]',
        'div.c-quiz-container',
        'div.c-quiz-questions',
        'form[class*="quiz" i]',
        'div[class*="AssessmentApp" i]',
        'div[class*="QuizPrompt" i]',
        'div[aria-label*="Quiz" i]',
        'div[data-testid="question-item"]',
        '.cds-Form-content',
    ]

    async def detect(self, page: Page) -> AssessmentDetectionResult:
        """Inspect live page to identify assessment status and grade implications."""
        current_url = page.url.lower()

        # Check URL patterns
        is_url_quiz = "/quiz/" in current_url
        is_url_exam = "/exam/" in current_url or "/assignment/" in current_url

        # Check DOM element presence
        has_assessment_dom = False
        for sel in self.ASSESSMENT_SELECTORS:
            el = await page.query_selector(sel)
            if el and await el.is_visible():
                has_assessment_dom = True
                break

        # Check presence of question inputs (radios / checkboxes)
        inputs = await page.query_selector_all('input[type="radio"], input[type="checkbox"]')
        has_question_inputs = len(inputs) >= 2

        is_assessment = has_assessment_dom or is_url_quiz or is_url_exam or has_question_inputs
        if not is_assessment:
            return AssessmentDetectionResult(is_assessment=False, confidence=0.98)

        body_text = await page.evaluate("() => document.body ? document.body.innerText.toLowerCase() : ''")

        # Determine if graded vs practice
        practice_match = any(re.search(p, body_text) for p in self.PRACTICE_SIGNALS)
        graded_match = any(re.search(p, body_text) for p in self.GRADED_SIGNALS)

        if is_url_exam or (graded_match and not practice_match):
            return AssessmentDetectionResult(
                is_assessment=True,
                is_graded=True,
                assessment_type="graded_quiz" if "/quiz/" in current_url else "exam",
                confidence=0.94,
                requires_review=True,  # Graded assessments ALWAYS require user review
                details="Graded assessment identified by keywords / URL.",
            )

        if practice_match and not graded_match:
            return AssessmentDetectionResult(
                is_assessment=True,
                is_graded=False,
                assessment_type="practice_quiz",
                confidence=0.90,
                requires_review=False,
                details="Ungraded practice activity identified.",
            )

        # Ambiguous case: assessment detected but markers are mixed
        return AssessmentDetectionResult(
            is_assessment=True,
            is_graded=True,  # Default to safer graded classification when ambiguous
            assessment_type="quiz",
            confidence=0.65,
            requires_review=True,
            details="Assessment markers ambiguous; safely treating as requiring review.",
        )
