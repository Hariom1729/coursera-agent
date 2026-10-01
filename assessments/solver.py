"""Automated Quiz and Assessment Solver and Submitter for Coursera."""

from __future__ import annotations

import asyncio
import logging
import re
from typing import List, Optional, Any
from playwright.async_api import Page, ElementHandle
from assessments.models import AssessmentData, QuestionItem
from ai.schemas import QuestionAnalysis

logger = logging.getLogger(__name__)


class AssessmentSolver:
    """Fills assessment questions based on AI candidate answers and submits them."""

    MODAL_CONTINUE_SELECTORS = [
        'button:has-text("Resume assignment")',
        'button:has-text("Start assignment")',
        'button:has-text("Resume quiz")',
        'button:has-text("Start quiz")',
        'button:has-text("Take quiz")',
        'button:has-text("Try again")',
        'button:has-text("Continue")',
        'button:has-text("I agree")',
        'button:has-text("Agree and continue")',
        'button[data-testid*="continue"]',
        'button:has-text("Resume")',
        'button:has-text("Start")',
    ]

    QUESTION_CONTAINER_SELECTORS = [
        'div[data-testid="question-item"]',
        'div[data-testid*="part-item"]',
        'div[class*="rc-FormPartsQuestion" i]',
        'div[class*="QuestionCard" i]',
        'div[class*="QuestionPrompt" i]',
        'div[class*="quiz-question" i]',
        'div[class*="c-quiz-question" i]',
        'div[role="radiogroup"]',
        'div.cds-RadioGroup-root',
        'fieldset',
    ]

    SUBMIT_SELECTORS = [
        'button:has-text("Submit Quiz")',
        'button:has-text("Submit assignment")',
        'button:has-text("Submit Assignment")',
        'button:has-text("Submit")',
        'button[data-e2e="submit-button"]',
        'button[data-testid="submit-button"]',
    ]

    CONFIRM_MODAL_SELECTORS = [
        'div[role="dialog"] button:has-text("Submit")',
        'div[role="dialog"] button:has-text("Confirm")',
        'div[role="dialog"] button:has-text("Yes")',
        'button:has-text("Submit now")',
    ]

    async def prepare_quiz(self, page: Page) -> bool:
        """Dismiss Honor Code modals, agree to terms, and click Start/Resume buttons."""
        logger.info("Preparing assessment page (checking for modals and Start/Resume buttons)...")
        dismissed = False

        for _ in range(5):
            # Check for honor code checkboxes in modals
            try:
                honor_checks = await page.query_selector_all(
                    'div[role="dialog"] input[type="checkbox"], label:has-text("Honor Code") input, input[name*="honor" i]'
                )
                for cb in honor_checks:
                    if await cb.is_visible() and not await cb.is_checked():
                        await cb.check()
                        logger.info("Checked Honor Code checkbox in modal.")
            except Exception as e:
                logger.debug(f"Honor check error: {e}")

            # Click Continue / Start / Resume buttons
            clicked_any = False
            for selector in self.MODAL_CONTINUE_SELECTORS:
                try:
                    btn = await page.query_selector(selector)
                    if btn and await btn.is_visible() and await btn.is_enabled():
                        btn_text = (await btn.inner_text()).strip()
                        logger.info(f"Clicking assessment modal button: '{btn_text}'")
                        await btn.click()
                        await page.wait_for_timeout(2500)
                        clicked_any = True
                        dismissed = True
                        break
                except Exception as e:
                    logger.debug(f"Error clicking {selector}: {e}")

            # Check if questions have appeared on the page
            has_questions = await page.query_selector(
                'input[type="radio"], div[role="radiogroup"], div.cds-RadioGroup-root, fieldset, div[class*="rc-FormPartsQuestion" i]'
            )
            if has_questions and await has_questions.is_visible():
                logger.info("Assessment questions successfully loaded on page.")
                return True

            if not clicked_any:
                break
            await page.wait_for_timeout(1000)

        return dismissed

    async def fill_and_submit(
        self,
        page: Page,
        assessment: AssessmentData,
        analyses: List[Any],
    ) -> bool:
        """Fill all question choices and submit the assessment."""
        logger.info(f"Automatically solving and submitting assessment: '{assessment.title}'")

        # 1. Ensure questions are loaded
        await self.prepare_quiz(page)

        # 2. Locate all question blocks
        question_containers: List[ElementHandle] = []
        for selector in self.QUESTION_CONTAINER_SELECTORS:
            elems = await page.query_selector_all(selector)
            if elems and len(elems) >= 1:
                question_containers = elems
                break

        logger.info(f"Found {len(question_containers)} question containers on page.")

        # Map analyses by question index
        for i, q in enumerate(assessment.questions):
            item = analyses[i] if i < len(analyses) else None
            if not item:
                logger.warning(f"No AI analysis found for question #{i+1}; skipping answer.")
                continue

            # Safely unpack Tuple[QuestionItem, QuestionAnalysis, ModelComparisonResult]
            if isinstance(item, tuple):
                analysis: QuestionAnalysis = item[1]
            else:
                analysis = item

            cand_answer = (getattr(analysis, "candidate_answer", None) or "").strip()
            logger.info(f"Answering Question #{i+1}: AI candidate answer = '{cand_answer}'")

            # Try to get question container
            container = question_containers[i] if i < len(question_containers) else None

            try:
                answered = await self._answer_single_question(page, container, q, cand_answer)
                if answered:
                    logger.info(f"Successfully selected answer for Question #{i+1}.")
                else:
                    logger.warning(f"Could not select answer for Question #{i+1}.")
            except Exception as e:
                logger.error(f"Error answering Question #{i+1}: {e}")

            await page.wait_for_timeout(800)

        # 3. Scroll to bottom and check agreement checkbox if required
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await page.wait_for_timeout(1000)

        try:
            bottom_checkboxes = await page.query_selector_all('input[type="checkbox"]:not(:checked)')
            for cb in bottom_checkboxes:
                if await cb.is_visible():
                    await cb.check()
                    logger.info("Checked agreement / honor checkbox before submitting.")
                    await page.wait_for_timeout(500)
        except Exception as e:
            logger.debug(f"Agreement checkbox error: {e}")

        # 4. Click Submit
        submitted = False
        for sub_sel in self.SUBMIT_SELECTORS:
            try:
                sub_btn = await page.query_selector(sub_sel)
                if sub_btn and await sub_btn.is_visible() and await sub_btn.is_enabled():
                    btn_label = (await sub_btn.inner_text()).strip()
                    logger.info(f"Clicking assessment submission button: '{btn_label}'")
                    await sub_btn.click()
                    await page.wait_for_timeout(2500)
                    submitted = True
                    break
            except Exception as e:
                logger.debug(f"Error clicking submit {sub_sel}: {e}")

        # 5. Handle submission confirmation modal if present
        for conf_sel in self.CONFIRM_MODAL_SELECTORS:
            try:
                conf_btn = await page.query_selector(conf_sel)
                if conf_btn and await conf_btn.is_visible():
                    logger.info("Clicking confirmation submit dialog button...")
                    await conf_btn.click()
                    await page.wait_for_timeout(3000)
                    submitted = True
                    break
            except Exception as e:
                logger.debug(f"Confirmation modal handling: {e}")

        if submitted:
            logger.info("Assessment submitted successfully. Waiting for results...")
            await page.wait_for_timeout(4000)
            return True
        else:
            logger.warning("Could not locate or click Submit button on assessment page.")
            return False

    async def _answer_single_question(
        self,
        page: Page,
        container: Optional[ElementHandle],
        q_item: QuestionItem,
        candidate_answer: str,
    ) -> bool:
        """Find and click the appropriate option radio/checkbox/label."""
        scope = container or page

        cand_clean = candidate_answer.strip().upper()
        letter_match = re.search(r'\b([A-H])\b', cand_clean)
        target_letter = letter_match.group(1) if letter_match else None

        # 1. Collect option elements
        option_elements = await scope.query_selector_all(
            'label[class*="Radio" i], label[class*="Checkbox" i], '
            'div[class*="cds-Radio" i], div[class*="cds-Checkbox" i], '
            'label.cds-Radio-container, label.cds-Checkbox-container, '
            'input[type="radio"], input[type="checkbox"], label'
        )

        # Strategy A: Match by option letter index (A=0, B=1, C=2, D=3...)
        if target_letter:
            letter_idx = ord(target_letter) - ord('A')
            if 0 <= letter_idx < len(q_item.options):
                opt_info = q_item.options[letter_idx]
                target_text = opt_info.text.strip().lower()
                for el in option_elements:
                    text = (await el.inner_text()).strip().lower()
                    if target_text and (target_text in text or text in target_text):
                        await el.click()
                        return True

            # Fallback to index of inputs
            inputs = await scope.query_selector_all('input[type="radio"], input[type="checkbox"]')
            if 0 <= letter_idx < len(inputs):
                inp = inputs[letter_idx]
                try:
                    await inp.click(force=True)
                    return True
                except Exception:
                    parent = await inp.evaluate_handle("el => el.closest('label') || el")
                    await parent.as_element().click()
                    return True

        # Strategy B: Match by text content
        for el in option_elements:
            text = (await el.inner_text()).strip()
            if not text:
                continue
            if candidate_answer.lower() in text.lower() or text.lower() in candidate_answer.lower():
                await el.click()
                return True

        # Strategy C: Text input / short answer
        text_inputs = await scope.query_selector_all('textarea, input[type="text"]')
        for ti in text_inputs:
            if await ti.is_visible():
                await ti.fill(candidate_answer)
                return True

        return False
