"""Module and Week discovery and extraction for Coursera courses."""

from __future__ import annotations

import logging
import re
from typing import List, Optional
from pydantic import BaseModel
from playwright.async_api import Page
from database.database import DatabaseSessionManager
from database.repositories import ModuleRepository

logger = logging.getLogger(__name__)


class ModuleInfo(BaseModel):
    id: str
    course_id: str
    title: str
    module_index: int
    url: Optional[str] = None
    is_completed: bool = False

ModuleInfo.model_rebuild()


class ModuleManager:
    """Discovers, expands, and tracks modules/weeks in a Coursera course."""

    MODULE_SELECTORS = [
        'div[data-testid*="accordion-item"]',
        'div[data-track-component="outline_week"]',
        'div.cds-AccordionRoot-container',
        'div[class*="SyllabusWeek" i]',
        'div[class*="WeekCard" i]',
        'div.week-item',
        'a[href*="/home/week/"]',
        'a[href*="/home/module/"]',
    ]

    EXPAND_BUTTON_SELECTORS = [
        'main div[class*="accordion" i] button[aria-expanded="false"]',
        'main div[data-testid*="accordion"] button[aria-expanded="false"]',
        'div[class*="Syllabus" i] button[aria-expanded="false"]',
        'button:has-text("Show more")',
        'button:has-text("View all")',
    ]

    def __init__(self, db_manager: DatabaseSessionManager):
        self.db_manager = db_manager

    async def expand_all_accordions(self, page: Page):
        """Click on collapsed content accordions to reveal full syllabus items."""
        for selector in self.EXPAND_BUTTON_SELECTORS:
            try:
                buttons = await page.query_selector_all(selector)
                for btn in buttons[:8]:  # Limit to avoid hanging on non-content menus
                    aria_label = (await btn.get_attribute("aria-label") or "").lower()
                    btn_text = (await btn.inner_text() or "").lower()
                    # Skip navigation, help, profile, and notification popups
                    if any(x in aria_label or x in btn_text for x in ["help", "notification", "account", "profile", "feedback"]):
                        continue
                    if await btn.is_visible():
                        await btn.click()
                        await page.wait_for_timeout(250)
            except Exception as e:
                logger.debug(f"Non-fatal error expanding accordion: {e}")

    async def discover_modules(self, page: Page, course_id: str) -> List[ModuleInfo]:
        """Inspect page structure to discover all modules/weeks."""
        logger.info("Discovering course modules and weeks...")
        slug = course_id.replace("course_", "")

        modules: List[ModuleInfo] = []
        modules_by_index: dict[int, ModuleInfo] = {}

        # Strategy 1: Sidebar & navigation elements mentioning Module/Week
        sidebar_elems = await page.query_selector_all(
            'nav a, nav button, aside a, aside button, '
            'div[class*="sidebar" i] a, div[class*="sidebar" i] button, '
            'div[class*="navigation" i] a, div[class*="navigation" i] button, '
            'div[role="navigation"] a, div[role="navigation"] button, '
            'a[href*="/week/"], a[href*="/module/"], '
            'button:has-text("Module"), a:has-text("Module"), '
            'button:has-text("Week"), a:has-text("Week")'
        )
        for elem in sidebar_elems:
            try:
                text = (await elem.inner_text()).strip()
                if not text:
                    continue
                first_line = text.split("\n")[0].strip()
                match = re.search(r'\b(?:Module|Week)\s*(\d+)\b', first_line, re.IGNORECASE)
                if match:
                    idx = int(match.group(1))
                    if idx in modules_by_index:
                        continue
                    href = await elem.get_attribute("href")
                    full_url = None
                    if href:
                        full_url = href if href.startswith("http") else f"https://www.coursera.org{href}"
                    else:
                        full_url = f"https://www.coursera.org/learn/{slug}/home/week/{idx}"

                    mod_id = f"{course_id}_mod_{idx}"
                    modules_by_index[idx] = ModuleInfo(
                        id=mod_id,
                        course_id=course_id,
                        title=f"Module {idx}",
                        module_index=idx,
                        url=full_url,
                    )
            except Exception as e:
                logger.debug(f"Error inspecting module element: {e}")

        if modules_by_index:
            modules = [modules_by_index[i] for i in sorted(modules_by_index.keys())]

        # Strategy 2: If sidebar had no numbered modules, try expanding syllabus accordions
        if not modules:
            await self.expand_all_accordions(page)
            found_titles = set()
            faq_patterns = [
                r"when will i have access",
                r"refund policy",
                r"frequently asked questions",
                r"financial aid",
                r"how much does",
                r"can i earn",
            ]
            for selector in self.MODULE_SELECTORS:
                elements = await page.query_selector_all(selector)
                if elements and len(elements) > 1:
                    idx = 1
                    for elem in elements:
                        heading = await elem.query_selector('h2, h3, h4, button, [class*="title" i]')
                        raw_title = await heading.inner_text() if heading else await elem.inner_text()
                        first_line = raw_title.strip().split("\n")[0].strip()
                        if any(re.search(p, first_line.lower()) for p in faq_patterns):
                            continue
                        if first_line and first_line not in found_titles and len(first_line) > 2:
                            found_titles.add(first_line)
                            mod_id = f"{course_id}_mod_{idx}"
                            modules.append(
                                ModuleInfo(
                                    id=mod_id,
                                    course_id=course_id,
                                    title=first_line,
                                    module_index=idx,
                                    url=f"https://www.coursera.org/learn/{slug}/home/week/{idx}",
                                )
                            )
                            idx += 1
                    if modules:
                        break

        # Strategy 3: Default fallback if Coursera displays single-page outline
        if not modules:
            logger.info("Single module / standard structure assumed.")
            modules.append(
                ModuleInfo(
                    id=f"{course_id}_mod_1",
                    course_id=course_id,
                    title="Module 1",
                    module_index=1,
                    url=f"https://www.coursera.org/learn/{slug}/home/week/1",
                )
            )

        # Persist modules into SQLite
        async with self.db_manager.session() as session:
            repo = ModuleRepository(session)
            for m in modules:
                await repo.upsert_module(
                    module_id=m.id,
                    course_id=m.course_id,
                    title=m.title,
                    module_index=m.module_index,
                )

        logger.info(f"Discovered {len(modules)} course modules.")
        return modules
