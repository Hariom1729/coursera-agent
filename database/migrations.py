"""Database migrations and table initialization."""

from __future__ import annotations

import logging
from database.database import DatabaseSessionManager
from database.models import Base

logger = logging.getLogger(__name__)


async def run_migrations(db_path: str = "./database/coursera.db"):
    """Initialize database tables if they do not exist."""
    manager = DatabaseSessionManager(db_path=db_path)
    manager.init()
    try:
        await manager.create_all()
        logger.info(f"Database schema initialized successfully at {db_path}")
    finally:
        await manager.close()
