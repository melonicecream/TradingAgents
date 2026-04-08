import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pandas as pd
from yfinance.exceptions import YFRateLimitError

from tradingagents.dataflows.alpha_vantage_indicator import get_indicator
from tradingagents.dataflows.stockstats_utils import (
    StockstatsUtils,
    _clean_dataframe,
    yf_retry,
)
from tradingagents.dataflows.y_finance import (
    _get_stock_stats_bulk,
    get_YFin_data_online,
    get_balance_sheet,
    get_cashflow,
    get_fundamentals,
    get_income_statement,
    get_insider_transactions,
    get_stock_stats_indicators_window,
    get_stockstats_indicator,
)
from tradingagents.dataflows.yfinance_news import (
    _extract_article_data,
    get_global_news_yfinance,
    get_news_yfinance,
)


class MarketDataAdaptersTests(unittest.TestCase):
    def test_yf_retry_retries_then_succeeds_and_can_exhaust(self):
        attempts = {"count": 0}

        def flaky():
            attempts["count"] += 1
            if attempts["count"] < 3:
                raise YFRateLimitError()
            return "ok"

        with patch("tradingagents.dataflows.stockstats_utils.time.sleep") as sleep:
            self.assertEqual(yf_retry(flaky, max_retries=3, base_delay=1), "ok")
            self.assertEqual(sleep.call_count, 2)

        with patch("tradingagents.dataflows.stockstats_utils.time.sleep"):
            with self.assertRaises(YFRateLimitError):
                yf_retry(
                    lambda: (_ for _ in ()).throw(YFRateLimitError()),
                    max_retries=1,
                )

    def test_clean_dataframe_normalizes_dates_and_fills_prices(self):
        data = pd.DataFrame(
            {
                "Date": ["2026-01-15", "bad-date", "2026-01-16"],
                "Open": [100, 101, None],
                "High": [110, 111, None],
                "Low": [90, 91, None],
                "Close": [105, None, 106],
                "Volume": [1000, 1001, None],
            }
        )

        cleaned = _clean_dataframe(data)
        price_frame = cleaned[["Open", "High", "Low", "Close", "Volume"]]

        self.assertEqual(len(cleaned), 2)
        self.assertTrue(pd.api.types.is_datetime64_any_dtype(cleaned["Date"]))
        self.assertFalse(price_frame.isna().to_numpy().any())

    def test_stockstats_utils_uses_cached_csv_and_returns_indicator_or_na(self):
        cached = pd.DataFrame(
            {
                "Date": ["2026-01-14", "2026-01-15"],
                "Open": [1, 2],
                "High": [2, 3],
                "Low": [0.5, 1.5],
                "Close": [1.5, 2.5],
                "Volume": [100, 200],
                "rsi": [45, 50],
            }
        )

        with (
            patch(
                "tradingagents.dataflows.stockstats_utils.get_config",
                return_value={"data_cache_dir": "/tmp/cache"},
            ),
            patch(
                "tradingagents.dataflows.stockstats_utils.os.path.exists",
                return_value=True,
            ),
            patch(
                "tradingagents.dataflows.stockstats_utils.pd.read_csv",
                return_value=cached,
            ),
            patch(
                "tradingagents.dataflows.stockstats_utils.wrap",
                side_effect=lambda df: df,
            ),
            patch("tradingagents.dataflows.stockstats_utils.os.makedirs"),
        ):
            self.assertEqual(
                StockstatsUtils.get_stock_stats("NVDA", "rsi", "2026-01-15"), 50
            )
            self.assertEqual(
                StockstatsUtils.get_stock_stats("NVDA", "rsi", "2026-01-18"),
                "N/A: Not a trading day (weekend or holiday)",
            )

    def test_alpha_vantage_indicator_covers_error_and_success_paths(self):
        with self.assertRaises(ValueError):
            get_indicator("NVDA", "unknown", "2026-01-15", 5)

        vwma = get_indicator("NVDA", "vwma", "2026-01-15", 5)
        self.assertIn("VWMA", vwma)

        with patch(
            "tradingagents.dataflows.alpha_vantage_indicator._make_api_request",
            return_value="time,SMA\n",
        ):
            self.assertIn(
                "No data returned",
                get_indicator("NVDA", "close_50_sma", "2026-01-15", 5),
            )

        with patch(
            "tradingagents.dataflows.alpha_vantage_indicator._make_api_request",
            return_value="date,SMA\n2026-01-15,123\n",
        ):
            self.assertIn(
                "'time' column not found",
                get_indicator("NVDA", "close_50_sma", "2026-01-15", 5),
            )

        with patch(
            "tradingagents.dataflows.alpha_vantage_indicator._make_api_request",
            return_value="time,OTHER\n2026-01-15,123\n",
        ):
            self.assertIn(
                "Column 'SMA' not found",
                get_indicator("NVDA", "close_50_sma", "2026-01-15", 5),
            )

        csv_data = "time,MACD\n2026-01-10,1.1\n2026-01-15,2.2\n"
        with patch(
            "tradingagents.dataflows.alpha_vantage_indicator._make_api_request",
            return_value=csv_data,
        ):
            result = get_indicator("NVDA", "macd", "2026-01-15", 5)
        self.assertIn("2026-01-15: 2.2", result)
        self.assertIn("MACD", result)

    def test_get_yfin_data_online_formats_header_and_handles_empty(self):
        empty_df = pd.DataFrame()
        ticker = MagicMock()
        ticker.history.return_value = empty_df

        with patch("tradingagents.dataflows.y_finance.yf.Ticker", return_value=ticker):
            self.assertIn(
                "No data found",
                get_YFin_data_online("nvda", "2026-01-01", "2026-01-15"),
            )

        index = pd.DatetimeIndex(["2026-01-14", "2026-01-15"], tz="UTC")
        data = pd.DataFrame(
            {
                "Open": [100.123, 101.987],
                "High": [102.456, 103.654],
                "Low": [99.321, 100.111],
                "Close": [101.555, 102.444],
                "Adj Close": [101.555, 102.444],
            },
            index=index,
        )
        ticker.history.return_value = data
        with patch("tradingagents.dataflows.y_finance.yf.Ticker", return_value=ticker):
            result = get_YFin_data_online("nvda", "2026-01-01", "2026-01-15")
        self.assertIn("# Stock data for NVDA", result)
        self.assertIn("101.56", result)

    def test_yfinance_indicator_window_and_bulk_paths(self):
        with self.assertRaises(ValueError):
            get_stock_stats_indicators_window("NVDA", "unknown", "2026-01-15", 2)

        with patch(
            "tradingagents.dataflows.y_finance._get_stock_stats_bulk",
            return_value={"2026-01-15": "1.5", "2026-01-14": "1.0"},
        ):
            result = get_stock_stats_indicators_window("NVDA", "rsi", "2026-01-15", 2)
        self.assertIn("2026-01-15: 1.5", result)
        self.assertIn("2026-01-13: N/A: Not a trading day", result)

        with (
            patch(
                "tradingagents.dataflows.y_finance._get_stock_stats_bulk",
                side_effect=Exception("bulk fail"),
            ),
            patch(
                "tradingagents.dataflows.y_finance.get_stockstats_indicator",
                side_effect=["3.0", "2.0", "1.0"],
            ),
        ):
            fallback_result = get_stock_stats_indicators_window(
                "NVDA", "macd", "2026-01-15", 2
            )
        self.assertIn("2026-01-15: 3.0", fallback_result)
        self.assertIn("MACD: Computes momentum", fallback_result)

    def test_get_stock_stats_bulk_handles_local_and_online_sources(self):
        local_df = pd.DataFrame(
            {
                "Date": ["2026-01-14", "2026-01-15"],
                "Open": [1, 2],
                "High": [2, 3],
                "Low": [0.5, 1.5],
                "Close": [1.5, 2.5],
                "Volume": [100, 200],
                "rsi": [None, 55],
            }
        )

        with (
            patch(
                "tradingagents.dataflows.config.get_config",
                return_value={
                    "data_vendors": {"technical_indicators": "local"},
                    "data_cache_dir": "/tmp/cache",
                },
            ),
            patch("pandas.read_csv", return_value=local_df),
            patch("stockstats.wrap", side_effect=lambda df: df),
        ):
            local_result = _get_stock_stats_bulk("NVDA", "rsi", "2026-01-15")
        self.assertEqual(local_result["2026-01-14"], "N/A")
        self.assertEqual(local_result["2026-01-15"], "55.0")

        online_df = pd.DataFrame(
            {
                "Date": ["2026-01-15"],
                "Open": [1],
                "High": [2],
                "Low": [0.5],
                "Close": [1.5],
                "Volume": [100],
                "rsi": [60],
            }
        )
        downloaded_df = online_df.set_index(pd.DatetimeIndex(["2026-01-15"]))
        with (
            patch(
                "tradingagents.dataflows.config.get_config",
                return_value={
                    "data_vendors": {"technical_indicators": "yfinance"},
                    "data_cache_dir": "/tmp/cache",
                },
            ),
            patch(
                "tradingagents.dataflows.y_finance.os.path.exists", return_value=False
            ),
            patch("tradingagents.dataflows.y_finance.os.makedirs"),
            patch(
                "tradingagents.dataflows.y_finance.yf.download",
                return_value=downloaded_df,
            ),
            patch("pandas.DataFrame.to_csv"),
            patch("stockstats.wrap", side_effect=lambda df: df),
        ):
            online_result = _get_stock_stats_bulk("NVDA", "rsi", "2026-01-15")
        self.assertEqual(online_result["2026-01-15"], "60")

    def test_get_stockstats_indicator_returns_string_or_empty_on_error(self):
        with patch(
            "tradingagents.dataflows.y_finance.StockstatsUtils.get_stock_stats",
            return_value=42,
        ):
            self.assertEqual(
                get_stockstats_indicator("NVDA", "rsi", "2026-01-15"), "42"
            )

        with patch(
            "tradingagents.dataflows.y_finance.StockstatsUtils.get_stock_stats",
            side_effect=Exception("fail"),
        ):
            self.assertEqual(get_stockstats_indicator("NVDA", "rsi", "2026-01-15"), "")

    def test_yfinance_fundamental_statement_and_insider_helpers(self):
        ticker = MagicMock()
        ticker.info = {"longName": "NVIDIA", "marketCap": 100}
        ticker.quarterly_balance_sheet = pd.DataFrame({"2026Q1": [1]})
        ticker.balance_sheet = pd.DataFrame()
        ticker.quarterly_cashflow = pd.DataFrame({"2026Q1": [2]})
        ticker.cashflow = pd.DataFrame({"2025": [3]})
        ticker.quarterly_income_stmt = pd.DataFrame({"2026Q1": [4]})
        ticker.income_stmt = pd.DataFrame({"2025": [5]})
        ticker.insider_transactions = pd.DataFrame({"shares": [10]})

        with patch("tradingagents.dataflows.y_finance.yf.Ticker", return_value=ticker):
            self.assertIn("# Company Fundamentals for NVDA", get_fundamentals("nvda"))
            self.assertIn(
                "# Balance Sheet data for NVDA (quarterly)",
                get_balance_sheet("nvda", "quarterly"),
            )
            self.assertIn(
                "No balance sheet data found", get_balance_sheet("nvda", "annual")
            )
            self.assertIn(
                "# Cash Flow data for NVDA (annual)", get_cashflow("nvda", "annual")
            )
            self.assertIn(
                "# Income Statement data for NVDA (quarterly)",
                get_income_statement("nvda", "quarterly"),
            )
            self.assertIn(
                "# Insider Transactions data for NVDA", get_insider_transactions("nvda")
            )

        ticker.info = {}
        ticker.insider_transactions = None
        with patch("tradingagents.dataflows.y_finance.yf.Ticker", return_value=ticker):
            self.assertIn("No fundamentals data found", get_fundamentals("nvda"))
            self.assertIn(
                "No insider transactions data found", get_insider_transactions("nvda")
            )

    def test_yfinance_news_extract_and_render_paths(self):
        nested_article = {
            "content": {
                "title": "Fed holds rates",
                "summary": "Markets react",
                "provider": {"displayName": "Reuters"},
                "canonicalUrl": {"url": "https://example.com/story"},
                "pubDate": "2026-01-15T12:00:00Z",
            }
        }
        flat_article = {
            "title": "Flat story",
            "publisher": "AP",
            "link": "https://flat",
        }
        self.assertEqual(_extract_article_data(nested_article)["publisher"], "Reuters")
        self.assertEqual(_extract_article_data(flat_article)["title"], "Flat story")

        ticker = MagicMock()
        ticker.get_news.return_value = [nested_article, flat_article]
        with patch(
            "tradingagents.dataflows.yfinance_news.yf.Ticker", return_value=ticker
        ):
            result = get_news_yfinance("NVDA", "2026-01-14", "2026-01-15")
            self.assertIn("## NVDA News", result)
            self.assertIn("Fed holds rates", result)

        ticker.get_news.return_value = []
        with patch(
            "tradingagents.dataflows.yfinance_news.yf.Ticker", return_value=ticker
        ):
            self.assertIn(
                "No news found", get_news_yfinance("NVDA", "2026-01-14", "2026-01-15")
            )

        search_one = MagicMock(news=[nested_article, nested_article])
        search_two = MagicMock(news=[flat_article])
        with patch(
            "tradingagents.dataflows.yfinance_news.yf.Search",
            side_effect=[search_one, search_two],
        ):
            global_result = get_global_news_yfinance(
                "2026-01-15", look_back_days=2, limit=2
            )
            self.assertIn("## Global Market News", global_result)
            self.assertIn("Fed holds rates", global_result)

        with patch(
            "tradingagents.dataflows.yfinance_news.yf.Search",
            side_effect=Exception("boom"),
        ):
            self.assertIn(
                "Error fetching global news", get_global_news_yfinance("2026-01-15")
            )


if __name__ == "__main__":
    unittest.main()
