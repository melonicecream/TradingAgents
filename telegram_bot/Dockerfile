FROM python:3.12-slim

WORKDIR /app

# Install minimal runtime tools
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Install uv for faster dependency installation
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy packaging metadata first for layer caching
COPY pyproject.toml README.md .env.example ./
COPY web_api/requirements.txt ./web_api-requirements.txt

# Install web/runtime dependencies needed by telegram_bot -> web_api imports
RUN uv pip install --system -r web_api-requirements.txt

# Copy application packages used by the telegram bot
COPY tradingagents/ ./tradingagents/
COPY web_api/ ./web_api/
COPY cli/ ./cli/
COPY telegram_bot/ ./telegram_bot/

# Install the project including telegram dependency
RUN uv pip install --system .

# Create non-root user
RUN useradd --create-home appuser && chown -R appuser /app
USER appuser

# Run telegram bot
CMD ["tradingagents-telegram"]
