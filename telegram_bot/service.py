"""Telegram-facing service layer reusing the web execution lifecycle."""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, AsyncIterator, cast

from sqlalchemy.ext.asyncio import AsyncSession

from web_api.db.database import AsyncSessionLocal, bootstrap_checkpointer, init_db
from web_api.main import (
    get_engine_info,
    get_execution_detail,
    get_executions,
    get_system_stats,
    trading_service,
)
from web_api.schemas.analysis import ExecutionDetailResponse


class TelegramAnalysisService:
    def __init__(self):
        self._initialized = False

    async def ensure_ready(self) -> None:
        if not self._initialized:
            await init_db()
            self._initialized = True

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        await self.ensure_ready()
        async with AsyncSessionLocal() as session:
            yield session

    async def stream_analysis(
        self,
        ticker: str,
        analysis_date: str,
        analysts: list[str],
    ) -> AsyncIterator[dict[str, Any]]:
        await self.ensure_ready()
        async with AsyncSessionLocal() as session:
            async with bootstrap_checkpointer() as checkpointer:
                async for event in trading_service.analyze_stream(
                    ticker=ticker,
                    date=analysis_date,
                    analysts=analysts,
                    db=session,
                    request=None,
                    checkpointer=checkpointer,
                ):
                    if not event.startswith("data: "):
                        continue
                    yield json.loads(event[len("data: ") :].strip())

    async def get_engine_info(self) -> dict[str, Any]:
        return (await get_engine_info()).model_dump()

    async def get_stats(self) -> dict[str, Any]:
        async with self.session() as session:
            return (await get_system_stats(session)).model_dump()

    async def get_recent_executions(
        self, page: int = 1, page_size: int = 8
    ) -> list[dict[str, Any]]:
        async with self.session() as session:
            response = await get_executions(page=page, page_size=page_size, db=session)
            return [item.model_dump() for item in response.items]

    async def get_execution_detail(self, execution_id: int) -> dict[str, Any]:
        async with self.session() as session:
            detail = await get_execution_detail(execution_id=execution_id, db=session)
            if hasattr(detail, "model_dump"):
                return cast(ExecutionDetailResponse, detail).model_dump()
            return cast(dict[str, Any], detail)


def default_analysis_date() -> str:
    return datetime.now().strftime("%Y-%m-%d")
