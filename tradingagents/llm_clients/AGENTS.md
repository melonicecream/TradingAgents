# LLM Clients Module

**Purpose:** Multi-provider LLM abstraction layer  
**Providers:** OpenAI, Anthropic, Google, xAI, OpenRouter, Ollama  
**Pattern:** Abstract base class + factory

## Structure

```
llm_clients/
├── __init__.py              # Exports: BaseLLMClient, create_llm_client
├── base_client.py           # Abstract base class
├── factory.py               # create_llm_client() factory function
├── openai_client.py         # OpenAI/GPT, xAI, OpenRouter, Ollama
├── anthropic_client.py      # Claude
├── google_client.py         # Gemini
└── validators.py            # Model validation utilities
```

## BaseLLMClient

Abstract base class defining the interface.

```python
class BaseLLMClient(ABC):
    @abstractmethod
    def get_llm(self) -> Any:
        """Return configured LLM instance."""
        pass
    
    @abstractmethod
    def validate_model(self) -> bool:
        """Check if model is supported."""
        pass
```

## Factory Pattern

```python
def create_llm_client(
    provider: str,
    model: str,
    base_url: Optional[str] = None,
    **kwargs
) -> BaseLLMClient:
    """Factory creates appropriate client."""
    provider_lower = provider.lower()
    
    if provider_lower in ("openai", "ollama", "openrouter"):
        return OpenAIClient(model, base_url, provider=provider_lower, **kwargs)
    
    if provider_lower == "xai":
        return OpenAIClient(model, base_url, provider="xai", **kwargs)
    
    if provider_lower == "anthropic":
        return AnthropicClient(model, base_url, **kwargs)
    
    if provider_lower == "google":
        return GoogleClient(model, base_url, **kwargs)
    
    raise ValueError(f"Unsupported LLM provider: {provider}")
```

## Provider Implementations

### OpenAIClient

Handles: OpenAI, xAI, OpenRouter, Ollama

```python
class OpenAIClient(BaseLLMClient):
    def __init__(self, model, base_url=None, provider="openai", **kwargs):
        self.model = model
        self.provider = provider
        self.kwargs = kwargs  # callbacks, reasoning_effort, etc.
    
    def get_llm(self):
        if self.provider == "openai":
            return ChatOpenAI(model=self.model, **self.kwargs)
        elif self.provider == "xai":
            return ChatOpenAI(
                model=self.model,
                base_url="https://api.x.ai/v1",
                api_key=os.getenv("XAI_API_KEY"),
                **self.kwargs
            )
        # ... etc
```

### AnthropicClient

```python
class AnthropicClient(BaseLLMClient):
    def get_llm(self):
        return ChatAnthropic(
            model=self.model,
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
            **self.kwargs
        )
```

### GoogleClient

```python
class GoogleClient(BaseLLMClient):
    def get_llm(self):
        return ChatGoogleGenerativeAI(
            model=self.model,
            google_api_key=os.getenv("GOOGLE_API_KEY"),
            **self.kwargs
        )
```

## Usage in TradingAgentsGraph

```python
class TradingAgentsGraph:
    def __init__(self, ..., config=None):
        # Get provider-specific kwargs
        llm_kwargs = self._get_provider_kwargs()
        
        # Create clients
        deep_client = create_llm_client(
            provider=self.config["llm_provider"],
            model=self.config["deep_think_llm"],
            base_url=self.config.get("backend_url"),
            **llm_kwargs
        )
        quick_client = create_llm_client(
            provider=self.config["llm_provider"],
            model=self.config["quick_think_llm"],
            base_url=self.config.get("backend_url"),
            **llm_kwargs
        )
        
        # Get LLM instances
        self.deep_thinking_llm = deep_client.get_llm()
        self.quick_thinking_llm = quick_client.get_llm()
```

## Provider-Specific Configuration

### OpenAI

```python
config = {
    "llm_provider": "openai",
    "deep_think_llm": "gpt-5.2",
    "quick_think_llm": "gpt-5-mini",
    "backend_url": "https://api.openai.com/v1",
    "openai_reasoning_effort": "medium",  # "low", "medium", "high"
}
```

### Anthropic

```python
config = {
    "llm_provider": "anthropic",
    "deep_think_llm": "claude-4-6-20251101",
    "quick_think_llm": "claude-4-1-20251101",
    "anthropic_effort": "high",  # "low", "medium", "high"
}
```

### Google

```python
config = {
    "llm_provider": "google",
    "deep_think_llm": "gemini-3.1-pro",
    "quick_think_llm": "gemini-3.1-flash",
    "google_thinking_level": "high",  # "low", "medium", "high"
}
```

### Ollama (Local)

```python
config = {
    "llm_provider": "ollama",
    "deep_think_llm": "llama3.1:70b",
    "quick_think_llm": "llama3.1:8b",
    "backend_url": "http://localhost:11434",
}
```

## Adding a New Provider

1. **Create client class**:
   ```python
   # llm_clients/my_provider_client.py
   class MyProviderClient(BaseLLMClient):
       def get_llm(self):
           return MyLLMClass(model=self.model, ...)
   ```

2. **Update factory**:
   ```python
   # factory.py
   if provider_lower == "my_provider":
       return MyProviderClient(model, base_url, **kwargs)
   ```

3. **Export**:
   ```python
   # __init__.py (if needed)
   from .my_provider_client import MyProviderClient
   ```

## Conventions

- **Environment variables** for API keys (not hardcoded)
- **Factory** is the only public constructor
- **Base class** enforces interface contract
- **Provider-specific kwargs** passed through to LLM constructor
- **Callbacks** supported for all providers (token tracking, etc.)

## Anti-Patterns

- Don't instantiate clients directly (use factory)
- Don't hardcode API keys
- Don't skip validation
- Don't assume all providers support same features

## Model Validation

```python
# validators.py
VALID_MODELS = {
    "openai": ["gpt-5.2", "gpt-5-mini", "gpt-5.4", ...],
    "anthropic": ["claude-4-6-20251101", "claude-4-1-20251101", ...],
    "google": ["gemini-3.1-pro", "gemini-3.1-flash", ...],
}

def validate_model(provider: str, model: str) -> bool:
    return model in VALID_MODELS.get(provider, [])
```
