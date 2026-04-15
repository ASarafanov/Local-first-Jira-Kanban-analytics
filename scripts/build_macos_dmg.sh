#!/bin/sh

set -eu

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
APP_PATH="$ROOT_DIR/dist/Kanban Metrics.app"
DMG_PATH="$ROOT_DIR/dist/Kanban Metrics.dmg"
GUIDE_SOURCE_PATH="$ROOT_DIR/assets/open_anyway_guide.png"
GUIDE_OUTPUT_PATH="$ROOT_DIR/dist/How to Open on macOS.png"
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
rm -f "$GUIDE_OUTPUT_PATH"

hdiutil create \
  -volname "$VOLUME_NAME" \
  -srcfolder "$STAGING_DIR" \
  -ov \
  -format UDZO \
  "$DMG_PATH"

if [ -f "$GUIDE_SOURCE_PATH" ]; then
  cp "$GUIDE_SOURCE_PATH" "$GUIDE_OUTPUT_PATH"
fi

echo "Created $DMG_PATH"
