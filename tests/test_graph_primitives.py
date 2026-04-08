import unittest
from types import SimpleNamespace
from typing import cast

from langchain_openai import ChatOpenAI
from tradingagents.agents.utils.agent_states import (
    AgentState,
    InvestDebateState,
    RiskDebateState,
)
from tradingagents.graph.conditional_logic import ConditionalLogic
from tradingagents.graph.propagation import Propagator
from tradingagents.graph.reflection import Reflector
from tradingagents.graph.signal_processing import SignalProcessor


class FakeLLM:
    def __init__(self, content):
        self.content = content
        self.calls = []

    def invoke(self, input, config=None, *, stop=None, **kwargs):
        del config, stop, kwargs
        messages = input
        self.calls.append(messages)
        return SimpleNamespace(content=self.content)


class FakeMemory:
    def __init__(self):
        self.items = []

    def add_situations(self, situations):
        self.items.append(situations)


def make_investment_state(count: int, current_response: str) -> AgentState:
    return {
        "messages": [],
        "company_of_interest": "NVDA",
        "trade_date": "2026-01-15",
        "sender": "tester",
        "market_report": "market",
        "sentiment_report": "sentiment",
        "news_report": "news",
        "fundamentals_report": "fundamentals",
        "investment_debate_state": InvestDebateState(
            {
                "bull_history": "bull",
                "bear_history": "bear",
                "history": "history",
                "current_response": current_response,
                "judge_decision": "judge",
                "count": count,
            }
        ),
        "investment_plan": "plan",
        "trader_investment_plan": "trader plan",
        "risk_debate_state": RiskDebateState(
            {
                "aggressive_history": "agg",
                "conservative_history": "cons",
                "neutral_history": "neu",
                "history": "history",
                "latest_speaker": "Neutral Analyst",
                "current_aggressive_response": "",
                "current_conservative_response": "",
                "current_neutral_response": "",
                "judge_decision": "portfolio",
                "count": 0,
            }
        ),
        "final_trade_decision": "HOLD",
    }


def make_risk_state(count: int, latest_speaker: str) -> AgentState:
    state = make_investment_state(0, "Bull")
    state["risk_debate_state"] = RiskDebateState(
        {
            "aggressive_history": "agg",
            "conservative_history": "cons",
            "neutral_history": "neu",
            "history": "history",
            "latest_speaker": latest_speaker,
            "current_aggressive_response": "a",
            "current_conservative_response": "c",
            "current_neutral_response": "n",
            "judge_decision": "portfolio",
            "count": count,
        }
    )
    return state


def make_chat_model(content: str) -> tuple[ChatOpenAI, FakeLLM]:
    fake_llm = FakeLLM(content)
    return cast(ChatOpenAI, fake_llm), fake_llm


class GraphPrimitiveTests(unittest.TestCase):
    def test_should_continue_tool_driven_analyst_flows(self):
        logic = ConditionalLogic()
        state_with_tools = {"messages": [SimpleNamespace(tool_calls=[{"name": "x"}])]}
        state_without_tools = {"messages": [SimpleNamespace(tool_calls=[])]}

        expectations = [
            (logic.should_continue_market, "tools_market", "Msg Clear Market"),
            (logic.should_continue_social, "tools_social", "Msg Clear Social"),
            (logic.should_continue_news, "tools_news", "Msg Clear News"),
            (
                logic.should_continue_fundamentals,
                "tools_fundamentals",
                "Msg Clear Fundamentals",
            ),
        ]

        for method, expected_with_tools, expected_without_tools in expectations:
            with self.subTest(method=method.__name__):
                self.assertEqual(method(state_with_tools), expected_with_tools)
                self.assertEqual(method(state_without_tools), expected_without_tools)

    def test_should_continue_debate_routes_by_count_and_speaker(self):
        logic = ConditionalLogic(max_debate_rounds=2)

        self.assertEqual(
            logic.should_continue_debate(make_investment_state(4, "Bull argues again")),
            "Research Manager",
        )
        self.assertEqual(
            logic.should_continue_debate(make_investment_state(1, "Bull sees upside")),
            "Bear Researcher",
        )
        self.assertEqual(
            logic.should_continue_debate(make_investment_state(1, "Bear sees risk")),
            "Bull Researcher",
        )

    def test_should_continue_risk_analysis_routes_all_branches(self):
        logic = ConditionalLogic(max_risk_discuss_rounds=2)

        self.assertEqual(
            logic.should_continue_risk_analysis(
                make_risk_state(6, "Aggressive Analyst")
            ),
            "Portfolio Manager",
        )
        self.assertEqual(
            logic.should_continue_risk_analysis(
                make_risk_state(1, "Aggressive Analyst")
            ),
            "Conservative Analyst",
        )
        self.assertEqual(
            logic.should_continue_risk_analysis(
                make_risk_state(1, "Conservative Analyst")
            ),
            "Neutral Analyst",
        )
        self.assertEqual(
            logic.should_continue_risk_analysis(make_risk_state(1, "Neutral Analyst")),
            "Aggressive Analyst",
        )

    def test_propagator_create_initial_state_and_graph_args(self):
        propagator = Propagator(max_recur_limit=42)

        initial_state = propagator.create_initial_state("NVDA", "2026-01-15")
        args_without_callbacks = propagator.get_graph_args()
        args_with_callbacks = propagator.get_graph_args(callbacks=["cb"])

        self.assertEqual(initial_state["messages"], [("human", "NVDA")])
        self.assertEqual(initial_state["company_of_interest"], "NVDA")
        self.assertEqual(initial_state["trade_date"], "2026-01-15")
        self.assertEqual(initial_state["investment_debate_state"]["count"], 0)
        self.assertEqual(initial_state["risk_debate_state"]["latest_speaker"], "")
        self.assertEqual(
            args_without_callbacks,
            {"stream_mode": "values", "config": {"recursion_limit": 42}},
        )
        self.assertEqual(
            args_with_callbacks,
            {
                "stream_mode": "values",
                "config": {"recursion_limit": 42, "callbacks": ["cb"]},
            },
        )

    def test_propagator_merges_runtime_graph_overrides(self):
        propagator = Propagator(max_recur_limit=42)

        args = propagator.get_graph_args(
            callbacks=["cb"],
            runtime_overrides={
                "durability": "sync",
                "config": {"configurable": {"thread_id": "thread-1"}},
            },
        )

        self.assertEqual(
            args,
            {
                "stream_mode": "values",
                "durability": "sync",
                "config": {
                    "recursion_limit": 42,
                    "callbacks": ["cb"],
                    "configurable": {"thread_id": "thread-1"},
                },
            },
        )

    def test_reflector_extracts_situation_and_updates_memories(self):
        llm, recorder = make_chat_model("reflection output")
        reflector = Reflector(llm)
        state = {
            "market_report": "market",
            "sentiment_report": "sentiment",
            "news_report": "news",
            "fundamentals_report": "fundamentals",
            "investment_debate_state": {
                "bull_history": "bull thesis",
                "bear_history": "bear thesis",
                "judge_decision": "judge call",
            },
            "risk_debate_state": {"judge_decision": "portfolio call"},
            "trader_investment_plan": "trader plan",
        }

        situation = reflector._extract_current_situation(state)
        memories = [FakeMemory() for _ in range(5)]

        reflector.reflect_bull_researcher(state, 0.12, memories[0])
        reflector.reflect_bear_researcher(state, -0.05, memories[1])
        reflector.reflect_trader(state, 0.04, memories[2])
        reflector.reflect_invest_judge(state, 0.01, memories[3])
        reflector.reflect_portfolio_manager(state, -0.02, memories[4])

        self.assertEqual(situation, "market\n\nsentiment\n\nnews\n\nfundamentals")
        self.assertEqual(len(recorder.calls), 5)
        for memory in memories:
            self.assertEqual(memory.items, [[(situation, "reflection output")]])

    def test_signal_processor_extracts_llm_content(self):
        llm, recorder = make_chat_model("BUY")
        processor = SignalProcessor(llm)

        result = processor.process_signal("full analyst report")

        self.assertEqual(result, "BUY")
        self.assertEqual(recorder.calls[0][1], ("human", "full analyst report"))


if __name__ == "__main__":
    unittest.main()
