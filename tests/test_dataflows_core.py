import unittest
from datetime import datetime
from unittest.mock import MagicMock, patch

from tradingagents.dataflows import config as config_module
from tradingagents.dataflows.alpha_vantage_common import (
    AlphaVantageRateLimitError,
    _filter_csv_by_date_range,
    _make_api_request,
    format_datetime_for_api,
    get_api_key,
)
from tradingagents.dataflows.interface import (
    get_category_for_method,
    get_vendor,
    route_to_vendor,
)


class DataflowsCoreTests(unittest.TestCase):
    def test_get_category_for_method_and_unknown_method(self):
        self.assertEqual(get_category_for_method("get_stock_data"), "core_stock_apis")
        self.assertEqual(get_category_for_method("get_global_news"), "news_data")
        with self.assertRaises(ValueError):
            get_category_for_method("missing_method")

    def test_get_vendor_prefers_tool_override_then_category_default(self):
        with patch(
            "tradingagents.dataflows.interface.get_config",
            return_value={
                "tool_vendors": {"get_stock_data": "alpha_vantage"},
                "data_vendors": {"core_stock_apis": "yfinance"},
            },
        ):
            self.assertEqual(
                get_vendor("core_stock_apis", "get_stock_data"), "alpha_vantage"
            )

        with patch(
            "tradingagents.dataflows.interface.get_config",
            return_value={
                "tool_vendors": {},
                "data_vendors": {"core_stock_apis": "yfinance"},
            },
        ):
            self.assertEqual(
                get_vendor("core_stock_apis", "get_stock_data"), "yfinance"
            )

    def test_route_to_vendor_uses_primary_vendor_and_fallback(self):
        alpha_impl = MagicMock(side_effect=AlphaVantageRateLimitError("limit"))
        yfinance_impl = MagicMock(return_value="fallback data")

        with patch(
            "tradingagents.dataflows.interface.get_vendor", return_value="alpha_vantage"
        ):
            with patch.dict(
                "tradingagents.dataflows.interface.VENDOR_METHODS",
                {
                    "get_stock_data": {
                        "alpha_vantage": alpha_impl,
                        "yfinance": yfinance_impl,
                    }
                },
                clear=False,
            ):
                result = route_to_vendor(
                    "get_stock_data", "NVDA", "2026-01-01", "2026-01-31"
                )

        self.assertEqual(result, "fallback data")
        alpha_impl.assert_called_once_with("NVDA", "2026-01-01", "2026-01-31")
        yfinance_impl.assert_called_once_with("NVDA", "2026-01-01", "2026-01-31")

    def test_route_to_vendor_raises_when_no_vendor_succeeds(self):
        failing_impl = MagicMock(side_effect=AlphaVantageRateLimitError("limit"))

        with patch(
            "tradingagents.dataflows.interface.get_vendor", return_value="alpha_vantage"
        ):
            with patch.dict(
                "tradingagents.dataflows.interface.VENDOR_METHODS",
                {
                    "get_stock_data": {
                        "alpha_vantage": failing_impl,
                        "yfinance": failing_impl,
                    }
                },
                clear=False,
            ):
                with self.assertRaises(RuntimeError):
                    route_to_vendor(
                        "get_stock_data", "NVDA", "2026-01-01", "2026-01-31"
                    )

    def test_route_to_vendor_skips_unknown_primary_vendor_and_uses_available_one(self):
        yfinance_impl = MagicMock(return_value="ok")

        with patch(
            "tradingagents.dataflows.interface.get_vendor",
            return_value="missing_vendor",
        ):
            with patch.dict(
                "tradingagents.dataflows.interface.VENDOR_METHODS",
                {"get_stock_data": {"yfinance": yfinance_impl}},
                clear=False,
            ):
                result = route_to_vendor(
                    "get_stock_data", "NVDA", "2026-01-01", "2026-01-31"
                )

        self.assertEqual(result, "ok")
        yfinance_impl.assert_called_once()

    def test_config_module_initializes_updates_and_returns_copy(self):
        original = config_module._config
        try:
            config_module._config = None
            config_module.initialize_config()
            baseline = config_module.get_config()

            config_module.set_config({"custom_key": "value"})
            current = config_module.get_config()
            current["custom_key"] = "mutated"

            self.assertIn("data_vendors", baseline)
            self.assertEqual(config_module.get_config()["custom_key"], "value")
        finally:
            config_module._config = original

    def test_get_api_key_and_datetime_formatting(self):
        with patch.dict(
            "os.environ", {"ALPHA_VANTAGE_API_KEY": "alpha-key"}, clear=True
        ):
            self.assertEqual(get_api_key(), "alpha-key")

        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(ValueError):
                get_api_key()

        self.assertEqual(format_datetime_for_api("2026-01-15"), "20260115T0000")
        self.assertEqual(format_datetime_for_api("2026-01-15 13:45"), "20260115T1345")
        self.assertEqual(format_datetime_for_api("20260115T1345"), "20260115T1345")
        self.assertEqual(
            format_datetime_for_api(datetime(2026, 1, 15, 9, 30)),
            "20260115T0930",
        )
        with self.assertRaises(ValueError):
            format_datetime_for_api("15/01/2026")
        with self.assertRaises(ValueError):
            format_datetime_for_api(123)

    @patch(
        "tradingagents.dataflows.alpha_vantage_common.get_api_key",
        return_value="alpha-key",
    )
    @patch("tradingagents.dataflows.alpha_vantage_common.requests.get")
    def test_make_api_request_handles_csv_and_entitlement(self, mock_get, _mock_key):
        response = MagicMock()
        response.text = "timestamp,close\n2026-01-15,100\n"
        response.raise_for_status.return_value = None
        mock_get.return_value = response

        result = _make_api_request(
            "TIME_SERIES_DAILY", {"symbol": "NVDA", "entitlement": None}
        )

        self.assertIn("timestamp,close", result)
        _, kwargs = mock_get.call_args
        self.assertEqual(kwargs["params"]["function"], "TIME_SERIES_DAILY")
        self.assertEqual(kwargs["params"]["apikey"], "alpha-key")
        self.assertNotIn("entitlement", kwargs["params"])

    @patch(
        "tradingagents.dataflows.alpha_vantage_common.get_api_key",
        return_value="alpha-key",
    )
    @patch("tradingagents.dataflows.alpha_vantage_common.requests.get")
    def test_make_api_request_raises_rate_limit_error_from_json(
        self, mock_get, _mock_key
    ):
        response = MagicMock()
        response.text = '{"Information": "API rate limit exceeded for free tier"}'
        response.raise_for_status.return_value = None
        mock_get.return_value = response

        with self.assertRaises(AlphaVantageRateLimitError):
            _make_api_request("TIME_SERIES_DAILY", {"symbol": "NVDA"})

    def test_filter_csv_by_date_range_filters_and_falls_back(self):
        csv_data = "timestamp,close\n2026-01-01,100\n2026-01-15,110\n2026-02-01,120\n"

        filtered = _filter_csv_by_date_range(csv_data, "2026-01-05", "2026-01-31")

        self.assertIn("2026-01-15", filtered)
        self.assertNotIn("2026-01-01", filtered)
        self.assertNotIn("2026-02-01", filtered)
        self.assertEqual(_filter_csv_by_date_range("", "2026-01-01", "2026-01-31"), "")

        with patch(
            "tradingagents.dataflows.alpha_vantage_common.pd.read_csv",
            side_effect=Exception("boom"),
        ):
            self.assertEqual(
                _filter_csv_by_date_range(csv_data, "2026-01-05", "2026-01-31"),
                csv_data,
            )


if __name__ == "__main__":
    unittest.main()
