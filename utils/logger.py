"""Logging configuration with custom formatting and file handlers."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional


class CustomFormatter(logging.Formatter):
    """Formats logs with timestamp like [HH:MM:SS] LEVEL message."""

    def format(self, record: logging.LogRecord) -> str:
        asctime = self.formatTime(record, "%H:%M:%S")
        levelname = f"{record.levelname:<8}"
        return f"[{asctime}] {levelname} {record.getMessage()}"


def setup_logging(
    level: str = "INFO",
    log_file: Optional[str] = "./logs/agent.log",
) -> logging.Logger:
    """Configure root logger with console and file output."""
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    # Clear existing handlers
    root_logger.handlers = []

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(CustomFormatter())
    root_logger.addHandler(console_handler)

    # File handler
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(str(log_path), encoding="utf-8")
        file_handler.setLevel(numeric_level)
        file_handler.setFormatter(
            logging.Formatter(
                "[%(asctime)s] %(levelname)-8s %(name)s: %(message)s",
                "%Y-%m-%d %H:%M:%S",
            )
        )
        root_logger.addHandler(file_handler)

    # Silence overly verbose external libraries
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)

    return root_logger
