from typing import Any, Optional

from langchain_anthropic import ChatAnthropic

from .base_client import BaseLLMClient, invoke_with_incremental_retry, normalize_content
from .validators import validate_model

_PASSTHROUGH_KWARGS = (
    "timeout",
    "max_retries",
    "api_key",
    "max_tokens",
    "callbacks",
    "http_client",
    "http_async_client",
    "effort",
)


class NormalizedChatAnthropic(ChatAnthropic):
    """ChatAnthropic with normalized content output."""

    def invoke(self, input, config=None, **kwargs) -> Any:
        return normalize_content(
            invoke_with_incremental_retry(
                super().invoke,
                input,
                config,
                **kwargs,
            )
        )


class AnthropicClient(BaseLLMClient):
    """Client for Anthropic Claude models."""

    def __init__(self, model: str, base_url: Optional[str] = None, **kwargs):
        super().__init__(model, base_url, **kwargs)

    def get_llm(self) -> Any:
        self.warn_if_unknown_model()
        llm_kwargs: dict[str, Any] = {"model": self.model}

        if self.base_url:
            llm_kwargs["base_url"] = self.base_url

        for key in _PASSTHROUGH_KWARGS:
            if key in self.kwargs:
                llm_kwargs[key] = self.kwargs[key]

        return NormalizedChatAnthropic(**llm_kwargs)

    def validate_model(self) -> bool:
        return validate_model("anthropic", self.model)
