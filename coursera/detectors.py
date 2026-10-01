"""Content detectors for Coursera page types (videos, readings, practice, graded assessments)."""

from __future__ import annotations

import logging
import re
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel
from playwright.async_api import Page

logger = logging.getLogger(__name__)


class PageContentType(str, Enum):
    VIDEO = "video"
    READING = "reading"
    PRACTICE_ACTIVITY = "practice"
    GRADED_ASSESSMENT = "graded_assessment"
    ASSIGNMENT = "assignment"
    DISCUSSION = "discussion"
    UNKNOWN = "unknown"


class VideoMetadata(BaseModel):
    video_detected: bool = False
    duration_text: Optional[str] = None
    progress_text: Optional[str] = None
    completion_state: str = "INCOMPLETE"


class ReadingContent(BaseModel):
    title: str = ""
    headings: List[str] = []
    paragraphs: List[str] = []
    code_snippets: List[str] = []
    full_text: str = ""


class ContentDetector:
    """Inspects live Coursera DOM to determine page type and extract relevant content."""

    VIDEO_SELECTORS = [
        "video",
        ".video-js",
        'div[data-testid="video-player"]',
        'div[aria-label*="video player" i]',
        ".c-video-player",
        'iframe[src*="youtube"]',
    ]

    ASSESSMENT_SELECTORS = [
        'div[data-testid="assessment-app"]',
        'div[data-testid="quiz-attempt"]',
        'form[class*="quiz" i]',
        'div[class*="AssessmentForm" i]',
        'div[class*="QuizPrompt" i]',
        'div[aria-label*="Quiz" i]',
    ]

    GRADED_BADGE_PATTERNS = [
        r"\bgraded\s+quiz\b",
        r"\bgraded\s+assessment\b",
        r"\bgraded\s+assignment\b",
        r"\bcounts\s+towards\s+your\s+grade\b",
        r"\bworth\s+\d+\s+points?\b",
        r"\bgraded\b",
    ]

    UNGRADED_BADGE_PATTERNS = [
        r"\bpractice\s+quiz\b",
        r"\bungraded\b",
        r"\bpractice\s+exercise\b",
        r"\bdoes\s+not\s+count\b",
    ]

    READING_SELECTORS = [
        'div[data-testid="reading-content"]',
        'div.cds-119',
        'div.reading-content',
        'div[class*="ReadingContent" i]',
        'div[class*="ItemContent" i]',
        'article',
        'main',
    ]

    async def detect_page_type(self, page: Page) -> tuple[PageContentType, float]:
        """Detect current page content type with confidence score."""
        current_url = page.url.lower()

        # 1. URL pattern hints
        if "/lecture/" in current_url:
            return PageContentType.VIDEO, 0.95
        if "/supplement/" in current_url:
            return PageContentType.READING, 0.95

        # 2. Check for Video Player
        for sel in self.VIDEO_SELECTORS:
            elem = await page.query_selector(sel)
            if elem and await elem.is_visible():
                return PageContentType.VIDEO, 0.90

        # 3. Check for Quiz or Assessment
        for sel in self.ASSESSMENT_SELECTORS:
            elem = await page.query_selector(sel)
            if elem and await elem.is_visible():
                is_graded = await self.is_page_graded(page)
                if is_graded:
                    return PageContentType.GRADED_ASSESSMENT, 0.92
                return PageContentType.PRACTICE_ACTIVITY, 0.88

        # 4. Check for Reading Elements
        headings = await page.query_selector_all("h1, h2, h3, article, p")
        if len(headings) >= 3:
            is_graded = await self.is_page_graded(page)
            if is_graded:
                return PageContentType.GRADED_ASSESSMENT, 0.75
            return PageContentType.READING, 0.80

        return PageContentType.UNKNOWN, 0.40

    async def is_page_graded(self, page: Page) -> bool:
        """Analyze page text and metadata to determine if this is a graded assessment."""
        url = page.url.lower()
        if "/exam/" in url or "/assignment/" in url:
            return True

        body_text = await page.evaluate("() => document.body ? document.body.innerText.toLowerCase() : ''")

        # Explicit ungraded / practice phrases take precedence
        for pattern in self.UNGRADED_BADGE_PATTERNS:
            if re.search(pattern, body_text):
                return False

        # Check graded markers
        for pattern in self.GRADED_BADGE_PATTERNS:
            if re.search(pattern, body_text):
                return True

        return False

    async def extract_video_metadata(self, page: Page) -> VideoMetadata:
        """Inspect video player elements for duration and state."""
        meta = VideoMetadata()
        for sel in self.VIDEO_SELECTORS:
            video_el = await page.query_selector(sel)
            if video_el:
                meta.video_detected = True
                break

        # Check for duration displays
        duration_el = await page.query_selector('[class*="duration" i], [aria-label*="duration" i]')
        if duration_el and await duration_el.is_visible():
            meta.duration_text = (await duration_el.inner_text()).strip()

        return meta

    async def extract_reading_content(self, page: Page) -> ReadingContent:
        """Extract sanitized textual content, headings, and code from reading pages."""
        content = ReadingContent()

        # Title
        title_el = await page.query_selector("h1")
        if title_el:
            content.title = (await title_el.inner_text()).strip()

        # Headings
        headings = await page.query_selector_all("h2, h3")
        for h in headings:
            text = (await h.inner_text()).strip()
            if text:
                content.headings.append(text)

        # Paragraphs
        paragraphs = await page.query_selector_all("p")
        for p in paragraphs:
            text = (await p.inner_text()).strip()
            if text and len(text) > 15:
                content.paragraphs.append(text)

        # Code snippets
        code_blocks = await page.query_selector_all("pre, code")
        for c in code_blocks:
            code_text = (await c.inner_text()).strip()
            if code_text and len(code_text) > 5:
                content.code_snippets.append(code_text)

        content.full_text = f"{content.title}\n\n" + "\n\n".join(content.paragraphs)
        return content
