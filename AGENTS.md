# TradingAgents Knowledge Base

**Project:** Multi-Agent LLM Financial Trading Framework  
**Stack:** Python 3.10+, LangGraph, LangChain, Typer  
**Entry Point:** `main.py` or `python -m cli.main`

## Overview

Multi-agent trading system using LangGraph state machines. Agents collaborate through a directed workflow: Analysts → Researchers (debate) → Trader → Risk Management (debate) → Portfolio Manager.

## Structure

```
.
├── main.py                    # Package entry point
├── cli/                       # Interactive CLI (Typer)
├── tradingagents/
│   ├── graph/                 # LangGraph orchestration
│   │   ├── trading_graph.py   # Main TradingAgentsGraph class
│   │   ├── setup.py           # GraphSetup (node/edge assembly)
│   │   ├── propagation.py     # State initialization
│   │   ├── conditional_logic.py  # Flow control
│   │   └── reflection.py      # Memory updates
│   ├── agents/                # Agent implementations
│   │   ├── analysts/          # Market, Social, News, Fundamentals
│   │   ├── researchers/       # Bull, Bear researchers
│   │   ├── risk_mgmt/         # Aggressive, Conservative, Neutral debators
│   │   ├── managers/          # Research Manager, Portfolio Manager
│   │   ├── trader/            # Trader agent
│   │   └── utils/             # Tools, states, memory
│   ├── llm_clients/           # Multi-provider LLM abstraction
│   └── dataflows/             # Financial data (yfinance/Alpha Vantage)
└── tests/                     # unittest-based tests
```

## Where to Look

| Task | Location | Notes |
|------|----------|-------|
| Add new agent | `tradingagents/agents/` | Follow `create_*()` factory pattern |
| Modify workflow | `tradingagents/graph/setup.py` | `setup_graph()` method |
| Add data source | `tradingagents/dataflows/` | See vendor routing pattern |
| Change LLM provider | `tradingagents/llm_clients/` | Factory pattern in `factory.py` |
| CLI changes | `cli/` | Typer-based commands |
| Configuration | `tradingagents/default_config.py` | DEFAULT_CONFIG dict |

## Code Map

### Key Classes

| Class | File | Role |
|-------|------|------|
| `TradingAgentsGraph` | `graph/trading_graph.py` | Main orchestrator |
| `GraphSetup` | `graph/setup.py` | Builds LangGraph StateGraph |
| `FinancialSituationMemory` | `agents/utils/memory.py` | BM25-based retrieval |
| `AgentState` | `agents/utils/agent_states.py` | Main graph state |
| `BaseLLMClient` | `llm_clients/base_client.py` | Abstract LLM client |

### Agent Factory Functions

```python
# Analysts
create_market_analyst(llm)
create_social_media_analyst(llm)
create_news_analyst(llm)
create_fundamentals_analyst(llm)

# Researchers (with memory)
create_bull_researcher(llm, memory)
create_bear_researcher(llm, memory)

# Risk Management
create_aggressive_debator(llm)
create_conservative_debator(llm)
create_neutral_debator(llm)

# Managers (with memory)
create_research_manager(llm, memory)
create_portfolio_manager(llm, memory)

# Trader (with memory)
create_trader(llm, memory)
```

## Conventions

### Naming
- **Modules:** `snake_case` (e.g., `market_analyst.py`)
- **Classes:** `PascalCase` (e.g., `TradingAgentsGraph`)
- **Functions:** `snake_case` (e.g., `create_market_analyst`)
- **Private:** `_` prefix for module-level helpers (e.g., `_clean_dataframe`)
- **Factories:** `create_<entity>` pattern (e.g., `create_bull_researcher`)

### Imports
```python
# 1. Standard library
import time
import logging

# 2. Third-party
import pandas as pd
from langchain_core.tools import tool

# 3. Project (relative)
from .base_client import BaseLLMClient
from .config import get_config
```

### Type Hints
- Use `Annotated` for tool parameters (LangChain convention)
- Use `TypedDict` for state definitions
- Return unions: `dict[str, str] | str`

```python
from typing import Annotated

def get_stock_data(
    symbol: Annotated[str, "ticker symbol"],
    start_date: Annotated[str, "yyyy-mm-dd"],
) -> str:
    ...
```

### Agent Node Pattern
```python
def create_market_analyst(llm):
    """Factory returns node function."""
    def market_analyst_node(state):
        # Process state, call tools
        return {"messages": [result], "market_report": report}
    return market_analyst_node
```

### Error Handling
- Define custom exceptions (e.g., `AlphaVantageRateLimitError`)
- Use `try/except` with meaningful error messages
- Implement exponential backoff for retries

```python
def yf_retry(func, max_retries=3, base_delay=2.0):
    for attempt in range(max_retries + 1):
        try:
            return func()
        except YFRateLimitError:
            delay = base_delay * (2 ** attempt)
            time.sleep(delay)
```

### Logging
```python
logger = logging.getLogger(__name__)
logger.warning(f"Rate limited, retrying in {delay}s...")
```

## Anti-Patterns

- **Never** use `as any` or `@ts-ignore` equivalents (Python has no direct equivalent, but avoid bare `except:`)
- **Never** hardcode API keys (use environment variables or config)
- **Never** modify state in-place (return new state dict)
- **Never** block the event loop (use async where appropriate)

## Unique Patterns

### Vendor Routing (Dataflows)
```python
VENDOR_METHODS = {
    "get_stock_data": {
        "alpha_vantage": get_alpha_vantage_stock,
        "yfinance": get_YFin_data_online,
    },
}
```

### LLM Client Factory
```python
def create_llm_client(provider, model, base_url=None, **kwargs) -> BaseLLMClient:
    if provider in ("openai", "ollama", "openrouter"):
        return OpenAIClient(...)
    if provider == "anthropic":
        return AnthropicClient(...)
```

### Memory Integration
```python
# In agent node
memories = memory.get_memories(current_situation, n_matches=2)
# Inject memories into prompt
```

## Commands

```bash
# Install
pip install .

# Run CLI
tradingagents
python -m cli.main

# Run tests
python -m unittest tests/test_ticker_symbol_handling.py

# Run package example
python main.py
```

## Environment Variables

```bash
export OPENAI_API_KEY=...
export ANTHROPIC_API_KEY=...
export GOOGLE_API_KEY=...
export ALPHA_VANTAGE_API_KEY=...
```

## Notes

- **No CI/CD configured** — add `.github/workflows/` for automation
- **No Docker** — consider adding `Dockerfile` for containerization
- **Caching:** File-based CSV in `dataflows/data_cache/`
- **Memory:** BM25-based lexical similarity (not semantic)
- **Graph flow:** Analysts → Debate → Trader → Risk Debate → Portfolio Manager

## Subdirectory Guides

- `tradingagents/agents/` — Agent architecture and patterns
- `tradingagents/dataflows/` — Data vendor routing
- `tradingagents/graph/` — LangGraph orchestration
- `tradingagents/llm_clients/` — Multi-provider LLM abstraction
- `cli/` — Typer CLI patterns
