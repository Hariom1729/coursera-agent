"""Exponential retry decorators and helpers."""

from __future__ import annotations

import logging
from typing import Callable, Any
from tenacity import retry, stop_after_attempt, wait_exponential, before_sleep_log

logger = logging.getLogger(__name__)


def with_retry(
    max_attempts: int = 4,
    min_wait: float = 2.0,
    max_wait: float = 30.0,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Configurable exponential retry decorator."""
    return retry(
        reraise=True,
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=2, min=min_wait, max=max_wait),
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
