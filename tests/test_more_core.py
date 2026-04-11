import re
import unittest
from datetime import datetime
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import MagicMock, patch

from tradingagents.agents.analysts.fundamentals_analyst import (
    create_fundamentals_analyst,
)
from tradingagents.agents.analysts.news_analyst import create_news_analyst
from tradingagents.agents.analysts.social_media_analyst import (
    create_social_media_analyst,
)
from tradingagents.agents.managers.portfolio_manager import create_portfolio_manager
from tradingagents.agents.researchers.bear_researcher import create_bear_researcher
from tradingagents.agents.risk_mgmt.conservative_debator import (
    create_conservative_debator,
)
from tradingagents.agents.risk_mgmt.neutral_debator import create_neutral_debator
from tradingagents.agents.utils.agent_utils import create_msg_delete
from tradingagents.agents.utils.core_stock_tools import get_stock_data
from tradingagents.agents.utils.fundamental_data_tools import (
    get_balance_sheet,
    get_cashflow,
    get_fundamentals,
    get_income_statement,
)
from tradingagents.agents.utils.news_data_tools import (
    get_global_news,
    get_insider_transactions,
    get_news,
)
from tradingagents.agents.utils.technical_indicators_tools import get_indicators
from tradingagents.dataflows.alpha_vantage_fundamentals import (
    get_balance_sheet as get_alpha_balance_sheet,
    get_cashflow as get_alpha_cashflow,
    get_fundamentals as get_alpha_fundamentals,
    get_income_statement as get_alpha_income_statement,
)
from tradingagents.dataflows.alpha_vantage_news import (
    get_global_news as get_alpha_global_news,
    get_insider_transactions as get_alpha_insider_transactions,
    get_news as get_alpha_news,
)
from tradingagents.dataflows.alpha_vantage_stock import get_stock
from tradingagents.dataflows.utils import (
    decorate_all_methods,
    get_current_date,
    get_next_weekday,
    save_output,
)
from tradingagents.summary_report import (
    generate_summary_report,
    get_report_filename,
    get_template_structure,
)


def make_state():
    return {
        "messages": [SimpleNamespace(id="m1", content="hello")],
        "company_of_interest": "NVDA",
        "trade_date": "2026-01-15",
        "market_report": "market report",
        "sentiment_report": "sentiment report",
        "news_report": "news report",
        "fundamentals_report": "fundamentals report",
        "investment_plan": "investment plan",
        "trader_investment_plan": "BUY with sizing",
        "investment_debate_state": {
            "history": "debate history",
            "bull_history": "bull history",
            "bear_history": "bear history",
            "current_response": "Bull Analyst: strong growth",
            "judge_decision": "buy",
            "count": 2,
        },
        "risk_debate_state": {
            "history": "risk history",
            "aggressive_history": "aggressive history",
            "conservative_history": "conservative history",
            "neutral_history": "neutral history",
            "latest_speaker": "Neutral",
            "current_aggressive_response": "aggressive push",
            "current_conservative_response": "conservative push",
            "current_neutral_response": "neutral push",
            "judge_decision": "Hold",
            "count": 3,
        },
        "final_trade_decision": "BUY",
    }


class FakePrompt:
    def partial(self, **kwargs):
        return self

    def __or__(self, other):
        return other


class FakeBoundChain:
    def __init__(self, result):
        self.result = result

    def invoke(self, messages):
        return self.result


class FakeLLMWithTools:
    def __init__(self, result):
        self.result = result
        self.bound_tools = None

    def bind_tools(self, tools):
        self.bound_tools = tools
        return FakeBoundChain(self.result)


class MoreCoreTests(unittest.TestCase):
    def test_additional_analyst_nodes_handle_report_and_tool_paths(self):
        cases = [
            (
                "tradingagents.agents.analysts.social_media_analyst",
                create_social_media_analyst,
                "sentiment_report",
                1,
            ),
            (
                "tradingagents.agents.analysts.news_analyst",
                create_news_analyst,
                "news_report",
                2,
            ),
            (
                "tradingagents.agents.analysts.fundamentals_analyst",
                create_fundamentals_analyst,
                "fundamentals_report",
                4,
            ),
        ]

        for module_path, factory, report_key, tool_count in cases:
            with self.subTest(factory=factory.__name__):
                state = make_state()
                llm = FakeLLMWithTools(SimpleNamespace(content="report", tool_calls=[]))
                with (
                    patch(
                        f"{module_path}.ChatPromptTemplate.from_messages",
                        return_value=FakePrompt(),
                    ),
                    patch(
                        f"{module_path}.build_instrument_context",
                        return_value="instrument context",
                    ),
                ):
                    output = factory(llm)(state)
                self.assertEqual(output[report_key], "report")
                self.assertEqual(len(cast(list, llm.bound_tools)), tool_count)

                llm_with_tool_call = FakeLLMWithTools(
                    SimpleNamespace(
                        content="intermediate", tool_calls=[{"name": "tool"}]
                    )
                )
                with (
                    patch(
                        f"{module_path}.ChatPromptTemplate.from_messages",
                        return_value=FakePrompt(),
                    ),
                    patch(
                        f"{module_path}.build_instrument_context",
                        return_value="instrument context",
                    ),
                ):
                    output = factory(llm_with_tool_call)(state)
                self.assertEqual(output[report_key], "")

    def test_bear_researcher_updates_bear_history(self):
        llm = MagicMock()
        llm.invoke.return_value = SimpleNamespace(content="avoid the trade")
        memory = MagicMock()
        memory.get_memories.return_value = [{"recommendation": "Past caution"}]

        output = create_bear_researcher(llm, memory)(make_state())

        debate_state = output["investment_debate_state"]
        self.assertIn("Bear Analyst: avoid the trade", debate_state["history"])
        self.assertEqual(
            debate_state["current_response"], "Bear Analyst: avoid the trade"
        )
        self.assertEqual(debate_state["count"], 3)

    def test_conservative_and_neutral_debators_update_risk_state(self):
        state = make_state()
        conservative_llm = MagicMock()
        conservative_llm.invoke.return_value = SimpleNamespace(
            content="de-risk the plan"
        )
        neutral_llm = MagicMock()
        neutral_llm.invoke.return_value = SimpleNamespace(
            content="balance upside and downside"
        )

        conservative_state = create_conservative_debator(conservative_llm)(state)[
            "risk_debate_state"
        ]
        neutral_state = create_neutral_debator(neutral_llm)(state)["risk_debate_state"]

        self.assertEqual(conservative_state["latest_speaker"], "Conservative")
        self.assertEqual(
            conservative_state["current_conservative_response"],
            "Conservative Analyst: de-risk the plan",
        )
        self.assertEqual(neutral_state["latest_speaker"], "Neutral")
        self.assertEqual(
            neutral_state["current_neutral_response"],
            "Neutral Analyst: balance upside and downside",
        )

    def test_portfolio_manager_sets_final_trade_decision(self):
        llm = MagicMock()
        llm.invoke.return_value = SimpleNamespace(content="Overweight")
        memory = MagicMock()
        memory.get_memories.return_value = [{"recommendation": "Past lesson"}]

        with patch(
            "tradingagents.agents.managers.portfolio_manager.build_instrument_context",
            return_value="instrument context",
        ):
            output = create_portfolio_manager(llm, memory)(make_state())

        self.assertEqual(output["final_trade_decision"], "Overweight")
        self.assertEqual(output["risk_debate_state"]["judge_decision"], "Overweight")
        self.assertEqual(output["risk_debate_state"]["latest_speaker"], "Judge")

    def test_tool_wrappers_delegate_to_route_to_vendor(self):
        with patch(
            "tradingagents.agents.utils.core_stock_tools.route_to_vendor",
            return_value="stock",
        ) as core_route:
            self.assertEqual(
                cast(Any, get_stock_data).func("NVDA", "2026-01-01", "2026-01-31"),
                "stock",
            )
            core_route.assert_called_once_with(
                "get_stock_data", "NVDA", "2026-01-01", "2026-01-31"
            )

        with patch(
            "tradingagents.agents.utils.fundamental_data_tools.route_to_vendor",
            return_value="fund",
        ) as fund_route:
            self.assertEqual(
                cast(Any, get_fundamentals).func("NVDA", "2026-01-15"), "fund"
            )
            self.assertEqual(
                cast(Any, get_balance_sheet).func("NVDA", "annual", "2026-01-15"),
                "fund",
            )
            self.assertEqual(
                cast(Any, get_cashflow).func("NVDA", "quarterly", "2026-01-15"),
                "fund",
            )
            self.assertEqual(
                cast(Any, get_income_statement).func("NVDA", "quarterly", "2026-01-15"),
                "fund",
            )
            self.assertEqual(fund_route.call_count, 4)

        with patch(
            "tradingagents.agents.utils.news_data_tools.route_to_vendor",
            return_value="news",
        ) as news_route:
            self.assertEqual(
                cast(Any, get_news).func("NVDA", "2026-01-01", "2026-01-31"),
                "news",
            )
            self.assertEqual(
                cast(Any, get_global_news).func("2026-01-15", 7, 5), "news"
            )
            self.assertEqual(cast(Any, get_insider_transactions).func("NVDA"), "news")
            self.assertEqual(news_route.call_count, 3)

    def test_get_indicators_splits_multiple_values(self):
        with patch(
            "tradingagents.agents.utils.technical_indicators_tools.route_to_vendor",
            side_effect=["rsi-data", "macd-data"],
        ) as route:
            result = cast(Any, get_indicators).func(
                "NVDA", "rsi, macd", "2026-01-15", 30
            )

        self.assertEqual(result, "rsi-data\n\nmacd-data")
        self.assertEqual(route.call_count, 2)

        with patch(
            "tradingagents.agents.utils.technical_indicators_tools.route_to_vendor",
            return_value="single",
        ) as route:
            self.assertEqual(
                cast(Any, get_indicators).func("NVDA", " rsi ", "2026-01-15", 30),
                "single",
            )
            route.assert_called_once_with(
                "get_indicators", "NVDA", "rsi", "2026-01-15", 30
            )

    def test_create_msg_delete_removes_messages_and_adds_placeholder(self):
        state = {"messages": [SimpleNamespace(id="a"), SimpleNamespace(id="b")]}

        result = create_msg_delete()(state)

        self.assertEqual(len(result["messages"]), 3)
        self.assertEqual(result["messages"][-1].content, "Continue")

    def test_alpha_vantage_wrappers_build_expected_requests(self):
        with (
            patch(
                "tradingagents.dataflows.alpha_vantage_stock._make_api_request",
                return_value="csv",
            ) as request,
            patch(
                "tradingagents.dataflows.alpha_vantage_stock._filter_csv_by_date_range",
                return_value="filtered",
            ) as filter_csv,
            patch(
                "tradingagents.dataflows.alpha_vantage_stock.datetime"
            ) as fake_datetime,
        ):
            fake_datetime.strptime.side_effect = lambda value, fmt: datetime.strptime(
                value, fmt
            )
            fake_datetime.now.return_value = datetime(2026, 1, 20)
            self.assertEqual(get_stock("NVDA", "2026-01-01", "2026-01-15"), "filtered")
            request.assert_called_once_with(
                "TIME_SERIES_DAILY_ADJUSTED",
                {"symbol": "NVDA", "outputsize": "compact", "datatype": "csv"},
            )
            filter_csv.assert_called_once_with("csv", "2026-01-01", "2026-01-15")

        with patch(
            "tradingagents.dataflows.alpha_vantage_fundamentals._make_api_request",
            return_value="ok",
        ) as request:
            self.assertEqual(get_alpha_fundamentals("NVDA"), "ok")
            self.assertEqual(get_alpha_balance_sheet("NVDA"), "ok")
            self.assertEqual(get_alpha_cashflow("NVDA"), "ok")
            self.assertEqual(get_alpha_income_statement("NVDA"), "ok")
            self.assertEqual(request.call_count, 4)

        with (
            patch(
                "tradingagents.dataflows.alpha_vantage_news._make_api_request",
                return_value="news",
            ) as request,
            patch(
                "tradingagents.dataflows.alpha_vantage_news.format_datetime_for_api",
                side_effect=lambda value: f"fmt:{value}",
            ),
        ):
            self.assertEqual(get_alpha_news("NVDA", "2026-01-01", "2026-01-15"), "news")
            self.assertEqual(
                get_alpha_global_news("2026-01-15", look_back_days=2, limit=3), "news"
            )
            self.assertEqual(get_alpha_insider_transactions("NVDA"), "news")
            self.assertEqual(request.call_count, 3)

    def test_dataflow_utils_cover_save_date_decorator_and_next_weekday(self):
        dataframe = MagicMock()
        with patch("builtins.print") as mock_print:
            save_output(dataframe, "prices", "/tmp/output.csv")
            dataframe.to_csv.assert_called_once_with("/tmp/output.csv")
            mock_print.assert_called_once()

        with patch("tradingagents.dataflows.utils.date") as fake_date:
            fake_date.today.return_value = datetime(2026, 1, 15)
            self.assertEqual(get_current_date(), "2026-01-15")

        def uppercase_decorator(func):
            def wrapper(*args, **kwargs):
                return func(*args, **kwargs).upper()

            return wrapper

        @decorate_all_methods(uppercase_decorator)
        class Demo:
            def greet(self):
                return "hello"

        self.assertEqual(Demo().greet(), "HELLO")
        self.assertEqual(
            get_next_weekday("2026-01-17").strftime("%Y-%m-%d"), "2026-01-19"
        )
        self.assertEqual(
            get_next_weekday(datetime(2026, 1, 15)).strftime("%Y-%m-%d"), "2026-01-15"
        )

    def test_summary_report_helpers_generate_prompt_and_filename(self):
        english_structure = get_template_structure("English")
        korean_structure = get_template_structure("한국어")
        self.assertIn("# Investment Analysis Summary Report", english_structure)
        self.assertIn("## 최종 결정", korean_structure)

        llm = MagicMock()
        llm.invoke.return_value = SimpleNamespace(content="요약 보고서")
        report = generate_summary_report(make_state(), "한국어", llm)

        self.assertEqual(report, "요약 보고서")
        prompt = llm.invoke.call_args.args[0]
        self.assertIn("한국어", prompt)
        self.assertIn("BUY", prompt)
        self.assertEqual(get_report_filename("日本語"), "summary_ja.md")
        self.assertEqual(get_report_filename("Unknown"), "summary.md")


if __name__ == "__main__":
    unittest.main()
