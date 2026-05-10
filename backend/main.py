"""cmus-web - PWA remote control for cmus."""

import asyncio
import json
import logging
import os
import pathlib
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from sse_starlette.sse import EventSourceResponse

from backend.cmus import (
    CmusNotRunning,
    CmusRemote,
    CmusRemoteError,
    CmusRemoteNotFound,
    NoTrackLoaded,
    get_album_art,
)

logger = logging.getLogger(__name__)

app = FastAPI(title="cmus-web")

# Mount static files from frontend/ directory
frontend_dir = os.path.join(os.path.dirname(__file__), "..", "frontend")
app.mount("/static", StaticFiles(directory=frontend_dir), name="static")

# cmus-remote wrapper instance
cmus = CmusRemote()


@app.get("/")
async def root() -> FileResponse:
    """Serve the placeholder index.html."""

    index_path = os.path.join(frontend_dir, "index.html")

    return FileResponse(index_path)


@app.get("/sse")
async def sse_endpoint(request: Request) -> EventSourceResponse:
    """Stream player state as Server-Sent Events with adaptive polling."""

    async def event_generator():
        while True:
            try:
                state = cmus.query_status()
                yield {
                    "event": "state",
                    "data": json.dumps(
                        {
                            "status": state.status,
                            "title": state.title,
                            "artist": state.artist,
                            "album": state.album,
                            "file": state.file,
                            "position": state.position,
                            "duration": state.duration,
                            "volume": state.volume,
                            "shuffle": state.shuffle,
                            "repeat": state.repeat,
                        }
                    ),
                }
                interval = 0.5 if state.status == "playing" else 1.0

            except CmusNotRunning:
                yield {"event": "state", "data": json.dumps({"status": "not_running"})}
                interval = 2.0
            except NoTrackLoaded:
                yield {"event": "state", "data": json.dumps({"status": "no_track"})}
                interval = 1.0
            except CmusRemoteNotFound:
                yield {"event": "state", "data": json.dumps({"status": "no_cmus"})}
                interval = 5.0
            except CmusRemoteError:
                yield {"event": "state", "data": json.dumps({"status": "error"})}
                interval = 5.0
            except Exception:
                logger.exception("SSE poll error")
                yield {"event": "state", "data": json.dumps({"status": "error"})}
                interval = 5.0

            await asyncio.sleep(interval)
            if await request.is_disconnected():
                break

    return EventSourceResponse(event_generator())


# ---------------------------------------------------------------------------
# Command dispatch
# ---------------------------------------------------------------------------

VALID_COMMANDS = {
    "play",
    "pause",
    "next",
    "prev",
    "seek",
    "volume",
    "shuffle",
    "repeat",
}


@app.post("/command/{action}")
async def command_endpoint(
    action: str, body: Optional[dict[str, object]] = None
) -> dict:
    """Dispatch playback commands to cmus-remote."""

    if action not in VALID_COMMANDS:
        return JSONResponse(
            {"error": "invalid_command", "message": f"Unknown command: {action}"},
            status_code=400,
        )

    value = body.get("value") if body else None

    if action in ("seek", "volume") and value is not None:
        if not isinstance(value, (int, float)):
            return JSONResponse(
                {
                    "error": "bad_request",
                    "message": f"value must be numeric, got {type(value).__name__}",
                },
                status_code=400,
            )

        value = int(value)

    try:
        cmus.send_command(action, value)
    except ValueError as e:
        return JSONResponse(
            {"error": "bad_request", "message": str(e)},
            status_code=400,
        )

    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Album art
# ---------------------------------------------------------------------------


@app.get("/art")
async def art_endpoint(t: str) -> Response:
    """Return album art for the given file path."""

    # Reject path traversal attempts
    if ".." in t:
        return Response(status_code=400)

    resolved = pathlib.Path(t).resolve()
    if not resolved.is_absolute():
        return Response(status_code=400)

    result = get_album_art(str(resolved))
    if result is None:
        return Response(status_code=404)

    data, mime = result

    return Response(content=data, media_type=mime)


# ---------------------------------------------------------------------------
# Exception handlers
# ---------------------------------------------------------------------------


@app.exception_handler(CmusNotRunning)
async def cmus_not_running_handler(
    request: Request, exc: CmusNotRunning
) -> JSONResponse:
    return JSONResponse(
        {"error": "cmus_not_running", "message": str(exc)}, status_code=503
    )


@app.exception_handler(NoTrackLoaded)
async def no_track_loaded_handler(request: Request, exc: NoTrackLoaded) -> JSONResponse:
    return JSONResponse(
        {"error": "no_track_loaded", "message": str(exc)}, status_code=503
    )


@app.exception_handler(CmusRemoteNotFound)
async def cmus_not_found_handler(
    request: Request, exc: CmusRemoteNotFound
) -> JSONResponse:
    return JSONResponse(
        {"error": "cmus_not_found", "message": str(exc)}, status_code=500
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=True)
