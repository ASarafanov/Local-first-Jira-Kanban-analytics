#!/bin/sh

set -eu

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
APP_PATH="$ROOT_DIR/dist/Kanban Metrics.app"
DMG_PATH="$ROOT_DIR/dist/Kanban Metrics.dmg"
STAGING_DIR="$ROOT_DIR/build/dmg-staging"
VOLUME_NAME="Kanban Metrics"

if [ ! -d "$APP_PATH" ]; then
  echo "Missing app bundle at $APP_PATH. Build the app first with ./scripts/build_macos_app.sh" >&2
  exit 1
fi

rm -rf "$STAGING_DIR"
mkdir -p "$STAGING_DIR"
cp -R "$APP_PATH" "$STAGING_DIR/"
ln -s /Applications "$STAGING_DIR/Applications"
rm -f "$DMG_PATH"

hdiutil create \
  -volname "$VOLUME_NAME" \
  -srcfolder "$STAGING_DIR" \
  -ov \
  -format UDZO \
  "$DMG_PATH"

echo "Created $DMG_PATH"
