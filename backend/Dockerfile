# Knowledge Graph Backend Dockerfile
#
# Multi-stage build for development and production:
# - Base: Common dependencies and UV setup
# - Development: Hot reload, debug tools
# - Production: Optimized, minimal runtime

# =============================================================================
# Base Stage - Common dependencies and UV setup
# =============================================================================
FROM python:3.12-slim as base

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    # Essential tools
    curl \
    # Build dependencies for some Python packages
    gcc \
    g++ \
    # Cleanup
    && rm -rf /var/lib/apt/lists/*

# Install UV for fast Python package management
RUN pip install uv

# Create non-root user for security
RUN groupadd --gid 1000 appuser && \
    useradd --uid 1000 --gid appuser --shell /bin/bash --create-home appuser

# Set working directory
WORKDIR /app

# Copy dependency files
COPY backend/pyproject.toml backend/uv.lock ./
COPY README.md ./

# Install dependencies using UV (much faster than pip)
RUN uv sync --frozen --no-cache

# =============================================================================
# Development Stage - Hot reload, debug tools
# =============================================================================
FROM base as development

# Install development dependencies
RUN uv sync --frozen --no-cache --extra dev

# Copy application code (will be overridden by volume mount in docker-compose)
COPY backend/kg/ ./kg/

# Create directories for mounted volumes
RUN mkdir -p /app/spec/schemas

# Change ownership to non-root user
RUN chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Development command with hot reload
CMD ["uv", "run", "--no-sync", "uvicorn", "kg.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# =============================================================================
# Production Stage - Optimized, minimal runtime
# =============================================================================
FROM base as production

# Install only production dependencies
RUN uv sync --frozen --no-cache --no-dev

# Copy application code
COPY backend/kg/ ./kg/

# Copy schema specifications (needed for schema loading)
COPY spec/ ./spec/

# Change ownership to non-root user
RUN chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Production command with optimized settings
CMD ["uv", "run", "--no-sync", "uvicorn", "kg.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]

# =============================================================================
# CLI Stage - Lightweight CLI-only image
# =============================================================================
FROM base as cli

# Install only core dependencies (no server dependencies)
RUN uv sync --frozen --no-dev

# Copy application code
COPY backend/kg/ ./kg/

# Copy schema specifications
COPY spec/ ./spec/

# Change ownership to non-root user
RUN chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# CLI entrypoint
ENTRYPOINT ["uv", "run", "--no-sync", "kg"]
