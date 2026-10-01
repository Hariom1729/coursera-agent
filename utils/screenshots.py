"""Screenshot manager saving timestamped diagnostic images."""

from __future__ import annotations

import datetime
import logging
import re
from pathlib import Path
from typing import Optional
from playwright.async_api import Page

logger = logging.getLogger(__name__)


class ScreenshotManager:
    """Captures and stores categorised screenshots for AI analysis and debugging."""

    CATEGORIES = ["course", "lessons", "assessments", "errors"]

    def __init__(self, base_dir: str = "./screenshots"):
        self.base_dir = Path(base_dir)
        self.init_directories()

    def init_directories(self):
        """Create subdirectories for each category."""
        for cat in self.CATEGORIES:
            (self.base_dir / cat).mkdir(parents=True, exist_ok=True)

    def _generate_filename(self, event_name: str) -> str:
        """Create timestamped filename: YYYYMMDD_HHMMSS_<event>.png."""
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        clean_event = re.sub(r'[^a-zA-Z0-9_]', '_', event_name.lower())
        return f"{timestamp}_{clean_event}.png"

    async def capture(
        self,
        page: Page,
        event_name: str,
        category: str = "errors",
    ) -> Optional[str]:
        """Capture screenshot and return absolute file path."""
        try:
            if category not in self.CATEGORIES:
                category = "errors"

            target_dir = self.base_dir / category
            filename = self._generate_filename(event_name)
            filepath = target_dir / filename

            await page.screenshot(path=str(filepath), full_page=False)
            logger.info(f"Captured screenshot [{category}]: {filepath}")
            return str(filepath.resolve())
        except Exception as e:
            logger.warning(f"Could not take screenshot for '{event_name}': {e}")
            return None
