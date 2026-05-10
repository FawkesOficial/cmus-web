# cmus-web - PWA remote control for cmus
#
# Usage:
#   docker build -t cmus-web .
#   docker run -v /run/user/1000/cmus-socket:/tmp/cmus-socket -p 8000:8000 cmus-web
#
# The socket volume mount is required - cmus-web communicates with cmus
# via the Unix domain socket at the mounted path.

FROM python:3.13-slim AS base

WORKDIR /app

# Install uv for fast dependency resolution
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency files first (layer caching)
COPY pyproject.toml ./

# Install dependencies
RUN uv pip install --system --no-cache .

# Copy application code
COPY backend/ backend/
COPY frontend/ frontend/

# Create non-root user for security
RUN useradd --create-home appuser
USER appuser

# Expose default port
EXPOSE 8000

# cmus socket mount point - bind mount from host at runtime
VOLUME /tmp/cmus-socket

# Health check - verify server is responding
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/')"

# Entry point - use the cmus-web CLI command
ENTRYPOINT ["cmus-web"]
CMD ["--host", "0.0.0.0", "--port", "8000"]
