# Local-first Jira Kanban analytics

Configure Jira scope, sync issue history, and inspect cycle time, phase ratio, throughput, and CFD without shipping your data anywhere else.

## Current state

This repository contains a runnable Python foundation with:

- a local HTTP server
- a native macOS desktop wrapper that embeds the web UI in its own window
- SQLite schema and repositories
- local credential storage with OS secure-store preference
- core metric calculation engine
- Jira API client skeleton with retry and pagination helpers
- a local UI for configuration and dashboard views
- demo data bootstrap for offline exploration
- app icon assets and macOS bundle build scripts
- unit tests for the metric engine

## Run

```bash
python3 -m kanban_metrics
```

For development, the local server starts on `http://127.0.0.1:8765` and opens the UI in your browser.

## First use

- Open the browser UI, or launch the macOS app bundle described below.
- Click `Load demo` to see a complete dashboard without Jira credentials.
- Or enter Jira URL and personal access token, then use `Test connection`.
- Saved credentials are kept in the OS secure store when available. A local fallback file is used only when secure-store access is unavailable.
- TLS certificate verification is always skipped for Jira connections in this build.

## macOS app bundle

For a standalone macOS app bundle that starts without Terminal and without a system Python install:

```bash
./scripts/build_macos_app.sh
```

The build output is created at `dist/Kanban Metrics.app`.
The bundled app opens the dashboard in its own native macOS window instead of launching your browser.
The app icon is generated from `assets/app_icon_1024.png` and bundled as `assets/app_icon.icns`.

The packaged app stores its writable data in `~/Library/Application Support/Kanban Metrics/`.
Legacy developer runs may still have data in `.local/kanban_metrics.db`; the desktop app reads from the Application Support location.

For local debugging you can override the default host, port, and writable data directory with `KANBAN_METRICS_HOST`, `KANBAN_METRICS_PORT`, and `KANBAN_METRICS_DATA_DIR`.

## macOS installer image

To build a distributable macOS `.dmg` that contains the app bundle and an `Applications` shortcut:

```bash
./scripts/build_macos_dmg.sh
```

The installer image is created at `dist/Kanban Metrics.dmg`.

## GitHub release flow

Pushing a tag like `v0.1.0` triggers `.github/workflows/release.yml`, which:

- runs the unit tests
- builds the native macOS `.app`
- packages `dist/Kanban Metrics.dmg`
- publishes a GitHub Release with the DMG attached

## Test

```bash
python3 -m unittest discover -s tests
```

## Notes

- The runtime service code intentionally stays close to the Python standard library, while the macOS bundle build uses `PyInstaller`, `Pillow`, and `pywebview`.
- The app exposes board import, JQL validation, sync jobs, and local metrics endpoints.
- The demo dataset is local-only and intended to validate charts and flows before connecting a real Jira tenant.
