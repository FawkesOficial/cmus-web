"""cmus-web - Click CLI entry point for the FastAPI server."""

import os

import click
import uvicorn

from backend.main import app


@click.command()
@click.option("--host", default="127.0.0.1", help="Bind address (default: 127.0.0.1)")
@click.option("--port", default=8000, type=int, help="Port (default: 8000)")
@click.option(
    "--socket", default=None, help="cmus socket path (overrides CMUS_SOCKET env)"
)
def main(host: str, port: int, socket: str | None) -> None:
    """cmus-web - PWA remote control for cmus."""

    if socket:
        os.environ["CMUS_SOCKET"] = socket

    uvicorn.run(app, host=host, port=port)
