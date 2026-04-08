FROM python:3.12-slim

WORKDIR /app

# Install curl for healthcheck
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Install uv for faster package management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy requirements
COPY web_api/requirements.txt ./requirements.txt

# Install dependencies
RUN uv pip install --system -r requirements.txt

# Copy web_api code
COPY web_api/ ./web_api/

# Copy tradingagents core (read-only reference)
COPY tradingagents/ ./tradingagents/

# Create non-root user
RUN useradd --create-home appuser && chown -R appuser /app
USER appuser

# Expose port
EXPOSE 8000

# Run with uvicorn
CMD ["uvicorn", "web_api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
