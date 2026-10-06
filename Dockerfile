# Production Dockerfile for Glyph
# Multi-stage build for optimized image size
#
# SCOPE: This image is "API/UI only". It does NOT bundle a JDK or Ghidra, and
# PyGhidra is not a dependency, so binary decompilation (the core analysis
# feature) cannot run inside this image. The web UI and REST API work fully,
# but upload/analysis endpoints that require decompilation will fail until the
# app is given a Ghidra runtime.
#
# To enable decompilation, run Glyph in an environment that has:
#   - a JDK (17+) and a Ghidra 12.0+ installation,
#   - `pyghidra` installed in the app's Python environment,
#   - GHIDRA_INSTALL_DIR pointing at the Ghidra directory.
# This is typically done by running the app on a host that already has Ghidra,
# or by extending this image with a Ghidra/JDK layer.

# Version stage: derive the version from the source of truth (app/_version.py)
# and fail the build if the GLYPH_VERSION build-arg disagrees with it, so the
# label below can never silently drift from the code.
FROM python:3.12-slim AS version
WORKDIR /src
COPY app/_version.py app/_version.py
ARG GLYPH_VERSION=0.3.0
RUN ACTUAL=$(python -c "from app._version import __version__; print(__version__)") \
    && if [ "$ACTUAL" != "$GLYPH_VERSION" ]; then \
         echo "ERROR: GLYPH_VERSION ($GLYPH_VERSION) does not match app/_version.py ($ACTUAL)." >&2 \
         && echo "Update the GLYPH_VERSION build-arg (or its default below) to match app/_version.py." >&2 \
         && exit 1; \
       fi \
    && echo "$ACTUAL" > /version.txt

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

# Set labels. The version must match app/_version.py — the "version" stage above
# fails the build if it does not, so this label can never silently drift.
ARG GLYPH_VERSION=0.3.0
LABEL maintainer="glyph-team"
LABEL description="Glyph - Architecture-independent binary analysis tool (API/UI only; Ghidra/JDK not bundled)"
LABEL version="${GLYPH_VERSION}"

# Create non-root user
RUN groupadd -r glyph && useradd -r -g glyph -d /app -m glyph

# Set working directory
WORKDIR /app

# Derived version file (source of truth: app/_version.py)
COPY --from=version --chown=glyph:glyph /version.txt /app/VERSION

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
