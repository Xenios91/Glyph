# Production Dockerfile for Glyph
# Multi-stage build for optimized image size

# Build stage
FROM python:3.12-slim AS builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast dependency resolution
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency files
COPY pyproject.toml .
COPY license.md .
COPY README.md .

# Create virtual environment and install dependencies
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN uv pip install --no-cache-dir .

# Production stage
FROM python:3.12-slim AS production

# Set labels
LABEL maintainer="glyph-team"
LABEL description="Glyph - Architecture-independent binary analysis tool"
LABEL version="0.2.0"

# Create non-root user
RUN groupadd -r glyph && useradd -r -g glyph -d /app -m glyph

# Set working directory
WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libmagic1 \
    libffi8 \
    && rm -rf /var/lib/apt/lists/* \
    && chmod -R 755 /app

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application code
COPY --chown=glyph:glyph . .

# Create necessary directories
RUN mkdir -p /app/binaries /app/logs /app/models /app/data
RUN chown -R glyph:glyph /app

# Switch to non-root user
USER glyph

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Environment defaults
ENV GLYPH_ENV=production \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Run with uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
