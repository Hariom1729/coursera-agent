"""Browser crash recovery and resilient page handling."""

from __future__ import annotations

import asyncio
import logging
from typing import Callable, TypeVar, Any
from playwright.async_api import Page, Error as PlaywrightError
from browser.manager import BrowserManager

logger = logging.getLogger(__name__)
T = TypeVar("T")


class BrowserRecovery:
    """Handles browser crashes, detached DOM elements, and navigation reloads."""

    def __init__(self, browser_manager: BrowserManager, max_retries: int = 3):
        self.browser_manager = browser_manager
        self.max_retries = max_retries

    async def recover_page(self, last_url: str = "") -> Page:
        """Recover a closed or crashed page, reopening context if required."""
        logger.warning("Initiating browser page recovery...")
        try:
            page = await self.browser_manager.get_page()
            if page.is_closed():
                page = await self.browser_manager.start()
        except Exception as e:
            logger.error(f"Failed to get page from manager: {e}. Restarting entire browser manager...")
            await self.browser_manager.close()
            page = await self.browser_manager.start()

        if last_url:
            logger.info(f"Restoring navigation to: {last_url}")
            try:
                await page.goto(last_url, wait_until="domcontentloaded", timeout=45000)
                await asyncio.sleep(2)
            except Exception as nav_err:
                logger.warning(f"Could not immediately restore URL {last_url}: {nav_err}")

        return page

    async def execute_with_recovery(
        self,
        operation: Callable[[Page], Any],
        fallback_url: str = "",
    ) -> Any:
        """Execute a page action with automatic retry and browser recovery on failure."""
        attempt = 0
        last_exception: Exception | None = None

        while attempt < self.max_retries:
            attempt += 1
            try:
                page = await self.browser_manager.get_page()
                return await operation(page)
            except PlaywrightError as e:
                last_exception = e
                logger.warning(f"Playwright error during operation (attempt {attempt}/{self.max_retries}): {e}")
                if "Target page, context or browser has been closed" in str(e) or "Crash" in str(e):
                    await self.recover_page(fallback_url)
                await asyncio.sleep(attempt * 2)
            except Exception as e:
                last_exception = e
                logger.warning(f"Unexpected error during browser action (attempt {attempt}/{self.max_retries}): {e}")
                await asyncio.sleep(attempt * 2)

        raise RuntimeError(f"Operation failed after {self.max_retries} recovery attempts. Last error: {last_exception}")
