from __future__ import annotations

import os
from pathlib import Path

import webview

from .app import APP_NAME, create_server, start_server_in_thread, stop_server, wait_until_server_ready


def _configured_port(default: int = 0) -> int:
    raw = os.environ.get("KANBAN_METRICS_PORT")
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _configured_host(default: str = "127.0.0.1") -> str:
    return os.environ.get("KANBAN_METRICS_HOST", default)


def _bundle_icon_path() -> str | None:
    executable = Path(__file__).resolve()
    for parent in executable.parents:
        if parent.name == "MacOS" and parent.parent.name == "Contents":
            icon_path = parent.parent / "Resources" / "app_icon.icns"
            if icon_path.exists():
                return str(icon_path)
    return None


def launch_native_window() -> None:
    host = _configured_host()
    requested_port = _configured_port()
    server = create_server(host=host, port=requested_port)
    server_thread = start_server_in_thread(server)
    actual_host, actual_port = server.server_address[:2]

    if not wait_until_server_ready(actual_host, actual_port):
        stop_server(server, server_thread)
        raise RuntimeError("Local UI server did not become ready in time")

    url = f"http://{actual_host}:{actual_port}"
    window = webview.create_window(
        APP_NAME,
        url,
        width=1440,
        height=960,
        min_size=(1100, 760),
        text_select=True,
    )

    def _shutdown_window(*_: object) -> None:
        stop_server(server, server_thread)

    window.events.closing += _shutdown_window

    try:
        webview.start(gui="cocoa", icon=_bundle_icon_path())
    finally:
        stop_server(server, server_thread)
