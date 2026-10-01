"""Persistent Playwright browser manager."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional
from playwright.async_api import (
    async_playwright,
    BrowserContext,
    Page,
    Playwright,
)
from config import BrowserConfig

logger = logging.getLogger(__name__)


class BrowserManager:
    """Manages persistent Playwright browser context and active pages."""

    def __init__(self, config: BrowserConfig):
        self.config = config
        self._playwright: Optional[Playwright] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None

    async def start(self) -> Page:
        """Launch persistent context and return active page."""
        if self._context is not None and self._page is not None and not self._page.is_closed():
            return self._page

        profile_dir = Path(self.config.profile_path).resolve()
        profile_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"Launching persistent browser context from {profile_dir} (headless={self.config.headless})")

        self._playwright = await async_playwright().start()

        # Chromium launch arguments for smooth desktop automation
        args = [
            "--disable-blink-features=AutomationControlled",
            "--no-default-browser-check",
            "--disable-infobars",
            "--start-maximized",
        ]

        self._context = await self._playwright.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            headless=self.config.headless,
            slow_mo=self.config.slow_mo,
            viewport={
                "width": self.config.viewport_width,
                "height": self.config.viewport_height,
            },
            args=args,
            accept_downloads=True,
        )

        # Get existing or create new page
        pages = self._context.pages
        if pages:
            self._page = pages[0]
        else:
            self._page = await self._context.new_page()

        # Register event handlers for robustness
        self._page.on("crash", self._on_page_crash)
        self._page.on("close", self._on_page_close)

        logger.info("Browser session initialized successfully.")
        return self._page

    async def _on_page_crash(self, page: Page):
        logger.error("Active browser page crashed! Recovery needed.")

    async def _on_page_close(self, page: Page):
        logger.warning("Active browser page was closed.")

    async def get_page(self) -> Page:
        """Get or re-initialize current page."""
        if self._page is None or self._page.is_closed():
            if self._context is None:
                return await self.start()
            self._page = await self._context.new_page()
            self._page.on("crash", self._on_page_crash)
            self._page.on("close", self._on_page_close)
        return self._page

    async def close(self):
        """Cleanly close context and Playwright engine."""
        logger.info("Closing browser session...")
        try:
            if self._context:
                await self._context.close()
                self._context = None
            if self._playwright:
                await self._playwright.stop()
                self._playwright = None
            self._page = None
            logger.info("Browser session closed cleanly.")
        except Exception as e:
            logger.warning(f"Error during browser teardown: {e}")
