# Multi-stage build for MOEX Pair Trading Screener
FROM python:3.11-slim as builder

# Install UV
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Set working directory
WORKDIR /app

# Copy dependency files
COPY pyproject.toml ./

# Install dependencies using UV
RUN uv pip install --system -e .

# Production stage
FROM python:3.11-slim

# Install UV in production
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Create non-root user
RUN useradd -m -u 1000 screener && \
    mkdir -p /app/logs /app/data/cache && \
    chown -R screener:screener /app

# Set working directory
WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY --chown=screener:screener src/ ./src/
COPY --chown=screener:screener pyproject.toml ./

# Switch to non-root user
USER screener

# Health check (can be added later when API is implemented)
# HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
#     CMD python -c "import sys; sys.exit(0)"

# Set Python path
ENV PYTHONPATH=/app

# Default command - run production screener
CMD ["python", "-m", "src.screener"]

