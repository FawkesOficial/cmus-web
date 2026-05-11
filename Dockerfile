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

# Install system dependencies (cmus provides cmus-remote)
RUN apt-get update && \
    apt-get install -y --no-install-recommends cmus && \
    rm -rf /var/lib/apt/lists/*

# Copy uv binary from official image (pinned for reproducibility)
COPY --from=ghcr.io/astral-sh/uv:0.11.11 /uv /uvx /bin/

# Optimizations
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
ENV UV_NO_DEV=1

# Install dependencies in a separate layer (cached until pyproject.toml or uv.lock change)
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project

# Copy project source code
COPY pyproject.toml uv.lock ./
COPY backend/ ./backend/
COPY frontend/ ./frontend/

# Sync the project itself
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked

# Make virtual env binaries available on PATH
ENV PATH="/app/.venv/bin:$PATH"

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
