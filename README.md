# cmus-web

[![PyPI - Version](https://img.shields.io/pypi/v/freetubedb.svg)](https://pypi.org/project/freetubedb)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/freetubedb.svg)](https://pypi.org/project/freetubedb)

<!-- TODO: Replace with actual screenshot -->
<!-- ![cmus-web screenshot](./screenshot.png) -->

A self-hosted PWA remote control for [cmus](https://cmus.github.io/). Control your player from any device on your network.

---

## Table of contents

- [Features](#features)
- [A note on PWA and HTTPS](#a-note-on-pwa-and-https)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Usage](#usage)
- [Docker](#docker)
- [Keyboard shortcuts](#keyboard-shortcuts)
- [Tech stack](#tech-stack)
- [License](#license)

## Features

- Real-time player state via SSE (track, position, volume, shuffle/repeat)
- Embedded album art extraction (MP3, FLAC, M4A, etc.)
- Installable PWA with offline caching
- Keyboard shortcuts for all playback controls
- Customizable accent color (persisted in localStorage)
- Zero-build frontend (vanilla HTML/CSS/JS + Alpine.js)

## A note on PWA and HTTPS

The install/Add to Home Screen prompt only works over HTTPS. Browsers require a secure context for service workers and PWA installation. If you're only accessing cmus-web over LAN on `http://192.168.x.x:8000`, the app still works fine as a regular web page, you just won't get the install prompt.

If you want full PWA support, you need a domain name with a TLS certificate. This is straightforward with a reverse proxy like [Traefik](https://traefik.io/traefik/), which handles automatic HTTPS via Let's Encrypt. Put cmus-web behind Traefik and you're done.

## Prerequisites

- Python 3.13+
- [cmus](https://cmus.github.io/) running with a socket (default: `$XDG_RUNTIME_DIR/cmus-socket` or `/tmp/cmus-socket`)
- `cmus-remote` on your `PATH`

## Installation

### From PyPI

```bash
pip install cmus-web
```

Or with [pipx](https://pypa.github.io/pipx/) (isolated, recommended for CLI tools):

```bash
pipx install cmus-web
```

### From source

```bash
git clone https://github.com/FawkesOficial/cmus-web.git
cd cmus-web
uv sync
```

## Usage

Make sure cmus is running, then:

```bash
cmus-web
```

Open http://127.0.0.1:8000 in your browser.

### CLI options

```
cmus-web [OPTIONS]

Options:
  --host TEXT       Bind address (default: 127.0.0.1)
  --port INTEGER    Port (default: 8000)
  --socket TEXT     cmus socket path (overrides CMUS_SOCKET env)
  --music-dir TEXT  Path to music directory for album art in Docker
  --prefix TEXT     Host path prefix from cmus-remote to strip (for Docker)
  --help            Show this message and exit.
```

### Examples

```bash
# Bind to all interfaces (accessible from other devices)
cmus-web --host 0.0.0.0

# Use a custom socket path
cmus-web --socket /run/user/1000/cmus-socket

# Run on a different port
cmus-web --port 9090
```

## Docker

### Important: cmus socket

cmus-web communicates with cmus through a Unix domain socket. If the socket path you mount does not exist on the host, **Docker will silently create a directory in its place**, which will break the connection and can be confusing to debug.

Use this helper script to verify the socket exists before starting the container:

```bash
#!/usr/bin/env bash
# start-cmus-web.sh - verify cmus socket exists, then start the container

SOCKET="${CMUS_SOCKET:-$XDG_RUNTIME_DIR/cmus-socket}"

if [ ! -S "$SOCKET" ]; then
  echo "Error: cmus socket not found at $SOCKET"
  echo "Make sure cmus is running and the socket path is correct."
  exit 1
fi

docker run -d \
  -v "$SOCKET":/tmp/cmus-socket \
  -v ~/Music:/music \
  -e CMUS_WEB_PREFIX="$HOME/Music" \
  -p 8000:8000 \
  cmus-web
```

### docker run

```bash
docker build -t cmus-web .

docker run -d \
  -v /run/user/1000/cmus-socket:/tmp/cmus-socket \
  -v ~/Music:/music \
  -e CMUS_WEB_PREFIX=/home/user/Music \
  -p 8000:8000 \
  cmus-web
```

The music volume mount enables album art extraction. Use `CMUS_WEB_PREFIX` to tell cmus-web what host path to strip from cmus-remote file paths so they resolve correctly inside the container.

### docker compose

```yaml
services:
  cmus-web:
    build: .
    container_name: cmus-web
    ports:
      - "8000:8000"
    volumes:
      - /run/user/1000/cmus-socket:/tmp/cmus-socket
      - ~/Music:/music
    environment:
      - CMUS_WEB_PREFIX=/home/user/Music
    restart: unless-stopped
```

```bash
docker compose up -d
```

## Keyboard shortcuts

| Key | Action |
|---|---|
| `Space` / `C` | Play / Pause |
| `B` | Next track |
| `Z` | Previous track |
| `S` | Toggle shuffle |
| `R` | Toggle repeat |
| `L` | Search lyrics online |
| `+` / `-` | Volume up / down |
| `Arrow Left` / `Right` | Seek -5s / +5s |
| `Arrow Up` / `Down` | Volume up / down |

## Tech stack

- **Backend:** Python, FastAPI, uvicorn, Mutagen, SSE-Starlette
- **Frontend:** Vanilla HTML/CSS/JS, Alpine.js
- **Packaging:** uv, Hatchling
- **Container:** Debian slim, uv

## License

`cmus-web` is distributed under the terms of the [GPL-3.0](LICENSE) license.
