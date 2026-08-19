# =============================================================================
# Cartographer Backend — Dockerfile
# Multi-stage build: dependencies → development → production
# =============================================================================

# ---------------------------------------------------------------------------
# Stage 1: Base with uv (fast Python package manager)
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install uv
RUN pip install uv

# ---------------------------------------------------------------------------
# Stage 2: Dependencies
# ---------------------------------------------------------------------------
FROM base AS deps

COPY pyproject.toml README.md ./

# Install production dependencies
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system -e "." --extra-index-url https://download.pytorch.org/whl/cpu

# ---------------------------------------------------------------------------
# Stage 3: Development (hot-reload, dev dependencies)
# ---------------------------------------------------------------------------
FROM deps AS development

RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system -e ".[dev]" --extra-index-url https://download.pytorch.org/whl/cpu

COPY . .

EXPOSE 8000 9090

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# ---------------------------------------------------------------------------
# Stage 4: Production (slim, no dev deps)
# ---------------------------------------------------------------------------
FROM deps AS production

COPY . .

# Create non-root user
RUN groupadd -r cartographer && useradd -r -g cartographer cartographer
RUN chown -R cartographer:cartographer /app
USER cartographer

EXPOSE 8000

# Use gunicorn + uvicorn workers for production
CMD ["uvicorn", "app.main:app", \
    "--host", "0.0.0.0", \
    "--port", "8000", \
    "--workers", "4", \
    "--loop", "uvloop", \
    "--http", "httptools", \
    "--access-log"]
