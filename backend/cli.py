"""cmus-web - Click CLI entry point for the FastAPI server."""

import logging
import os
import pathlib
from typing import Optional

import click
import uvicorn

from backend.main import app

logger = logging.getLogger(__name__)


@click.command()
@click.option("--host", default="127.0.0.1", help="Bind address (default: 127.0.0.1)")
@click.option("--port", default=8000, type=int, help="Port (default: 8000)")
@click.option(
    "--socket", default=None, help="cmus socket path (overrides CMUS_SOCKET env)"
)
@click.option(
    "--music-dir",
    default=None,
    envvar="CMUS_WEB_MUSIC_DIR",
    help="Container path to music directory (for album art in Docker)",
)
@click.option(
    "--prefix",
    default=None,
    envvar="CMUS_WEB_PREFIX",
    help="Host path prefix from cmus-remote to strip (e.g., /home/user/Music)",
)
def main(
    host: str,
    port: int,
    socket: Optional[str],
    music_dir: Optional[str],
    prefix: Optional[str],
) -> None:
    """cmus-web - PWA remote control for cmus."""

    if socket:
        os.environ["CMUS_SOCKET"] = socket

    if music_dir:
        music_path = pathlib.Path(music_dir)
        if not music_path.is_dir():
            logger.error("Music directory does not exist: %s", music_dir)
            raise click.BadParameter(
                f"Music directory does not exist: {music_dir}",
                param_hint="--music-dir",
            )
        os.environ["CMUS_WEB_MUSIC_DIR"] = str(music_path.resolve())

    if prefix:
        os.environ["CMUS_WEB_PREFIX"] = prefix

    if prefix and not music_dir:
        logger.warning(
            "--prefix is set but --music-dir is not. Path translation will not occur."
        )

    uvicorn.run(app, host=host, port=port)
