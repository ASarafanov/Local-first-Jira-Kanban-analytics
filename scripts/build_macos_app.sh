#!/bin/sh

set -eu

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
VENV_DIR="$ROOT_DIR/.venv-build"
DIST_DIR="$ROOT_DIR/dist"
WORK_DIR="$ROOT_DIR/build/pyinstaller"
SPEC_DIR="$ROOT_DIR/build/pyinstaller-spec"
PYINSTALLER_CONFIG_DIR="$ROOT_DIR/.pyinstaller-config"
ICONSET_DIR="$ROOT_DIR/assets/app_icon.iconset"
ICON_PATH="$ROOT_DIR/assets/app_icon.icns"

python3 -m venv "$VENV_DIR"
"$VENV_DIR/bin/python" -m pip install --disable-pip-version-check -r "$ROOT_DIR/requirements-build.txt"

rm -rf "$ICONSET_DIR"
"$VENV_DIR/bin/python" "$ROOT_DIR/scripts/generate_app_icon.py"
/usr/bin/iconutil -c icns "$ICONSET_DIR" -o "$ICON_PATH"

export PYINSTALLER_CONFIG_DIR
"$VENV_DIR/bin/python" -m PyInstaller \
  --noconfirm \
  --clean \
  --windowed \
  --name "Kanban Metrics" \
  --icon "$ICON_PATH" \
  --osx-bundle-identifier "local.kanbanmetrics.app" \
  --distpath "$DIST_DIR" \
  --workpath "$WORK_DIR" \
  --specpath "$SPEC_DIR" \
  --add-data "$ROOT_DIR/kanban_metrics/static:kanban_metrics/static" \
  --add-data "$ROOT_DIR/kanban_metrics/schema.sql:kanban_metrics" \
  "$ROOT_DIR/kanban_metrics/macos_main.py"
