import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import cast
from unittest.mock import patch

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.graph.propagation import Propagator
from web_api.db.database import Base
from web_api.db.models import AnalysisCheckpoint, AnalysisExecution, AnalysisHistory
from web_api.main import TradingService
from web_api.services.execution_identity import (
    CHECKPOINT_SCHEMA_VERSION,
    GRAPH_VERSION,
    STATUS_COMPLETED,
    STATUS_RESUMABLE,
    build_execution_identity,
)


class FakeRequest:
    def __init__(self, disconnected: bool = False):
        self._disconnected = disconnected

    async def is_disconnected(self) -> bool:
        return self._disconnected


def make_snapshot(
    thread_id: str,
    values: dict,
    checkpoint_id: str | None = None,
    step: int = 0,
    checkpoint_ns: str = "",
):
    configurable = {"thread_id": thread_id}
    if checkpoint_id is not None:
        configurable["checkpoint_id"] = checkpoint_id
        configurable["checkpoint_ns"] = checkpoint_ns
    return SimpleNamespace(
        values=values,
        config={"configurable": configurable},
        metadata={"step": step},
    )


class FakeCompiledGraph:
    def __init__(
        self, snapshots, history_snapshots=None, chunks=None, stream_error=None
    ):
        self.snapshots = list(snapshots)
        self.history_snapshots = list(history_snapshots or [])
        self.chunks = list(chunks or [])
        self.stream_error = stream_error
        self.state_call_count = 0
        self.history_call_count = 0
        self.stream_calls = []

    def stream(self, input_state, **kwargs):
        self.stream_calls.append((input_state, kwargs))
        for chunk in self.chunks:
            yield chunk
        if self.stream_error is not None:
            raise self.stream_error

    async def astream(self, input_state, **kwargs):
        self.stream_calls.append((input_state, kwargs))
        for chunk in self.chunks:
            yield chunk
        if self.stream_error is not None:
            raise self.stream_error

    async def aget_state(self, config):
        if not self.snapshots:
            return make_snapshot(config["configurable"]["thread_id"], {})
        index = min(self.state_call_count, len(self.snapshots) - 1)
        self.state_call_count += 1
        return self.snapshots[index]

    def aget_state_history(self, config, limit=1):
        async def generator():
            if not self.history_snapshots:
                return
            index = min(self.history_call_count, len(self.history_snapshots) - 1)
            snapshot = self.history_snapshots[index]
            self.history_call_count += 1
            if snapshot is not None:
                yield snapshot

        return generator()


def make_final_chunk():
    return {
        "market_report": "market ready",
        "investment_plan": "research plan",
        "trader_investment_plan": "trader plan",
        "investment_debate_state": {"bull_history": "bull", "bear_history": "bear"},
        "risk_debate_state": {
            "count": 3,
            "aggressive_history": "agg",
            "conservative_history": "cons",
            "neutral_history": "neu",
            "judge_decision": "approved",
        },
        "final_trade_decision": "Rating: Buy",
    }


class WebApiExecutionLifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        db_path = Path(self.tmpdir.name) / "web-api-lifecycle.db"
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

    async def test_fresh_run_persists_milestones_and_finalizes_once(self):
        service = TradingService()
        service.config = {
            **DEFAULT_CONFIG,
            "language": "한국어",
            "max_risk_discuss_rounds": 1,
        }
        initial_empty = make_snapshot("thread-fresh", {})
        fallback_market = make_snapshot(
            "thread-fresh",
            {"market_report": "market ready"},
            checkpoint_id="cp-1",
            step=1,
        )
        final_chunk = make_final_chunk()
        final_snapshot = make_snapshot(
            "thread-fresh",
            final_chunk,
            checkpoint_id="cp-2",
            step=2,
        )
        fake_runtime = FakeCompiledGraph(
            snapshots=[
                initial_empty,
                initial_empty,
                make_snapshot("thread-fresh", {"market_report": "market ready"}),
                final_snapshot,
            ],
            history_snapshots=[None, None, fallback_market],
            chunks=[{"market_report": "market ready"}, final_chunk],
        )
        fake_graph = SimpleNamespace(graph=fake_runtime, propagator=Propagator())

        async with self.session_factory() as session:
            with patch.object(service, "get_graph", return_value=fake_graph):
                events = [
                    payload
                    async for payload in service.analyze_stream(
                        "NVDA",
                        "2026-04-08",
                        ["market"],
                        session,
                        request=cast(Request, FakeRequest()),
                        checkpointer=object(),
                    )
                ]

            execution = await self._load_single_execution(session)
            history_rows = await self._load_history_rows(session)
            checkpoints = await self._load_checkpoints(session)

        complete_payload = self._decode_sse(events[-1])
        self.assertEqual(complete_payload["type"], "complete")
        self.assertEqual(complete_payload["status"], STATUS_COMPLETED)
        self.assertEqual(execution.status, STATUS_COMPLETED)
        self.assertEqual(execution.last_completed_milestone, "portfolio_complete")
        self.assertEqual(len(history_rows), 1)
        self.assertEqual(len(checkpoints), 4)
        self.assertEqual(
            [checkpoint.milestone for checkpoint in checkpoints],
            [
                "market_complete",
                "research_complete",
                "trader_complete",
                "portfolio_complete",
            ],
        )
        self.assertEqual(fake_runtime.history_call_count, 3)

    async def test_failure_then_resume_reuses_thread_and_none_input(self):
        service = TradingService()
        service.config = {
            **DEFAULT_CONFIG,
            "language": "한국어",
            "max_risk_discuss_rounds": 1,
        }
        first_runtime = FakeCompiledGraph(
            snapshots=[
                make_snapshot("thread-resume", {}),
                make_snapshot("thread-resume", {}),
                make_snapshot(
                    "thread-resume",
                    {"market_report": "market ready"},
                    checkpoint_id="cp-1",
                    step=1,
                ),
            ],
            history_snapshots=[None, None, None],
            chunks=[{"market_report": "market ready"}],
            stream_error=RuntimeError("429 rate limit exceeded"),
        )
        resume_final = make_final_chunk()
        second_runtime = FakeCompiledGraph(
            snapshots=[
                make_snapshot(
                    "thread-resume",
                    {"market_report": "market ready"},
                    checkpoint_id="cp-1",
                    step=1,
                ),
                make_snapshot(
                    "thread-resume",
                    {"market_report": "market ready"},
                    checkpoint_id="cp-1",
                    step=1,
                ),
                make_snapshot(
                    "thread-resume",
                    resume_final,
                    checkpoint_id="cp-2",
                    step=2,
                ),
            ],
            chunks=[resume_final],
        )

        fake_graph_one = SimpleNamespace(graph=first_runtime, propagator=Propagator())
        fake_graph_two = SimpleNamespace(graph=second_runtime, propagator=Propagator())

        async with self.session_factory() as session:
            with patch.object(
                service, "get_graph", side_effect=[fake_graph_one, fake_graph_two]
            ):
                first_events = [
                    payload
                    async for payload in service.analyze_stream(
                        "AAPL",
                        "2026-04-08",
                        ["market"],
                        session,
                        request=cast(Request, FakeRequest()),
                        checkpointer=object(),
                    )
                ]

                execution_after_failure = await self._load_single_execution(session)
                failed_thread_id = execution_after_failure.thread_id
                failed_execution_id = execution_after_failure.id
                failed_status = execution_after_failure.status
                failed_milestone = execution_after_failure.last_completed_milestone

                second_events = [
                    payload
                    async for payload in service.analyze_stream(
                        "AAPL",
                        "2026-04-08",
                        ["market"],
                        session,
                        request=cast(Request, FakeRequest()),
                        checkpointer=object(),
                    )
                ]

                execution_after_resume = await self._load_single_execution(session)
                history_rows = await self._load_history_rows(session)

        error_payload = self._decode_sse(first_events[-1])
        complete_payload = self._decode_sse(second_events[-1])
        self.assertEqual(error_payload["status"], STATUS_RESUMABLE)
        self.assertEqual(error_payload["last_completed_milestone"], "market_complete")
        self.assertEqual(failed_status, STATUS_RESUMABLE)
        self.assertEqual(failed_milestone, "market_complete")
        self.assertEqual(execution_after_resume.status, STATUS_COMPLETED)
        self.assertEqual(execution_after_resume.id, failed_execution_id)
        self.assertEqual(execution_after_resume.thread_id, failed_thread_id)
        self.assertIsNone(second_runtime.stream_calls[0][0])
        self.assertEqual(complete_payload["status"], STATUS_COMPLETED)
        self.assertEqual(len(history_rows), 1)

    async def test_completed_checkpoint_short_circuits_without_stream(self):
        service = TradingService()
        service.config = {
            **DEFAULT_CONFIG,
            "language": "한국어",
            "max_risk_discuss_rounds": 1,
        }
        identity = build_execution_identity(
            ticker="MSFT",
            analysis_date="2026-04-08",
            analysts=["market"],
            config=service.config,
            graph_version=GRAPH_VERSION,
            checkpoint_schema_version=CHECKPOINT_SCHEMA_VERSION,
        )
        completed_snapshot = make_snapshot(
            "thread-complete",
            make_final_chunk(),
            checkpoint_id="cp-finished",
            step=5,
        )
        fake_runtime = FakeCompiledGraph(
            snapshots=[completed_snapshot, completed_snapshot],
            chunks=[],
        )
        fake_graph = SimpleNamespace(graph=fake_runtime, propagator=Propagator())

        async with self.session_factory() as session:
            execution = AnalysisExecution(
                execution_key=identity.execution_key,
                thread_id="thread-complete",
                ticker=identity.ticker,
                analysis_date=identity.analysis_date,
                analysts_json=["market"],
                config_hash=identity.config_hash,
                graph_version=identity.graph_version,
                checkpoint_schema_version=identity.checkpoint_schema_version,
                status=STATUS_COMPLETED,
            )
            session.add(execution)
            await session.commit()

            with patch.object(service, "get_graph", return_value=fake_graph):
                events = [
                    payload
                    async for payload in service.analyze_stream(
                        "MSFT",
                        "2026-04-08",
                        ["market"],
                        session,
                        request=cast(Request, FakeRequest()),
                        checkpointer=object(),
                    )
                ]

            refreshed_execution = await self._load_single_execution(session)
            history_rows = await self._load_history_rows(session)

        complete_payload = self._decode_sse(events[-1])
        self.assertEqual(complete_payload["status"], STATUS_COMPLETED)
        self.assertEqual(refreshed_execution.status, STATUS_COMPLETED)
        self.assertEqual(len(fake_runtime.stream_calls), 0)
        self.assertEqual(len(history_rows), 1)

    async def _load_single_execution(self, session: AsyncSession) -> AnalysisExecution:
        result = await session.execute(select(AnalysisExecution))
        return result.scalar_one()

    async def _load_checkpoints(self, session: AsyncSession):
        result = await session.execute(
            select(AnalysisCheckpoint).order_by(AnalysisCheckpoint.id.asc())
        )
        return list(result.scalars().all())

    async def _load_history_rows(self, session: AsyncSession):
        result = await session.execute(
            select(AnalysisHistory).order_by(AnalysisHistory.id.asc())
        )
        return list(result.scalars().all())

    def _decode_sse(self, payload: str):
        self.assertTrue(payload.startswith("data: "))
        return json.loads(payload.removeprefix("data: ").strip())


if __name__ == "__main__":
    unittest.main()
