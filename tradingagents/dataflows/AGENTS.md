# Dataflows Module

**Purpose:** Financial data abstraction layer with vendor routing  
**Sources:** Yahoo Finance (default), Alpha Vantage (alternative)  
**Pattern:** Vendor-neutral routing with fallback chain

## Structure

```
dataflows/
├── interface.py                   # Main routing interface
├── config.py                      # Configuration singleton
├── y_finance.py                   # Yahoo Finance implementation
├── yfinance_news.py              # Yahoo Finance news
├── stockstats_utils.py           # Technical indicators (stockstats)
├── alpha_vantage.py              # Alpha Vantage entry point
├── alpha_vantage_common.py       # Shared utilities & rate limits
├── alpha_vantage_stock.py        # Stock data (Alpha Vantage)
├── alpha_vantage_fundamentals.py # Fundamentals (Alpha Vantage)
├── alpha_vantage_news.py         # News (Alpha Vantage)
├── alpha_vantage_indicator.py    # Indicators (Alpha Vantage)
└── utils.py                      # General utilities
```

## Vendor Routing

### VENDOR_METHODS Mapping

```python
VENDOR_METHODS = {
    "get_stock_data": {
        "alpha_vantage": get_alpha_vantage_stock,
        "yfinance": get_YFin_data_online,
    },
    "get_indicators": {
        "alpha_vantage": get_alpha_vantage_indicator,
        "yfinance": get_stock_stats_indicators_window,
    },
    "get_fundamentals": {...},
    "get_balance_sheet": {...},
    "get_cashflow": {...},
    "get_income_statement": {...},
    "get_news": {...},
    "get_global_news": {...},
    "get_insider_transactions": {...},
}
```

### Tool Categories

```python
TOOLS_CATEGORIES = {
    "core_stock_apis": {
        "description": "OHLCV stock price data",
        "tools": ["get_stock_data"]
    },
    "technical_indicators": {
        "description": "Technical analysis indicators",
        "tools": ["get_indicators"]
    },
    "fundamental_data": {
        "description": "Company fundamentals",
        "tools": ["get_fundamentals", "get_balance_sheet", 
                  "get_cashflow", "get_income_statement"]
    },
    "news_data": {
        "description": "News and insider data",
        "tools": ["get_news", "get_global_news", "get_insider_transactions"]
    }
}
```

### Routing Logic

```python
def route_to_vendor(method: str, *args, **kwargs):
    """Route method call to appropriate vendor with fallback."""
    # 1. Determine category and primary vendor
    category = get_category_for_method(method)
    primary_vendor = get_vendor(category, method)
    
    # 2. Build fallback chain
    fallback_vendors = [primary_vendor] + [v for v in VENDOR_LIST if v != primary_vendor]
    
    # 3. Try each vendor
    for vendor in fallback_vendors:
        try:
            impl_func = VENDOR_METHODS[method][vendor]
            return impl_func(*args, **kwargs)
        except AlphaVantageRateLimitError:
            continue  # Try next vendor
    
    raise RuntimeError(f"No available vendor for '{method}'")
```

## Configuration

### Default Config (default_config.py)

```python
DEFAULT_CONFIG = {
    "data_cache_dir": ".../tradingagents/dataflows/data_cache",
    "data_vendors": {
        "core_stock_apis": "yfinance",
        "technical_indicators": "yfinance",
        "fundamental_data": "yfinance",
        "news_data": "yfinance",
    },
    "tool_vendors": {
        # Tool-level overrides
        # "get_stock_data": "alpha_vantage",
    },
}
```

### Config Access

```python
from tradingagents.dataflows.config import get_config, set_config

# Get current config
config = get_config()

# Set custom config
set_config(my_config)
```

## Data Sources

### Yahoo Finance (yfinance)

- **Free, no API key required**
- **Rate limits:** Exponential backoff with `yf_retry()`
- **Caching:** CSV files in `data_cache/`
- **Best for:** Quick prototyping, US stocks

```python
# y_finance.py
def get_YFin_data_online(symbol, start_date, end_date):
    """Fetch stock data with caching."""
    cache_file = f"{symbol}-YFin-data-{start_date}-{end_date}.csv"
    if os.path.exists(cache_file):
        return pd.read_csv(cache_file)
    
    data = yf.download(symbol, start=start_date, end=end_date)
    data.to_csv(cache_file)
    return data
```

### Alpha Vantage

- **Requires API key:** `ALPHA_VANTAGE_API_KEY` env var
- **Rate limits:** 5 calls/minute (free tier)
- **Best for:** Fundamental data, wider coverage

```python
# alpha_vantage_common.py
class AlphaVantageRateLimitError(Exception):
    """Raised when rate limit exceeded."""
```

## Caching

### File-based CSV Caching

Location: `tradingagents/dataflows/data_cache/`

```python
cache_file = f"{symbol}-YFin-data-{start_date}-{end_date}.csv"
```

### Cache Behavior

- **Hit:** Read CSV directly
- **Miss:** Download, save to CSV, then return
- **15-year window:** Default bulk download range

## Error Handling

### Retry Pattern (Yahoo Finance)

```python
def yf_retry(func, max_retries=3, base_delay=2.0):
    for attempt in range(max_retries + 1):
        try:
            return func()
        except YFRateLimitError:
            if attempt < max_retries:
                delay = base_delay * (2 ** attempt)
                time.sleep(delay)
            else:
                raise
```

### Fallback Pattern (Alpha Vantage)

```python
try:
    return alpha_vantage_func(...)
except AlphaVantageRateLimitError:
    # Router automatically falls back to yfinance
    continue
```

## Technical Indicators

### Supported Indicators

```python
best_ind_params = {
    "close_50_sma",      # 50-day Simple Moving Average
    "close_200_sma",     # 200-day SMA
    "close_10_ema",      # 10-day Exponential MA
    "macd",              # MACD line
    "macds",             # MACD Signal
    "macdh",             # MACD Histogram
    "rsi",               # Relative Strength Index
    "boll",              # Bollinger Bands Middle
    "boll_ub",           # Bollinger Upper Band
    "boll_lb",           # Bollinger Lower Band
    "atr",               # Average True Range
    "vwma",              # Volume Weighted MA
    "mfi",               # Money Flow Index
}
```

### Calculation

```python
# stockstats_utils.py
from stockstats import wrap

def get_stock_stats(symbol, indicator, curr_date):
    data = download_stock_data(symbol)
    ss = wrap(data)
    return ss[indicator]
```

## Adding a New Data Source

1. **Create implementation file**:
   ```python
   # dataflows/my_provider.py
   def get_stock_data_my_provider(symbol, start, end):
       # Implementation
       return data
   ```

2. **Add to VENDOR_LIST**:
   ```python
   VENDOR_LIST = ["yfinance", "alpha_vantage", "my_provider"]
   ```

3. **Add to VENDOR_METHODS**:
   ```python
   VENDOR_METHODS = {
       "get_stock_data": {
           "yfinance": ...,
           "alpha_vantage": ...,
           "my_provider": get_stock_data_my_provider,
       }
   }
   ```

4. **Update config** (optional):
   ```python
   DEFAULT_CONFIG["data_vendors"]["core_stock_apis"] = "my_provider"
   ```

## Conventions

- **Always** use `route_to_vendor()` for data fetching
- **Always** implement rate limit handling
- **Always** cache bulk downloads
- **Return** strings (not raw objects) for LangChain compatibility
- **Use** `Annotated` type hints for tool parameters

## Anti-Patterns

- Don't call vendor APIs directly (use routing)
- Don't skip error handling for rate limits
- Don't cache without cache key scheme
- Don't return DataFrames (convert to strings)
