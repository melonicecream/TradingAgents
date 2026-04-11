"""
AnalysisHistory repository with specialized queries.
"""

from typing import Optional, Sequence
from sqlalchemy import select, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession
from web_api.db.models import AnalysisHistory
from web_api.repositories.base import BaseRepository


class AnalysisHistoryRepository(BaseRepository[AnalysisHistory]):
    """Repository for AnalysisHistory model."""

    def __init__(self, session: AsyncSession):
        super().__init__(AnalysisHistory, session)

    async def get_by_ticker(
        self, ticker: str, skip: int = 0, limit: int = 10
    ) -> Sequence[AnalysisHistory]:
        """Get analysis history by ticker."""
        result = await self.session.execute(
            select(AnalysisHistory)
            .where(AnalysisHistory.ticker == ticker.upper())
            .order_by(desc(AnalysisHistory.created_at))
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()

    async def get_latest_by_ticker(self, ticker: str) -> Optional[AnalysisHistory]:
        """Get latest analysis for a ticker."""
        result = await self.session.execute(
            select(AnalysisHistory)
            .where(AnalysisHistory.ticker == ticker.upper())
            .order_by(desc(AnalysisHistory.created_at))
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_by_date_range(
        self, start_date: str, end_date: str, ticker: Optional[str] = None
    ) -> Sequence[AnalysisHistory]:
        """Get analyses within date range."""
        conditions = [
            AnalysisHistory.analysis_date >= start_date,
            AnalysisHistory.analysis_date <= end_date,
        ]
        if ticker:
            conditions.append(AnalysisHistory.ticker == ticker.upper())

        result = await self.session.execute(
            select(AnalysisHistory)
            .where(and_(*conditions))
            .order_by(desc(AnalysisHistory.created_at))
        )
        return result.scalars().all()

    async def get_recent(self, limit: int = 10) -> Sequence[AnalysisHistory]:
        """Get recent analyses."""
        result = await self.session.execute(
            select(AnalysisHistory)
            .order_by(desc(AnalysisHistory.created_at))
            .limit(limit)
        )
        return result.scalars().all()
