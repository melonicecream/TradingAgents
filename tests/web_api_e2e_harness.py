"""Deterministic web API harness for browser E2E checks."""

from __future__ import annotations

import os
from types import SimpleNamespace
from typing import Any, cast


os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./data/tradingagents-e2e.db")

from tradingagents.graph.propagation import Propagator
from web_api.main import app, trading_service


def make_snapshot(
    thread_id: str,
    values: dict[str, Any],
    checkpoint_id: str | None = None,
    step: int = 0,
    checkpoint_ns: str = "",
) -> SimpleNamespace:
    configurable: dict[str, Any] = {"thread_id": thread_id}
    if checkpoint_id is not None:
        configurable["checkpoint_id"] = checkpoint_id
        configurable["checkpoint_ns"] = checkpoint_ns
    return SimpleNamespace(
        values=values,
        config={"configurable": configurable},
        metadata={"step": step},
    )


def make_final_chunk() -> dict[str, Any]:
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


class FakeCompiledGraph:
    def __init__(self) -> None:
        self.stream_calls: list[tuple[Any, dict[str, Any]]] = []
        self._state_call_count = 0

    def stream(self, input_state: Any, **kwargs: Any):
        self.stream_calls.append((input_state, kwargs))
        yield {"market_report": "market ready"}
        self._state_call_count = 2
        yield make_final_chunk()
        self._state_call_count = 3

    async def aget_state(self, config: dict[str, Any]) -> SimpleNamespace:
        thread_id = config["configurable"]["thread_id"]
        final_chunk = make_final_chunk()
        snapshots = [
            make_snapshot(thread_id, {}),
            make_snapshot(thread_id, {}),
            make_snapshot(thread_id, {"market_report": "market ready"}),
            make_snapshot(thread_id, final_chunk, checkpoint_id="cp-e2e", step=2),
        ]
        index = min(self._state_call_count, len(snapshots) - 1)
        self._state_call_count += 1
        return snapshots[index]

    def aget_state_history(self, config: dict[str, Any], limit: int = 1):
        thread_id = config["configurable"]["thread_id"]

        async def generator():
            if self._state_call_count == 3:
                yield make_snapshot(
                    thread_id,
                    {"market_report": "market ready"},
                    checkpoint_id="cp-market",
                    step=1,
                )

        return generator()


def install_e2e_graph() -> None:
    fake_graph = SimpleNamespace(graph=FakeCompiledGraph(), propagator=Propagator())
    trading_service._graphs = {}
    trading_service.config = {
        **trading_service.config,
        "language": "한국어",
        "max_risk_discuss_rounds": 1,
    }
    setattr(
        trading_service,
        "get_graph",
        cast(Any, lambda analysts=None, checkpointer=None: fake_graph),
    )


install_e2e_graph()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8001)
