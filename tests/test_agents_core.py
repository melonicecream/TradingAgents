import unittest
from types import SimpleNamespace
from typing import cast
from unittest.mock import MagicMock, patch

from tradingagents.agents.analysts.market_analyst import create_market_analyst
from tradingagents.agents.managers.research_manager import create_research_manager
from tradingagents.agents.researchers.bull_researcher import create_bull_researcher
from tradingagents.agents.risk_mgmt.aggressive_debator import create_aggressive_debator
from tradingagents.agents.trader.trader import create_trader
from tradingagents.agents.utils.memory import FinancialSituationMemory


def make_agent_state():
    return {
        "messages": [SimpleNamespace(content="hello")],
        "company_of_interest": "NVDA",
        "trade_date": "2026-01-15",
        "market_report": "market report",
        "sentiment_report": "sentiment report",
        "news_report": "news report",
        "fundamentals_report": "fundamentals report",
        "investment_plan": "buy the dip",
        "trader_investment_plan": "BUY aggressively",
        "investment_debate_state": {
            "history": "history",
            "bull_history": "bull history",
            "bear_history": "bear history",
            "current_response": "Bear Analyst: too risky",
            "judge_decision": "judge says buy",
            "count": 1,
        },
        "risk_debate_state": {
            "history": "risk history",
            "aggressive_history": "aggressive history",
            "conservative_history": "conservative history",
            "neutral_history": "neutral history",
            "latest_speaker": "Neutral",
            "current_aggressive_response": "",
            "current_conservative_response": "conservative pushback",
            "current_neutral_response": "neutral pushback",
            "judge_decision": "BUY",
            "count": 2,
        },
    }


class FakePrompt:
    def partial(self, **kwargs):
        return self

    def __or__(self, other):
        return other


class FakeBoundChain:
    def __init__(self, result):
        self.result = result
        self.invocations = []

    def invoke(self, messages):
        self.invocations.append(messages)
        return self.result


class FakeLLMWithTools:
    def __init__(self, result):
        self.result = result
        self.bound_tools = None
        self.chain = FakeBoundChain(result)

    def bind_tools(self, tools):
        self.bound_tools = tools
        return self.chain


class AgentCoreTests(unittest.TestCase):
    def test_financial_situation_memory_adds_ranks_and_clears(self):
        memory = FinancialSituationMemory("memory")
        memory.add_situations(
            [
                ("High inflation and rising rates", "Be defensive"),
                ("Tech volatility and selling pressure", "Reduce exposure"),
            ]
        )

        memories = memory.get_memories("Tech volatility with rates rising", n_matches=2)

        self.assertEqual(memory._tokenize("NVDA, Inc.!")[:2], ["nvda", "inc"])
        self.assertEqual(len(memories), 2)
        self.assertEqual(
            {item["recommendation"] for item in memories},
            {"Be defensive", "Reduce exposure"},
        )
        self.assertGreaterEqual(
            memories[0]["similarity_score"], memories[1]["similarity_score"]
        )
        memory.clear()
        self.assertEqual(memory.get_memories("anything"), [])

    def test_market_analyst_returns_report_only_when_no_tool_calls(self):
        state = make_agent_state()
        result = SimpleNamespace(content="detailed market report", tool_calls=[])
        fake_llm = FakeLLMWithTools(result)

        with (
            patch(
                "tradingagents.agents.analysts.market_analyst.ChatPromptTemplate.from_messages",
                return_value=FakePrompt(),
            ),
            patch(
                "tradingagents.agents.analysts.market_analyst.build_instrument_context",
                return_value="instrument context",
            ),
        ):
            node = create_market_analyst(fake_llm)
            output = node(state)

        self.assertEqual(output["messages"], [result])
        self.assertEqual(output["market_report"], "detailed market report")
        self.assertIsNotNone(fake_llm.bound_tools)
        self.assertEqual(len(cast(list, fake_llm.bound_tools)), 2)
        self.assertEqual(fake_llm.chain.invocations[0], state["messages"])

    def test_market_analyst_suppresses_report_when_tool_calls_present(self):
        state = make_agent_state()
        result = SimpleNamespace(
            content="intermediate", tool_calls=[{"name": "get_stock_data"}]
        )
        fake_llm = FakeLLMWithTools(result)

        with (
            patch(
                "tradingagents.agents.analysts.market_analyst.ChatPromptTemplate.from_messages",
                return_value=FakePrompt(),
            ),
            patch(
                "tradingagents.agents.analysts.market_analyst.build_instrument_context",
                return_value="instrument context",
            ),
        ):
            output = create_market_analyst(fake_llm)(state)

        self.assertEqual(output["market_report"], "")

    def test_bull_researcher_updates_history_and_uses_memories(self):
        state = make_agent_state()
        llm = MagicMock()
        llm.invoke.return_value = SimpleNamespace(content="strong upside")
        memory = MagicMock()
        memory.get_memories.return_value = [{"recommendation": "Lean into momentum"}]

        output = create_bull_researcher(llm, memory)(state)

        debate_state = output["investment_debate_state"]
        self.assertIn("Bull Analyst: strong upside", debate_state["history"])
        self.assertEqual(
            debate_state["current_response"], "Bull Analyst: strong upside"
        )
        self.assertEqual(debate_state["count"], 2)
        memory.get_memories.assert_called_once()

    def test_research_manager_sets_judge_decision_and_plan(self):
        state = make_agent_state()
        llm = MagicMock()
        llm.invoke.return_value = SimpleNamespace(content="Buy with conviction")
        memory = MagicMock()
        memory.get_memories.return_value = [{"recommendation": "Past lesson"}]

        with patch(
            "tradingagents.agents.managers.research_manager.build_instrument_context",
            return_value="instrument context",
        ):
            output = create_research_manager(llm, memory)(state)

        self.assertEqual(output["investment_plan"], "Buy with conviction")
        self.assertEqual(
            output["investment_debate_state"]["judge_decision"],
            "Buy with conviction",
        )

    def test_trader_returns_message_plan_and_sender(self):
        state = make_agent_state()
        llm = MagicMock()
        llm.invoke.return_value = SimpleNamespace(
            content="FINAL TRANSACTION PROPOSAL: **BUY**"
        )
        memory = MagicMock()
        memory.get_memories.return_value = []

        with patch(
            "tradingagents.agents.trader.trader.build_instrument_context",
            return_value="instrument context",
        ):
            output = create_trader(llm, memory)(state)

        self.assertEqual(output["sender"], "Trader")
        self.assertEqual(
            output["trader_investment_plan"], "FINAL TRANSACTION PROPOSAL: **BUY**"
        )
        self.assertEqual(
            output["messages"][0].content, "FINAL TRANSACTION PROPOSAL: **BUY**"
        )

    def test_aggressive_debator_updates_risk_state(self):
        state = make_agent_state()
        llm = MagicMock()
        llm.invoke.return_value = SimpleNamespace(content="Take the high-upside trade")

        output = create_aggressive_debator(llm)(state)

        risk_state = output["risk_debate_state"]
        self.assertIn(
            "Aggressive Analyst: Take the high-upside trade", risk_state["history"]
        )
        self.assertEqual(risk_state["latest_speaker"], "Aggressive")
        self.assertEqual(risk_state["count"], 3)


if __name__ == "__main__":
    unittest.main()
