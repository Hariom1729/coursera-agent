"""Finite State Machine managing course lifecycle and progress persistence."""

from __future__ import annotations

import logging
from enum import Enum
from typing import Optional
from database.database import DatabaseSessionManager
from database.repositories import AutomationRunRepository

logger = logging.getLogger(__name__)


class AutomationState(str, Enum):
    START = "START"
    LOAD_SESSION = "LOAD_SESSION"
    OPEN_COURSE = "OPEN_COURSE"
    DISCOVER_STRUCTURE = "DISCOVER_STRUCTURE"
    LOAD_PROGRESS = "LOAD_PROGRESS"
    PROCESS_MODULE = "PROCESS_MODULE"
    PROCESS_LESSON = "PROCESS_LESSON"
    WAIT_FOR_USER = "WAIT_FOR_USER"
    MARK_COMPLETE = "MARK_COMPLETE"
    NEXT_LESSON = "NEXT_LESSON"
    NEXT_MODULE = "NEXT_MODULE"
    COURSE_COMPLETE = "COURSE_COMPLETE"
    CERTIFICATE_CHECK = "CERTIFICATE_CHECK"
    DONE = "DONE"
    ERROR = "ERROR"


class AutomationStateMachine:
    """Tracks and transitions the automation state, persisting every transition to SQLite."""

    def __init__(self, run_id: str, db_manager: DatabaseSessionManager):
        self.run_id = run_id
        self.db_manager = db_manager
        self.current_state: AutomationState = AutomationState.START
        self.last_module_id: Optional[str] = None
        self.last_lesson_id: Optional[str] = None

    async def transition_to(
        self,
        new_state: AutomationState,
        module_id: Optional[str] = None,
        lesson_id: Optional[str] = None,
        status: Optional[str] = None,
    ):
        """Execute state transition and persist update to SQLite."""
        old_state = self.current_state
        self.current_state = new_state
        if module_id is not None:
            self.last_module_id = module_id
        if lesson_id is not None:
            self.last_lesson_id = lesson_id

        logger.info(f"[State Transition] {old_state.value} -> {new_state.value}")

        async with self.db_manager.session() as session:
            repo = AutomationRunRepository(session)
            await repo.update_state(
                run_id=self.run_id,
                state=new_state.value,
                last_module_id=self.last_module_id,
                last_lesson_id=self.last_lesson_id,
                status=status,
            )
            await repo.log_event(
                run_id=self.run_id,
                event_type="STATE_CHANGE",
                message=f"Transitioned from {old_state.value} to {new_state.value}",
                details={"module_id": self.last_module_id, "lesson_id": self.last_lesson_id},
            )
