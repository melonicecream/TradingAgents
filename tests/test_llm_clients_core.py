import os
import unittest
from types import SimpleNamespace
from typing import cast
from unittest.mock import patch

from tradingagents.llm_clients.anthropic_client import AnthropicClient
from tradingagents.llm_clients.base_client import (
    invoke_with_incremental_retry,
    is_retryable_rate_limit_error,
    normalize_content,
)
from tradingagents.llm_clients.factory import create_llm_client
from tradingagents.llm_clients.google_client import NormalizedChatGoogleGenerativeAI
from tradingagents.llm_clients.google_client import GoogleClient
from tradingagents.llm_clients.openai_client import NormalizedChatOpenAI
from tradingagents.llm_clients.openai_client import OpenAIClient
from tradingagents.llm_clients.anthropic_client import NormalizedChatAnthropic
from tradingagents.llm_clients.validators import validate_model


class LLMClientCoreTests(unittest.TestCase):
    def test_normalize_content_flattens_text_blocks(self):
        response = SimpleNamespace(
            content=[
                {"type": "reasoning", "text": "skip"},
                {"type": "text", "text": "BUY"},
                "NOW",
                {"type": "text", "text": "FAST"},
                123,
            ]
        )

        normalized = normalize_content(response)

        self.assertIs(normalized, response)
        self.assertEqual(response.content, "BUY\nNOW\nFAST")

    def test_validate_model_handles_provider_rules(self):
        self.assertTrue(validate_model("openai", "gpt-5.4"))
        self.assertFalse(validate_model("openai", "not-a-real-model"))
        self.assertTrue(validate_model("ollama", "llama3.1:8b"))
        self.assertTrue(validate_model("openrouter", "anything/goes"))
        self.assertTrue(validate_model("unknown-provider", "whatever"))

    def test_rate_limit_detection_and_incremental_retry(self):
        self.assertTrue(
            is_retryable_rate_limit_error(Exception("429 Rate limit exceeded"))
        )
        self.assertTrue(
            is_retryable_rate_limit_error(Exception("FreeUsageLimitError: try later"))
        )
        self.assertFalse(
            is_retryable_rate_limit_error(Exception("authentication failed"))
        )

        calls = {"count": 0}

        def flaky(input, config=None, **kwargs):
            del input, config, kwargs
            calls["count"] += 1
            if calls["count"] < 3:
                raise Exception("Error code: 429 - Rate limit exceeded")
            return SimpleNamespace(content="ok")

        with patch("tradingagents.llm_clients.base_client.time.sleep") as sleep:
            result = invoke_with_incremental_retry(flaky, "prompt")

        self.assertEqual(result.content, "ok")
        self.assertEqual(calls["count"], 3)
        self.assertEqual([call.args[0] for call in sleep.call_args_list], [1.0, 2.0])

        with patch("tradingagents.llm_clients.base_client.time.sleep"):
            with self.assertRaises(Exception):
                invoke_with_incremental_retry(
                    lambda input, config=None, **kwargs: (_ for _ in ()).throw(
                        Exception("Rate limit exceeded")
                    ),
                    "prompt",
                    max_retries=1,
                )

    @patch("tradingagents.llm_clients.openai_client.ChatOpenAI.invoke")
    def test_normalized_openai_retries_on_rate_limit(self, mock_invoke):
        mock_invoke.side_effect = [
            Exception("FreeUsageLimitError: Rate limit exceeded"),
            SimpleNamespace(content="BUY"),
        ]

        llm = object.__new__(NormalizedChatOpenAI)

        with patch("tradingagents.llm_clients.base_client.time.sleep") as sleep:
            result = cast(SimpleNamespace, llm.invoke("prompt"))

        self.assertEqual(result.content, "BUY")
        self.assertEqual(mock_invoke.call_count, 2)
        sleep.assert_called_once_with(1.0)

    @patch("tradingagents.llm_clients.anthropic_client.ChatAnthropic.invoke")
    def test_normalized_anthropic_retries_on_rate_limit(self, mock_invoke):
        mock_invoke.side_effect = [
            Exception("429 too many requests"),
            SimpleNamespace(content="SELL"),
        ]

        llm = object.__new__(NormalizedChatAnthropic)

        with patch("tradingagents.llm_clients.base_client.time.sleep"):
            result = cast(SimpleNamespace, llm.invoke("prompt"))

        self.assertEqual(result.content, "SELL")
        self.assertEqual(mock_invoke.call_count, 2)

    @patch("tradingagents.llm_clients.google_client.ChatGoogleGenerativeAI.invoke")
    def test_normalized_google_retries_on_rate_limit(self, mock_invoke):
        mock_invoke.side_effect = [
            Exception("Rate limit exceeded. Please try again later."),
            SimpleNamespace(content="HOLD"),
        ]

        llm = object.__new__(NormalizedChatGoogleGenerativeAI)

        with patch("tradingagents.llm_clients.base_client.time.sleep"):
            result = cast(SimpleNamespace, llm.invoke("prompt"))

        self.assertEqual(result.content, "HOLD")
        self.assertEqual(mock_invoke.call_count, 2)

    def test_factory_routes_to_expected_client_types(self):
        self.assertIsInstance(create_llm_client("openai", "gpt-5.4"), OpenAIClient)
        xai_client = cast(
            OpenAIClient, create_llm_client("xai", "grok-4-fast-reasoning")
        )
        self.assertEqual(xai_client.provider, "xai")
        self.assertIsInstance(
            create_llm_client("anthropic", "claude-sonnet-4-6"),
            AnthropicClient,
        )
        self.assertIsInstance(
            create_llm_client("google", "gemini-2.5-pro"),
            GoogleClient,
        )
        with self.assertRaises(ValueError):
            create_llm_client("unsupported", "model")

    @patch("tradingagents.llm_clients.openai_client.NormalizedChatOpenAI")
    def test_openai_client_uses_responses_api_without_custom_base_url(self, mock_chat):
        client = OpenAIClient("gpt-5.4", timeout=30, reasoning_effort="high")

        client.get_llm()

        _, kwargs = mock_chat.call_args
        self.assertEqual(kwargs["model"], "gpt-5.4")
        self.assertEqual(kwargs["timeout"], 30)
        self.assertEqual(kwargs["reasoning_effort"], "high")
        self.assertTrue(kwargs["use_responses_api"])
        self.assertNotIn("base_url", kwargs)

    @patch("tradingagents.llm_clients.openai_client.NormalizedChatOpenAI")
    def test_openai_client_disables_responses_api_for_custom_base_url(self, mock_chat):
        client = OpenAIClient(
            "gpt-5.4",
            base_url="https://gateway.example/v1",
            api_key="sk-test",
        )

        client.get_llm()

        _, kwargs = mock_chat.call_args
        self.assertEqual(kwargs["base_url"], "https://gateway.example/v1")
        self.assertEqual(kwargs["api_key"], "sk-test")
        self.assertFalse(kwargs["use_responses_api"])

    @patch("tradingagents.llm_clients.openai_client.NormalizedChatOpenAI")
    def test_openai_compatible_provider_uses_env_config(self, mock_chat):
        with patch.dict(os.environ, {"XAI_API_KEY": "xai-secret"}, clear=False):
            OpenAIClient("grok-4-0709", provider="xai").get_llm()

        _, kwargs = mock_chat.call_args
        self.assertEqual(kwargs["base_url"], "https://api.x.ai/v1")
        self.assertEqual(kwargs["api_key"], "xai-secret")
        self.assertNotIn("use_responses_api", kwargs)

    @patch("tradingagents.llm_clients.openai_client.NormalizedChatOpenAI")
    def test_ollama_provider_sets_default_auth(self, mock_chat):
        OpenAIClient("llama3.1:8b", provider="ollama").get_llm()

        _, kwargs = mock_chat.call_args
        self.assertEqual(kwargs["base_url"], "http://localhost:11434/v1")
        self.assertEqual(kwargs["api_key"], "ollama")

    @patch("tradingagents.llm_clients.anthropic_client.NormalizedChatAnthropic")
    def test_anthropic_client_forwards_supported_kwargs(self, mock_chat):
        client = AnthropicClient(
            "claude-sonnet-4-6",
            base_url="https://anthropic.example/v1",
            timeout=10,
            effort="medium",
            max_tokens=2048,
        )

        client.get_llm()

        _, kwargs = mock_chat.call_args
        self.assertEqual(kwargs["model"], "claude-sonnet-4-6")
        self.assertEqual(kwargs["base_url"], "https://anthropic.example/v1")
        self.assertEqual(kwargs["timeout"], 10)
        self.assertEqual(kwargs["effort"], "medium")
        self.assertEqual(kwargs["max_tokens"], 2048)

    @patch("tradingagents.llm_clients.google_client.NormalizedChatGoogleGenerativeAI")
    def test_google_client_maps_minimal_to_low_for_gemini_3_pro(self, mock_chat):
        client = GoogleClient("gemini-3.1-pro-preview", thinking_level="minimal")

        client.get_llm()

        _, kwargs = mock_chat.call_args
        self.assertEqual(kwargs["model"], "gemini-3.1-pro-preview")
        self.assertEqual(kwargs["thinking_level"], "low")
        self.assertNotIn("thinking_budget", kwargs)

    @patch("tradingagents.llm_clients.google_client.NormalizedChatGoogleGenerativeAI")
    def test_google_client_maps_thinking_budget_for_gemini_2_5(self, mock_chat):
        client = GoogleClient(
            "gemini-2.5-pro",
            thinking_level="high",
            timeout=12,
            google_api_key="g-key",
        )

        client.get_llm()

        _, kwargs = mock_chat.call_args
        self.assertEqual(kwargs["thinking_budget"], -1)
        self.assertEqual(kwargs["timeout"], 12)
        self.assertEqual(kwargs["google_api_key"], "g-key")


if __name__ == "__main__":
    unittest.main()
