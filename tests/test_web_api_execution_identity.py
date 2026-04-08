from datetime import datetime, timedelta
import tempfile
import unittest
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from tradingagents.default_config import DEFAULT_CONFIG
from web_api.db.database import Base
from web_api.repositories.execution import AnalysisExecutionRepository
from web_api.services.execution_identity import (
    CHECKPOINT_SCHEMA_VERSION,
    GRAPH_VERSION,
    STATUS_PENDING,
    STATUS_RUNNING,
    build_execution_identity,
    is_execution_compatible,
)


class WebApiExecutionIdentityTests(unittest.IsolatedAsyncioTestCase):
    def test_identical_requests_share_execution_key(self):
        config = DEFAULT_CONFIG.copy()
        config["language"] = "한국어"

        first = build_execution_identity(
            ticker="aapl",
            analysis_date="2026-04-08",
            analysts=["news", "market"],
            config=config,
        )
        second = build_execution_identity(
            ticker="AAPL",
            analysis_date="2026-04-08",
            analysts=["market", "news"],
            config=config,
        )

        self.assertEqual(first.execution_key, second.execution_key)
        self.assertEqual(first.config_hash, second.config_hash)
        self.assertEqual(first.ticker, "AAPL")
        self.assertEqual(first.analysts, ["market", "news"])

    def test_duplicate_analysts_do_not_change_execution_identity(self):
        config = DEFAULT_CONFIG.copy()
        config["language"] = "한국어"

        deduped = build_execution_identity(
            ticker="NVDA",
            analysis_date="2026-04-08",
            analysts=["market", "news"],
            config=config,
        )
        duplicated = build_execution_identity(
            ticker="NVDA",
            analysis_date="2026-04-08",
            analysts=["market", "news", "market"],
            config=config,
        )

        self.assertEqual(deduped.execution_key, duplicated.execution_key)
        self.assertEqual(deduped.analysts, duplicated.analysts)

    def test_provider_change_breaks_execution_identity(self):
        config = DEFAULT_CONFIG.copy()
        config["language"] = "한국어"
        other_config = DEFAULT_CONFIG.copy()
        other_config["language"] = "한국어"
        other_config["llm_provider"] = "anthropic"

        baseline = build_execution_identity(
            ticker="AAPL",
            analysis_date="2026-04-08",
            analysts=["market", "news"],
            config=config,
        )
        changed_provider = build_execution_identity(
            ticker="AAPL",
            analysis_date="2026-04-08",
            analysts=["market", "news"],
            config=other_config,
        )

        self.assertNotEqual(baseline.execution_key, changed_provider.execution_key)
        self.assertNotEqual(baseline.config_hash, changed_provider.config_hash)

    async def test_lease_conflict_is_deterministic(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "execution-identity.db"
            engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
            session_factory = async_sessionmaker(
                engine,
                class_=AsyncSession,
                expire_on_commit=False,
                autoflush=False,
                autocommit=False,
            )
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)

            async with session_factory() as session:
                repo = AnalysisExecutionRepository(session)
                now = datetime(2026, 4, 8, 12, 0, 0)
                identity = build_execution_identity(
                    ticker="NVDA",
                    analysis_date=None,
                    analysts=["market", "news"],
                    config={**DEFAULT_CONFIG, "language": "한국어"},
                    now=now,
                )
                execution = await repo.create(
                    execution_key=identity.execution_key,
                    thread_id="thread-lease-1",
                    ticker=identity.ticker,
                    analysis_date=identity.analysis_date,
                    analysts_json=identity.analysts,
                    config_hash=identity.config_hash,
                    graph_version=GRAPH_VERSION,
                    checkpoint_schema_version=CHECKPOINT_SCHEMA_VERSION,
                    status=STATUS_PENDING,
                )
                await session.commit()

                acquired = await repo.acquire_lease(execution, "owner-a", now=now)
                await session.commit()

                self.assertTrue(acquired)
                self.assertEqual(execution.lease_owner, "owner-a")

                conflicted = await repo.acquire_lease(
                    execution,
                    "owner-b",
                    now=now + timedelta(seconds=30),
                )

                self.assertFalse(conflicted)
                self.assertEqual(execution.lease_owner, "owner-a")

                reacquired = await repo.acquire_lease(
                    execution,
                    "owner-b",
                    now=now + timedelta(minutes=6),
                )
                await session.commit()

                self.assertTrue(reacquired)
                self.assertEqual(execution.lease_owner, "owner-b")

                released_by_old_owner = await repo.release_lease(execution, "owner-a")
                self.assertFalse(released_by_old_owner)
                self.assertEqual(execution.lease_owner, "owner-b")

                running_by_old_owner = await repo.mark_running(
                    execution,
                    "owner-a",
                    now=now + timedelta(minutes=6, seconds=30),
                )
                self.assertFalse(running_by_old_owner)

                running_by_new_owner = await repo.mark_running(
                    execution,
                    "owner-b",
                    now=now + timedelta(minutes=6, seconds=30),
                )
                await session.commit()

                self.assertTrue(running_by_new_owner)
                self.assertEqual(execution.status, STATUS_RUNNING)

                released_by_current_owner = await repo.release_lease(
                    execution, "owner-b"
                )
                await session.commit()

                self.assertTrue(released_by_current_owner)
                self.assertIsNone(execution.lease_owner)

            await engine.dispose()

    async def test_compatibility_requires_hash_and_versions_match(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "execution-compatibility.db"
            engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
            session_factory = async_sessionmaker(
                engine,
                class_=AsyncSession,
                expire_on_commit=False,
                autoflush=False,
                autocommit=False,
            )
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)

            async with session_factory() as session:
                repo = AnalysisExecutionRepository(session)
                identity = build_execution_identity(
                    ticker="AAPL",
                    analysis_date="2026-04-08",
                    analysts=["market"],
                    config={**DEFAULT_CONFIG, "language": "한국어"},
                )
                execution = await repo.create(
                    execution_key=identity.execution_key,
                    thread_id="thread-compat-1",
                    ticker=identity.ticker,
                    analysis_date=identity.analysis_date,
                    analysts_json=identity.analysts,
                    config_hash=identity.config_hash,
                    graph_version=identity.graph_version,
                    checkpoint_schema_version=identity.checkpoint_schema_version,
                    status=STATUS_RUNNING,
                )
                await session.commit()

                self.assertTrue(is_execution_compatible(execution, identity))

                mismatched_identity = build_execution_identity(
                    ticker="AAPL",
                    analysis_date="2026-04-08",
                    analysts=["market"],
                    config={
                        **DEFAULT_CONFIG,
                        "language": "한국어",
                        "quick_think_llm": "gpt-5.4-mini",
                    },
                )

                self.assertFalse(
                    is_execution_compatible(execution, mismatched_identity)
                )

            await engine.dispose()


if __name__ == "__main__":
    unittest.main()
