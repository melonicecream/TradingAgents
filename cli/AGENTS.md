# CLI Module

**Purpose:** Interactive terminal interface  
**Framework:** Typer + Rich  
**Entry Point:** `cli.main:app`

## Structure

```
cli/
├── __init__.py              # Module marker
├── main.py                  # Main Typer app (1,370 lines)
├── models.py                # Pydantic models for CLI
├── utils.py                 # Utility functions
├── config.py                # CLI-specific config
├── stats_handler.py         # LLM stats tracking
└── announcements.py         # Community announcements
```

## Typer App

```python
app = typer.Typer(
    name="TradingAgents",
    help="TradingAgents CLI: Multi-Agents LLM Financial Trading Framework",
    add_completion=True,
)
```

### Command Registration

```python
@app.command()
def analyze(
    ticker: str = typer.Option(..., help="Stock ticker symbol"),
    date: str = typer.Option(..., help="Analysis date (YYYY-MM-DD)"),
    analysts: List[str] = typer.Option(["market", "social", "news", "fundamentals"]),
):
    """Run trading analysis on a ticker."""
    ...
```

## MessageBuffer

Real-time progress tracking and display.

```python
class MessageBuffer:
    """Buffers agent messages for live display."""
    
    FIXED_AGENTS = {
        "Research Team": ["Bull Researcher", "Bear Researcher", "Research Manager"],
        "Trading Team": ["Trader"],
        "Risk Management": ["Aggressive Analyst", "Neutral Analyst", "Conservative Analyst"],
        "Portfolio Management": ["Portfolio Manager"],
    }
    
    ANALYST_MAPPING = {
        "market": "Market Analyst",
        "social": "Social Analyst",
        "news": "News Analyst",
        "fundamentals": "Fundamentals Analyst",
    }
    
    REPORT_SECTIONS = {
        "market_report": ("market", "Market Analyst"),
        "sentiment_report": ("social", "Social Analyst"),
        "news_report": ("news", "News Analyst"),
        "fundamentals_report": ("fundamentals", "Fundamentals Analyst"),
        "investment_plan": (None, "Research Manager"),
        "trader_investment_plan": (None, "Trader"),
        "final_trade_decision": (None, "Portfolio Manager"),
    }
```

## Rich UI Components

### Live Display

```python
with Live(display_layout, refresh_per_second=4, screen=True):
    # Stream graph execution
    for event in ta.propagate(ticker, date, stream=True):
        message_buffer.process_event(event)
        update_display()
```

### Panels and Tables

```python
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree

# Create panels
news_panel = Panel("News content", title="News Analysis")
table = Table(title="Trade Decision")
table.add_column("Action")
table.add_column("Confidence")
```

### Progress Tracking

```python
from rich.progress import Progress

with Progress() as progress:
    task = progress.add_task("[cyan]Analyzing...", total=100)
    # Update as agents complete
    progress.update(task, advance=10)
```

## Stats Tracking

`StatsCallbackHandler` tracks LLM usage.

```python
class StatsCallbackHandler:
    """Tracks token usage and costs."""
    
    def on_llm_end(self, response):
        self.total_tokens += response.usage.total_tokens
        self.total_cost += self.calculate_cost(response)
```

## Interactive Prompts

```python
import questionary

# Select analysts
selected = questionary.checkbox(
    "Select analysts:",
    choices=["market", "social", "news", "fundamentals"],
).ask()

# Select date
date = questionary.text("Enter date (YYYY-MM-DD):").ask()
```

## Configuration

CLI loads config from:
1. Command-line options
2. Config file (`~/.tradingagents/config.yaml`)
3. Environment variables
4. Default values

```python
# config.py
CLI_CONFIG = {
    "default_analysts": ["market", "social", "news", "fundamentals"],
    "default_date": "today",
    "results_dir": "./results",
}
```

## Adding a New Command

1. **Define command function**:
   ```python
   @app.command()
   def my_command(
       arg: str = typer.Option(..., help="Description"),
       flag: bool = typer.Option(False, help="Toggle"),
   ):
       """Command help text."""
       console.print(f"Processing {arg}...")
       result = process(arg)
       console.print(result)
   ```

2. **Add to `__main__`**:
   ```python
   if __name__ == "__main__":
       app()
   ```

## Conventions

- **Use** `typer.Option()` for all CLI arguments
- **Use** `console.print()` for output (not print())
- **Use** `questionary` for interactive prompts
- **Use** Rich panels/tables for structured output
- **Handle** KeyboardInterrupt gracefully

## Anti-Patterns

- Don't use bare `print()` (breaks Rich formatting)
- Don't hardcode colors (use Rich styles)
- Don't block on network calls without progress indicator
- Don't ignore typer's type validation

## Entry Points

```python
# pyproject.toml
[project.scripts]
tradingagents = "cli.main:app"
```

Usage:
```bash
tradingagents --help
tradingagents analyze --ticker NVDA --date 2026-01-15
python -m cli.main
```
