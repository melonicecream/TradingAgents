"""
TradingAgents Web API
FastAPI wrapper for TradingAgents core - zero modifications to core
"""

import asyncio
import json
import os
import sys
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from uuid import uuid4
from typing import Any, AsyncGenerator, Dict, List, Optional, cast

from fastapi import Depends, FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

sys.path.insert(0, str(Path(__file__).parent.parent))

from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.graph.trading_graph import TradingAgentsGraph
from web_api.db.database import DATABASE_URL, bootstrap_checkpointer, get_db, init_db
from web_api.db.models import AnalysisExecution
from web_api.repositories.analysis import AnalysisHistoryRepository
from web_api.repositories.execution import (
    AnalysisCheckpointRepository,
    AnalysisExecutionRepository,
)
from web_api.services.execution_identity import (
    CHECKPOINT_SCHEMA_VERSION,
    GRAPH_VERSION,
    STATUS_COMPLETED,
    STATUS_FAILED_TERMINAL,
    STATUS_PENDING,
    STATUS_RESUMABLE,
    STATUS_RUNNING,
    build_execution_identity,
    is_execution_compatible,
)
from web_api.schemas.analysis import (
    AnalysisHistoryCreate,
    AnalysisHistoryList,
    AnalysisHistoryResponse,
    PaginatedResponse,
)


def build_web_graph_runtime_args(thread_id: str) -> Dict[str, Any]:
    """Build web-only runtime graph args for durable checkpointing."""
    return {
        "durability": "sync",
        "config": {
            "configurable": {
                "thread_id": thread_id,
            }
        },
    }


@asynccontextmanager
async def lifespan(
    app: FastAPI,
    database_url: str | None = DATABASE_URL,
    checkpointer_bootstrap=bootstrap_checkpointer,
    db_initializer=init_db,
):
    """Application lifespan - initialize database on startup."""
    await db_initializer()
    async with checkpointer_bootstrap(database_url) as checkpointer:
        app.state.checkpointer = checkpointer
        try:
            yield
        finally:
            app.state.checkpointer = None


app = FastAPI(
    title="TradingAgents API",
    description="한국어 지원 주식 분석 AI 에이전트 API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class AnalysisRequest(BaseModel):
    ticker: str = Field(..., description="주식 종목 코드 (예: 005930.KS, AAPL)")
    date: str = Field(
        default_factory=lambda: datetime.now().strftime("%Y-%m-%d"),
        description="분석 날짜 (YYYY-MM-DD)",
    )
    analysts: List[str] = Field(
        default=["market", "social", "news", "fundamentals"],
        description="사용할 분석가 유형",
    )


class TradingService:
    """Service layer wrapping TradingAgents core."""

    def __init__(self):
        self.config = DEFAULT_CONFIG.copy()
        self.config["language"] = "한국어"
        self._graphs: Dict[tuple[tuple[str, ...], int | None], TradingAgentsGraph] = {}

    def get_graph(
        self,
        analysts: Optional[List[str]] = None,
        checkpointer: Any | None = None,
    ):
        selected_analysts = tuple(
            analysts or ["market", "social", "news", "fundamentals"]
        )
        cache_key = (selected_analysts, id(checkpointer) if checkpointer else None)
        if cache_key not in self._graphs:
            self._graphs[cache_key] = TradingAgentsGraph(
                selected_analysts=list(selected_analysts),
                config=self.config,
                checkpointer=checkpointer,
            )
        return self._graphs[cache_key]

    async def analyze_stream(
        self,
        ticker: str,
        date: str,
        analysts: Optional[List[str]] = None,
        db: Optional[AsyncSession] = None,
        request: Optional[Request] = None,
        checkpointer: Any | None = None,
    ):
        """Run analysis with SSE streaming and save to database."""
        if db is None:
            raise ValueError("Database session is required for web analysis.")

        normalized_analysts = self._normalize_requested_analysts(analysts)
        execution_repo = AnalysisExecutionRepository(db)
        checkpoint_repo = AnalysisCheckpointRepository(db)
        history_repo = AnalysisHistoryRepository(db)
        execution_owner = str(uuid4())
        execution: AnalysisExecution | None = None
        try:
            (
                execution,
                graph,
                stream_input,
                runtime_args,
            ) = await self._prepare_execution(
                ticker=ticker,
                date=date,
                analysts=normalized_analysts,
                db=db,
                execution_repo=execution_repo,
                checkpointer=checkpointer,
                execution_owner=execution_owner,
            )

            latest_snapshot = await self._get_latest_snapshot(graph, runtime_args)
            latest_state = self._snapshot_values(latest_snapshot)
            if latest_state.get("final_trade_decision"):
                final_data = await self._finalize_execution(
                    execution=execution,
                    chunk=latest_state,
                    db=db,
                    history_repo=history_repo,
                    execution_repo=execution_repo,
                )
                yield f"data: {json.dumps(final_data, ensure_ascii=False)}\n\n"
                return

            agent_status = {}
            prev_chunk = {}
            current_step = 0
            total_steps = len(normalized_analysts) + 8

            final_result = None

            for chunk in cast(Any, graph.graph).stream(stream_input, **runtime_args):
                if request is not None and await request.is_disconnected():
                    raise asyncio.CancelledError(
                        "Client disconnected during analysis stream."
                    )

                current_step += 1
                progress_data = self._extract_progress(
                    chunk, prev_chunk, agent_status, current_step, total_steps
                )
                prev_chunk = chunk.copy()
                final_result = chunk

                snapshot = await self._get_latest_snapshot(graph, runtime_args)
                await self._record_milestones(
                    execution=execution,
                    selected_analysts=normalized_analysts,
                    chunk=chunk,
                    snapshot=snapshot,
                    db=db,
                    execution_repo=execution_repo,
                    checkpoint_repo=checkpoint_repo,
                )

                yield f"data: {json.dumps(progress_data, ensure_ascii=False)}\n\n"
                await asyncio.sleep(0.01)

            final_state = final_result or latest_state
            final_data = await self._finalize_execution(
                execution=execution,
                chunk=final_state,
                db=db,
                history_repo=history_repo,
                execution_repo=execution_repo,
            )
            yield f"data: {json.dumps(final_data, ensure_ascii=False)}\n\n"

        except asyncio.CancelledError as exc:
            if execution is not None:
                await self._mark_execution_interrupted(
                    execution=execution,
                    error=exc,
                    status=STATUS_RESUMABLE,
                    db=db,
                    execution_repo=execution_repo,
                    execution_owner=execution_owner,
                )
            raise
        except Exception as e:
            error_status = (
                STATUS_RESUMABLE
                if self._is_resumable_exception(e)
                else STATUS_FAILED_TERMINAL
            )
            last_completed_milestone = None
            if execution is not None:
                await self._mark_execution_interrupted(
                    execution=execution,
                    error=e,
                    status=error_status,
                    db=db,
                    execution_repo=execution_repo,
                    execution_owner=execution_owner,
                )
                last_completed_milestone = cast(
                    Optional[str], execution.last_completed_milestone
                )
            error_data = {
                "type": "error",
                "error": str(e),
                "message": "Analysis error occurred.",
                "execution_id": cast(Optional[int], execution.id)
                if execution
                else None,
                "status": error_status,
                "last_completed_milestone": last_completed_milestone,
            }
            yield f"data: {json.dumps(error_data, ensure_ascii=False)}\n\n"

    async def _prepare_execution(
        self,
        ticker: str,
        date: str,
        analysts: List[str],
        db: AsyncSession,
        execution_repo: AnalysisExecutionRepository,
        checkpointer: Any | None,
        execution_owner: str,
    ) -> tuple[
        AnalysisExecution, TradingAgentsGraph, Dict[str, Any] | None, Dict[str, Any]
    ]:
        identity = build_execution_identity(
            ticker=ticker,
            analysis_date=date,
            analysts=analysts,
            config=self.config,
            graph_version=GRAPH_VERSION,
            checkpoint_schema_version=CHECKPOINT_SCHEMA_VERSION,
        )
        existing_execution = await execution_repo.get_by_execution_key(
            identity.execution_key
        )
        execution = existing_execution

        if execution is None or not is_execution_compatible(execution, identity):
            execution = await execution_repo.create(
                execution_key=identity.execution_key,
                thread_id=str(uuid4()),
                ticker=identity.ticker,
                analysis_date=identity.analysis_date,
                analysts_json=analysts,
                config_hash=identity.config_hash,
                graph_version=identity.graph_version,
                checkpoint_schema_version=identity.checkpoint_schema_version,
                status=STATUS_PENDING,
            )
            await db.commit()

        graph = self.get_graph(analysts, checkpointer=checkpointer)
        runtime_args = graph.propagator.get_graph_args(
            runtime_overrides=build_web_graph_runtime_args(
                cast(str, execution.thread_id)
            )
        )
        latest_snapshot = await self._get_latest_snapshot(graph, runtime_args)
        latest_state = self._snapshot_values(latest_snapshot)

        if latest_state.get("final_trade_decision"):
            return execution, graph, None, runtime_args

        lease_acquired = await execution_repo.mark_running(
            execution,
            execution_owner,
            now=datetime.now(),
        )
        if not lease_acquired:
            raise RuntimeError(
                "Another analysis worker is already running this execution."
            )

        if latest_state:
            current_resume_count = cast(int, execution.resume_count or 0)
            setattr(execution, "resume_count", current_resume_count + 1)
            setattr(execution, "status", STATUS_RUNNING)
            setattr(
                execution,
                "current_milestone",
                cast(Optional[str], execution.last_completed_milestone),
            )
            setattr(execution, "last_error_type", None)
            setattr(execution, "last_error_message", None)
            db.add(execution)
            await db.commit()
            return execution, graph, None, runtime_args

        setattr(execution, "last_error_type", None)
        setattr(execution, "last_error_message", None)
        db.add(execution)
        await db.commit()
        init_state = graph.propagator.create_initial_state(
            identity.ticker, identity.analysis_date
        )
        return execution, graph, init_state, runtime_args

    async def _get_latest_snapshot(
        self, graph: TradingAgentsGraph, runtime_args: Dict[str, Any]
    ) -> Any | None:
        config = runtime_args.get("config", {})
        snapshot = await cast(Any, graph.graph).aget_state(config)
        snapshot_config = getattr(snapshot, "config", {}) or {}
        configurable = (
            snapshot_config.get("configurable", {}) if snapshot_config else {}
        )
        if configurable.get("checkpoint_id"):
            return snapshot

        history = cast(Any, graph.graph).aget_state_history(config, limit=1)
        async for prior_snapshot in history:
            return prior_snapshot
        return snapshot

    def _snapshot_values(self, snapshot: Any | None) -> Dict[str, Any]:
        if snapshot is None:
            return {}
        values = getattr(snapshot, "values", None)
        if isinstance(values, dict):
            return values
        return {}

    async def _record_milestones(
        self,
        execution: AnalysisExecution,
        selected_analysts: List[str],
        chunk: Dict[str, Any],
        snapshot: Any | None,
        db: AsyncSession,
        execution_repo: AnalysisExecutionRepository,
        checkpoint_repo: AnalysisCheckpointRepository,
    ) -> None:
        snapshot_config = getattr(snapshot, "config", {}) or {}
        configurable = (
            snapshot_config.get("configurable", {}) if snapshot_config else {}
        )
        checkpoint_id = configurable.get("checkpoint_id")
        if not checkpoint_id:
            return

        checkpoint_ns = configurable.get("checkpoint_ns", "")
        metadata = getattr(snapshot, "metadata", {}) or {}
        step_index = cast(Optional[int], metadata.get("step")) or 0

        milestones = self._derive_milestones(chunk, selected_analysts)
        execution_id = cast(int, execution.id)
        latest_milestone = cast(Optional[str], execution.last_completed_milestone)
        for milestone, summary in milestones:
            existing = await checkpoint_repo.get_by_execution_and_milestone(
                execution_id, milestone
            )
            if existing is not None:
                latest_milestone = milestone
                continue

            await checkpoint_repo.create(
                execution_id=execution_id,
                milestone=milestone,
                checkpoint_id=checkpoint_id,
                checkpoint_ns=checkpoint_ns,
                step_index=step_index,
                summary_json=summary,
                status="completed",
            )
            latest_milestone = milestone

        if latest_milestone is not None:
            setattr(execution, "last_completed_milestone", latest_milestone)
            setattr(execution, "current_milestone", latest_milestone)
            db.add(execution)
            await db.commit()
            await db.refresh(execution)

    def _derive_milestones(
        self, chunk: Dict[str, Any], selected_analysts: List[str]
    ) -> List[tuple[str, Dict[str, Any]]]:
        milestones: List[tuple[str, Dict[str, Any]]] = []
        analyst_keys = {
            "market": "market_report",
            "social": "sentiment_report",
            "news": "news_report",
            "fundamentals": "fundamentals_report",
        }
        for analyst in selected_analysts:
            report_key = analyst_keys.get(analyst)
            if report_key and chunk.get(report_key):
                milestones.append(
                    (
                        f"{analyst}_complete",
                        {"report_key": report_key, "agent": analyst},
                    )
                )

        if chunk.get("investment_plan"):
            milestones.append(
                (
                    "research_complete",
                    {"investment_plan": bool(chunk.get("investment_plan"))},
                )
            )
        if chunk.get("trader_investment_plan"):
            milestones.append(
                (
                    "trader_complete",
                    {"trader_plan": bool(chunk.get("trader_investment_plan"))},
                )
            )

        risk_state = chunk.get("risk_debate_state", {})
        if self._is_risk_complete(risk_state) and not chunk.get("final_trade_decision"):
            milestones.append(
                (
                    "risk_complete",
                    {"risk_count": risk_state.get("count", 0)},
                )
            )
        if chunk.get("final_trade_decision"):
            milestones.append(
                (
                    "portfolio_complete",
                    {"decision": chunk.get("final_trade_decision", "")},
                )
            )
        return milestones

    def _is_risk_complete(self, risk_state: Dict[str, Any]) -> bool:
        max_rounds = cast(int, self.config.get("max_risk_discuss_rounds", 1))
        return cast(int, risk_state.get("count", 0)) >= 3 * max_rounds

    async def _mark_execution_interrupted(
        self,
        execution: AnalysisExecution,
        error: BaseException,
        status: str,
        db: AsyncSession,
        execution_repo: AnalysisExecutionRepository,
        execution_owner: str,
    ) -> None:
        setattr(execution, "status", status)
        setattr(execution, "last_error_type", type(error).__name__)
        setattr(execution, "last_error_message", str(error))
        setattr(execution, "retry_count", cast(int, execution.retry_count or 0) + 1)
        db.add(execution)
        await db.commit()
        await execution_repo.release_lease(execution, execution_owner)
        await db.commit()
        await db.refresh(execution)

    async def _finalize_execution(
        self,
        execution: AnalysisExecution,
        chunk: Dict[str, Any],
        db: AsyncSession,
        history_repo: AnalysisHistoryRepository,
        execution_repo: AnalysisExecutionRepository,
    ) -> Dict[str, Any]:
        analysis_history_id = cast(Optional[int], execution.analysis_history_id)
        if analysis_history_id is None:
            full_decision = chunk.get("final_trade_decision", "")
            simple_decision = self._parse_decision_rating(full_decision)
            history = await history_repo.create(
                ticker=cast(str, execution.ticker),
                analysis_date=cast(str, execution.analysis_date),
                decision=simple_decision,
                full_decision=full_decision,
                reports={
                    "market": chunk.get("market_report", ""),
                    "sentiment": chunk.get("sentiment_report", ""),
                    "news": chunk.get("news_report", ""),
                    "fundamentals": chunk.get("fundamentals_report", ""),
                },
                research={
                    "investment_plan": chunk.get("investment_plan", ""),
                    "trader_plan": chunk.get("trader_investment_plan", ""),
                    "bull_history": chunk.get("investment_debate_state", {}).get(
                        "bull_history", ""
                    ),
                    "bear_history": chunk.get("investment_debate_state", {}).get(
                        "bear_history", ""
                    ),
                },
                risk={
                    "aggressive": chunk.get("risk_debate_state", {}).get(
                        "aggressive_history", ""
                    ),
                    "conservative": chunk.get("risk_debate_state", {}).get(
                        "conservative_history", ""
                    ),
                    "neutral": chunk.get("risk_debate_state", {}).get(
                        "neutral_history", ""
                    ),
                    "final_decision": chunk.get("risk_debate_state", {}).get(
                        "judge_decision", ""
                    ),
                },
            )
            setattr(execution, "analysis_history_id", cast(int, history.id))

        setattr(execution, "status", STATUS_COMPLETED)
        setattr(execution, "current_milestone", "portfolio_complete")
        setattr(execution, "last_completed_milestone", "portfolio_complete")
        setattr(execution, "last_error_type", None)
        setattr(execution, "last_error_message", None)
        db.add(execution)
        await db.commit()
        lease_owner = cast(Optional[str], execution.lease_owner)
        if lease_owner is not None:
            await execution_repo.release_lease(execution, lease_owner)
            await db.commit()
        await db.refresh(execution)
        return {
            **self._extract_final_result(chunk),
            "execution_id": cast(int, execution.id),
            "status": STATUS_COMPLETED,
            "last_completed_milestone": cast(
                Optional[str], execution.last_completed_milestone
            ),
            "thread_id": cast(str, execution.thread_id),
        }

    def _normalize_requested_analysts(self, analysts: Optional[List[str]]) -> List[str]:
        ordered: List[str] = []
        seen: set[str] = set()
        for analyst in analysts or ["market", "social", "news", "fundamentals"]:
            normalized = analyst.strip().lower()
            if normalized and normalized not in seen:
                seen.add(normalized)
                ordered.append(normalized)
        return ordered

    def _is_resumable_exception(self, error: BaseException) -> bool:
        if isinstance(error, (TimeoutError, ConnectionError)):
            return True
        message = str(error).lower()
        return any(
            token in message
            for token in [
                "429",
                "rate limit",
                "freeusagelimiterror",
                "temporarily unavailable",
                "connection reset",
            ]
        )

    def _extract_progress(
        self, chunk: Dict, prev_chunk: Dict, agent_status: Dict, step: int, total: int
    ) -> Dict:
        """Extract progress by comparing chunks."""
        current_agent = None

        if chunk.get("market_report") and not prev_chunk.get("market_report"):
            agent_status["시장 분석가"] = "completed"
            current_agent = "시장 분석가"

        if chunk.get("sentiment_report") and not prev_chunk.get("sentiment_report"):
            agent_status["소셜 미디어 분석가"] = "completed"
            current_agent = "소셜 미디어 분석가"

        if chunk.get("news_report") and not prev_chunk.get("news_report"):
            agent_status["뉴스 분석가"] = "completed"
            current_agent = "뉴스 분석가"

        if chunk.get("fundamentals_report") and not prev_chunk.get(
            "fundamentals_report"
        ):
            agent_status["펀더멘털 분석가"] = "completed"
            current_agent = "펀더멘털 분석가"

        inv_state = chunk.get("investment_debate_state", {})
        prev_inv = prev_chunk.get("investment_debate_state", {})
        if inv_state.get("bull_history") and inv_state.get(
            "bull_history"
        ) != prev_inv.get("bull_history"):
            agent_status["공시 투자 연구원"] = "completed"
            current_agent = "공시 투자 연구원"
        if inv_state.get("bear_history") and inv_state.get(
            "bear_history"
        ) != prev_inv.get("bear_history"):
            agent_status["비관적 연구원"] = "completed"
            current_agent = "비관적 연구원"

        if chunk.get("investment_plan") and not prev_chunk.get("investment_plan"):
            agent_status["리서치 매니저"] = "completed"
            current_agent = "리서치 매니저"

        if chunk.get("trader_investment_plan") and not prev_chunk.get(
            "trader_investment_plan"
        ):
            agent_status["트레이더"] = "completed"
            current_agent = "트레이더"

        risk_state = chunk.get("risk_debate_state", {})
        prev_risk = prev_chunk.get("risk_debate_state", {})
        if risk_state.get("aggressive_history") and risk_state.get(
            "aggressive_history"
        ) != prev_risk.get("aggressive_history"):
            agent_status["공격적 리스크 분석가"] = "completed"
            current_agent = "공격적 리스크 분석가"
        if risk_state.get("conservative_history") and risk_state.get(
            "conservative_history"
        ) != prev_risk.get("conservative_history"):
            agent_status["보수적 리스크 분석가"] = "completed"
            current_agent = "보수적 리스크 분석가"
        if risk_state.get("neutral_history") and risk_state.get(
            "neutral_history"
        ) != prev_risk.get("neutral_history"):
            agent_status["중립적 리스크 분석가"] = "completed"
            current_agent = "중립적 리스크 분석가"

        if chunk.get("final_trade_decision") and not prev_chunk.get(
            "final_trade_decision"
        ):
            agent_status["포트폴리오 매니저"] = "completed"
            current_agent = "포트폴리오 매니저"

        reports = {}
        for key in [
            "market_report",
            "sentiment_report",
            "news_report",
            "fundamentals_report",
        ]:
            if chunk.get(key):
                reports[key] = "completed"

        return {
            "type": "progress",
            "step": step,
            "total": total,
            "progress": min(step / total * 100, 99),
            "agent": current_agent,
            "agent_status": agent_status,
            "reports": reports,
            "timestamp": datetime.now().isoformat(),
        }

    def _extract_final_result(self, chunk: Dict) -> Dict:
        full_decision = chunk.get("final_trade_decision", "")
        simple_decision = self._parse_decision_rating(full_decision)

        return {
            "type": "complete",
            "progress": 100,
            "decision": simple_decision,
            "full_decision": full_decision,
            "reports": {
                "market": chunk.get("market_report", ""),
                "sentiment": chunk.get("sentiment_report", ""),
                "news": chunk.get("news_report", ""),
                "fundamentals": chunk.get("fundamentals_report", ""),
            },
            "research": {
                "investment_plan": chunk.get("investment_plan", ""),
                "trader_plan": chunk.get("trader_investment_plan", ""),
                "bull_history": chunk.get("investment_debate_state", {}).get(
                    "bull_history", ""
                ),
                "bear_history": chunk.get("investment_debate_state", {}).get(
                    "bear_history", ""
                ),
            },
            "risk": {
                "aggressive": chunk.get("risk_debate_state", {}).get(
                    "aggressive_history", ""
                ),
                "conservative": chunk.get("risk_debate_state", {}).get(
                    "conservative_history", ""
                ),
                "neutral": chunk.get("risk_debate_state", {}).get(
                    "neutral_history", ""
                ),
                "final_decision": chunk.get("risk_debate_state", {}).get(
                    "judge_decision", ""
                ),
            },
            "timestamp": datetime.now().isoformat(),
        }

    def _parse_decision_rating(self, full_decision: str) -> str:
        import re

        patterns = [
            r"Rating:\s*(Buy|Overweight|Hold|Underweight|Sell)",
            r"\*\*Rating:\*\*\s*(Buy|Overweight|Hold|Underweight|Sell)",
            r"\*\*(Buy|Overweight|Hold|Underweight|Sell)\*\*",
            r"^(Buy|Overweight|Hold|Underweight|Sell)$",
        ]

        for pattern in patterns:
            match = re.search(pattern, full_decision, re.IGNORECASE | re.MULTILINE)
            if match:
                return match.group(1).capitalize()

        return "Hold"

    async def _save_analysis(
        self, ticker: str, date: str, chunk: Dict, db: AsyncSession
    ):
        """Save analysis result to database."""
        try:
            repo = AnalysisHistoryRepository(db)
            full_decision = chunk.get("final_trade_decision", "")
            simple_decision = self._parse_decision_rating(full_decision)

            await repo.create(
                ticker=ticker.upper(),
                analysis_date=date,
                decision=simple_decision,
                full_decision=full_decision,
                reports={
                    "market": chunk.get("market_report", ""),
                    "sentiment": chunk.get("sentiment_report", ""),
                    "news": chunk.get("news_report", ""),
                    "fundamentals": chunk.get("fundamentals_report", ""),
                },
                research={
                    "investment_plan": chunk.get("investment_plan", ""),
                    "trader_plan": chunk.get("trader_investment_plan", ""),
                    "bull_history": chunk.get("investment_debate_state", {}).get(
                        "bull_history", ""
                    ),
                    "bear_history": chunk.get("investment_debate_state", {}).get(
                        "bear_history", ""
                    ),
                },
                risk={
                    "aggressive": chunk.get("risk_debate_state", {}).get(
                        "aggressive_history", ""
                    ),
                    "conservative": chunk.get("risk_debate_state", {}).get(
                        "conservative_history", ""
                    ),
                    "neutral": chunk.get("risk_debate_state", {}).get(
                        "neutral_history", ""
                    ),
                    "final_decision": chunk.get("risk_debate_state", {}).get(
                        "judge_decision", ""
                    ),
                },
            )
            await db.commit()
        except Exception as e:
            await db.rollback()
            print(f"Failed to save analysis: {e}")


def _set_custom_api_key_environment() -> None:
    provider = os.getenv("LLM_PROVIDER", "").strip().lower()
    custom_api_key = os.getenv("CUSTOM_API_KEY", "").strip()

    if not provider or not custom_api_key:
        return

    env_var = {
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
    }.get(provider)

    if env_var and not os.getenv(env_var):
        os.environ[env_var] = custom_api_key


_set_custom_api_key_environment()


trading_service = TradingService()


@app.get("/")
async def root():
    return {
        "message": "TradingAgents API",
        "version": "1.0.0",
        "language": "한국어",
        "docs": "/docs",
        "features": ["real-time analysis", "history tracking", "korean UI"],
    }


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "language": "한국어",
    }


@app.get("/analyze/{ticker}")
async def analyze_stock(
    request: Request,
    ticker: str,
    date: Optional[str] = None,
    analysts: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """Analyze stock with SSE streaming and save to history."""
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")

    analyst_list = (
        [a.strip() for a in analysts.split(",") if a.strip()]
        if analysts
        else ["market", "social", "news", "fundamentals"]
    )

    return StreamingResponse(
        trading_service.analyze_stream(
            ticker,
            date,
            analyst_list,
            db,
            request=request,
            checkpointer=request.app.state.checkpointer,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# ========== History API Endpoints ==========


@app.get("/history", response_model=PaginatedResponse)
async def get_history(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Get all analysis history with pagination."""
    repo = AnalysisHistoryRepository(db)
    skip = (page - 1) * page_size

    items = await repo.get_all(
        skip=skip,
        limit=page_size,
        order_by=repo.model.created_at.desc(),
    )
    items = cast(List[AnalysisHistoryResponse], list(items))
    total = await repo.count()
    pages = (total + page_size - 1) // page_size

    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@app.get("/history/{ticker}", response_model=PaginatedResponse)
async def get_ticker_history(
    ticker: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Get analysis history for specific ticker."""
    repo = AnalysisHistoryRepository(db)
    skip = (page - 1) * page_size

    items = await repo.get_by_ticker(ticker.upper(), skip=skip, limit=page_size)
    items = cast(List[AnalysisHistoryResponse], list(items))

    # Count for this ticker
    all_items = await repo.get_by_ticker(ticker.upper(), skip=0, limit=10000)
    total = len(all_items)
    pages = (total + page_size - 1) // page_size

    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@app.get("/history/{ticker}/latest", response_model=AnalysisHistoryResponse)
async def get_latest_analysis(
    ticker: str,
    db: AsyncSession = Depends(get_db),
):
    """Get latest analysis for a ticker."""
    repo = AnalysisHistoryRepository(db)
    result = await repo.get_latest_by_ticker(ticker.upper())

    if not result:
        return {"error": "No analysis found for this ticker"}

    return result


@app.get("/analysts")
async def get_analysts():
    """Get available analyst types."""
    return {
        "analysts": [
            {
                "id": "market",
                "name": "시장 분석가",
                "description": "기술적 지표 및 시장 동향 분석",
            },
            {"id": "social", "name": "소셜 미디어", "description": "감성 분석"},
            {
                "id": "news",
                "name": "뉴스 분석가",
                "description": "뉴스 및 매크로 경제 분석",
            },
            {
                "id": "fundamentals",
                "name": "펀더멘털",
                "description": "재무제표 및 기업 가치 분석",
            },
        ]
    }


@app.get("/decisions")
async def get_decision_types():
    """Get possible decision types."""
    return {
        "decisions": [
            {"value": "Buy", "label": "매수", "color": "#22c55e"},
            {"value": "Overweight", "label": "비중 확대", "color": "#84cc16"},
            {"value": "Hold", "label": "보유", "color": "#eab308"},
            {"value": "Underweight", "label": "비중 축소", "color": "#f97316"},
            {"value": "Sell", "label": "매도", "color": "#ef4444"},
        ]
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
