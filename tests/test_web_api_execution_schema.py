import tempfile
import unittest
from pathlib import Path
from typing import cast

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from web_api.db.database import Base
from web_api.db.models import AnalysisCheckpoint, AnalysisExecution, AnalysisHistory
from web_api.repositories.analysis import AnalysisHistoryRepository
from web_api.repositories.execution import (
    AnalysisCheckpointRepository,
    AnalysisExecutionRepository,
)


class WebApiExecutionSchemaTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        db_path = Path(self._tmpdir.name) / "execution-schema.db"
        self.engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
        self.session_factory = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
            autocommit=False,
        )
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def asyncTearDown(self):
        await self.engine.dispose()
        self._tmpdir.cleanup()

    async def test_create_execution_and_multiple_checkpoint_rows(self):
        async with self.session_factory() as session:
            execution_repo = AnalysisExecutionRepository(session)
            checkpoint_repo = AnalysisCheckpointRepository(session)

            execution = await execution_repo.create(
                execution_key="exec-key-1",
                thread_id="thread-1",
                ticker="AAPL",
                analysis_date="2026-04-05",
                analysts_json=["market", "news"],
                config_hash="cfg-1",
                graph_version="graph-v1",
                checkpoint_schema_version="checkpoint-v1",
                status="running",
            )
            execution_id = cast(int, execution.id)

            checkpoint_one = await checkpoint_repo.create(
                execution_id=execution_id,
                milestone="market_complete",
                checkpoint_id="cp-1",
                checkpoint_ns="",
                step_index=1,
                summary_json={"agent": "market"},
                status="completed",
            )
            checkpoint_two = await checkpoint_repo.create(
                execution_id=execution_id,
                milestone="research_complete",
                checkpoint_id="cp-2",
                checkpoint_ns="",
                step_index=2,
                summary_json={"agent": "research_manager"},
                status="completed",
            )
            await session.commit()

            reloaded_execution = await execution_repo.get_by_execution_key("exec-key-1")
            checkpoints = await checkpoint_repo.get_by_execution_id(execution_id)
            latest_checkpoint = await checkpoint_repo.get_latest_for_execution(
                execution_id
            )

            self.assertIsNotNone(reloaded_execution)
            reloaded_execution = cast(AnalysisExecution, reloaded_execution)
            self.assertEqual(reloaded_execution.thread_id, "thread-1")
            self.assertEqual(len(checkpoints), 2)
            self.assertEqual(checkpoints[0].id, checkpoint_one.id)
            self.assertEqual(checkpoints[1].id, checkpoint_two.id)
            self.assertIsNotNone(latest_checkpoint)
            latest_checkpoint = cast(AnalysisCheckpoint, latest_checkpoint)
            self.assertEqual(latest_checkpoint.milestone, "research_complete")

    async def test_uniqueness_constraints_are_enforced(self):
        async with self.session_factory() as session:
            execution_repo = AnalysisExecutionRepository(session)
            checkpoint_repo = AnalysisCheckpointRepository(session)

            execution = await execution_repo.create(
                execution_key="exec-key-unique",
                thread_id="thread-unique",
                ticker="MSFT",
                analysis_date="2026-04-05",
                analysts_json=["market"],
                config_hash="cfg-1",
                graph_version="graph-v1",
                checkpoint_schema_version="checkpoint-v1",
                status="running",
            )
            execution_id = cast(int, execution.id)
            await checkpoint_repo.create(
                execution_id=execution_id,
                milestone="market_complete",
                checkpoint_id="cp-1",
                checkpoint_ns="",
                step_index=1,
                summary_json={"agent": "market"},
                status="completed",
            )
            await session.commit()

            with self.assertRaises(IntegrityError):
                await execution_repo.create(
                    execution_key="exec-key-unique",
                    thread_id="thread-other",
                    ticker="MSFT",
                    analysis_date="2026-04-05",
                    analysts_json=["market"],
                    config_hash="cfg-1",
                    graph_version="graph-v1",
                    checkpoint_schema_version="checkpoint-v1",
                    status="running",
                )
                await session.commit()

            await session.rollback()

            with self.assertRaises(IntegrityError):
                await checkpoint_repo.create(
                    execution_id=execution_id,
                    milestone="market_complete",
                    checkpoint_id="cp-2",
                    checkpoint_ns="",
                    step_index=2,
                    summary_json={"agent": "market"},
                    status="completed",
                )
                await session.commit()

            await session.rollback()

    async def test_history_repository_remains_queryable_without_execution_rows(self):
        async with self.session_factory() as session:
            history_repo = AnalysisHistoryRepository(session)

            created = await history_repo.create(
                ticker="NVDA",
                analysis_date="2026-04-05",
                decision="Buy",
                full_decision="Rating: Buy",
                reports={"market": "done"},
                research={"investment_plan": "go"},
                risk={"final_decision": "approved"},
            )
            await session.commit()

            latest = await history_repo.get_latest_by_ticker("nvda")
            items = await history_repo.get_by_ticker("nvda")

            self.assertIsNotNone(latest)
            latest = cast(AnalysisHistory, latest)
            self.assertEqual(latest.id, created.id)
            self.assertEqual(latest.decision, "Buy")
            self.assertEqual(len(items), 1)
            self.assertEqual(items[0].ticker, "NVDA")


if __name__ == "__main__":
    unittest.main()
