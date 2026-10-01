"""Native macOS notification dispatcher using osascript."""

from __future__ import annotations

import asyncio
import logging
import platform
import subprocess
from config import NotificationsConfig

logger = logging.getLogger(__name__)


class MacOSNotifier:
    """Sends native macOS desktop notifications with sound."""

    def __init__(self, config: NotificationsConfig):
        self.config = config
        self.is_macos = platform.system() == "Darwin"

    def notify_sync(self, title: str, message: str, subtitle: str = "Coursera Agent"):
        """Synchronously dispatch notification via osascript."""
        if not self.config.enabled or not self.is_macos:
            return

        # Sanitize single and double quotes
        safe_title = title.replace('"', '\\"').replace("'", "\\'")
        safe_msg = message.replace('"', '\\"').replace("'", "\\'")
        safe_sub = subtitle.replace('"', '\\"').replace("'", "\\'")

        apple_script = (
            f'display notification "{safe_msg}" '
            f'with title "{safe_title}" '
            f'subtitle "{safe_sub}" '
            f'sound name "Ping"'
        )

        try:
            subprocess.run(
                ["osascript", "-e", apple_script],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
                timeout=5,
            )
        except Exception as e:
            logger.debug(f"Failed to deliver macOS desktop notification: {e}")

    async def notify(self, title: str, message: str, subtitle: str = "Coursera Agent"):
        """Asynchronously dispatch notification without blocking the event loop."""
        if not self.config.enabled or not self.is_macos:
            return

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self.notify_sync, title, message, subtitle)

    async def on_start(self, course_name: str):
        if self.config.on_start:
            await self.notify("Course Agent Started", f"Processing: {course_name}")

    async def on_course_opened(self, course_title: str):
        await self.notify("Course Opened", course_title)

    async def on_module_completed(self, module_title: str):
        await self.notify("Module Completed", f"{module_title} completed.")

    async def on_assessment(self, assessment_title: str):
        if self.config.on_assessment:
            await self.notify("Graded Assessment Detected", f"User review required for: {assessment_title}")

    async def on_disagreement(self, question_num: int):
        await self.notify("AI Disagreement Detected", f"Models disagreed on Question #{question_num}.")

    async def on_error(self, error_message: str):
        if self.config.on_error:
            await self.notify("Coursera Agent Error", error_message[:60])

    async def on_completion(self, course_title: str):
        if self.config.on_completion:
            await self.notify("Course Complete!", f"Congratulations on completing {course_title}!")

    async def on_certificate(self, course_title: str):
        if self.config.on_certificate:
            await self.notify("🎓 Certificate Available", f"Certificate is ready for {course_title}!")
