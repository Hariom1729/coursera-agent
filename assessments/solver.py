"""Automated Quiz and Assessment Solver and Submitter for Coursera."""

from __future__ import annotations

import asyncio
import logging
import re
from typing import List, Optional
from playwright.async_api import Page, ElementHandle
from assessments.models import AssessmentData, QuestionItem
from ai.schemas import QuestionAnalysis

logger = logging.getLogger(__name__)


class AssessmentSolver:
    """Fills assessment questions based on AI candidate answers and submits them."""

    MODAL_CONTINUE_SELECTORS = [
        'button:has-text("Continue")',
        'button:has-text("I agree")',
        'button:has-text("Agree and continue")',
        'button[data-testid*="continue"]',
        'button:has-text("Start")',
        'button:has-text("Start quiz")',
        'button:has-text("Start assignment")',
        'button:has-text("Resume")',
        'button:has-text("Resume quiz")',
        'button:has-text("Take quiz")',
        'button:has-text("Try again")',
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
        logger.info("Preparing assessment page (checking for modals and Start buttons)...")
        dismissed = False

        for _ in range(4):
            clicked_any = False
            # Check for honor code checkboxes
            try:
                honor_checks = await page.query_selector_all(
                    'div[role="dialog"] input[type="checkbox"], label:has-text("Honor Code") input, input[name*="honor" i]'
                )
                for cb in honor_checks:
                    if await cb.is_visible() and not await cb.is_checked():
                        await cb.check()
                        logger.info("Checked Honor Code checkbox in modal.")
                        clicked_any = True
            except Exception as e:
                logger.debug(f"Honor check error: {e}")

            # Click Continue / Start / Resume buttons
            for selector in self.MODAL_CONTINUE_SELECTORS:
                try:
                    btn = await page.query_selector(selector)
                    if btn and await btn.is_visible() and await btn.is_enabled():
                        btn_text = (await btn.inner_text()).strip()
                        logger.info(f"Clicking assessment modal button: '{btn_text}'")
                        await btn.click()
                        await page.wait_for_timeout(2000)
                        clicked_any = True
                        dismissed = True
                        break
                except Exception as e:
                    logger.debug(f"Error clicking {selector}: {e}")

            if not clicked_any:
                break
            await page.wait_for_timeout(1000)

        # Wait for questions to be present
        try:
            await page.wait_for_selector('fieldset, div[data-testid*="part-item"], form', timeout=5000)
        except Exception:
            pass

        return dismissed

    async def fill_and_submit(
        self,
        page: Page,
        assessment: AssessmentData,
        analyses: List[QuestionAnalysis],
    ) -> bool:
        """Fill all question choices and submit the assessment."""
        logger.info(f"Automatically solving and submitting assessment: '{assessment.title}'")

        # 1. Ensure modal is dismissed
        await self.prepare_quiz(page)

        # 2. Locate all question blocks
        question_containers = await page.query_selector_all(
            'div[data-testid="question-item"], div[data-testid="part-item"], '
            'div[class*="QuestionCard" i], div[class*="c-quiz-question" i], '
            'fieldset, div.cds-Form-content'
        )

        logger.info(f"Found {len(question_containers)} question containers on page.")

        # Map analyses by question index (0-indexed or 1-indexed)
        for i, q in enumerate(assessment.questions):
            analysis = analyses[i] if i < len(analyses) else None
            if not analysis:
                logger.warning(f"No AI analysis found for question #{i+1}; skipping answer.")
                continue

            cand_answer = (analysis.candidate_answer or "").strip()
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
            # Check any honor code / agreement checkbox before submission
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

        # Clean candidate answer
        cand_clean = candidate_answer.strip().upper()
        letter_match = re.search(r'\b([A-H])\b', cand_clean)
        target_letter = letter_match.group(1) if letter_match else None

        # 1. Find all option elements in this question container
        option_elements = await scope.query_selector_all(
            'label[class*="option" i], label[class*="Radio" i], label[class*="Checkbox" i], '
            'div[class*="cds-Radio" i], div[class*="cds-Checkbox" i], '
            'input[type="radio"], input[type="checkbox"], label'
        )

        # Strategy A: Match by option index or letter (A=0, B=1, C=2, D=3...)
        if target_letter:
            letter_idx = ord(target_letter) - ord('A')
            # Look at options list from question item
            if 0 <= letter_idx < len(q_item.options):
                opt_info = q_item.options[letter_idx]
                target_text = opt_info.text.lower()
                # Find matching element containing this text
                for el in option_elements:
                    text = (await el.inner_text()).strip().lower()
                    if target_text in text or text in target_text:
                        input_el = await el.query_selector('input')
                        target_click = input_el or el
                        await target_click.click()
                        return True

            # Fallback: click the N-th radio or checkbox input
            inputs = await scope.query_selector_all('input[type="radio"], input[type="checkbox"]')
            if 0 <= letter_idx < len(inputs):
                inp = inputs[letter_idx]
                if await inp.is_visible():
                    await inp.click()
                    return True
                else:
                    # Click parent label
                    parent = await inp.evaluate_handle("el => el.closest('label') || el")
                    await parent.as_element().click()
                    return True

        # Strategy B: Match by text content
        for el in option_elements:
            text = (await el.inner_text()).strip()
            if not text:
                continue
            # If candidate answer text appears in option text
            if candidate_answer.lower() in text.lower() or text.lower() in candidate_answer.lower():
                input_el = await el.query_selector('input')
                target_click = input_el or el
                await target_click.click()
                return True

        # Strategy C: Text input / short answer
        text_inputs = await scope.query_selector_all('textarea, input[type="text"]')
        for ti in text_inputs:
            if await ti.is_visible():
                await ti.fill(candidate_answer)
                return True

        return False
