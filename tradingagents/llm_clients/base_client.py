import logging
import time
from abc import ABC, abstractmethod
from typing import Any, Optional


logger = logging.getLogger(__name__)


_RATE_LIMIT_RETRY_SUBSTRINGS = (
    "429",
    "rate limit exceeded",
    "freeusagelimiterror",
    "too many requests",
)


def is_retryable_rate_limit_error(error: Exception) -> bool:
    message = str(error).lower()
    return any(fragment in message for fragment in _RATE_LIMIT_RETRY_SUBSTRINGS)


def invoke_with_incremental_retry(
    invoke_func,
    input,
    config=None,
    *,
    max_retries: int = 10,
    base_delay: float = 1.0,
    **kwargs,
) -> Any:
    for attempt in range(max_retries + 1):
        try:
            return invoke_func(input, config=config, **kwargs)
        except Exception as error:
            if not is_retryable_rate_limit_error(error) or attempt >= max_retries:
                raise

            delay = base_delay * (2**attempt)
            logger.warning(
                "LLM rate limited, retrying in %.0fs (attempt %s/%s)",
                delay,
                attempt + 1,
                max_retries,
            )
            time.sleep(delay)


def normalize_content(response):
    """Normalize LLM response content to a plain string.

    Multiple providers (OpenAI Responses API, Google Gemini 3) return content
    as a list of typed blocks, e.g. [{'type': 'reasoning', ...}, {'type': 'text', 'text': '...'}].
    Downstream agents expect response.content to be a string. This extracts
    and joins the text blocks, discarding reasoning/metadata blocks.
    """
    content = response.content
    if isinstance(content, list):
        texts = [
            item.get("text", "")
            if isinstance(item, dict) and item.get("type") == "text"
            else item
            if isinstance(item, str)
            else ""
            for item in content
        ]
        response.content = "\n".join(t for t in texts if t)
    return response


class BaseLLMClient(ABC):
    """Abstract base class for LLM clients."""

    def __init__(self, model: str, base_url: Optional[str] = None, **kwargs):
        self.model = model
        self.base_url = base_url
        self.kwargs = kwargs

    @abstractmethod
    def get_llm(self) -> Any:
        """Return the configured LLM instance."""
        pass

    @abstractmethod
    def validate_model(self) -> bool:
        """Validate that the model is supported by this client."""
        pass
