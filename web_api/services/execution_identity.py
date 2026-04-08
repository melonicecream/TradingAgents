"""Helpers for resumable execution identity and compatibility checks."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
from typing import Any, Iterable, cast

from web_api.db.models import AnalysisExecution

GRAPH_VERSION = "web-api-graph-v1"
CHECKPOINT_SCHEMA_VERSION = "checkpoint-schema-v1"

STATUS_PENDING = "pending"
STATUS_RUNNING = "running"
STATUS_RESUMABLE = "resumable"
STATUS_FAILED_TERMINAL = "failed_terminal"
STATUS_COMPLETED = "completed"
STATUS_CANCELLED = "cancelled"

TERMINAL_STATUSES = {
    STATUS_FAILED_TERMINAL,
    STATUS_COMPLETED,
    STATUS_CANCELLED,
}

LEASE_SECONDS = 300


@dataclass(frozen=True)
class ExecutionIdentity:
    """Deterministic identity bundle for one web analysis request."""

    execution_key: str
    config_hash: str
    ticker: str
    analysis_date: str
    analysts: list[str]
    graph_version: str
    checkpoint_schema_version: str


def normalize_ticker(ticker: str) -> str:
    return ticker.strip().upper()


def resolve_analysis_date(
    analysis_date: str | None, now: datetime | None = None
) -> str:
    if analysis_date and analysis_date.strip():
        return analysis_date.strip()
    return (now or datetime.now()).strftime("%Y-%m-%d")


def normalize_analysts(analysts: Iterable[str]) -> list[str]:
    return sorted({item.strip().lower() for item in analysts if item.strip()})


def build_execution_identity(
    ticker: str,
    analysis_date: str | None,
    analysts: Iterable[str],
    config: dict[str, Any],
    *,
    graph_version: str = GRAPH_VERSION,
    checkpoint_schema_version: str = CHECKPOINT_SCHEMA_VERSION,
    now: datetime | None = None,
) -> ExecutionIdentity:
    normalized_ticker = normalize_ticker(ticker)
    resolved_date = resolve_analysis_date(analysis_date, now=now)
    normalized_analysts = normalize_analysts(analysts)

    execution_payload = {
        "ticker": normalized_ticker,
        "analysis_date": resolved_date,
        "analysts": normalized_analysts,
        "llm_provider": config.get("llm_provider"),
        "deep_think_llm": config.get("deep_think_llm"),
        "quick_think_llm": config.get("quick_think_llm"),
        "max_debate_rounds": config.get("max_debate_rounds"),
        "max_risk_discuss_rounds": config.get("max_risk_discuss_rounds"),
        "language": config.get("language"),
        "graph_version": graph_version,
        "checkpoint_schema_version": checkpoint_schema_version,
    }
    config_payload = {
        **execution_payload,
        "backend_url": config.get("backend_url"),
        "google_thinking_level": config.get("google_thinking_level"),
        "openai_reasoning_effort": config.get("openai_reasoning_effort"),
        "anthropic_effort": config.get("anthropic_effort"),
        "data_vendors": config.get("data_vendors"),
        "tool_vendors": config.get("tool_vendors"),
    }

    return ExecutionIdentity(
        execution_key=_sha256_json(execution_payload),
        config_hash=_sha256_json(config_payload),
        ticker=normalized_ticker,
        analysis_date=resolved_date,
        analysts=normalized_analysts,
        graph_version=graph_version,
        checkpoint_schema_version=checkpoint_schema_version,
    )


def is_execution_compatible(
    execution: AnalysisExecution, identity: ExecutionIdentity
) -> bool:
    return (
        cast(str, execution.config_hash) == identity.config_hash
        and cast(str, execution.graph_version) == identity.graph_version
        and cast(str, execution.checkpoint_schema_version)
        == identity.checkpoint_schema_version
    )


def _sha256_json(payload: dict[str, Any]) -> str:
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
