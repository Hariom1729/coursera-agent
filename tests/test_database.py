"""Unit tests for SQLite database operations and repositories."""

import pytest
import tempfile
from pathlib import Path
from database.database import DatabaseSessionManager
from database.repositories import (
    CourseRepository,
    ModuleRepository,
    LessonRepository,
    AICacheRepository,
    AutomationRunRepository,
)


@pytest.fixture
async def temp_db():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test.db")
        manager = DatabaseSessionManager(db_path=db_path)
        manager.init()
        await manager.create_all()
        yield manager
        await manager.close()


@pytest.mark.asyncio
async def test_course_and_module_persistence(temp_db):
    async with temp_db.session() as session:
        c_repo = CourseRepository(session)
        course = await c_repo.upsert_course(
            course_id="course_test",
            title="Test Course",
            url="https://coursera.org/learn/test",
            instructor="Dr. Test",
        )
        assert course.id == "course_test"

        m_repo = ModuleRepository(session)
        mod = await m_repo.upsert_module(
            module_id="mod_1",
            course_id="course_test",
            title="Week 1",
            module_index=1,
        )
        assert mod.title == "Week 1"

        modules = await m_repo.get_modules("course_test")
        assert len(modules) == 1


@pytest.mark.asyncio
async def test_lesson_progress_lifecycle(temp_db):
    async with temp_db.session() as session:
        c_repo = CourseRepository(session)
        await c_repo.upsert_course("c1", "Course 1", "https://coursera.org")

        m_repo = ModuleRepository(session)
        await m_repo.upsert_module("m1", "c1", "Mod 1", 1)

        l_repo = LessonRepository(session)
        lesson = await l_repo.upsert_lesson(
            lesson_id="l1",
            course_id="c1",
            module_id="m1",
            title="Intro Video",
            url="https://coursera.org/lecture/1",
            lesson_type="video",
        )
        assert lesson.status == "DISCOVERED"

        # Record started progress
        await l_repo.record_progress("c1", "m1", "l1", status="STARTED")
        updated = await l_repo.get_by_id("l1")
        assert updated.status == "STARTED"

        # Record completed progress
        await l_repo.record_progress("c1", "m1", "l1", status="COMPLETED")
        completed = await l_repo.get_by_id("l1")
        assert completed.status == "COMPLETED"


@pytest.mark.asyncio
async def test_ai_cache_repository(temp_db):
    async with temp_db.session() as session:
        cache_repo = AICacheRepository(session)
        hash_val = "abc123hash"
        model_name = "gemini-2.5-flash"

        # Cache miss
        res = await cache_repo.get_cached_analysis(hash_val, model_name)
        assert res is None

        # Save analysis
        await cache_repo.save_analysis(
            content_hash=hash_val,
            provider="gemini",
            model=model_name,
            response_json='{"answer": "A"}',
            candidate_answer="A",
            confidence=0.95,
        )

        # Cache hit
        cached = await cache_repo.get_cached_analysis(hash_val, model_name)
        assert cached is not None
        assert cached.candidate_answer == "A"
        assert cached.confidence == 0.95
