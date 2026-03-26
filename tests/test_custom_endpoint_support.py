import os
import unittest
from unittest.mock import patch

from cli.utils import (
    CUSTOM_MODEL_CHOICE_VALUE,
    CUSTOM_PROVIDER_CHOICE_VALUE,
    select_deep_thinking_agent,
    select_llm_provider,
    select_shallow_thinking_agent,
    set_custom_api_key_environment,
)
from tradingagents.llm_clients.anthropic_client import AnthropicClient
from tradingagents.llm_clients.openai_client import OpenAIClient


class PromptResult:
    """Simple stub that mimics questionary prompt objects."""

    def __init__(self, value):
        self.value = value

    def ask(self):
        return self.value


class CustomEndpointSupportTests(unittest.TestCase):
    def test_select_llm_provider_supports_custom_url_without_env_backend(self):
        """Custom URL mode should be available even without BACKEND_URL."""

        def fake_select(message, choices, **kwargs):
            if message == "Select your LLM backend:":
                self.assertTrue(
                    any(
                        getattr(choice, "value", (None,))[0]
                        == CUSTOM_PROVIDER_CHOICE_VALUE
                        for choice in choices
                    )
                )
                return PromptResult(
                    (
                        CUSTOM_PROVIDER_CHOICE_VALUE,
                        "https://api.openai.com/v1",
                        None,
                    )
                )

            if message == "Select protocol for custom URL:":
                self.assertEqual(
                    [getattr(choice, "value", None) for choice in choices],
                    ["openai", "anthropic"],
                )
                return PromptResult("anthropic")

            raise AssertionError(f"Unexpected prompt: {message}")

        with patch.dict(os.environ, {}, clear=False):
            with patch("cli.utils.questionary.select", side_effect=fake_select):
                with patch(
                    "cli.utils.questionary.text",
                    side_effect=[
                        PromptResult("https://gateway.example/v1"),
                        PromptResult("sk-custom"),
                    ],
                ):
                    provider, url, api_key = select_llm_provider()

        self.assertEqual(provider, "anthropic")
        self.assertEqual(url, "https://gateway.example/v1")
        self.assertEqual(api_key, "sk-custom")

    def test_select_shallow_thinking_agent_always_allows_custom_model(self):
        """Quick thinker selection should always allow free-form custom models."""

        def fake_select(message, choices, **kwargs):
            self.assertEqual(message, "Select Your [Quick-Thinking LLM Engine]:")
            self.assertIn(
                CUSTOM_MODEL_CHOICE_VALUE,
                [getattr(choice, "value", None) for choice in choices],
            )
            return PromptResult(CUSTOM_MODEL_CHOICE_VALUE)

        with patch.dict(os.environ, {}, clear=False):
            with patch("cli.utils.questionary.select", side_effect=fake_select):
                with patch(
                    "cli.utils.questionary.text",
                    return_value=PromptResult("openai/custom-quick-model"),
                ):
                    selected_model = select_shallow_thinking_agent("openai")

        self.assertEqual(selected_model, "openai/custom-quick-model")

    def test_select_deep_thinking_agent_always_allows_custom_model(self):
        """Deep thinker selection should always allow free-form custom models."""

        def fake_select(message, choices, **kwargs):
            self.assertEqual(message, "Select Your [Deep-Thinking LLM Engine]:")
            self.assertIn(
                CUSTOM_MODEL_CHOICE_VALUE,
                [getattr(choice, "value", None) for choice in choices],
            )
            return PromptResult(CUSTOM_MODEL_CHOICE_VALUE)

        with patch.dict(os.environ, {}, clear=False):
            with patch("cli.utils.questionary.select", side_effect=fake_select):
                with patch(
                    "cli.utils.questionary.text",
                    return_value=PromptResult("anthropic/custom-deep-model"),
                ):
                    selected_model = select_deep_thinking_agent("anthropic")

        self.assertEqual(selected_model, "anthropic/custom-deep-model")

    def test_set_custom_api_key_environment_uses_provider_specific_env_var(self):
        """Custom endpoint auth should reuse the provider's standard env var."""
        with patch.dict(os.environ, {}, clear=True):
            set_custom_api_key_environment("openai", "sk-openai")
            self.assertEqual(os.environ["OPENAI_API_KEY"], "sk-openai")

        with patch.dict(os.environ, {}, clear=True):
            set_custom_api_key_environment("anthropic", "sk-anthropic")
            self.assertEqual(os.environ["ANTHROPIC_API_KEY"], "sk-anthropic")

    @patch("tradingagents.llm_clients.openai_client.NormalizedChatOpenAI")
    def test_openai_client_disables_responses_api_for_custom_base_url(
        self, mock_chat_openai
    ):
        """Custom OpenAI-compatible endpoints should use chat completions mode."""
        OpenAIClient(
            "custom-openai-model",
            base_url="https://gateway.example/v1",
            api_key="sk-test",
        ).get_llm()

        _, kwargs = mock_chat_openai.call_args
        self.assertEqual(kwargs["base_url"], "https://gateway.example/v1")
        self.assertEqual(kwargs["api_key"], "sk-test")
        self.assertFalse(kwargs["use_responses_api"])

    @patch("tradingagents.llm_clients.anthropic_client.NormalizedChatAnthropic")
    def test_anthropic_client_forwards_custom_base_url(self, mock_chat_anthropic):
        """Custom Anthropic-compatible endpoints should forward base_url."""
        AnthropicClient(
            "custom-anthropic-model",
            base_url="https://gateway.example/v1",
            api_key="sk-test",
        ).get_llm()

        _, kwargs = mock_chat_anthropic.call_args
        self.assertEqual(kwargs["base_url"], "https://gateway.example/v1")
        self.assertEqual(kwargs["api_key"], "sk-test")


if __name__ == "__main__":
    unittest.main()
