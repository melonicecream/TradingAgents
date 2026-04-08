import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import cast
from unittest.mock import MagicMock, mock_open, patch

from langchain_openai import ChatOpenAI
from langgraph.prebuilt import ToolNode
from tradingagents.agents.utils.memory import FinancialSituationMemory
from tradingagents.graph.conditional_logic import ConditionalLogic
from tradingagents.graph.setup import GraphSetup
from tradingagents.graph.trading_graph import TradingAgentsGraph


class FakeWorkflow:
    def __init__(self):
        self.nodes = []
        self.edges = []
        self.conditional_edges = []

    def add_node(self, name, node):
        self.nodes.append((name, node))

    def add_edge(self, source, target):
        self.edges.append((source, target))

    def add_conditional_edges(self, node_name, router, mapping):
        self.conditional_edges.append((node_name, router, mapping))

    def compile(self, **kwargs):
        self.compile_kwargs = kwargs
        return "compiled-graph"


def make_final_state():
    return {
        "messages": [SimpleNamespace(pretty_print=MagicMock())],
        "company_of_interest": "NVDA",
        "trade_date": "2026-01-15",
        "market_report": "market",
        "sentiment_report": "sentiment",
        "news_report": "news",
        "fundamentals_report": "fundamentals",
        "investment_debate_state": {
            "bull_history": "bull",
            "bear_history": "bear",
            "history": "history",
            "current_response": "Bull Analyst: thesis",
            "judge_decision": "buy",
        },
        "trader_investment_plan": "trader plan",
        "risk_debate_state": {
            "aggressive_history": "agg",
            "conservative_history": "cons",
            "neutral_history": "neu",
            "history": "risk history",
            "judge_decision": "BUY",
        },
        "investment_plan": "investment plan",
        "final_trade_decision": "BUY",
    }


class GraphSetupTests(unittest.TestCase):
    def setUp(self):
        self.conditional_logic = cast(
            ConditionalLogic,
            SimpleNamespace(
                should_continue_market="market_router",
                should_continue_social="social_router",
                should_continue_news="news_router",
                should_continue_fundamentals="fund_router",
                should_continue_debate="debate_router",
                should_continue_risk_analysis="risk_router",
            ),
        )
        self.graph_setup = GraphSetup(
            quick_thinking_llm=cast(ChatOpenAI, MagicMock()),
            deep_thinking_llm=cast(ChatOpenAI, MagicMock()),
            tool_nodes={
                "market": cast(ToolNode, MagicMock()),
                "news": cast(ToolNode, MagicMock()),
            },
            bull_memory="bull-memory",
            bear_memory="bear-memory",
            trader_memory="trader-memory",
            invest_judge_memory="judge-memory",
            portfolio_manager_memory="portfolio-memory",
            conditional_logic=self.conditional_logic,
        )

    def test_setup_graph_requires_at_least_one_analyst(self):
        with self.assertRaises(ValueError):
            self.graph_setup.setup_graph([])

    def test_setup_graph_wires_selected_analysts_and_core_flow(self):
        workflow = FakeWorkflow()

        with (
            patch("tradingagents.graph.setup.StateGraph", return_value=workflow),
            patch(
                "tradingagents.graph.setup.create_market_analyst",
                return_value="market-node",
            ),
            patch(
                "tradingagents.graph.setup.create_news_analyst",
                return_value="news-node",
            ),
            patch(
                "tradingagents.graph.setup.create_msg_delete",
                side_effect=["delete-market", "delete-news"],
            ),
            patch(
                "tradingagents.graph.setup.create_bull_researcher",
                return_value="bull-node",
            ),
            patch(
                "tradingagents.graph.setup.create_bear_researcher",
                return_value="bear-node",
            ),
            patch(
                "tradingagents.graph.setup.create_research_manager",
                return_value="research-manager",
            ),
            patch(
                "tradingagents.graph.setup.create_trader", return_value="trader-node"
            ),
            patch(
                "tradingagents.graph.setup.create_aggressive_debator",
                return_value="aggressive-node",
            ),
            patch(
                "tradingagents.graph.setup.create_neutral_debator",
                return_value="neutral-node",
            ),
            patch(
                "tradingagents.graph.setup.create_conservative_debator",
                return_value="conservative-node",
            ),
            patch(
                "tradingagents.graph.setup.create_portfolio_manager",
                return_value="portfolio-manager",
            ),
        ):
            compiled = self.graph_setup.setup_graph(["market", "news"])

        self.assertEqual(compiled, "compiled-graph")
        node_names = [name for name, _ in workflow.nodes]
        self.assertIn("Market Analyst", node_names)
        self.assertIn("Msg Clear Market", node_names)
        self.assertIn("tools_market", node_names)
        self.assertIn("News Analyst", node_names)
        self.assertIn("Msg Clear News", node_names)
        self.assertIn("tools_news", node_names)
        self.assertIn(("__start__", "Market Analyst"), workflow.edges)
        self.assertIn(("tools_market", "Market Analyst"), workflow.edges)
        self.assertIn(("Msg Clear Market", "News Analyst"), workflow.edges)
        self.assertIn(("Msg Clear News", "Bull Researcher"), workflow.edges)
        self.assertIn(("Research Manager", "Trader"), workflow.edges)
        self.assertIn(("Portfolio Manager", "__end__"), workflow.edges)
        self.assertEqual(workflow.conditional_edges[0][0], "Market Analyst")
        self.assertEqual(workflow.conditional_edges[1][0], "News Analyst")
        self.assertEqual(workflow.conditional_edges[2][0], "Bull Researcher")
        self.assertEqual(workflow.compile_kwargs, {})

    def test_setup_graph_passes_optional_checkpointer_to_compile(self):
        workflow = FakeWorkflow()

        with (
            patch("tradingagents.graph.setup.StateGraph", return_value=workflow),
            patch(
                "tradingagents.graph.setup.create_market_analyst",
                return_value="market-node",
            ),
            patch(
                "tradingagents.graph.setup.create_msg_delete",
                return_value="delete-market",
            ),
            patch(
                "tradingagents.graph.setup.create_bull_researcher",
                return_value="bull-node",
            ),
            patch(
                "tradingagents.graph.setup.create_bear_researcher",
                return_value="bear-node",
            ),
            patch(
                "tradingagents.graph.setup.create_research_manager",
                return_value="research-manager",
            ),
            patch(
                "tradingagents.graph.setup.create_trader", return_value="trader-node"
            ),
            patch(
                "tradingagents.graph.setup.create_aggressive_debator",
                return_value="aggressive-node",
            ),
            patch(
                "tradingagents.graph.setup.create_neutral_debator",
                return_value="neutral-node",
            ),
            patch(
                "tradingagents.graph.setup.create_conservative_debator",
                return_value="conservative-node",
            ),
            patch(
                "tradingagents.graph.setup.create_portfolio_manager",
                return_value="portfolio-manager",
            ),
        ):
            self.graph_setup.setup_graph(
                ["market"],
                checkpointer="checkpoint-store",
                compile_kwargs={"name": "checkpointed"},
            )

        self.assertEqual(
            workflow.compile_kwargs,
            {"checkpointer": "checkpoint-store", "name": "checkpointed"},
        )


class TradingAgentsGraphTests(unittest.TestCase):
    def test_get_provider_kwargs_handles_provider_specific_fields(self):
        graph = object.__new__(TradingAgentsGraph)

        graph.config = {"llm_provider": "google", "google_thinking_level": "high"}
        self.assertEqual(graph._get_provider_kwargs(), {"thinking_level": "high"})

        graph.config = {"llm_provider": "openai", "openai_reasoning_effort": "medium"}
        with patch.dict("os.environ", {"CUSTOM_API_KEY": "custom-openai"}, clear=False):
            self.assertEqual(
                graph._get_provider_kwargs(),
                {"reasoning_effort": "medium", "api_key": "custom-openai"},
            )

        graph.config = {"llm_provider": "anthropic", "anthropic_effort": "high"}
        with patch.dict(
            "os.environ", {"CUSTOM_API_KEY": "custom-anthropic"}, clear=False
        ):
            self.assertEqual(
                graph._get_provider_kwargs(),
                {"effort": "high", "api_key": "custom-anthropic"},
            )

    def test_init_builds_dependencies_and_passes_callbacks(self):
        fake_deep_client = MagicMock()
        fake_deep_client.get_llm.return_value = "deep-llm"
        fake_quick_client = MagicMock()
        fake_quick_client.get_llm.return_value = "quick-llm"
        fake_graph_setup = MagicMock()
        fake_graph_setup.setup_graph.return_value = "compiled-graph"
        fake_propagator = MagicMock()
        fake_reflector = MagicMock()
        fake_signal_processor = MagicMock()

        config = {
            "project_dir": "/tmp/project",
            "llm_provider": "openai",
            "deep_think_llm": "gpt-5.4",
            "quick_think_llm": "gpt-5-mini",
            "backend_url": "https://gateway.example/v1",
            "max_debate_rounds": 2,
            "max_risk_discuss_rounds": 3,
            "openai_reasoning_effort": "high",
        }

        with (
            patch("tradingagents.graph.trading_graph.set_config") as mock_set_config,
            patch("tradingagents.graph.trading_graph.os.makedirs") as mock_makedirs,
            patch(
                "tradingagents.graph.trading_graph.create_llm_client",
                side_effect=[fake_deep_client, fake_quick_client],
            ) as mock_create_llm_client,
            patch(
                "tradingagents.graph.trading_graph.FinancialSituationMemory",
                side_effect=["bull", "bear", "trader", "judge", "portfolio"],
            ),
            patch(
                "tradingagents.graph.trading_graph.GraphSetup",
                return_value=fake_graph_setup,
            ),
            patch(
                "tradingagents.graph.trading_graph.Propagator",
                return_value=fake_propagator,
            ),
            patch(
                "tradingagents.graph.trading_graph.Reflector",
                return_value=fake_reflector,
            ),
            patch(
                "tradingagents.graph.trading_graph.SignalProcessor",
                return_value=fake_signal_processor,
            ),
            patch.dict("os.environ", {"CUSTOM_API_KEY": "custom-key"}, clear=False),
        ):
            graph = TradingAgentsGraph(config=config, callbacks=["cb"])

        mock_set_config.assert_called_once_with(config)
        mock_makedirs.assert_called_once_with(
            "/tmp/project/dataflows/data_cache", exist_ok=True
        )
        first_call = mock_create_llm_client.call_args_list[0]
        self.assertEqual(first_call.kwargs["provider"], "openai")
        self.assertEqual(first_call.kwargs["reasoning_effort"], "high")
        self.assertEqual(first_call.kwargs["api_key"], "custom-key")
        self.assertEqual(first_call.kwargs["callbacks"], ["cb"])
        self.assertEqual(graph.deep_thinking_llm, "deep-llm")
        self.assertEqual(graph.quick_thinking_llm, "quick-llm")
        self.assertEqual(graph.graph, "compiled-graph")

    def test_init_passes_optional_checkpointer_and_compile_kwargs(self):
        fake_deep_client = MagicMock()
        fake_deep_client.get_llm.return_value = "deep-llm"
        fake_quick_client = MagicMock()
        fake_quick_client.get_llm.return_value = "quick-llm"
        fake_graph_setup = MagicMock()
        fake_graph_setup.setup_graph.return_value = "compiled-graph"

        config = {
            "project_dir": "/tmp/project",
            "llm_provider": "openai",
            "deep_think_llm": "gpt-5.4",
            "quick_think_llm": "gpt-5-mini",
            "backend_url": "https://gateway.example/v1",
            "max_debate_rounds": 2,
            "max_risk_discuss_rounds": 3,
        }

        with (
            patch("tradingagents.graph.trading_graph.set_config"),
            patch("tradingagents.graph.trading_graph.os.makedirs"),
            patch(
                "tradingagents.graph.trading_graph.create_llm_client",
                side_effect=[fake_deep_client, fake_quick_client],
            ),
            patch(
                "tradingagents.graph.trading_graph.FinancialSituationMemory",
                side_effect=["bull", "bear", "trader", "judge", "portfolio"],
            ),
            patch(
                "tradingagents.graph.trading_graph.GraphSetup",
                return_value=fake_graph_setup,
            ),
            patch(
                "tradingagents.graph.trading_graph.Propagator", return_value=MagicMock()
            ),
            patch(
                "tradingagents.graph.trading_graph.Reflector", return_value=MagicMock()
            ),
            patch(
                "tradingagents.graph.trading_graph.SignalProcessor",
                return_value=MagicMock(),
            ),
        ):
            TradingAgentsGraph(
                config=config,
                checkpointer="checkpoint-store",
                compile_kwargs={"name": "checkpointed"},
            )

        fake_graph_setup.setup_graph.assert_called_once_with(
            ["market", "social", "news", "fundamentals"],
            checkpointer="checkpoint-store",
            compile_kwargs={"name": "checkpointed"},
        )

    def test_create_tool_nodes_groups_tools_by_domain(self):
        graph = object.__new__(TradingAgentsGraph)

        with patch(
            "tradingagents.graph.trading_graph.ToolNode",
            side_effect=lambda tools: tuple(tools),
        ):
            tool_nodes = graph._create_tool_nodes()

        self.assertEqual(len(cast(tuple, tool_nodes["market"])), 2)
        self.assertEqual(len(cast(tuple, tool_nodes["social"])), 1)
        self.assertEqual(len(cast(tuple, tool_nodes["news"])), 3)
        self.assertEqual(len(cast(tuple, tool_nodes["fundamentals"])), 4)

    def test_propagate_uses_invoke_in_standard_mode(self):
        graph = object.__new__(TradingAgentsGraph)
        graph.debug = False
        graph.propagator = MagicMock()
        graph.graph = MagicMock()
        graph.signal_processor = MagicMock()
        graph._log_state = MagicMock()

        init_state = {"messages": []}
        final_state = make_final_state()
        graph.propagator.create_initial_state.return_value = init_state
        graph.propagator.get_graph_args.return_value = {
            "stream_mode": "values",
            "config": {},
        }
        graph.graph.invoke.return_value = final_state
        graph.signal_processor.process_signal.return_value = "BUY"

        returned_state, decision = graph.propagate("NVDA", "2026-01-15")

        graph.graph.invoke.assert_called_once_with(
            init_state, stream_mode="values", config={}
        )
        graph._log_state.assert_called_once_with("2026-01-15", final_state)
        self.assertEqual(returned_state, final_state)
        self.assertEqual(decision, "BUY")
        self.assertEqual(graph.curr_state, final_state)
        self.assertEqual(graph.ticker, "NVDA")

    def test_propagate_merges_runtime_graph_args(self):
        graph = object.__new__(TradingAgentsGraph)
        graph.debug = False
        graph.propagator = MagicMock()
        graph.graph = MagicMock()
        graph.signal_processor = MagicMock()
        graph._log_state = MagicMock()

        init_state = {"messages": []}
        final_state = make_final_state()
        runtime_graph_args = {
            "durability": "sync",
            "config": {"configurable": {"thread_id": "thread-1"}},
        }
        graph.propagator.create_initial_state.return_value = init_state
        graph.propagator.get_graph_args.return_value = {
            "stream_mode": "values",
            "durability": "sync",
            "config": {
                "recursion_limit": 100,
                "configurable": {"thread_id": "thread-1"},
            },
        }
        graph.graph.invoke.return_value = final_state
        graph.signal_processor.process_signal.return_value = "BUY"

        returned_state, decision = graph.propagate(
            "NVDA",
            "2026-01-15",
            runtime_graph_args=runtime_graph_args,
        )

        graph.propagator.get_graph_args.assert_called_once_with(
            runtime_overrides=runtime_graph_args
        )
        graph.graph.invoke.assert_called_once_with(
            init_state,
            stream_mode="values",
            durability="sync",
            config={"recursion_limit": 100, "configurable": {"thread_id": "thread-1"}},
        )
        self.assertEqual(returned_state, final_state)
        self.assertEqual(decision, "BUY")

    def test_propagate_uses_stream_in_debug_mode(self):
        graph = object.__new__(TradingAgentsGraph)
        graph.debug = True
        graph.propagator = MagicMock()
        graph.graph = MagicMock()
        graph.signal_processor = MagicMock()
        graph._log_state = MagicMock()

        init_state = {"messages": []}
        first_chunk = {"messages": []}
        final_state = make_final_state()
        graph.propagator.create_initial_state.return_value = init_state
        graph.propagator.get_graph_args.return_value = {
            "stream_mode": "values",
            "config": {},
        }
        graph.graph.stream.return_value = [first_chunk, final_state]
        graph.signal_processor.process_signal.return_value = "BUY"

        returned_state, decision = graph.propagate("NVDA", "2026-01-15")

        graph.graph.stream.assert_called_once_with(
            init_state, stream_mode="values", config={}
        )
        final_state["messages"][-1].pretty_print.assert_called_once()
        self.assertEqual(returned_state, final_state)
        self.assertEqual(decision, "BUY")

    def test_log_state_writes_json_snapshot(self):
        graph = object.__new__(TradingAgentsGraph)
        graph.ticker = "NVDA"
        graph.log_states_dict = {}
        final_state = make_final_state()

        with (
            patch.object(Path, "mkdir") as mock_mkdir,
            patch("builtins.open", mock_open()) as mocked_open,
            patch("tradingagents.graph.trading_graph.json.dump") as mock_dump,
        ):
            graph._log_state("2026-01-15", final_state)

        mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)
        mocked_open.assert_called_once()
        logged = graph.log_states_dict["2026-01-15"]
        self.assertEqual(logged["company_of_interest"], "NVDA")
        self.assertEqual(logged["risk_debate_state"]["judge_decision"], "BUY")
        mock_dump.assert_called_once()

    def test_reflect_and_remember_delegates_to_reflector(self):
        graph = object.__new__(TradingAgentsGraph)
        graph.curr_state = make_final_state()
        graph.reflector = MagicMock()
        graph.bull_memory = cast(FinancialSituationMemory, MagicMock())
        graph.bear_memory = cast(FinancialSituationMemory, MagicMock())
        graph.trader_memory = cast(FinancialSituationMemory, MagicMock())
        graph.invest_judge_memory = cast(FinancialSituationMemory, MagicMock())
        graph.portfolio_manager_memory = cast(FinancialSituationMemory, MagicMock())

        graph.reflect_and_remember(0.12)

        graph.reflector.reflect_bull_researcher.assert_called_once_with(
            graph.curr_state, 0.12, graph.bull_memory
        )
        graph.reflector.reflect_bear_researcher.assert_called_once_with(
            graph.curr_state, 0.12, graph.bear_memory
        )
        graph.reflector.reflect_trader.assert_called_once_with(
            graph.curr_state, 0.12, graph.trader_memory
        )
        graph.reflector.reflect_invest_judge.assert_called_once_with(
            graph.curr_state, 0.12, graph.invest_judge_memory
        )
        graph.reflector.reflect_portfolio_manager.assert_called_once_with(
            graph.curr_state, 0.12, graph.portfolio_manager_memory
        )

    def test_process_signal_delegates_to_signal_processor(self):
        graph = object.__new__(TradingAgentsGraph)
        graph.signal_processor = MagicMock()
        graph.signal_processor.process_signal.return_value = "SELL"

        self.assertEqual(graph.process_signal("raw signal"), "SELL")
        graph.signal_processor.process_signal.assert_called_once_with("raw signal")


if __name__ == "__main__":
    unittest.main()
