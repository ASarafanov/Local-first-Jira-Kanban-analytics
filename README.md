# Local-first Jira Kanban analytics

Configure Jira scope, sync issue history, and inspect cycle time, phase ratio, throughput, and CFD without shipping your data anywhere else.

## Current state

This repository contains a runnable Python foundation with:

- a local HTTP server
- SQLite schema and repositories
- local credential storage with OS secure-store preference
- core metric calculation engine
- Jira API client skeleton with retry and pagination helpers
- a starter browser UI for configuration and dashboard views
- demo data bootstrap for offline exploration
- unit tests for the metric engine

## Run

```bash
python3 -m kanban_metrics
```

The app starts on `http://127.0.0.1:8765`.

## First use

- Open the app in a browser.
- Click `Load demo` to see a complete dashboard without Jira credentials.
- Or enter Jira URL and personal access token, then use `Test connection`.
- Saved credentials are kept in the OS secure store when available. A local fallback file is used only when secure-store access is unavailable.
- TLS certificate verification is always skipped for Jira connections in this build.

## Test

```bash
python3 -m unittest discover -s tests
```

## Notes

- The project intentionally uses only Python standard library dependencies.
- The app exposes board import, JQL validation, sync jobs, and local metrics endpoints.
- The demo dataset is local-only and intended to validate charts and flows before connecting a real Jira tenant.
