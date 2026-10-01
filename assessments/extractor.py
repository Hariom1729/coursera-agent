"""Visible assessment and question extraction from live Coursera DOM."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import List, Optional
from playwright.async_api import Page, ElementHandle
from assessments.models import QuestionItem, OptionItem, QuestionType, AssessmentData
from assessments.parser import AssessmentParser

logger = logging.getLogger(__name__)


class AssessmentExtractor:
    """Extracts visible question text, options, and diagram flags without interacting with answer inputs."""

    QUESTION_CONTAINER_SELECTORS = [
        'div[data-testid="question-item"]',
        'div[data-testid="part-item"]',
        'div[class*="QuestionCard" i]',
        'div[class*="QuestionPrompt" i]',
        'div[class*="quiz-question" i]',
        'div[class*="c-quiz-question" i]',
        'div.cds-Form-content',
        'fieldset',
    ]

    OPTION_CONTAINER_SELECTORS = [
        'label[class*="option" i]',
        'div[class*="option" i]',
        'label[class*="Radio" i]',
        'label[class*="Checkbox" i]',
        'div[class*="Choice" i]',
        'div.cds-Radio-container',
        'div.cds-Checkbox-container',
        'li[role="radio"]',
        'li[role="checkbox"]',
    ]

    def __init__(self, parser: Optional[AssessmentParser] = None):
        self.parser = parser or AssessmentParser()

    async def extract_assessment(
        self,
        page: Page,
        assessment_id: str,
        title: str,
        is_graded: bool,
        screenshots_dir: str = "./screenshots/assessments",
    ) -> AssessmentData:
        """Extract all visible questions and options from the assessment page."""
        logger.info(f"Extracting questions for assessment: {title} (Graded: {is_graded})")
        Path(screenshots_dir).mkdir(parents=True, exist_ok=True)

        question_items: List[QuestionItem] = []

        # Ensure any Honor Code modal or Start/Resume button is clicked
        try:
            from assessments.solver import AssessmentSolver
            await AssessmentSolver().prepare_quiz(page)
        except Exception as e:
            logger.debug(f"Quiz preparation note: {e}")

        # Find all question blocks
        containers: List[ElementHandle] = []
        for selector in self.QUESTION_CONTAINER_SELECTORS:
            elems = await page.query_selector_all(selector)
            if elems and len(elems) >= 1:
                containers = elems
                break

        if not containers:
            logger.warning("No explicit question containers matched. Falling back to whole-form inspection.")
            containers = await page.query_selector_all("form fieldset, form > div")

        for idx, container in enumerate(containers, start=1):
            try:
                # 1. Question Prompt
                prompt_el = await container.query_selector(
                    'legend, [class*="prompt" i], [class*="question-text" i], h3, h4, p'
                )
                raw_prompt = await prompt_el.inner_text() if prompt_el else await container.inner_text()
                question_text = self.parser.clean_question_text(raw_prompt)

                # 2. Check for diagrams, canvas, or images
                has_visuals = False
                canvas_or_svg = await container.query_selector('canvas, svg, img[src*="diagram"], img[src*="asset"]')
                if canvas_or_svg and await canvas_or_svg.is_visible():
                    has_visuals = True

                # Screenshot if question contains diagram
                screenshot_path = None
                if has_visuals:
                    screenshot_file = Path(screenshots_dir) / f"{assessment_id}_q{idx}.png"
                    try:
                        await container.screenshot(path=str(screenshot_file))
                        screenshot_path = str(screenshot_file)
                        logger.info(f"Captured question diagram screenshot: {screenshot_path}")
                    except Exception as e:
                        logger.debug(f"Failed to capture element screenshot: {e}")

                # 3. Extract Options
                options: List[OptionItem] = []
                opt_elems = []
                for opt_sel in self.OPTION_CONTAINER_SELECTORS:
                    found = await container.query_selector_all(opt_sel)
                    if found:
                        opt_elems = found
                        break

                option_labels = ["A", "B", "C", "D", "E", "F", "G", "H"]
                for opt_idx, opt_el in enumerate(opt_elems):
                    opt_text = (await opt_el.inner_text()).strip()
                    clean_opt = self.parser.clean_option_text(opt_text)
                    if clean_opt:
                        lbl = option_labels[opt_idx] if opt_idx < len(option_labels) else f"Opt{opt_idx+1}"
                        options.append(OptionItem(label=lbl, text=clean_opt))

                # Determine question type
                q_type = self.parser.infer_question_type(container, options, has_visuals)

                q_item = QuestionItem(
                    id=f"{assessment_id}_q{idx}",
                    assessment_id=assessment_id,
                    question_number=idx,
                    question_text=question_text,
                    question_type=q_type,
                    options=options,
                    has_diagram_or_canvas=has_visuals,
                    screenshot_path=screenshot_path,
                )
                question_items.append(q_item)

            except Exception as e:
                logger.warning(f"Error parsing question #{idx}: {e}")

        logger.info(f"Extracted {len(question_items)} questions from assessment.")
        return AssessmentData(
            id=assessment_id,
            title=title,
            is_graded=is_graded,
            total_questions=len(question_items),
            questions=question_items,
            requires_review=is_graded or any(q.has_diagram_or_canvas for q in question_items),
        )
