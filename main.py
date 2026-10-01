"""Coursera AI Course Automation Agent - Main Entry Point."""

from __future__ import annotations

import asyncio
import sys
import logging
from config import load_config
from utils.logger import setup_logging
from cli import (
    create_parser,
    handle_doctor,
    handle_test_gemini,
    handle_test_local,
    handle_test_ai,
    handle_status,
)
from automation.engine import AutomationEngine
from browser.manager import BrowserManager
from coursera.course import CourseManager
from coursera.modules import ModuleManager
from coursera.lessons import LessonManager
from database.database import DatabaseSessionManager


async def handle_discover(config, course_url: str):
    """Discover and display course outline tree without navigating through lessons."""
    print(f"\nDiscovering course outline: {course_url} ...\n")
    db_manager = DatabaseSessionManager(db_path=config.database.path)
    db_manager.init()
    await db_manager.create_all()

    browser_mgr = BrowserManager(config=config.browser)
    course_mgr = CourseManager(db_manager)
    mod_mgr = ModuleManager(db_manager)
    lesson_mgr = LessonManager(db_manager)

    try:
        page = await browser_mgr.start()
        course_info = await course_mgr.discover_course(page, course_url)
        modules = await mod_mgr.discover_modules(page, course_info.id)

        print(f"Course: {course_info.title}")
        print(f"Instructor: {course_info.instructor or 'Unknown'}")
        print("=" * 60)

        for m in modules:
            print(f"\n📁 Module {m.module_index}: {m.title}")
            lessons = await lesson_mgr.discover_lessons_in_page(page, course_info.id, m.id)
            for l in lessons:
                graded_tag = " [GRADED ⚠]" if l.is_graded else ""
                print(f"   ├── [{l.lesson_type.upper():<10}] {l.title}{graded_tag}")

        print("\n" + "=" * 60)
        print("Course outline discovery complete.")
    finally:
        await browser_mgr.close()
        await db_manager.close()


async def main_async():
    parser = create_parser()
    args = parser.parse_args()

    # Load configuration
    config = load_config(args.config)
    setup_logging(level=config.logging.level, log_file=config.logging.file)

    if args.doctor:
        await handle_doctor(config)
        return

    if args.test_gemini:
        await handle_test_gemini(config)
        return

    if args.test_local:
        await handle_test_local(config)
        return

    if args.test_ai:
        await handle_test_ai(config)
        return

    if args.status:
        await handle_status(config)
        return

    target_course = args.course or config.course.url
    if args.discover:
        if not target_course:
            print("Error: No course URL specified. Provide --course <URL> or configure config.yaml.")
            sys.exit(1)
        await handle_discover(config, target_course)
        return

    # Standard execution or resume
    engine = AutomationEngine(config)
    await engine.run(course_url=target_course, resume=args.resume)


def main():
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        print("\n[!] Execution interrupted by user. Exiting gracefully...")
        sys.exit(0)
    except Exception as e:
        print(f"\n[FATAL] {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
