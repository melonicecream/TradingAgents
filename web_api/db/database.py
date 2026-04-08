"""
Database configuration module.
Modern SQLAlchemy 2.0 async setup with SQLite.
"""

import os
import importlib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base

AsyncSqliteSaver = importlib.import_module(
    "langgraph.checkpoint.sqlite.aio"
).AsyncSqliteSaver

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./data/tradingagents.db")


def _sqlite_conn_string(database_url: str | None = None) -> str:
    url = (database_url or DATABASE_URL).strip()
    for prefix in ("sqlite+aiosqlite:///", "sqlite:///"):
        if url.startswith(prefix):
            return url.removeprefix(prefix)
    return url


def _ensure_sqlite_parent_dir(database_url: str | None = None) -> Path:
    sqlite_path = Path(_sqlite_conn_string(database_url))
    if sqlite_path.as_posix() != ":memory:":
        sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    return sqlite_path


engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    future=True,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

Base = declarative_base()


async def get_db():
    """Dependency for getting async database sessions."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    """Initialize database tables."""
    _ensure_sqlite_parent_dir()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@asynccontextmanager
async def bootstrap_checkpointer(
    database_url: str | None = None,
) -> AsyncIterator[Any]:
    sqlite_path = _ensure_sqlite_parent_dir(database_url)
    async with AsyncSqliteSaver.from_conn_string(str(sqlite_path)) as checkpointer:
        await checkpointer.setup()
        yield checkpointer
