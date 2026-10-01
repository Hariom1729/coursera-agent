"""Command Line Interface (CLI) parser and command handlers."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from typing import Optional
from config import load_config, AppConfig
from utils.logger import setup_logging
from utils.health import SystemDoctor
from database.database import DatabaseSessionManager
from database.repositories import (
    CourseRepository,
    ModuleRepository,
    LessonRepository,
    AutomationRunRepository,
)
from ai.gemini import GeminiProvider
from ai.local_llm import LocalLLMClient
from ai.router import AIRouter
from ai.schemas import QuestionAnalysis


def create_parser() -> argparse.ArgumentParser:
    """Create command-line argument parser."""
    parser = argparse.ArgumentParser(
        prog="coursera-agent",
        description="Production-Grade Coursera AI Course Automation Agent",
    )
    parser.add_argument(
        "--course",
        type=str,
        default=None,
        help="Coursera course URL (overrides config.yaml)",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume course from the last recorded state in SQLite",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Display current progress and database state for courses",
    )
    parser.add_argument(
        "--doctor",
        action="store_true",
        help="Run comprehensive environment and connectivity diagnostics",
    )
    parser.add_argument(
        "--test-ai",
        action="store_true",
        help="Test dual AI routing with a sample question",
    )
    parser.add_argument(
        "--test-gemini",
        action="store_true",
        help="Test Google Gemini API connectivity and response",
    )
    parser.add_argument(
        "--test-local",
        action="store_true",
        help="Inspect local LM Studio OpenAI-compatible endpoint",
    )
    parser.add_argument(
        "--discover",
        action="store_true",
        help="Discover and display course outline tree without navigating lessons",
    )
    parser.add_argument(
        "--config",
        type=str,
        default="config.yaml",
        help="Path to configuration file",
    )
    return parser


async def handle_doctor(config: AppConfig):
    """Execute system health checks."""
    doctor = SystemDoctor(config)
    results = await doctor.check_all()
    doctor.print_report(results)


async def handle_test_gemini(config: AppConfig):
    """Test Google Gemini API connectivity."""
    print("Testing Gemini...")
    key = config.ai.gemini.api_key
    if not key:
        print("✗ GEMINI_API_KEY environment variable is not set.")
        print("Set it via: export GEMINI_API_KEY=\"your_key\" or add to .env file.")
        return

    # Check key exists without printing it
    masked_key = f"{key[:4]}...{key[-4:]}" if len(key) > 8 else "***"
    print("✓ API key found")

    provider = GeminiProvider(api_key=key, model_name=config.ai.gemini.model)
    health = await provider.health_check()
    if health["available"]:
        print("✓ Gemini connection successful")
        print(f"✓ Model response received: '{health.get('response', '')}'")
        print("\nGemini is ready.")
    else:
        print(f"✗ Gemini error: {health.get('message', 'Unknown failure')}")


async def handle_test_local(config: AppConfig):
    """Test LM Studio OpenAI-compatible endpoint."""
    print(f"Checking LM Studio at {config.ai.local.base_url}...")
    client = LocalLLMClient(base_url=config.ai.local.base_url, default_model=config.ai.local.model)
    health = await client.health_check()
    if health["available"]:
        print("LM Studio detected.\n")
        print("Available models:")
        for m in health.get("models", []):
            print(f" - {m}")
        print(f"\nActive model: {health.get('selected_model')}")
    else:
        print(f"✗ {health.get('message', 'Cannot reach LM Studio')}")
        print("Make sure LM Studio local server is started on port 1234.")


async def handle_test_ai(config: AppConfig):
    """Test dual-model AI routing with a sample question."""
    print("Testing AI router and dual-model verification...")
    router = AIRouter(config=config.ai)
    sample_question = """
Question 1: What is the primary purpose of Python's 'def' keyword?
Options:
  A. To define a variable
  B. To define a function
  C. To import a module
  D. To execute a loop
"""
    try:
        analysis, comp = await router.analyze_and_verify_question(sample_question)
        print("\nAnalysis Result:")
        print(f"  Candidate Answer : {analysis.candidate_answer}")
        print(f"  Confidence       : {int(analysis.confidence * 100)}%")
        print(f"  Reasoning        : {analysis.reasoning[:200]}...")
        print(f"  Models Agree     : {comp.agreement}")
        print("\nAI Router is operational.")
    except Exception as e:
        print(f"✗ AI Router test failed: {e}")


async def handle_status(config: AppConfig):
    """Display SQLite course progress status."""
    db_mgr = DatabaseSessionManager(db_path=config.database.path)
    db_mgr.init()
    await db_mgr.create_all()

    async with db_mgr.session() as session:
        c_repo = CourseRepository(session)
        m_repo = ModuleRepository(session)
        l_repo = LessonRepository(session)
        r_repo = AutomationRunRepository(session)

        latest_run = await r_repo.get_latest_run()
        print("\n==================================")
        print(" Coursera Agent Progress Status")
        print("==================================")
        if latest_run:
            print(f"Latest Run ID : {latest_run.id}")
            print(f"State         : {latest_run.current_state}")
            print(f"Status        : {latest_run.status}")
            print(f"Started At    : {latest_run.started_at}")
        else:
            print("No previous automation runs recorded.")

        print("----------------------------------")
        target_course = config.course.url
        course = await c_repo.get_by_url(target_course)
        if course:
            print(f"Course Title  : {course.title}")
            print(f"Completed     : {'YES ✓' if course.is_completed else 'NO'}")
            print(f"Certificate   : {'AVAILABLE 🎓' if course.certificate_available else 'Not ready'}")

            modules = await m_repo.get_modules(course.id)
            print(f"Modules Total : {len(modules)}")
            all_lessons = await l_repo.get_all_for_course(course.id)
            completed = [l for l in all_lessons if l.status == "COMPLETED"]
            print(f"Lessons Done  : {len(completed)} / {len(all_lessons)}")
        else:
            print(f"Course not yet discovered for {target_course}")
        print("==================================\n")
    await db_mgr.close()
