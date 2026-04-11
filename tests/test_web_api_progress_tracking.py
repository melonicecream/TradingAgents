import unittest
import tempfile
import asyncio
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import patch
from unittest.mock import MagicMock
from datetime import datetime, timedelta

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.graph.propagation import Propagator
from web_api.db.database import Base
from web_api.repositories.analysis import AnalysisHistoryRepository
from web_api.repositories.execution import AnalysisExecutionRepository
from web_api.main import TradingService, get_executions
from web_api.main import get_engine_info, get_execution_detail, get_system_stats
from web_api.db.models import AnalysisExecution
from web_api.schemas.analysis import ExecutionDetailResponse
from web_api.services.execution_identity import (
    CHECKPOINT_SCHEMA_VERSION,
    GRAPH_VERSION,
    STATUS_COMPLETED,
    STATUS_RUNNING,
)
from tests.test_web_api_execution_lifecycle import (
    FakeRequest,
    make_final_chunk,
    make_snapshot,
)


class WebApiProgressTrackingTests(unittest.TestCase):
    def test_progress_uses_milestone_count_instead_of_chunk_count(self):
        service = TradingService()
        execution = AnalysisExecution(
            execution_key="exec-local-1",
            thread_id="thread-local-1",
            ticker="NVDA",
            analysis_date="2026-04-08",
            analysts_json=["market", "news"],
            config_hash="cfg-local-1",
            graph_version=GRAPH_VERSION,
            checkpoint_schema_version=CHECKPOINT_SCHEMA_VERSION,
            status=STATUS_RUNNING,
            last_completed_milestone="market_complete",
            current_milestone="market_complete",
        )

        progress = service._extract_progress(
            execution=execution,
            chunk={"market_report": "done"},
            prev_chunk={},
            agent_status={},
            step=5,
            total=9,
            selected_analysts=["market", "news"],
        )

        self.assertEqual(progress["completed_milestones"], 1)
        self.assertEqual(progress["total_milestones"], 6)
        self.assertAlmostEqual(progress["progress"], (1 / 6) * 100)
        self.assertEqual(progress["current_stage"], "뉴스 분석")
        self.assertGreaterEqual(progress["elapsed_seconds"], 0)

    def test_progress_stage_uses_next_pending_milestone(self):
        service = TradingService()
        execution = AnalysisExecution(
            execution_key="exec-local-2",
            thread_id="thread-local-2",
            ticker="NVDA",
            analysis_date="2026-04-08",
            analysts_json=["market", "news"],
            config_hash="cfg-local-2",
            graph_version=GRAPH_VERSION,
            checkpoint_schema_version=CHECKPOINT_SCHEMA_VERSION,
            status=STATUS_RUNNING,
            last_completed_milestone="research_complete",
            current_milestone="research_complete",
        )

        progress = service._extract_progress(
            execution=execution,
            chunk={
                "market_report": "done",
                "news_report": "done",
                "investment_plan": "ready",
            },
            prev_chunk={},
            agent_status={},
            step=7,
            total=9,
            selected_analysts=["market", "news"],
        )

        self.assertEqual(progress["completed_milestones"], 3)
        self.assertEqual(progress["current_stage"], "트레이더 분석")
        self.assertEqual(progress["milestone_status"]["시장 분석"], "completed")
        self.assertEqual(progress["milestone_status"]["트레이더 분석"], "pending")


class WebApiExecutionEndpointTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        db_path = Path(self.tmpdir.name) / "web-api-progress.db"
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
        self.tmpdir.cleanup()

    async def test_get_executions_returns_live_progress_fields(self):
        async with self.session_factory() as session:
            execution_repo = AnalysisExecutionRepository(session)
            history_repo = AnalysisHistoryRepository(session)
            history = await history_repo.create(
                ticker="NVDA",
                analysis_date="2026-04-08",
                decision="Buy",
                full_decision="Rating: Buy",
            )
            execution = await execution_repo.create(
                execution_key="exec-progress-1",
                thread_id="thread-progress-1",
                ticker="NVDA",
                analysis_date="2026-04-08",
                analysts_json=["market", "news"],
                config_hash="cfg-1",
                graph_version=GRAPH_VERSION,
                checkpoint_schema_version=CHECKPOINT_SCHEMA_VERSION,
                status=STATUS_COMPLETED,
                analysis_history_id=history.id,
                last_completed_milestone="portfolio_complete",
                current_milestone="portfolio_complete",
            )
            await session.commit()

            response = await get_executions(page=1, page_size=10, db=session)

            self.assertEqual(response.total, 1)
            self.assertEqual(response.items[0].id, execution.id)
            self.assertEqual(response.items[0].status, "완료")
            self.assertEqual(response.items[0].progress, 100)
            self.assertEqual(response.items[0].current_stage, "포트폴리오 결정")
            self.assertEqual(response.items[0].decision, "Buy")

    async def test_engine_info_matches_web_runtime_defaults(self):
        response = await get_engine_info()

        self.assertEqual(response.provider, DEFAULT_CONFIG["llm_provider"])
        self.assertEqual(response.deep_model, DEFAULT_CONFIG["deep_think_llm"])
        self.assertEqual(response.quick_model, DEFAULT_CONFIG["quick_think_llm"])
        self.assertEqual(response.language, "한국어")
        self.assertEqual(response.total_agent_count, 12)
        self.assertEqual(response.cli_total_agent_count, 12)
        self.assertTrue(response.agent_count_matches_cli)
        self.assertTrue(response.supports_korean_summary)
        self.assertIn("포트폴리오 매니저", response.engine_explanation)

    async def test_system_stats_counts_execution_statuses(self):
        async with self.session_factory() as session:
            execution_repo = AnalysisExecutionRepository(session)
            await execution_repo.create(
                execution_key="stats-running",
                thread_id="stats-running",
                ticker="AAPL",
                analysis_date="2026-04-08",
                analysts_json=["market"],
                config_hash="cfg-running",
                graph_version=GRAPH_VERSION,
                checkpoint_schema_version=CHECKPOINT_SCHEMA_VERSION,
                status=STATUS_RUNNING,
                lease_owner="owner-1",
                lease_expires_at=datetime.now() + timedelta(minutes=5),
            )
            await execution_repo.create(
                execution_key="stats-completed",
                thread_id="stats-completed",
                ticker="MSFT",
                analysis_date="2026-04-08",
                analysts_json=["market"],
                config_hash="cfg-completed",
                graph_version=GRAPH_VERSION,
                checkpoint_schema_version=CHECKPOINT_SCHEMA_VERSION,
                status=STATUS_COMPLETED,
            )
            await session.commit()

            response = await get_system_stats(db=session)

            self.assertEqual(response.running_executions, 1)
            self.assertEqual(response.concurrent_runs, 1)
            self.assertEqual(response.completed_executions, 1)
            self.assertEqual(response.total_executions, 2)
            self.assertEqual(response.active_leases, 1)

    async def test_get_executions_uses_next_pending_stage_for_running_items(self):
        async with self.session_factory() as session:
            execution_repo = AnalysisExecutionRepository(session)
            await execution_repo.create(
                execution_key="exec-progress-2",
                thread_id="thread-progress-2",
                ticker="TSLA",
                analysis_date="2026-04-08",
                analysts_json=["market"],
                config_hash="cfg-2",
                graph_version=GRAPH_VERSION,
                checkpoint_schema_version=CHECKPOINT_SCHEMA_VERSION,
                status=STATUS_RUNNING,
                last_completed_milestone="market_complete",
                current_milestone="market_complete",
            )
            await session.commit()

            response = await get_executions(page=1, page_size=10, db=session)

            self.assertEqual(response.items[0].status, "분석 중")
            self.assertEqual(response.items[0].progress, 20)
            self.assertEqual(response.items[0].current_stage, "리서치 토론")

    async def test_running_execution_is_visible_as_soon_as_stream_starts(self):
        service = TradingService()
        service.config = {
            **DEFAULT_CONFIG,
            "language": "한국어",
            "max_risk_discuss_rounds": 1,
        }

        class SlowCompiledGraph:
            def __init__(self):
                self.first_yielded = False

            async def astream(self, input_state, **kwargs):
                yield {"market_report": "done"}
                await asyncio.sleep(60)

            async def aget_state(self, config):
                if not self.first_yielded:
                    self.first_yielded = True
                    return make_snapshot(config["configurable"]["thread_id"], {})
                return make_snapshot(
                    config["configurable"]["thread_id"],
                    {"market_report": "done"},
                    checkpoint_id="cp-1",
                    step=1,
                )

            def aget_state_history(self, config, limit=1):
                async def generator():
                    yield make_snapshot(
                        config["configurable"]["thread_id"],
                        {"market_report": "done"},
                        checkpoint_id="cp-1",
                        step=1,
                    )

                return generator()

        async with self.session_factory() as stream_session:
            fake_graph = SimpleNamespace(
                graph=SlowCompiledGraph(), propagator=Propagator()
            )
            with patch.object(service, "get_graph", return_value=fake_graph):
                generator = service.analyze_stream(
                    "META",
                    "2026-04-08",
                    ["market"],
                    stream_session,
                    request=cast(Request, FakeRequest()),
                    checkpointer=object(),
                )
                first_payload = await anext(generator)

                async with self.session_factory() as query_session:
                    response = await get_executions(
                        page=1, page_size=10, db=query_session
                    )

                self.assertIn('"type": "progress"', first_payload)
                self.assertEqual(response.items[0].ticker, "META")
                self.assertEqual(response.items[0].status, "분석 중")
                self.assertEqual(response.items[0].current_stage, "리서치 토론")

                await generator.aclose()

    async def test_execution_detail_includes_duration_and_summary(self):
        async with self.session_factory() as session:
            execution_repo = AnalysisExecutionRepository(session)
            history_repo = AnalysisHistoryRepository(session)
            history = await history_repo.create(
                ticker="NVDA",
                analysis_date="2026-04-08",
                decision="Buy",
                full_decision="Rating: Buy",
                reports={"market": "market report"},
                research={
                    "investment_plan": "plan",
                    "trader_plan": "trader plan",
                    "summary_report": "요약 보고서",
                },
                risk={"final_decision": "approved"},
            )
            execution = await execution_repo.create(
                execution_key="detail-exec",
                thread_id="detail-thread",
                ticker="NVDA",
                analysis_date="2026-04-08",
                analysts_json=["market", "news"],
                config_hash="cfg-detail",
                graph_version=GRAPH_VERSION,
                checkpoint_schema_version=CHECKPOINT_SCHEMA_VERSION,
                status=STATUS_COMPLETED,
                analysis_history_id=history.id,
                last_completed_milestone="portfolio_complete",
                current_milestone="portfolio_complete",
            )
            await session.commit()

            detail = cast(
                ExecutionDetailResponse,
                await get_execution_detail(
                    execution_id=cast(int, execution.id),
                    db=session,
                ),
            )

            self.assertEqual(detail.id, cast(int, execution.id))
            self.assertEqual(detail.analysts, ["market", "news"])
            self.assertEqual(detail.summary_report, "요약 보고서")
            self.assertGreaterEqual(detail.elapsed_seconds, 0)
            self.assertEqual(detail.decision, "Buy")
            self.assertEqual(detail.workflow_steps, [])

    async def test_finalize_execution_stores_korean_summary_report(self):
        service = TradingService()
        service.config = {
            **DEFAULT_CONFIG,
            "language": "한국어",
        }

        async with self.session_factory() as session:
            execution_repo = AnalysisExecutionRepository(session)
            history_repo = AnalysisHistoryRepository(session)
            execution = await execution_repo.create(
                execution_key="exec-summary-store",
                thread_id="thread-summary-store",
                ticker="NFLX",
                analysis_date="2026-04-08",
                analysts_json=["market"],
                config_hash="cfg-summary-store",
                graph_version=GRAPH_VERSION,
                checkpoint_schema_version=CHECKPOINT_SCHEMA_VERSION,
                status=STATUS_RUNNING,
            )
            await session.commit()

            with (
                patch.object(
                    service,
                    "get_graph",
                    return_value=SimpleNamespace(deep_thinking_llm=MagicMock()),
                ),
                patch(
                    "web_api.main.generate_summary_report",
                    return_value="한국어 요약 보고서",
                ),
            ):
                payload = await service._finalize_execution(
                    execution=execution,
                    chunk=make_final_chunk(),
                    db=session,
                    history_repo=history_repo,
                    execution_repo=execution_repo,
                )

            history = await history_repo.get_by_id(
                cast(int, execution.analysis_history_id)
            )

            self.assertIsNotNone(history)
            history = cast(Any, history)
            self.assertEqual(payload["summary_report"], "한국어 요약 보고서")
            self.assertEqual(history.research["summary_report"], "한국어 요약 보고서")


if __name__ == "__main__":
    unittest.main()
