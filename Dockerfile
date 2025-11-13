# Unsealed Networks MCP Server
# Multi-stage build for smaller final image

FROM python:3.11-slim AS builder

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Set working directory
WORKDIR /app

# Copy project files
COPY pyproject.toml uv.lock ./
COPY src/ ./src/
COPY README.md ./

# Install dependencies
RUN uv sync --frozen --no-dev

# Final stage
FROM python:3.11-slim

# Install sqlite3
RUN apt-get update && \
    apt-get install -y sqlite3 && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/src /app/src
COPY --from=builder /app/pyproject.toml /app/pyproject.toml

# Copy database
COPY data/unsealed.db /app/data/unsealed.db

# Copy entrypoint script
COPY --chmod=755 scripts/docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh

# Environment
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

# Expose port for SSE server (optional)
EXPOSE 8765

# Default to stdio MCP server
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
CMD ["stdio"]
