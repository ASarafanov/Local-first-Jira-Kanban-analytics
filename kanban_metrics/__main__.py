from __future__ import annotations

import os

from .app import run


def _configured_port(default: int = 8765) -> int:
    raw = os.environ.get("KANBAN_METRICS_PORT")
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _configured_host(default: str = "127.0.0.1") -> str:
    return os.environ.get("KANBAN_METRICS_HOST", default)


if __name__ == "__main__":
    run(host=_configured_host(), port=_configured_port(), open_browser=True)
