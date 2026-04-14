from __future__ import annotations

import os
import sys
from pathlib import Path


APP_NAME = "Kanban Metrics"
APP_ID = "kanban-metrics"


def resource_root() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent.parent


def user_data_dir() -> Path:
    override = os.environ.get("KANBAN_METRICS_DATA_DIR")
    if override:
        return Path(override).expanduser()
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_NAME
    if sys.platform == "win32":
        base = os.environ.get("APPDATA")
        if base:
            return Path(base) / APP_NAME
    xdg_data_home = os.environ.get("XDG_DATA_HOME")
    if xdg_data_home:
        return Path(xdg_data_home) / APP_ID
    return Path.home() / ".local" / "share" / APP_ID
