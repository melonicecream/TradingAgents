"""Execution and checkpoint repositories for resumable analysis runs."""

from datetime import datetime, timedelta
from typing import Any, Optional, Sequence, cast

from sqlalchemy import and_, desc, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from web_api.db.models import AnalysisCheckpoint, AnalysisExecution
from web_api.repositories.base import BaseRepository
from web_api.services.execution_identity import (
    LEASE_SECONDS,
    STATUS_PENDING,
    STATUS_RESUMABLE,
    STATUS_RUNNING,
)


class AnalysisExecutionRepository(BaseRepository[AnalysisExecution]):
    """Repository for AnalysisExecution model."""

    def __init__(self, session: AsyncSession):
        super().__init__(AnalysisExecution, session)

    async def get_by_execution_key(
        self, execution_key: str
    ) -> Optional[AnalysisExecution]:
        result = await self.session.execute(
            select(AnalysisExecution).where(
                AnalysisExecution.execution_key == execution_key
            )
        )
        return result.scalar_one_or_none()

    async def get_by_thread_id(self, thread_id: str) -> Optional[AnalysisExecution]:
        result = await self.session.execute(
            select(AnalysisExecution).where(AnalysisExecution.thread_id == thread_id)
        )
        return result.scalar_one_or_none()

    async def get_latest_for_ticker(
        self, ticker: str, limit: int = 10
    ) -> Sequence[AnalysisExecution]:
        result = await self.session.execute(
            select(AnalysisExecution)
            .where(AnalysisExecution.ticker == ticker.upper())
            .order_by(desc(AnalysisExecution.created_at))
            .limit(limit)
        )
        return result.scalars().all()

    async def acquire_lease(
        self,
        execution: AnalysisExecution,
        owner: str,
        *,
        now: datetime,
        lease_seconds: int = LEASE_SECONDS,
    ) -> bool:
        execution_id = cast(int, execution.id)
        result = await self.session.execute(
            update(AnalysisExecution)
            .where(
                AnalysisExecution.id == execution_id,
                AnalysisExecution.status.in_(
                    [STATUS_PENDING, STATUS_RESUMABLE, STATUS_RUNNING]
                ),
                or_(
                    and_(
                        AnalysisExecution.lease_owner.is_(None),
                        AnalysisExecution.lease_expires_at.is_(None),
                    ),
                    AnalysisExecution.lease_owner == owner,
                    and_(
                        AnalysisExecution.lease_expires_at.is_not(None),
                        AnalysisExecution.lease_expires_at <= now,
                    ),
                ),
            )
            .values(
                lease_owner=owner,
                lease_expires_at=now + timedelta(seconds=lease_seconds),
            )
        )
        rowcount = cast(int, getattr(cast(Any, result), "rowcount", 0))
        if rowcount == 0:
            await self.session.refresh(execution)
            return False

        await self.session.refresh(execution)
        return True

    async def release_lease(self, execution: AnalysisExecution, owner: str) -> bool:
        execution_id = cast(int, execution.id)
        result = await self.session.execute(
            update(AnalysisExecution)
            .where(
                AnalysisExecution.id == execution_id,
                AnalysisExecution.lease_owner == owner,
            )
            .values(lease_owner=None, lease_expires_at=None)
        )
        await self.session.refresh(execution)
        rowcount = cast(int, getattr(cast(Any, result), "rowcount", 0))
        return rowcount > 0

    async def mark_running(
        self,
        execution: AnalysisExecution,
        owner: str,
        *,
        now: datetime,
        lease_seconds: int = LEASE_SECONDS,
    ) -> bool:
        lease_acquired = await self.acquire_lease(
            execution,
            owner,
            now=now,
            lease_seconds=lease_seconds,
        )
        if not lease_acquired:
            return False

        execution_id = cast(int, execution.id)
        result = await self.session.execute(
            update(AnalysisExecution)
            .where(
                AnalysisExecution.id == execution_id,
                AnalysisExecution.lease_owner == owner,
            )
            .values(status=STATUS_RUNNING, current_milestone=None)
        )
        await self.session.refresh(execution)
        rowcount = cast(int, getattr(cast(Any, result), "rowcount", 0))
        return rowcount > 0


class AnalysisCheckpointRepository(BaseRepository[AnalysisCheckpoint]):
    """Repository for AnalysisCheckpoint model."""

    def __init__(self, session: AsyncSession):
        super().__init__(AnalysisCheckpoint, session)

    async def get_by_execution_id(
        self, execution_id: int
    ) -> Sequence[AnalysisCheckpoint]:
        result = await self.session.execute(
            select(AnalysisCheckpoint)
            .where(AnalysisCheckpoint.execution_id == execution_id)
            .order_by(
                AnalysisCheckpoint.step_index.asc(), AnalysisCheckpoint.created_at.asc()
            )
        )
        return result.scalars().all()

    async def get_latest_for_execution(
        self, execution_id: int
    ) -> Optional[AnalysisCheckpoint]:
        result = await self.session.execute(
            select(AnalysisCheckpoint)
            .where(AnalysisCheckpoint.execution_id == execution_id)
            .order_by(
                desc(AnalysisCheckpoint.step_index), desc(AnalysisCheckpoint.created_at)
            )
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_by_execution_and_milestone(
        self, execution_id: int, milestone: str
    ) -> Optional[AnalysisCheckpoint]:
        result = await self.session.execute(
            select(AnalysisCheckpoint).where(
                AnalysisCheckpoint.execution_id == execution_id,
                AnalysisCheckpoint.milestone == milestone,
            )
        )
        return result.scalar_one_or_none()
