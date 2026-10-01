"""Unit tests for crash recovery, state persistence, and resume functionality."""

import pytest
import tempfile
from pathlib import Path
from database.database import DatabaseSessionManager
from database.repositories import AutomationRunRepository
from automation.state_machine import AutomationStateMachine, AutomationState


@pytest.fixture
async def temp_db():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test_recovery.db")
        manager = DatabaseSessionManager(db_path=db_path)
        manager.init()
        await manager.create_all()
        yield manager
        await manager.close()


@pytest.mark.asyncio
async def test_state_machine_transitions_and_persistence(temp_db):
    run_id = "run_test_123"
    async with temp_db.session() as session:
        r_repo = AutomationRunRepository(session)
        await r_repo.start_run(run_id, "https://coursera.org/learn/python")

    sm = AutomationStateMachine(run_id, temp_db)
    assert sm.current_state == AutomationState.START

    # Transition to LOAD_SESSION
    await sm.transition_to(AutomationState.LOAD_SESSION)
    assert sm.current_state == AutomationState.LOAD_SESSION

    # Transition to PROCESS_LESSON with module and lesson IDs
    await sm.transition_to(
        AutomationState.PROCESS_LESSON,
        module_id="mod_1",
        lesson_id="lesson_42",
    )
    assert sm.current_state == AutomationState.PROCESS_LESSON
    assert sm.last_module_id == "mod_1"
    assert sm.last_lesson_id == "lesson_42"

    # Verify latest run in DB preserves this state for resume
    async with temp_db.session() as session:
        r_repo = AutomationRunRepository(session)
        latest = await r_repo.get_latest_run()
        assert latest is not None
        assert latest.id == run_id
        assert latest.current_state == AutomationState.PROCESS_LESSON.value
        assert latest.last_module_id == "mod_1"
        assert latest.last_lesson_id == "lesson_42"
        assert latest.status == "RUNNING"
