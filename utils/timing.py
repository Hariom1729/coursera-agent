"""Timing utilities and execution timers."""

from __future__ import annotations

import time


class ExecutionTimer:
    """Simple context manager to measure operation durations."""

    def __init__(self, name: str = "Operation"):
        self.name = name
        self.start_time: float = 0.0
        self.elapsed: float = 0.0

    def __enter__(self):
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.elapsed = time.perf_counter() - self.start_time
