"""Course discovery and metadata extraction."""

from __future__ import annotations

import logging
import re
from typing import Optional
from pydantic import BaseModel
from playwright.async_api import Page
from database.database import DatabaseSessionManager
from database.repositories import CourseRepository

logger = logging.getLogger(__name__)


class CourseInfo(BaseModel):
    id: str
    title: str
    slug: str
    url: str
    instructor: Optional[str] = None


class CourseManager:
    """Manages course navigation, discovery, and metadata extraction."""

    COURSE_TITLE_SELECTORS = [
        '[data-e2e="course-title"]',
        'h1[data-e2e="course-title"]',
        'h1.cds-119',
        'h1.banner-title',
        'h1[class*="course-title" i]',
        'h1',
    ]

    INSTRUCTOR_SELECTORS = [
        '[data-e2e="instructor-name"]',
        '[data-testid="instructor-name"]',
        '.instructor-name',
        'div[class*="instructor" i] p',
        'div[class*="instructor" i] span',
    ]

    def __init__(self, db_manager: DatabaseSessionManager):
        self.db_manager = db_manager

    @staticmethod
    def extract_slug_from_url(url: str) -> str:
        """Extract course slug from URL, e.g. /learn/python-basics -> python-basics."""
        match = re.search(r'/learn/([^/?#]+)', url)
        if match:
            return match.group(1)
        # Fallback to sanitized URL string
        sanitized = re.sub(r'[^a-zA-Z0-9_-]', '_', url.replace('https://www.coursera.org/', ''))
        return sanitized[:50] or "unknown_course"

    async def discover_course(self, page: Page, course_url: str) -> CourseInfo:
        """Navigate to course URL and extract title, slug, and instructor."""
        logger.info(f"Opening course URL: {course_url}")
        await page.goto(course_url, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(3000)

        slug = self.extract_slug_from_url(course_url)
        course_id = f"course_{slug}"

        # 1. Extract Title
        title = ""
        for selector in self.COURSE_TITLE_SELECTORS:
            elem = await page.query_selector(selector)
            if elem and await elem.is_visible():
                text = (await elem.inner_text()).strip()
                if text and len(text) > 3 and not text.lower().startswith("coursera"):
                    title = text
                    break

        if not title:
            # Fallback to document title
            doc_title = await page.title()
            title = doc_title.split("|")[0].strip() or f"Course {slug}"

        # 2. Extract Instructor
        instructor = None
        for selector in self.INSTRUCTOR_SELECTORS:
            elem = await page.query_selector(selector)
            if elem and await elem.is_visible():
                inst_text = (await elem.inner_text()).strip()
                if inst_text:
                    instructor = inst_text
                    break

        course_info = CourseInfo(
            id=course_id,
            title=title,
            slug=slug,
            url=course_url,
            instructor=instructor,
        )

        # 3. Persist into SQLite
        async with self.db_manager.session() as session:
            repo = CourseRepository(session)
            await repo.upsert_course(
                course_id=course_info.id,
                title=course_info.title,
                url=course_info.url,
                slug=course_info.slug,
                instructor=course_info.instructor,
            )

        logger.info(f"Course discovered: '{course_info.title}' (Instructor: {course_info.instructor or 'Unknown'})")

        # 4. If on promotional/landing page, transition into the enrolled learning area
        current_url = page.url.lower()
        if "/home/" not in current_url and "/lecture/" not in current_url:
            # Check if enrollment is required
            enroll_button = await page.query_selector(
                'button:has-text("Enroll for free"), a:has-text("Enroll for free"), button:has-text("Enroll now"), a:has-text("Enroll now")'
            )
            if enroll_button and await enroll_button.is_visible():
                print("\n" + "=" * 65)
                print(" [!] COURSE ENROLLMENT REQUIRED")
                print("=" * 65)
                print(f"Course: {course_info.title}")
                print("You are logged in, but not yet enrolled in this course.")
                print("Please click 'Enroll for free' (or 'Audit') in the open browser window.")
                print("Waiting for enrollment so that real lectures and quizzes unlock...")
                print("=" * 65 + "\n")

                for _ in range(40):
                    await page.wait_for_timeout(3000)
                    try:
                        curr = page.url.lower()
                        if "/home/" in curr or "/lecture/" in curr or "/supplement/" in curr:
                            print("\n[✓] Course access detected! Proceeding...\n")
                            break
                        go_to = await page.query_selector('a[href*="/home/welcome"], a:has-text("Go to Course"), a:has-text("Go To Course"), a:has-text("Resume")')
                        if go_to and await go_to.is_visible():
                            await go_to.click()
                            await page.wait_for_timeout(3000)
                            break
                    except Exception:
                        pass

            go_to_course = await page.query_selector(
                'a[href*="/home/welcome"], a:has-text("Go to Course"), a:has-text("Go To Course"), a:has-text("Resume"), a:has-text("Start Learning"), button:has-text("Go to course")'
            )
            if go_to_course and await go_to_course.is_visible():
                logger.info("Found 'Go to Course' / 'Resume' button. Entering learning area...")
                try:
                    await go_to_course.click()
                    await page.wait_for_timeout(3000)
                except Exception as e:
                    logger.debug(f"Could not click 'Go to Course': {e}")
            else:
                # Direct navigation attempt into enrolled home
                welcome_url = f"https://www.coursera.org/learn/{slug}/home/welcome"
                logger.info(f"Navigating directly to enrolled syllabus area: {welcome_url}")
                try:
                    await page.goto(welcome_url, wait_until="domcontentloaded", timeout=20000)
                    await page.wait_for_timeout(2500)
                except Exception as e:
                    logger.debug(f"Direct welcome navigation attempt: {e}")

        return course_info
