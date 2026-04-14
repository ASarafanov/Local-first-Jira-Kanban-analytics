# Project Implementation Map

## Metadata

- `project`: `Local-first Jira Kanban Analytics`
- `source_of_truth`: the project codebase and local git history as of 2026-04-14
- `main_language`: Python + vanilla JavaScript
- `ui_runtime`: local HTTP server + static SPA + optional native macOS wrapper
- `persistence`: SQLite + runtime secret store

## 1. Purpose

- The project is meant for local Kanban flow analytics over Jira issue history.
- It persists sync configuration, loads issue transition history, and exposes four main views: cycle time, throughput, phase ratio, and CFD.
- The primary design principle is local-first operation with no external backend and no SaaS analytics dependency.

## 2. Development History Reconstructed From Git

1. `27427e6` created the project core: backend, SQLite, Jira sync, frontend, demo data, CFD adaptation, and tests.
2. `207e27f` added public repository bootstrap files and the license.
3. `2688d2f` added native macOS app packaging, `pywebview`, PyInstaller scripts, and moved user data into Application Support.
4. `854538a` completed the packaging story with `.dmg` output and a GitHub release workflow.

## 3. High-Level Architecture

```text
Jira REST API
  -> kanban_metrics/jira.py
  -> kanban_metrics/service.py (background sync + metric orchestration)
  -> kanban_metrics/db.py + schema.sql (local persistence)
  -> kanban_metrics/app.py (HTTP API + static file serving)
  -> kanban_metrics/static/app.js (dashboard state + chart rendering)
  -> Browser or kanban_metrics/desktop.py (native macOS shell)
```

- The entire backend lives inside a local Python process.
- The HTTP API and SPA are part of the same runtime.
- The native macOS app does not replace the backend: it launches the same local server and opens it in `pywebview`.

## 4. File Map

### Core Backend

- `kanban_metrics/app.py`
  - Application composition, DB initialization, runtime store setup, HTTP routes, and static file serving.
- `kanban_metrics/service.py`
  - Service layer between HTTP and computation code; starts sync jobs and assembles dashboard payloads.
- `kanban_metrics/jira.py`
  - Jira client, retries, pagination, board/project mapping, JQL builder, changelog fetch, and user-label resolution.
- `kanban_metrics/metrics.py`
  - Pure calculations over issue history.
- `kanban_metrics/db.py`
  - SQLite repositories and lightweight migrations.
- `kanban_metrics/models.py`
  - Domain dataclasses.
- `kanban_metrics/runtime_store.py`
  - Secret storage in keychain or a fallback file.

### UI

- `kanban_metrics/static/index.html`
  - Dashboard and configuration UI shell.
- `kanban_metrics/static/styles.css`
  - Static theme and component styling.
- `kanban_metrics/static/app.js`
  - State management, HTTP calls, local filtering, chart rendering, tooltips, and hidden-series logic.

### Packaging

- `kanban_metrics/desktop.py`
  - Native macOS window launcher.
- `kanban_metrics/macos_main.py`
  - Entrypoint for the packaged macOS app bundle.
- `kanban_metrics/paths.py`
  - Resolution of `resource_root()` and `user_data_dir()`.
- `scripts/build_macos_app.sh`
  - `.app` build script.
- `scripts/build_macos_dmg.sh`
  - `.dmg` packaging script.

### Validation

- `tests/test_metrics.py`
  - Unit tests for computation logic, Jira mappings, repositories, and config deletion.

## 5. Runtime Flow

### Startup

1. `python3 -m kanban_metrics` enters `kanban_metrics.__main__`.
2. `app.py` creates the `Database`, applies the schema and migrations.
3. `ConfigRepository`, `IssueRepository`, `JobRepository`, `RuntimeStore`, and `DashboardService` are created.
4. A `ThreadingHTTPServer` starts serving the API and static assets.

### Sync

1. The UI persists a `SyncConfig`.
2. Pressing sync creates a `SyncJob` in `running` state.
3. `JobManager` starts a background thread with `JiraClient` and `JiraSyncService`.
4. If scope = board, it first loads board configuration and refreshes `board_mapping`.
5. It then builds the effective JQL and downloads issue snapshots plus changelog history.
6. Issue history is written to the local DB transactionally via `replace_issues`.

### Metrics Load

1. The UI requests `cycle-time`, `throughput`, `phase-ratio`, and `cfd` in parallel.
2. The backend loads the config and its issue histories by `config_id`.
3. `DashboardService.get_metrics()` calls all computation functions and returns serialized payloads.
4. The UI does not recompute backend metrics from scratch; it only filters and aggregates the loaded data for the current view.

## 6. Local Data Model

### Domain Types

- `StatusTransition(timestamp, from_status_id, to_status_id, author_account_id)`
- `AssigneeTransition(timestamp, from_account_id, to_account_id)`
- `StatusInterval(start, end, status_id)`
- `BoardMapping(columns, phase_names, status_names)`
- `IssueHistory(...)`
- `SyncConfig(...)`
- `SyncJob(...)`
- `DailyCfdPoint(day, current, cumulative)`

- `IssueHistory` is the main analytics unit.
- All timestamps are normalized to UTC via `ensure_utc`.

### SQLite Tables

- `jira_instance`
  - Jira URL, auth type, verify flag, user, and secret reference.
- `config`
  - Scope, JQL, date bounds, status buckets, and board mapping.
- `issue`
  - Local issue snapshot.
- `changelog_event`
  - History for status and assignee transitions.
- `sync_job`
  - Background sync progress.

Important invariant:

- `IssueRepository` prefixes Jira issue ids with the config id (`cfg-id:issue-id`) so the same Jira issue can safely exist in multiple configurations.

## 7. Jira Integration

### Request Strategy

- The client uses `urllib.request` instead of an external HTTP SDK.
- Retries exist for `429` responses and transport errors.
- It supports fallback paths between REST API v3 and v2.

### Query Building

- Builder mode creates JQL from `project_keys`, `issue_types`, `sync_start_date`, and `sync_end_date`.
- Board mode derives its base filter from Jira board configuration and optionally appends `subQuery`.
- `extra_jql` is always appended as an additional `AND (...)` clause.

### History Fetch

- The service first tries bulk changelog fetch.
- If the bulk endpoint is unavailable, it falls back to per-issue changelog requests.
- Status and assignee transitions are then converted into local dataclass structures.

## 8. HTTP API

- `GET /api/configs`
  - List of saved configs.
- `POST /api/configs`
  - Create a config.
- `PUT /api/configs/{id}`
  - Update a config.
- `DELETE /api/configs/{id}`
  - Delete a config and its related local data.
- `POST /api/configs/{id}/sync`
  - Start a background sync.
- `GET /api/jobs/{id}`
  - Sync job status.
- `POST /api/jira/test-connection`
  - Test Jira credentials.
- `POST /api/jira/validate-jql`
  - Parse and normalize JQL.
- `POST /api/jira/projects`
  - List projects.
- `POST /api/jira/project-statuses`
  - Derive a status mapping for builder mode.
- `GET /api/metrics/cycle-time`
- `GET /api/metrics/throughput`
- `GET /api/metrics/phase-ratio`
- `GET /api/metrics/cfd`
- `POST /api/demo/bootstrap`
  - Create the demo config and demo issues.

## 9. Metric Logic

### 9.1 Shared Primitive: Status Intervals

Source:
- `build_status_intervals(issue, report_end)`

- For each issue, transitions are sorted by time.
- The first interval spans from `created_at` to the first transition.
- After every transition, the previous status closes and a new one opens.
- The last interval is extended to `report_end` or the current time.

This primitive feeds:
- cycle-time
- phase-ratio
- status-ratio
- CFD

### 9.2 Cycle Time

Source:
- `find_cycle_segments`
- `compute_elapsed_cycle_time`
- `compute_in_status_cycle_time`
- `cycle_report`

- `find_cycle_segments()` finds `start_status -> done_status` pairs.
- The default mode is `first_completion`: from the first entry into a start status to the first done.
- Other reopen semantics exist (`last_completion`, `sum_of_cycles`), but the service currently uses the default.
- `cycle_report()` returns summary stats (`median`, `p50`, `p85`, `p95`), monthly trend, histogram, and per-issue details.

UI rendering:
- Scatter plot where `X = issue.end`, `Y = issue.hours`.
- Percentile cards for visible issues are recomputed in the browser after filtering.

### 9.3 Throughput

Source:
- `find_completion_event`
- `throughput_report`
- `aggregateThroughputData` in `app.js`

- A completion event is created at the first transition into a done status.
- Attribution depends on `attribution_mode`:
  - `assignee_at_done`
  - `transition_author`
- The backend returns event lists and monthly aggregates.
- The UI re-bucketizes events by week or month only for the selected visual range.

### 9.4 Phase Ratio And Status Ratio

Source:
- `clip_intervals`
- `compute_phase_ratio`
- `compute_status_ratio`
- `phase_ratio_report`
- `aggregateCycleStatusSummary` in `app.js`

- The issue cycle is first clipped to the window between cycle start and cycle end.
- Durations are then accumulated:
  - by lane (`phase_name_for_column`)
  - by concrete status (`status_name`)
- `phase_ratio_report()` aggregates totals, average ratio, median ratio, dominant phase and status, and outliers.
- The UI currently visualizes the status-level summary: average days per status for the selected issue range.

### 9.5 CFD

Source:
- `resolve_report_timezone`
- `interval_day_span`
- `cfd_series_definition`
- `compute_cfd`
- `cfd_report`
- `renderStackedAreaChart` in `app.js`

Backend algorithm:

1. Build `StatusInterval` for each issue.
2. Map each status into a CFD series via `board_mapping`.
3. Convert each interval into a span of local calendar days for the selected timezone.
4. Write `+1` at `effective_start` and `-1` at `effective_end + 1 day`.
5. Sweep across days once, maintain running counts, and build snapshots.
6. For stacked rendering, also compute cumulative counts from the last lane back to the first.

Why this matters:

- reopened issues are handled correctly
- multiple same-day transitions collapse into the final state of that day
- an issue does not appear in the CFD before it is created
- the snapshot really depends on the browser or user timezone

Series behavior:

- If the mapping is specific to board columns, the series match the board lanes.
- If the mapping is generic (`inactive/active/done`) and groups multiple statuses together, CFD automatically expands to individual statuses.
- Historically observed statuses not present in the config can be appended as series to preserve continuity.
- `cfd_report()` adds warnings and bottleneck hints.

UI rendering:

- `renderCfd()` takes backend-ready `points`, filters them by the selected date range and hidden series, then passes them to `renderStackedAreaChart`.
- Stacking order comes from `meta.stackingOrder`, keeping done-like statuses closer to the baseline.

## 10. Frontend Behavior

- The UI loads all metrics in parallel.
- After the dashboard loads, filters and local interactive actions do not require additional API requests.
- The user can:
  - change the date range
  - limit the cycle chart Y-axis
  - hide individual cycle chart points
  - hide individual CFD series
  - switch throughput between week and month

Important nuance:

- The selected date range is effectively anchored to completed issues from the cycle chart, and the other views are filtered against the same window.

## 11. Demo Mode

- `bootstrap_demo()` creates a demo config with the range `2026-01-01..2026-04-30`.
- `build_demo_issues()` generates eight issues with varying types, transitions, and some assignee changes.
- The demo is used to validate the UI and charts without Jira access.

## 12. Packaging And Distribution

- Development mode: browser + local server.
- Desktop mode: `desktop.py` starts the local server on a free port and displays it in a native window.
- `paths.py` switches the writable data directory into a platform-specific location.
- The GitHub release workflow builds `.app` and `.dmg` on tag push.

## 13. Security And Constraints

- Secrets are preferably stored in the macOS keychain, with a file fallback available.
- TLS verification for Jira is disabled across the app, which is an intentional but risky simplification of the current version.
- The project is designed for a single-user local environment.

## 14. Test Coverage Summary

- The tests cover:
  - status intervals
  - cycle time with reopen cases
  - in-status cycle time
  - throughput and assignee attribution
  - phase and status ratio
  - timezone-sensitive CFD
  - same-day CFD transitions
  - generic CFD status expansion
  - project and JQL status mapping
  - repository scoping
  - config deletion rules

## 15. Best Next Extensions

1. Enable a real `verify_ssl` setting instead of hard-coding `False`.
2. Add explicit UI for reopen semantics (`first_completion`, `last_completion`, `sum_of_cycles`).
3. Extend the phase-ratio UI into a lane-level stacked breakdown.
4. Add CSV or JSON export for snapshot reports.
