"""Course completion and certificate availability detection."""

from __future__ import annotations

import logging
from typing import Optional
from pydantic import BaseModel
from playwright.async_api import Page
from database.database import DatabaseSessionManager
from database.repositories import CourseRepository

logger = logging.getLogger(__name__)


class CompletionStatus(BaseModel):
    is_course_completed: bool = False
    is_certificate_available: bool = False
    certificate_url: Optional[str] = None
    completion_message: Optional[str] = None


class CompletionDetector:
    """Detects whether a course is completed and if a certificate is ready."""

    CERTIFICATE_LINK_SELECTORS = [
        'a[href*="/certificate/"]',
        'a[href*="/accomplishments/certificate/"]',
        'a:has-text("View Certificate")',
        'a:has-text("Download Certificate")',
        'button:has-text("View Certificate")',
        'a:has-text("Share Certificate")',
        '[data-testid="view-certificate-button"]',
    ]

    COMPLETION_BANNER_SELECTORS = [
        'div:has-text("Congratulations! You completed")',
        'div:has-text("Course Completed")',
        'div:has-text("You have successfully completed this course")',
        '[data-testid="course-completion-banner"]',
        '.completion-banner',
    ]

    def __init__(self, db_manager: DatabaseSessionManager):
        self.db_manager = db_manager

    async def check_completion(self, page: Page, course_id: str) -> CompletionStatus:
        """Inspect page for completion banners or certificate links."""
        status = CompletionStatus()

        # 1. Check for certificate link
        for sel in self.CERTIFICATE_LINK_SELECTORS:
            try:
                el = await page.query_selector(sel)
                if el and await el.is_visible():
                    status.is_certificate_available = True
                    status.is_course_completed = True
                    href = await el.get_attribute("href")
                    if href:
                        status.certificate_url = (
                            href if href.startswith("http") else f"https://www.coursera.org{href}"
                        )
                    logger.info(f"Certificate detected! URL: {status.certificate_url}")
                    break
            except Exception as e:
                logger.debug(f"Error checking certificate selector {sel}: {e}")

        # 2. Check for completion banners if certificate was not directly found
        if not status.is_course_completed:
            for sel in self.COMPLETION_BANNER_SELECTORS:
                try:
                    el = await page.query_selector(sel)
                    if el and await el.is_visible():
                        status.is_course_completed = True
                        status.completion_message = (await el.inner_text()).strip()
                        logger.info("Course completion banner detected.")
                        break
                except Exception as e:
                    logger.debug(f"Error checking completion banner {sel}: {e}")

        # Persist into database if completed
        if status.is_course_completed:
            async with self.db_manager.session() as session:
                repo = CourseRepository(session)
                await repo.mark_completed(
                    course_id=course_id,
                    certificate_available=status.is_certificate_available,
                )

        return status
