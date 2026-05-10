"""cmus-remote subprocess wrapper with status parsing and album art extraction."""

import logging
import os
import subprocess
from collections import OrderedDict
from dataclasses import dataclass
from typing import Optional

import mutagen

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------


class CmusRemoteError(Exception):
    """Base exception for cmus-remote errors."""


class CmusNotRunning(CmusRemoteError):
    """Raised when cmus is not running."""


class NoTrackLoaded(CmusRemoteError):
    """Raised when cmus is running but no track is loaded."""


class CmusRemoteNotFound(CmusRemoteError):
    """Raised when the cmus-remote binary cannot be found."""


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class CmusState:
    """Parsed state from cmus-remote -Q output."""

    status: str  # "playing", "paused", "stopped"
    title: str
    artist: str
    album: str
    file: str
    position: int  # seconds
    duration: int  # seconds
    volume: int  # 0-100
    shuffle: str  # "off", "tracks", "albums"
    repeat: str  # "true", "false"


# ---------------------------------------------------------------------------
# Album art cache
# ---------------------------------------------------------------------------

_art_cache: OrderedDict[str, tuple[bytes, str]] = (
    OrderedDict()
)  # file_path -> (data, mime_type)
_ART_CACHE_MAX = 100


# ---------------------------------------------------------------------------
# CmusRemote class
# ---------------------------------------------------------------------------


class CmusRemote:
    """Wraps cmus-remote CLI for status queries and command dispatch."""

    def __init__(self, socket_path: Optional[str] = None) -> None:
        if socket_path is not None:
            self.socket_path = socket_path
        elif os.environ.get("CMUS_SOCKET"):
            self.socket_path = os.environ["CMUS_SOCKET"]
        else:
            xdg_runtime = os.environ.get("XDG_RUNTIME_DIR")
            if xdg_runtime:
                self.socket_path = os.path.join(xdg_runtime, "cmus-socket")
            else:
                self.socket_path = "/tmp/cmus-socket"

    # Map of high-level action names to raw cmus commands.
    # Adding a new simple command is as easy as adding an entry here.
    _COMMAND_MAP: dict[str, str] = {
        "play": "player-play",
        "pause": "player-pause",
        "next": "player-next",
        "prev": "player-prev",
        "repeat": "toggle repeat",
    }

    def query_status(self) -> CmusState:
        """Query cmus status via `cmus-remote -Q` and return parsed CmusState."""

        result = self._run_remote(["-Q"])

        return self._parse_status(result.stdout)

    def _send_raw_command(self, *commands: str) -> subprocess.CompletedProcess[str]:
        """Send one or more raw commands via ``cmus-remote -C``.

        Raw commands are the same as cmus command-mode commands (e.g.
        ``player-play``, ``toggle repeat``, ``seek +5``).
        """

        return self._run_remote(["-C", *commands])

    def _parse_status(self, output: str) -> CmusState:
        """Parse cmus-remote -Q output into a CmusState."""

        data: dict[str, str] = {}
        for line in output.strip().splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split(None, 1)
            if len(parts) == 2:
                key, value = parts
                # Handle tag lines: "tag title Song Name"
                # -> key="tag title", value="Song Name"
                if key == "tag":
                    sub_parts = value.split(None, 1)
                    if len(sub_parts) == 2:
                        tag_key, tag_value = sub_parts
                        data[tag_key] = tag_value
                elif key == "set":
                    sub_parts = value.split(None, 1)
                    if len(sub_parts) == 2:
                        set_key, set_value = sub_parts
                        data[set_key] = set_value
                else:
                    data[key] = value

        status_raw = data.get("status", "unknown")
        file_path = data.get("file", "")

        # No track loaded check
        if not file_path and status_raw in ("stopped", "unknown"):
            raise NoTrackLoaded("No track loaded")

        # Volume: prefer unified "vol", fall back to averaging vol_left/vol_right
        vol_str = data.get("vol")
        if vol_str is None:
            vol_left = data.get("vol_left")
            vol_right = data.get("vol_right")
            if vol_left is not None and vol_right is not None:
                vol_str = str((int(vol_left) + int(vol_right)) // 2)
            else:
                vol_str = "0"
        # cmus outputs "vol 50%" - strip the % before parsing
        volume = int(vol_str.rstrip("%"))

        return CmusState(
            status=status_raw,
            title=data.get("title", ""),
            artist=data.get("artist", ""),
            album=data.get("album", ""),
            file=file_path,
            position=int(data.get("position", 0)),
            duration=int(data.get("duration", 0)),
            volume=volume,
            shuffle=data.get("shuffle", "off"),
            repeat=data.get("repeat", "false"),
        )

    def send_command(self, command: str, value: Optional[int] = None) -> None:
        """Send a playback command via cmus-remote raw commands (``-C``).

        ``command`` is a high-level action name (e.g. ``"play"``, ``"seek"``).
        ``value`` is an optional integer parameter used by ``seek`` and ``volume``.
        """

        if command == "shuffle":
            # Use ``set shuffle=VALUE`` to toggle between off and tracks,
            # avoiding the albums state that ``toggle shuffle`` would cycle
            # through.  This is also a single call with no race condition.
            state = self.query_status()
            new_value = "off" if state.shuffle != "off" else "tracks"
            self._send_raw_command(f"set shuffle={new_value}")

        elif command == "seek":
            if value is None:
                raise ValueError("seek requires a value")
            self._send_raw_command(f"seek {value}")

        elif command == "volume":
            if value is None:
                raise ValueError("volume requires a value")
            self._send_raw_command(f"vol {value}%")

        elif command in self._COMMAND_MAP:
            self._send_raw_command(self._COMMAND_MAP[command])

        else:
            raise ValueError(f"Unknown command: {command}")

    def _run_remote(self, args: list[str]) -> subprocess.CompletedProcess[str]:
        """Run a cmus-remote command.

        ``args`` are the arguments *after* the ``cmus-remote`` binary.
        ``--server <socket>`` is prepended automatically so that it is
        parsed before any ``-C`` raw-command arguments.
        Returns the CompletedProcess so callers can access stdout.
        """

        cmd = ["cmus-remote", "--server", self.socket_path, *args]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
        except FileNotFoundError:
            logger.error("cmus-remote binary not found")
            raise CmusRemoteNotFound("cmus-remote binary not found") from None

        if result.returncode != 0:
            stderr = result.stderr.strip().lower()
            if "not running" in stderr or "no such file" in stderr:
                logger.warning("cmus is not running")
                raise CmusNotRunning("cmus is not running")
            logger.error("cmus-remote command failed: %s", result.stderr.strip())
            msg = f"cmus-remote error: {result.stderr.strip()}"
            raise CmusRemoteError(msg) from None

        return result


# ---------------------------------------------------------------------------
# Album art extraction
# ---------------------------------------------------------------------------


def _cache_put(file_path: str, art_data: tuple[bytes, str]) -> None:
    """Insert into LRU art cache, evicting oldest entry if at capacity."""

    if len(_art_cache) >= _ART_CACHE_MAX:
        _art_cache.popitem(last=False)
    _art_cache[file_path] = art_data


def get_album_art(file_path: str) -> Optional[tuple[bytes, str]]:
    """Extract embedded album art from an audio file.

    Returns (image_bytes, mime_type) or None if no art found.
    Results are cached in memory keyed by file_path.
    """

    if file_path in _art_cache:
        _art_cache.move_to_end(file_path)
        return _art_cache[file_path]

    try:
        audio = mutagen.File(file_path)
    except Exception:
        logger.warning("Could not open file for album art: %s", file_path)
        return None

    if audio is None or audio.tags is None:
        return None

    # ID3 (MP3) - APIC frames
    if hasattr(audio.tags, "getall"):
        apic_frames = list(audio.tags.getall("APIC"))
        if apic_frames:
            pic = apic_frames[0]
            art_data = (pic.data, pic.mime)
            _cache_put(file_path, art_data)
            return art_data

    # FLAC / Vorbis - pictures attribute
    if hasattr(audio, "pictures") and audio.pictures:
        pic = audio.pictures[0]
        art_data = (pic.data, pic.mime)
        _cache_put(file_path, art_data)
        return art_data

    # MP4 / M4A - covr atom
    if hasattr(audio.tags, "covr") and audio.tags.get("covr"):
        covr = audio.tags["covr"]
        if covr:
            art_data = (bytes(covr[0]), "image/png")
            _cache_put(file_path, art_data)
            return art_data

    return None
