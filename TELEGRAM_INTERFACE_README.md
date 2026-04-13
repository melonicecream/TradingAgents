Telegram Interface Guide

Overview
- Personal-use Telegram bot interface for TradingAgents.
- Reuses the existing durable web execution lifecycle and Korean summary flow.
- Supports menu-driven navigation, recent execution browsing, segmented report delivery, and final Korean summary delivery.

Features
- Main menu with:
  - New analysis
  - Recent executions
  - System stats
  - Engine info
  - Help
- Personal-use access restriction via allowed Telegram chat ID
- Long report delivery split into sections:
  - Summary
  - Analyst reports
  - Research / trading
  - Risk
- Final Korean summary reused from the same summary generator used by CLI/Web

Required environment variables
- TELEGRAM_BOT_TOKEN
- TELEGRAM_CHAT_ID
- DATABASE_URL (optional, defaults to ./data/tradingagents.db)

Run locally
1. Export your environment variables
2. Run:
   tradingagents-telegram

Run with Docker Compose
1. Set `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` in your shell or `.env.zen`
2. Start the full stack:
   docker compose up --build
3. Or start only the bot and backend:
   docker compose up --build api telegram
4. Frontend access on OrbStack:
   http://frontend.tradingagents-core.orb.local

Menu flow
1. /start
2. Choose 새 분석
3. Send ticker text
4. Toggle analysts with inline buttons
5. Send analysis date
6. Receive live progress updates
7. After completion, open sectioned detail with buttons

Notes
- Telegram callback payloads are kept short and only carry compact routing keys.
- Detailed report content is fetched from the execution/detail API layer and split into multiple messages when needed.
- The bot is intentionally scoped for one-person usage and rejects unknown chat IDs.
- The `telegram` service shares the same `data/` and `results/` volumes as the web API so execution history and summaries stay aligned.
