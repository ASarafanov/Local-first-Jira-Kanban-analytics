# Local-first Jira Kanban Analytics

A local-first desktop/web app that imports Jira issue history and calculates Kanban metrics without sending your data to external analytics services.

## Documentation

- Detailed implementation notes live in [docs/IMPLEMENTATION_AI.md](docs/IMPLEMENTATION_AI.md).
- A GitHub Wiki-ready page set lives in [docs/github-wiki/](docs/github-wiki/).

## What The Project Does

- Stores sync configuration and issue history in a local SQLite database.
- Runs a local HTTP server and serves a single-page UI from `kanban_metrics/static/`.
- Supports a demo mode that works without Jira credentials.
- Includes a native macOS wrapper built with `pywebview`.

## Implementation Overview

### Runtime Architecture

- `kanban_metrics/app.py` wires SQLite, the runtime secret store, the service layer, and the HTTP API.
- `kanban_metrics/service.py` orchestrates config persistence, background sync jobs, and metric assembly.
- `kanban_metrics/jira.py` implements the Jira client, pagination, retries, JQL building, and changelog parsing.
- `kanban_metrics/metrics.py` contains the pure computation logic for cycle time, phase ratio, throughput, and CFD.
- `kanban_metrics/static/app.js` renders the charts and applies local dashboard filters without re-syncing.

### Chart Calculation Logic

#### Cycle Time

- For each issue, the cycle starts at the first transition into any `start_status_ids` and ends at the first transition into any `done_status_ids`.
- `cycle_report()` builds the completed-issue list, summary percentiles, monthly trend, and a duration histogram.
- In the UI, the scatter plot uses `X = done date`, `Y = cycle time`, and X/Y filters are applied locally.

#### Throughput

- Throughput is counted from the first transition of an issue into a done status.
- The backend creates completion events and aggregates them by month, assignee/owner, and project.
- The UI re-aggregates the same events into weekly or monthly buckets inside the selected date range.

#### Phase Ratio

- For each completed issue, the cycle window is clipped from cycle start to completion, then time is accumulated by board lane and by individual statuses.
- The UI shows average days spent in each status for the completed issues inside the selected date range.

#### CFD

- The backend first builds continuous status intervals from changelog history.
- Each interval is then converted into local calendar-day spans for the selected timezone.
- Instead of iterating over every issue for every day, the algorithm writes `+1/-1` deltas at interval boundaries and performs a single sweep across days.
- Snapshots are end-of-day based, so multiple same-day transitions collapse into that day’s final state.
- If the mapping is generic (`inactive/active/done`), CFD expands into individual observed statuses so the chart does not lose detail.

## Local Data Model

- `jira_instance`: Jira instance settings and secret reference.
- `config`: persisted sync scope, JQL, date range, and board mapping.
- `issue`: local issue snapshot.
- `changelog_event`: status/assignee transition history.
- `sync_job`: background sync job progress.

## Run

```bash
python3 -m kanban_metrics
```

In development mode the app starts a local server on `http://127.0.0.1:8765` and opens your browser.

## First Use

- Click `Load demo` to inspect a complete dashboard without Jira credentials.
- Or provide a Jira URL and personal access token, then run `Test connection`.
- Secrets are stored in the macOS Keychain, with a local file fallback if the keychain is unavailable.

## macOS App Bundle

```bash
./scripts/build_macos_app.sh
```

- The build output is written to `dist/Kanban Metrics.app`.
- The native app uses `~/Library/Application Support/Kanban Metrics/` as its writable data directory.

## macOS DMG

```bash
./scripts/build_macos_dmg.sh
```

- The installer image is created at `dist/Kanban Metrics.dmg`.

## Release Flow

A tag like `v0.1.0` triggers `.github/workflows/release.yml`, which runs tests, builds the `.app`, packages the `.dmg`, and publishes a GitHub Release.

## Test

```bash
python3 -m unittest discover -s tests
```

## Current Constraints

- In the current build, Jira TLS verification is always disabled (`verify_ssl=False` throughout the app).
- The UI recalculates chart views locally on top of the already loaded dataset; new issue histories still require a new sync.
- The project is designed for local desktop/workstation usage, not multi-user server deployment.
