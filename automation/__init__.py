"""Automation engine package for Coursera automation agent."""

from automation.state_machine import AutomationStateMachine, AutomationState
from automation.scheduler import AutomationScheduler
from automation.engine import AutomationEngine

__all__ = [
    "AutomationStateMachine",
    "AutomationState",
    "AutomationScheduler",
    "AutomationEngine",
]
