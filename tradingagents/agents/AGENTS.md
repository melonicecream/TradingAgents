# Agents Module

**Purpose:** Multi-agent implementations for trading analysis  
**Pattern:** Factory functions + LangGraph nodes  
**State:** Shared via `AgentState` TypedDict

## Structure

```
agents/
├── analysts/              # Data collection agents
│   ├── market_analyst.py
│   ├── social_media_analyst.py
│   ├── news_analyst.py
│   └── fundamentals_analyst.py
├── researchers/           # Bull/Bear debate
│   ├── bull_researcher.py
│   └── bear_researcher.py
├── risk_mgmt/             # Risk assessment debate
│   ├── aggressive_debator.py
│   ├── conservative_debator.py
│   └── neutral_debator.py
├── managers/              # Decision makers
│   ├── research_manager.py
│   └── portfolio_manager.py
├── trader/                # Trading decisions
│   └── trader.py
└── utils/                 # Shared utilities
    ├── agent_states.py    # State type definitions
    ├── memory.py          # BM25-based memory
    ├── core_stock_tools.py
    ├── technical_indicators_tools.py
    ├── fundamental_data_tools.py
    ├── news_data_tools.py
    └── agent_utils.py
```

## Agent Architecture

### Factory Function Pattern

Every agent is created via a factory function that returns a node function:

```python
def create_market_analyst(llm):
    """Returns node function for LangGraph."""
    def market_analyst_node(state):
        # Access state fields
        ticker = state["company_of_interest"]
        # Call tools
        data = get_stock_data(ticker, ...)
        # Generate report
        report = generate_report(data)
        # Return state updates
        return {
            "messages": [result],
            "market_report": report
        }
    return market_analyst_node
```

### Agent Types

| Type | Memory | LLM | Responsibility |
|------|--------|-----|----------------|
| **Analysts** | No | Quick | Data collection & initial analysis |
| **Researchers** | Yes | Quick | Bull/Bear debate |
| **Trader** | Yes | Quick | Compose analysis into trade decision |
| **Risk Analysts** | No | Quick | Triple debate on risk (Aggressive/Conservative/Neutral) |
| **Managers** | Yes | Deep | Final decisions (Research Manager, Portfolio Manager) |

### Memory Usage

Agents with memory receive `FinancialSituationMemory` instance:

```python
def create_bull_researcher(llm, memory):
    def bull_researcher_node(state):
        # Retrieve past similar situations
        memories = memory.get_memories(current_situation, n_matches=2)
        # Use in prompt
        prompt = build_prompt(memories)
        ...
    return bull_researcher_node
```

## State Definitions

### AgentState (Main)

```python
class AgentState(MessagesState):
    # Context
    company_of_interest: str
    trade_date: str
    sender: str
    
    # Analyst reports
    market_report: str
    sentiment_report: str
    news_report: str
    fundamentals_report: str
    
    # Debate states
    investment_debate_state: InvestDebateState
    risk_debate_state: RiskDebateState
    
    # Decisions
    investment_plan: str
    trader_investment_plan: str
    final_trade_decision: str
```

### InvestDebateState

```python
class InvestDebateState(TypedDict):
    bull_history: str
    bear_history: str
    history: str
    current_response: str
    judge_decision: str
    count: int
```

### RiskDebateState

```python
class RiskDebateState(TypedDict):
    aggressive_history: str
    conservative_history: str
    neutral_history: str
    history: str
    latest_speaker: str
    current_aggressive_response: str
    current_conservative_response: str
    current_neutral_response: str
    judge_decision: str
    count: int
```

## Tools

Tools are in `utils/` and decorated with `@tool`:

```python
from langchain_core.tools import tool

@tool
def get_stock_data(
    symbol: Annotated[str, "ticker symbol"],
    start_date: Annotated[str, "yyyy-mm-dd"],
    end_date: Annotated[str, "yyyy-mm-dd"],
) -> str:
    """Fetch OHLCV stock data."""
    return route_to_vendor("get_stock_data", symbol, start_date, end_date)
```

| Tool File | Tools |
|-----------|-------|
| `core_stock_tools.py` | `get_stock_data` |
| `technical_indicators_tools.py` | `get_indicators` |
| `fundamental_data_tools.py` | `get_fundamentals`, `get_balance_sheet`, `get_cashflow`, `get_income_statement` |
| `news_data_tools.py` | `get_news`, `get_global_news`, `get_insider_transactions` |

## Adding a New Agent

1. **Create file** in appropriate subdirectory:
   ```python
   # agents/analysts/my_analyst.py
   def create_my_analyst(llm):
       def my_analyst_node(state):
           # Implementation
           return {"messages": [result], "my_report": report}
       return my_analyst_node
   ```

2. **Export in `__init__.py`**:
   ```python
   from .analysts.my_analyst import create_my_analyst
   __all__ = [..., "create_my_analyst"]
   ```

3. **Register in `GraphSetup`**:
   ```python
   # tradingagents/graph/setup.py
   if "my" in selected_analysts:
       analyst_nodes["my"] = create_my_analyst(quick_llm)
   ```

4. **Add to state** (if new report type):
   ```python
   # agents/utils/agent_states.py
   class AgentState(MessagesState):
       my_report: str
   ```

## Memory System

`FinancialSituationMemory` uses BM25 for lexical similarity:

```python
class FinancialSituationMemory:
    def add_situations(self, situations: List[Tuple[str, str]]):
        """Add (situation, recommendation) pairs."""
        
    def get_memories(self, situation: str, n_matches: int) -> List[dict]:
        """Retrieve most similar past situations."""
```

**Memory instances** (in `TradingAgentsGraph`):
- `bull_memory`, `bear_memory` — Researchers
- `trader_memory` — Trader
- `invest_judge_memory` — Research Manager
- `portfolio_manager_memory` — Portfolio Manager

## Conventions

- **Factory functions** always named `create_<role>_<type>(llm, [memory])`
- **Node functions** return dict with state field updates
- **LLM injection** via closure (not global)
- **Tool binding** via `llm.bind_tools([...])`
- **State updates** never modify in-place, always return new dict

## Anti-Patterns

- Don't access global state
- Don't hardcode prompts (use prompt templates)
- Don't skip `__init__.py` exports
- Don't forget to add state field to `AgentState`
