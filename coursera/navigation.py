"""Page navigation, SPA transition handling, and pagination controls."""

from __future__ import annotations

import asyncio
import logging
from typing import Optional
from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError

logger = logging.getLogger(__name__)


class NavigationManager:
    """Handles reliable navigation between Coursera lessons, waiting for network & DOM stability."""

    NEXT_BUTTON_SELECTORS = [
        'button[data-testid="next-item-button"]',
        'button:has-text("Next")',
        'a[data-testid="next-item-button"]',
        'a:has-text("Next")',
        'button[aria-label*="Next item" i]',
        'button[aria-label*="Next lecture" i]',
        'button[aria-label*="Next" i]',
        'button:has-text("Go to next item")',
    ]

    MARK_COMPLETE_SELECTORS = [
        'button:has-text("Mark as completed")',
        'button[data-testid="mark-complete"]',
        'button[aria-label*="Mark as completed" i]',
        'input[type="checkbox"][aria-label*="completed" i]',
    ]

    def __init__(self, default_timeout_ms: int = 30000):
        self.default_timeout_ms = default_timeout_ms

    async def wait_for_stability(self, page: Page, wait_seconds: float = 2.5):
        """Wait for dynamic single-page app (SPA) DOM to settle."""
        try:
            await page.wait_for_load_state("domcontentloaded", timeout=self.default_timeout_ms)
        except Exception:
            pass

        # Brief settle delay for client-side rendering
        await asyncio.sleep(wait_seconds)

    async def navigate_to_lesson(self, page: Page, lesson_url: str) -> bool:
        """Navigate directly to lesson URL and wait for DOM stabilization."""
        logger.info(f"Navigating to lesson: {lesson_url}")
        try:
            await page.goto(lesson_url, wait_until="domcontentloaded", timeout=self.default_timeout_ms)
            await self.wait_for_stability(page)
            return True
        except Exception as e:
            logger.error(f"Failed to navigate to {lesson_url}: {e}")
            return False

    async def fast_forward_video_to_end(self, page: Page) -> bool:
        """Seek HTML5 video or YouTube embed to the end so Coursera registers completion."""
        try:
            logger.info("Fast-forwarding video to end for automatic completion...")
            ff_script = """
            async () => {
                let success = false;
                const videos = document.querySelectorAll('video');
                for (const v of videos) {
                    if (v.duration && !isNaN(v.duration) && v.duration > 1) {
                        v.currentTime = Math.max(0, v.duration - 0.5);
                        try {
                            await v.play();
                        } catch(e) {}
                        v.dispatchEvent(new Event('timeupdate'));
                        v.dispatchEvent(new Event('ended'));
                        success = true;
                    }
                }
                const iframes = document.querySelectorAll('iframe');
                for (const f of iframes) {
                    try {
                        f.contentWindow.postMessage(JSON.stringify({
                            event: 'command',
                            func: 'seekTo',
                            args: [99999, true]
                        }), '*');
                    } catch (e) {}
                }
                return success;
            }
            """
            success = await page.evaluate(ff_script)
            await asyncio.sleep(2.0)
            return bool(success)
        except Exception as e:
            logger.debug(f"Could not fast-forward video: {e}")
            return False

    async def mark_current_lesson_completed_if_available(self, page: Page) -> bool:
        """Click 'Mark as completed' if legitimate Coursera control is exposed."""
        for selector in self.MARK_COMPLETE_SELECTORS:
            try:
                btn = await page.query_selector(selector)
                if btn and await btn.is_visible() and await btn.is_enabled():
                    logger.info("Found legitimate 'Mark as completed' button. Clicking...")
                    await btn.click()
                    await asyncio.sleep(1.0)
                    return True
            except Exception as e:
                logger.debug(f"Error attempting to click complete button: {e}")
        return False

    async def click_next(self, page: Page) -> bool:
        """Click the Next button to navigate to subsequent item."""
        for selector in self.NEXT_BUTTON_SELECTORS:
            try:
                btn = await page.query_selector(selector)
                if btn and await btn.is_visible() and await btn.is_enabled():
                    logger.info(f"Clicking next button with selector: {selector}")
                    await btn.click()
                    await self.wait_for_stability(page)
                    return True
            except Exception as e:
                logger.debug(f"Could not click next button with selector {selector}: {e}")
        return False
