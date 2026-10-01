"""Async SQLite database engine and session manager."""

from __future__ import annotations

import os
from pathlib import Path
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    AsyncEngine,
    create_async_engine,
    async_sessionmaker,
)

from database.models import Base


class DatabaseSessionManager:
    """Manages async SQLite connections and sessions."""

    def __init__(self, db_path: str = "./database/coursera.db"):
        self.db_path = db_path
        self._engine: AsyncEngine | None = None
        self._sessionmaker: async_sessionmaker[AsyncSession] | None = None

    def init(self):
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        sqlite_url = f"sqlite+aiosqlite:///{self.db_path}"
        self._engine = create_async_engine(
            sqlite_url,
            echo=False,
            future=True,
        )
        self._sessionmaker = async_sessionmaker(
            bind=self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

    async def create_all(self):
        if self._engine is None:
            self.init()
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def close(self):
        if self._engine is not None:
            await self._engine.dispose()
            self._engine = None
            self._sessionmaker = None

    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        if self._sessionmaker is None:
            self.init()
        session: AsyncSession = self._sessionmaker()
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# Global default instance
_default_db_manager = DatabaseSessionManager()


def init_db(db_path: str = "./database/coursera.db") -> DatabaseSessionManager:
    global _default_db_manager
    _default_db_manager = DatabaseSessionManager(db_path=db_path)
    _default_db_manager.init()
    return _default_db_manager


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async with _default_db_manager.session() as session:
        yield session
