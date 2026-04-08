# Graph Module

**Purpose:** LangGraph orchestration and workflow management  
**Pattern:** StateGraph with conditional edges  
**State:** `AgentState` TypedDict

## Structure

```
graph/
├── __init__.py              # Module exports
├── trading_graph.py         # Main TradingAgentsGraph class
├── setup.py                 # GraphSetup (node/edge assembly)
├── propagation.py           # Propagator (state initialization)
├── conditional_logic.py     # Conditional edge functions
├── reflection.py            # Reflector (memory updates)
└── signal_processing.py     # SignalProcessor (result handling)
```

## TradingAgentsGraph

Main orchestrator class in `trading_graph.py`.

### Initialization

```python
ta = TradingAgentsGraph(
    selected_analysts=["market", "social", "news", "fundamentals"],
    debug=False,
    config=DEFAULT_CONFIG.copy(),
    callbacks=None,  # Optional callback handlers
)
```

### Key Components

| Component | Class | File | Purpose |
|-----------|-------|------|---------|
| LLM Clients | `create_llm_client()` | `llm_clients/` | Quick/Deep thinking LLMs |
| Tool Nodes | `ToolNode` | LangGraph | Bind tools to agents |
| Graph Setup | `GraphSetup` | `setup.py` | Build StateGraph |
| Propagator | `Propagator` | `propagation.py` | Initialize state |
| Reflector | `Reflector` | `reflection.py` | Update memories |
| Signal Processor | `SignalProcessor` | `signal_processing.py` | Process results |

### Propagate Method

```python
final_state, decision = ta.propagate("NVDA", "2026-01-15")
```

Flow:
1. Create initial state (Propagator)
2. Invoke/stream graph
3. Process signals (SignalProcessor)
4. Return (state, decision)

## GraphSetup

Builds the LangGraph StateGraph workflow.

### Workflow Structure

```
START → Analysts (parallel/sequential)
  ↓
Research Team (Bull ↔ Bear debate, rounds=1-3)
  ↓
Research Manager (judges debate)
  ↓
Trader (composes analysis)
  ↓
Risk Team (Aggressive ↔ Conservative ↔ Neutral debate)
  ↓
Portfolio Manager (5-tier decision: Buy/Overweight/Hold/Underweight/Sell)
  ↓
END
```

### Setup Method

```python
def setup_graph(self, selected_analysts=["market", "social", "news", "fundamentals"]):
    # Create analyst nodes
    analyst_nodes = {}
    for analyst_type in selected_analysts:
        analyst_nodes[analyst_type] = create_<type>_analyst(self.quick_llm)
    
    # Create researcher nodes (with memory)
    bull_node = create_bull_researcher(self.quick_llm, self.bull_memory)
    bear_node = create_bear_researcher(self.quick_llm, self.bear_memory)
    
    # Create risk nodes
    aggressive_node = create_aggressive_debator(self.quick_llm)
    conservative_node = create_conservative_debator(self.quick_llm)
    neutral_node = create_neutral_debator(self.quick_llm)
    
    # Create managers (with memory)
    research_manager = create_research_manager(self.deep_llm, self.invest_judge_memory)
    portfolio_manager = create_portfolio_manager(self.deep_llm, self.portfolio_manager_memory)
    
    # Create trader (with memory)
    trader = create_trader(self.quick_llm, self.trader_memory)
    
    # Build graph
    builder = StateGraph(AgentState)
    
    # Add nodes
    for name, node in analyst_nodes.items():
        builder.add_node(name, node)
    builder.add_node("bull", bull_node)
    builder.add_node("bear", bear_node)
    # ... etc
    
    # Add edges with conditional logic
    builder.add_conditional_edges("bull", should_continue_invest_debate)
    builder.add_conditional_edges("aggressive", should_continue_risk_debate)
    
    return builder.compile()
```

## Conditional Logic

Controls debate rounds and flow branching.

### InvestDebate (Bull/Bear)

```python
def should_continue_invest_debate(state: InvestDebateState):
    """Returns 'judge' or 'continue'."""
    if state["count"] >= MAX_DEBATE_ROUNDS:
        return "judge"
    return "continue"
```

### RiskDebate (3-way)

```python
def should_continue_risk_debate(state: RiskDebateState):
    """Returns 'judge' or 'continue'."""
    if state["count"] >= MAX_RISK_ROUNDS:
        return "judge"
    return "continue"
```

## Propagation

Initializes state and runs the graph.

### Propagator

```python
class Propagator:
    def create_initial_state(self, ticker: str, date: str) -> AgentState:
        return {
            "company_of_interest": ticker,
            "trade_date": date,
            "messages": [],
            "market_report": "",
            # ... initialize all fields
        }
    
    def propagate(self, ticker: str, date: str, stream: bool = False):
        state = self.create_initial_state(ticker, date)
        if stream:
            return self.graph.stream(state)
        else:
            return self.graph.invoke(state)
```

## Reflection

Updates agent memories after trades.

### Reflector

```python
class Reflector:
    def reflect_and_remember(self, returns_losses):
        """Called after trade execution."""
        self.reflect_bull_researcher(current_state, returns_losses, self.bull_memory)
        self.reflect_bear_researcher(current_state, returns_losses, self.bear_memory)
        self.reflect_trader(current_state, returns_losses, self.trader_memory)
        # ... etc
    
    def reflect_bull_researcher(self, state, returns, memory):
        situation = self._extract_situation(state)
        result = self._generate_reflection("BULL", situation, returns)
        memory.add_situations([(situation, result)])
```

### Usage

```python
# After trade execution
ta.reflect_and_remember(returns_losses=0.05)  # 5% return
```

## Signal Processing

Handles graph execution results.

### SignalProcessor

```python
class SignalProcessor:
    def process_signal(self, final_state: AgentState):
        """Extract final decision from state."""
        decision = final_state["final_trade_decision"]
        return decision
```

## Tool Nodes

Tools are bound to agents via ToolNode.

### Tool Registration

```python
# In TradingAgentsGraph._create_tool_nodes()
self.tool_nodes = {
    "market": ToolNode([get_stock_data, get_indicators]),
    "social": ToolNode([get_news]),
    "news": ToolNode([get_news, get_global_news, get_insider_transactions]),
    "fundamentals": ToolNode([
        get_fundamentals, get_balance_sheet, 
        get_cashflow, get_income_statement
    ]),
}
```

### Tool Binding

```python
# In agent node
llm_with_tools = llm.bind_tools([get_stock_data, get_indicators])
result = llm_with_tools.invoke(prompt)
```

## Conventions

- **GraphSetup** assembles nodes but doesn't execute
- **Conditional edges** use `add_conditional_edges(node, router_func)`
- **State updates** always return new dict, never modify in-place
- **Memory** is injected at construction, not accessed globally
- **Tools** are bound per-analyst category

## Anti-Patterns

- Don't create cycles in graph (unless intentional)
- Don't modify state outside node functions
- Don't skip `__init__.py` exports
- Don't hardcode debate rounds (use config)

## Debugging

```python
# Enable debug mode
ta = TradingAgentsGraph(debug=True, config=config)

# Stream execution for real-time updates
for event in ta.propagate("NVDA", "2026-01-15", stream=True):
    print(event)
```
