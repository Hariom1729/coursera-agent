"""Scheduler and pacing engine to avoid robotic hammering and simulate natural reading delays."""

from __future__ import annotations

import asyncio
import logging
import random

logger = logging.getLogger(__name__)


class AutomationScheduler:
    """Provides gentle pacing and jittered human delays."""

    def __init__(self, base_delay: float = 2.0):
        self.base_delay = base_delay

    async def pace(self, multiplier: float = 1.0):
        """Wait for base delay plus random jitter (±30%)."""
        jitter = random.uniform(0.7, 1.3)
        delay = self.base_delay * multiplier * jitter
        logger.debug(f"Pacing delay: {delay:.2f}s")
        await asyncio.sleep(delay)

    async def simulated_reading_delay(self, word_count: int, max_seconds: float = 8.0):
        """Simulate quick reading time based on content length."""
        # Fast scanning pace: 350 wpm ~ 0.17 seconds per word, capped at max_seconds
        calculated = min(max_seconds, max(2.0, word_count * 0.015))
        logger.info(f"Simulating reading content ({word_count} words): pausing {calculated:.1f}s...")
        await asyncio.sleep(calculated)
