# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Run the app (development)

```bash
python3 -m kanban_metrics
```

Starts the local HTTP server on `127.0.0.1:8765` and opens the browser. Override with env vars:

```bash
KANBAN_METRICS_PORT=9000 KANBAN_METRICS_HOST=0.0.0.0 python3 -m kanban_metrics
```

Control the data directory:

```bash
KANBAN_METRICS_DATA_DIR=.local python3 -m kanban_metrics
```

### Run tests

```bash
python3 -m pytest
# or
python3 -m unittest discover -s tests
```

Run a single test class or method:

```bash
python3 -m pytest tests/test_metrics.py::MetricsTests::test_cycle_time
```

### Build the macOS app

```bash
# Requires .venv-build with pyinstaller, Pillow, pywebview
./scripts/build_macos_app.sh   # → dist/Kanban Metrics.app
./scripts/build_macos_dmg.sh   # → dist/Kanban Metrics.dmg
```

Build deps are in `requirements-build.txt`; install into `.venv-build`:

```bash
python3 -m venv .venv-build
.venv-build/bin/pip install -r requirements-build.txt
```

## Architecture

### Process model

One Python process hosts everything: the `ThreadingHTTPServer`, all SQLite I/O, Jira sync threads, and static file serving. There is no separate build step for the frontend — `kanban_metrics/static/` is served as-is.

```
python3 -m kanban_metrics
  └─ app.py           # bootstrap, HTTP routes, static serving
      ├─ service.py   # config save/load, sync orchestration, metric assembly
      ├─ db.py        # SQLite repositories + migrations
      ├─ jira.py      # Jira HTTP client, JQL builder, changelog fetch
      └─ metrics.py   # pure calculation functions
```

The native macOS app (`desktop.py` / `macos_main.py`) is a thin `pywebview` shell that launches the same backend on a free port and embeds it in a native window. No separate code path.

### Data directory

At runtime, `paths.py` resolves two roots:

- `resource_root()` — where source files live (project root in dev, `_MEIPASS` in frozen build)
- `user_data_dir()` — writable data: `~/Library/Application Support/Kanban Metrics` on macOS, overridable via `KANBAN_METRICS_DATA_DIR`

The SQLite database lives at `user_data_dir() / kanban_metrics.db`.

### Persistence

`db.py` owns schema init and migrations. `schema.sql` is the source of truth. Key tables: `jira_instance`, `config`, `issue`, `changelog_event`, `sync_job`.

**Critical invariant**: `IssueRepository` prefixes every Jira issue key with `<config_id>:` so the same Jira issue can exist under multiple configs without collision.

### Sync flow

1. UI `POST /api/configs/{id}/sync` → `JobManager.start_sync()` creates a `SyncJob` and spawns a background thread.
2. `JiraSyncService` builds JQL, fetches issues + changelog in pages, converts to `IssueHistory` domain objects.
3. `IssueRepository.replace_issues()` writes everything transactionally.
4. Progress is polled via `GET /api/jobs/{id}`.

Board scope: the sync first fetches the board configuration to derive the base JQL filter and build the `board_mapping` (columns → status IDs → lane names).

### Metric computation

All heavy computation lives in `metrics.py` as pure functions. The central primitive is `build_status_intervals(issue, report_end)` which converts raw `StatusTransition` lists into `StatusInterval` objects. Every metric (cycle time, throughput, phase ratio, CFD) is built on top of this.

`DashboardService.get_metrics()` in `service.py` calls these functions and serializes the results; the four metric endpoints (`/api/metrics/*`) each call it.

The frontend (`static/app.js`) only does lightweight local work after load: date-window filtering, week/month throughput rebucketing, hiding series/points. It does not re-derive the core metrics.

### CFD specifics

The CFD algorithm uses a sweep-line approach: for each issue interval, it writes `+1` at `effective_start` day and `-1` at `effective_end + 1 day`, then sweeps once to build daily snapshots. This correctly handles re-opened issues and same-day multiple transitions. The result depends on the user's timezone (resolved via `resolve_report_timezone`).

### Secret storage

`RuntimeStore` prefers the macOS keychain and falls back to a JSON file at `user_data_dir() / runtime-store.json`. Jira credentials (PAT or basic auth) are stored through this.

### Release

CI (`.github/workflows/release.yml`) triggers on `v*` tags: runs tests, calls both build scripts, and publishes the `.dmg` to GitHub Releases.
