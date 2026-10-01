"""Central Automation Engine orchestrating course navigation, AI analysis, and safety boundaries."""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Optional, List
from playwright.async_api import Page

from config import AppConfig
from database.database import DatabaseSessionManager
from database.repositories import (
    CourseRepository,
    ModuleRepository,
    LessonRepository,
    AutomationRunRepository,
)
from browser.manager import BrowserManager
from browser.session import SessionManager
from browser.recovery import BrowserRecovery
from coursera.course import CourseManager, CourseInfo
from coursera.modules import ModuleManager, ModuleInfo
from coursera.lessons import LessonManager, LessonInfo
from coursera.navigation import NavigationManager
from coursera.detectors import ContentDetector, PageContentType
from coursera.completion import CompletionDetector
from assessments.detector import AssessmentDetector
from assessments.extractor import AssessmentExtractor
from assessments.parser import AssessmentParser
from assessments.analyzer import AssessmentAnalyzer
from assessments.session import AssessmentSession
from assessments.solver import AssessmentSolver
from ai.router import AIRouter
from ai.cache import AICache
from ai.prompts import READING_SUMMARY_PROMPT, PRACTICE_ACTIVITY_PROMPT
from ai.schemas import GeneralAnalysis
from automation.state_machine import AutomationStateMachine, AutomationState
from automation.scheduler import AutomationScheduler
from notifications.macos import MacOSNotifier
from notifications.terminal import TerminalNotifier
from utils.screenshots import ScreenshotManager

logger = logging.getLogger(__name__)


class AutomationEngine:
    """Production-grade automation engine for taking Coursera courses with AI assistance."""

    def __init__(self, config: AppConfig):
        self.config = config
        self.run_id = f"run_{uuid.uuid4().hex[:10]}"

        # Database and Storage
        self.db_manager = DatabaseSessionManager(db_path=config.database.path)
        self.db_manager.init()
        self.cache = AICache(self.db_manager)

        # AI Router
        self.ai_router = AIRouter(config=config.ai, cache=self.cache)

        # Browser and Session
        self.browser_manager = BrowserManager(config=config.browser)
        self.session_manager = SessionManager()
        self.browser_recovery = BrowserRecovery(self.browser_manager)

        # Coursera Domain Services
        self.course_manager = CourseManager(self.db_manager)
        self.module_manager = ModuleManager(self.db_manager)
        self.lesson_manager = LessonManager(self.db_manager)
        self.navigation_manager = NavigationManager()
        self.content_detector = ContentDetector()
        self.completion_detector = CompletionDetector(self.db_manager)

        # Assessments Services
        self.assessment_detector = AssessmentDetector()
        self.assessment_extractor = AssessmentExtractor(AssessmentParser())
        self.assessment_analyzer = AssessmentAnalyzer(self.ai_router, self.db_manager)
        self.assessment_session = AssessmentSession()
        self.assessment_solver = AssessmentSolver()

        # State and Utilities
        self.state_machine = AutomationStateMachine(self.run_id, self.db_manager)
        self.scheduler = AutomationScheduler(base_delay=config.automation.retry_delay)
        self.macos_notifier = MacOSNotifier(config.notifications)
        self.terminal_notifier = TerminalNotifier()
        self.screenshot_manager = ScreenshotManager()

    async def initialize(self):
        """Prepare database tables and directories."""
        await self.db_manager.create_all()
        self.screenshot_manager.init_directories()

    async def run(self, course_url: Optional[str] = None, resume: bool = False):
        """Main automation execution loop."""
        await self.initialize()

        target_url = course_url or self.config.course.url
        if not target_url:
            raise ValueError("No course URL specified. Set course.url in config.yaml or pass --course <URL>.")

        # Show startup banner
        self.terminal_notifier.render_startup_banner(
            ai_provider=self.config.ai.primary_provider,
            local_model=self.config.ai.local.model,
        )

        page: Optional[Page] = None
        try:
            # 1. State: START
            async with self.db_manager.session() as session:
                run_repo = AutomationRunRepository(session)
                await run_repo.start_run(self.run_id, target_url)

            await self.macos_notifier.on_start(self.config.course.name or target_url)

            # 2. State: LOAD_SESSION
            await self.state_machine.transition_to(AutomationState.LOAD_SESSION)
            page = await self.browser_manager.start()
            await self.session_manager.ensure_authenticated(page)

            # 3. State: OPEN_COURSE
            await self.state_machine.transition_to(AutomationState.OPEN_COURSE)
            course_info = await self.course_manager.discover_course(page, target_url)
            await self.macos_notifier.on_course_opened(course_info.title)

            # 4. State: DISCOVER_STRUCTURE
            await self.state_machine.transition_to(AutomationState.DISCOVER_STRUCTURE)
            modules = await self.module_manager.discover_modules(page, course_info.id)
            if not modules:
                logger.warning("No modules detected; creating default container module.")
                modules = [ModuleInfo(id=f"{course_info.id}_mod_1", course_id=course_info.id, title="Module 1", module_index=1)]

            # 5. State: LOAD_PROGRESS / RESUME
            await self.state_machine.transition_to(AutomationState.LOAD_PROGRESS)
            completed_lesson_ids = set()

            if resume or self.config.automation.auto_resume:
                async with self.db_manager.session() as session:
                    l_repo = LessonRepository(session)
                    all_existing = await l_repo.get_all_for_course(course_info.id)
                    completed_lesson_ids = {l.id for l in all_existing if l.status == "COMPLETED"}
                    if completed_lesson_ids:
                        logger.info(f"Resume state found: {len(completed_lesson_ids)} lessons already completed.")

            # 6. Process Modules and Lessons
            total_modules = len(modules)
            total_lessons_found = 0
            for mod_idx, mod in enumerate(modules, start=1):
                await self.state_machine.transition_to(AutomationState.PROCESS_MODULE, module_id=mod.id)
                logger.info(f"--- Entering Module {mod_idx}/{total_modules}: {mod.title} ---")

                # Navigate directly to the module/week page in learning view
                target_url = mod.url
                if not target_url:
                    target_url = f"https://www.coursera.org/learn/{course_info.slug}/home/module/{mod.module_index}"

                try:
                    logger.info(f"Opening module view at: {target_url}")
                    await page.goto(target_url, wait_until="domcontentloaded", timeout=20000)
                    await self.navigation_manager.wait_for_stability(page, wait_seconds=2.5)
                except Exception as e:
                    logger.debug(f"Direct module navigation fallback: {e}")

                # Discover lessons in this module view
                lessons = await self.lesson_manager.discover_lessons_in_page(page, course_info.id, mod.id)
                if not lessons:
                    # Fallback to week URL if module URL didn't have lessons
                    week_fallback = f"https://www.coursera.org/learn/{course_info.slug}/home/week/{mod.module_index}"
                    if page.url != week_fallback:
                        try:
                            logger.info(f"Trying alternative week URL: {week_fallback}")
                            await page.goto(week_fallback, wait_until="domcontentloaded", timeout=20000)
                            await self.navigation_manager.wait_for_stability(page, wait_seconds=2.5)
                            lessons = await self.lesson_manager.discover_lessons_in_page(page, course_info.id, mod.id)
                        except Exception as e:
                            logger.debug(f"Week fallback navigation error: {e}")

                if not lessons:
                    logger.info("Direct lesson links not on main page. Attempting to click module link...")
                    try:
                        mod_link = await page.query_selector(
                            f'a[href*="/module/{mod.module_index}"], a[href*="/week/{mod.module_index}"], '
                            f'a:has-text("{mod.title}"), button:has-text("{mod.title}")'
                        )
                        if mod_link and await mod_link.is_visible():
                            await mod_link.click()
                            await self.navigation_manager.wait_for_stability(page, wait_seconds=2.5)
                            lessons = await self.lesson_manager.discover_lessons_in_page(page, course_info.id, mod.id)
                    except Exception as e:
                        logger.debug(f"Could not click module header: {e}")

                total_lessons_found += len(lessons)

                for l_idx, lesson in enumerate(lessons, start=1):
                    if lesson.id in completed_lesson_ids:
                        logger.info(f"Skipping already completed lesson: {lesson.title}")
                        continue

                    # Process individual lesson
                    await self._process_single_lesson(
                        page=page,
                        course_info=course_info,
                        module=mod,
                        lesson=lesson,
                        module_num=mod_idx,
                        total_modules=total_modules,
                        lesson_progress_pct=(l_idx / max(1, len(lessons))) * 100.0,
                    )

                    completed_lesson_ids.add(lesson.id)

                await self.macos_notifier.on_module_completed(mod.title)
                async with self.db_manager.session() as session:
                    m_repo = ModuleRepository(session)
                    await m_repo.mark_completed(mod.id)

            if total_lessons_found == 0:
                print("\n" + "=" * 65)
                print(" [!] NO ACTIVE LESSONS DISCOVERED")
                print("=" * 65)
                print(f"Course: {course_info.title}")
                print("No lecture, reading, or quiz items were accessible on this page.")
                print("Possible reasons:")
                print("1. Your account is not yet enrolled in this course (click 'Enroll for free' in browser).")
                print("2. You need to log in to Coursera with the account that has active access.")
                print("=" * 65 + "\n")
                await self.state_machine.transition_to(AutomationState.DONE, status="PAUSED")
                return

            # 7. State: COURSE_COMPLETE & CERTIFICATE_CHECK
            await self.state_machine.transition_to(AutomationState.COURSE_COMPLETE)
            comp_status = await self.completion_detector.check_completion(page, course_info.id)

            await self.state_machine.transition_to(AutomationState.CERTIFICATE_CHECK)
            if comp_status.is_course_completed:
                logger.info("🎓 COURSE COMPLETION CONFIRMED!")
                await self.macos_notifier.on_completion(course_info.title)

                if comp_status.is_certificate_available:
                    print("\n" + "=" * 60)
                    print("  🎓 CERTIFICATE DETECTED!")
                    print(f"  Course     : {course_info.title}")
                    print(f"  Certificate: Available at {comp_status.certificate_url or 'Course Dashboard'}")
                    print("=" * 60 + "\n")
                    await self.macos_notifier.on_certificate(course_info.title)

            # 8. State: DONE
            await self.state_machine.transition_to(AutomationState.DONE, status="COMPLETED")
            print("\n[✓] Automation completed all available course lessons successfully.\n")

        except Exception as e:
            logger.error(f"Fatal error during course automation run: {e}", exc_info=True)
            if page:
                await self.screenshot_manager.capture(page, "fatal_error", category="errors")
            await self.state_machine.transition_to(AutomationState.ERROR, status="FAILED")
            await self.macos_notifier.on_error(str(e))
            raise
        finally:
            await self.browser_manager.close()
            await self.db_manager.close()

    async def _process_single_lesson(
        self,
        page: Page,
        course_info: CourseInfo,
        module: ModuleInfo,
        lesson: LessonInfo,
        module_num: int,
        total_modules: int,
        lesson_progress_pct: float,
    ):
        """Process one lesson with appropriate detection, AI analysis, and safety checks."""
        await self.state_machine.transition_to(
            AutomationState.PROCESS_LESSON,
            module_id=module.id,
            lesson_id=lesson.id,
        )

        self.terminal_notifier.render_lesson_card(
            module_num=module_num,
            total_modules=total_modules,
            lesson_title=lesson.title,
            lesson_type=lesson.lesson_type,
            progress_pct=lesson_progress_pct,
            ai_status="Engaged",
        )

        # Navigate to lesson
        nav_success = await self.navigation_manager.navigate_to_lesson(page, lesson.url)
        if not nav_success:
            logger.warning(f"Could not navigate to {lesson.url}; attempting recovery...")
            page = await self.browser_recovery.recover_page(lesson.url)

        # Detect real on-page content type
        content_type, conf = await self.content_detector.detect_page_type(page)
        logger.info(f"Page type detected: {content_type.value} (Confidence: {int(conf*100)}%)")

        # ---------------------------------------------------------
        # Case A: Graded Assessment
        # ---------------------------------------------------------
        if content_type == PageContentType.GRADED_ASSESSMENT or lesson.is_graded:
            logger.info("GRADED ASSESSMENT ENCOUNTERED. Processing assessment...")
            await self.screenshot_manager.capture(page, f"graded_{lesson.id}", category="assessments")
            await self.macos_notifier.on_assessment(lesson.title)

            # Prepare quiz (dismiss Honor Code modal, click Continue / Start / Resume)
            await self.assessment_solver.prepare_quiz(page)

            # Extract visible question information
            extracted = await self.assessment_extractor.extract_assessment(
                page=page,
                assessment_id=f"assess_{lesson.id}",
                title=lesson.title,
                is_graded=True,
            )

            # Perform AI analysis and cross-verification
            analysis_results = await self.assessment_analyzer.analyze_assessment(extracted)

            if self.config.automation.auto_submit_assessments:
                logger.info(f"Auto-submit enabled. Filling answers and submitting '{lesson.title}'...")
                self.assessment_session.render_review_screen(extracted, analysis_results)
                await self.assessment_solver.fill_and_submit(page, extracted, analysis_results)
                await self.screenshot_manager.capture(page, f"submitted_{lesson.id}", category="assessments")
                await self.scheduler.pace(3.0)
            else:
                # Pause automation and mandate human review
                await self.state_machine.transition_to(
                    AutomationState.WAIT_FOR_USER,
                    module_id=module.id,
                    lesson_id=lesson.id,
                )
                await self.assessment_session.wait_for_user_review(extracted, analysis_results)

        # ---------------------------------------------------------
        # Case B: Ungraded Practice Activity -> Educational Help
        # ---------------------------------------------------------
        elif content_type == PageContentType.PRACTICE_ACTIVITY:
            logger.info("Practice / ungraded activity detected. Generating educational guidance...")
            await self.assessment_solver.prepare_quiz(page)
            extracted = await self.assessment_extractor.extract_assessment(
                page=page,
                assessment_id=f"practice_{lesson.id}",
                title=lesson.title,
                is_graded=False,
            )
            if extracted.questions:
                analysis_results = await self.assessment_analyzer.analyze_assessment(extracted)
                if self.config.automation.auto_submit_assessments:
                    logger.info(f"Auto-submit enabled. Filling answers and submitting practice '{lesson.title}'...")
                    self.assessment_session.render_review_screen(extracted, analysis_results)
                    await self.assessment_solver.fill_and_submit(page, extracted, analysis_results)
                    await self.scheduler.pace(2.0)
                else:
                    # Output suggested explanations to terminal
                    self.assessment_session.render_review_screen(extracted, analysis_results)
                    await self.scheduler.pace(1.5)

        # ---------------------------------------------------------
        # Case C: Video Lesson -> Fast-Forward to End
        # ---------------------------------------------------------
        elif content_type == PageContentType.VIDEO:
            v_meta = await self.content_detector.extract_video_metadata(page)
            logger.info(f"Video detected. Duration: {v_meta.duration_text or 'Standard'}. Fast-forwarding to end...")
            await self.navigation_manager.fast_forward_video_to_end(page)
            await self.scheduler.pace(2.0)
            await self.navigation_manager.mark_current_lesson_completed_if_available(page)

        # ---------------------------------------------------------
        # Case D: Reading Lesson
        # ---------------------------------------------------------
        elif content_type == PageContentType.READING:
            reading = await self.content_detector.extract_reading_content(page)
            word_count = len(reading.full_text.split())
            logger.info(f"Reading extracted: '{reading.title}' ({word_count} words).")

            # Quick educational summary using AI if content exists
            if word_count > 60:
                try:
                    summary_prompt = READING_SUMMARY_PROMPT.format(reading_content=reading.full_text[:1000])
                    summary = await asyncio.wait_for(
                        self.ai_router.analyze(
                            prompt=summary_prompt,
                            schema=GeneralAnalysis,
                            use_cache=True,
                        ),
                        timeout=8.0,
                    )
                    if hasattr(summary, "understanding"):
                        logger.info(f"AI Lesson Summary: {summary.understanding[:120]}...")
                except Exception as ai_err:
                    logger.debug(f"AI reading summary skipped: {ai_err}")

            await self.scheduler.simulated_reading_delay(word_count)
            await self.navigation_manager.mark_current_lesson_completed_if_available(page)

        # Mark lesson completed in SQLite
        await self.state_machine.transition_to(AutomationState.MARK_COMPLETE)
        async with self.db_manager.session() as session:
            l_repo = LessonRepository(session)
            await l_repo.record_progress(
                course_id=course_info.id,
                module_id=module.id,
                lesson_id=lesson.id,
                status="COMPLETED",
            )

        # Move to next
        await self.state_machine.transition_to(AutomationState.NEXT_LESSON)
        await self.navigation_manager.click_next(page)
        await self.scheduler.pace(1.0)
