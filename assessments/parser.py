"""Text sanitation and QuestionType inference for Coursera assessment questions."""

from __future__ import annotations

import re
from typing import List
from assessments.models import OptionItem, QuestionType

# Avoid circular imports with playwright typing
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from playwright.async_api import ElementHandle


class AssessmentParser:
    """Sanitizes text and infers question type from options and inputs."""

    @staticmethod
    def clean_question_text(raw_text: str) -> str:
        """Strip question number prefix, points badge, or clutter from question prompt."""
        # e.g. "1. Question text (1 point)" or "Question 3) Question text"
        cleaned = re.sub(r'^\s*(?:question\s*)?\d+[\.\):\s-]*', '', raw_text.strip(), flags=re.IGNORECASE)
        cleaned = re.sub(r'\s*\(\d+\s*points?\)\s*$', '', cleaned, flags=re.IGNORECASE)
        # Limit excessive whitespace
        cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
        return cleaned.strip()

    @staticmethod
    def clean_option_text(raw_text: str) -> str:
        """Strip radio/checkbox indicators or option prefix letters from option text."""
        cleaned = re.sub(r'^[A-Z][\.\)]\s*', '', raw_text.strip())
        return cleaned.strip()

    @staticmethod
    def infer_question_type(
        container: any,
        options: List[OptionItem],
        has_visuals: bool = False,
    ) -> QuestionType:
        """Infer question type using available options and visual markers."""
        if has_visuals:
            return QuestionType.IMAGE_BASED

        if not options:
            return QuestionType.SHORT_TEXT

        lower_texts = [opt.text.lower() for opt in options]
        if len(options) == 2 and ("true" in lower_texts and "false" in lower_texts):
            return QuestionType.TRUE_FALSE

        # Multiple choice vs multiple select
        return QuestionType.MULTIPLE_CHOICE
