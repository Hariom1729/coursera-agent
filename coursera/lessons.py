"""Lesson discovery, classification, and lifecycle tracking."""

from __future__ import annotations

import logging
import re
from typing import List, Optional
from pydantic import BaseModel
from playwright.async_api import Page
from database.database import DatabaseSessionManager
from database.repositories import LessonRepository

logger = logging.getLogger(__name__)


class LessonInfo(BaseModel):
    id: str
    course_id: str
    module_id: str
    title: str
    url: str
    lesson_type: str = "other"  # video, reading, quiz, assignment, discussion, other
    lesson_index: int = 0
    is_graded: bool = False
    status: str = "DISCOVERED"


class LessonManager:
    """Discovers, classifies, and updates lessons within modules."""

    LESSON_LINK_SELECTORS = [
        'a[href*="/lecture/"]',
        'a[href*="/supplement/"]',
        'a[href*="/quiz/"]',
        'a[href*="/exam/"]',
        'a[href*="/assignment/"]',
        'a[href*="/assignment-submission/"]',
        'a[href*="/item/"]',
        'li[data-testid*="item-card"] a',
        'div[data-testid*="item-card"] a',
    ]

    def __init__(self, db_manager: DatabaseSessionManager):
        self.db_manager = db_manager

    @staticmethod
    def classify_lesson_type(url: str, text: str, aria_label: str = "") -> tuple[str, bool]:
        """Classify lesson into (lesson_type, is_graded) from URL patterns and badge text."""
        combined = f"{url} {text} {aria_label}".lower()

        is_graded = False
        if "graded" in combined and "ungraded" not in combined and "practice" not in combined:
            is_graded = True
        elif "/exam/" in url or ("assignment" in combined and "practice" not in combined and "ungraded" not in combined):
            is_graded = True

        if "/lecture/" in url or "video" in combined:
            return "video", False
        elif "/supplement/" in url or "reading" in combined:
            return "reading", False
        elif "/quiz/" in url or "/assignment-submission/" in url or "quiz" in combined or "assignment" in combined:
            return "quiz", is_graded
        elif "/exam/" in url or "exam" in combined or "assessment" in combined:
            return "assessment", is_graded
        elif "/assignment/" in url or "assignment" in combined:
            return "assignment", is_graded
        elif "discussion" in combined:
            return "discussion", False
        else:
            return "reading" if "min" in combined else "other", is_graded

    async def discover_lessons_in_page(
        self,
        page: Page,
        course_id: str,
        module_id: str,
    ) -> List[LessonInfo]:
        """Discover and classify all lesson links currently displayed on the page."""
        logger.info(f"Scanning page for lessons in module {module_id}...")
        lessons: List[LessonInfo] = []
        seen_urls = set()

        links = await page.query_selector_all(", ".join(self.LESSON_LINK_SELECTORS))
        lesson_idx = 1

        for link in links:
            try:
                href = await link.get_attribute("href")
                if not href:
                    continue

                full_url = href if href.startswith("http") else f"https://www.coursera.org{href}"
                if full_url in seen_urls:
                    continue

                # Must be a learning item (lecture, supplement, quiz, exam, assignment, or item)
                if not re.search(r'/(?:lecture|supplement|quiz|exam|assignment|assignment-submission|item)/', full_url):
                    continue

                # Must belong to current course slug
                expected_slug = course_id.replace("course_", "")
                if "/learn/" in full_url:
                    slug_match = re.search(r'/learn/([^/?#]+)', full_url)
                    if slug_match and slug_match.group(1) != expected_slug:
                        continue
                elif expected_slug not in full_url:
                    continue

                seen_urls.add(full_url)

                text = (await link.inner_text()).strip()
                aria_label = (await link.get_attribute("aria-label")) or ""
                title_line = text.split("\n")[0].strip() or aria_label or f"Lesson {lesson_idx}"

                lesson_type, is_graded = self.classify_lesson_type(full_url, text, aria_label)

                # Extract stable lesson slug or identifier
                match = re.search(r'/(?:lecture|supplement|quiz|exam|assignment|assignment-submission|item)/([^/?#]+)', full_url)
                item_slug = match.group(1) if match else f"item_{lesson_idx}"
                lesson_id = f"{course_id}_{module_id}_{item_slug}"

                lesson = LessonInfo(
                    id=lesson_id,
                    course_id=course_id,
                    module_id=module_id,
                    title=title_line,
                    url=full_url,
                    lesson_type=lesson_type,
                    lesson_index=lesson_idx,
                    is_graded=is_graded,
                    status="DISCOVERED",
                )
                lessons.append(lesson)
                lesson_idx += 1
            except Exception as e:
                logger.debug(f"Error inspecting lesson link: {e}")

        # Persist discovered lessons into SQLite
        async with self.db_manager.session() as session:
            repo = LessonRepository(session)
            for l in lessons:
                await repo.upsert_lesson(
                    lesson_id=l.id,
                    course_id=l.course_id,
                    module_id=l.module_id,
                    title=l.title,
                    url=l.url,
                    lesson_type=l.lesson_type,
                    lesson_index=l.lesson_index,
                    is_graded=l.is_graded,
                )

        logger.info(f"Discovered {len(lessons)} lessons for module {module_id}.")
        return lessons

    async def update_status(self, lesson_id: str, status: str):
        """Update lesson state in database."""
        async with self.db_manager.session() as session:
            repo = LessonRepository(session)
            await repo.update_status(lesson_id, status)
            logger.debug(f"Updated lesson {lesson_id} status to {status}")
