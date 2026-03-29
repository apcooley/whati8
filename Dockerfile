# ── Build stage ────────────────────────────────────────────
FROM python:3.11-slim AS builder

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Copy dependency files first (layer cache)
COPY pyproject.toml uv.lock* ./

# Install dependencies
RUN uv sync --no-dev --frozen 2>/dev/null || uv sync --no-dev

# Copy application code
COPY whati8/ whati8/
COPY alembic/ alembic/
COPY alembic.ini ./
COPY scripts/ scripts/

# Build frontend if source exists
COPY frontend/ frontend/
RUN if [ -f frontend/package.json ]; then \
        apt-get update && apt-get install -y --no-install-recommends nodejs npm && \
        cd frontend && npm ci && npm run build && \
        rm -rf node_modules && \
        apt-get purge -y nodejs npm && apt-get autoremove -y && rm -rf /var/lib/apt/lists/*; \
    fi

# ── Runtime stage ─────────────────────────────────────────
FROM python:3.11-slim AS runtime

# Install runtime deps (pg_dump for backups)
RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-client curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv for runtime
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Create non-root user
RUN useradd --create-home --shell /bin/bash whati8
USER whati8
WORKDIR /app

# Copy from builder
COPY --from=builder --chown=whati8:whati8 /app /app

EXPOSE 9428

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -sf http://localhost:9428/health || exit 1

# Run with uv
CMD ["uv", "run", "python", "-m", "whati8", "serve"]
