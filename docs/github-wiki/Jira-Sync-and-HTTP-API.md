# Jira Sync and HTTP API

## Jira Client

The Jira client in `kanban_metrics/jira.py` is built on Python standard library HTTP primitives.

### Request behavior

- uses `urllib.request`
- sets JSON headers
- uses bearer token auth when a secret exists
- retries on `429`
- retries on transient URL errors
- falls back between Jira REST API v3 and v2 where useful

Important current constraint:

- TLS verification is effectively disabled in the current implementation because an unverified SSL context is always used.

## Sync Flow

The sync flow starts in `service.py` through `JobManager.start_sync()`.

### Steps

1. Create a `SyncJob` with status `running`.
2. Resolve the secret from the runtime store.
3. Build a `JiraClient`.
4. If board mode is selected, load board configuration and refresh `board_mapping`.
5. Build the effective JQL.
6. Load issues and changelog history.
7. Persist the resulting issue histories locally.
8. Mark the job completed or failed.

### Effective JQL rules

Builder mode:

- builds clauses from project keys
- builds clauses from issue types
- adds date clauses from sync start/end

Board mode:

- loads the board filter
- strips trailing `ORDER BY`
- optionally appends board `subQuery`

All modes:

- append `extra_jql` as an additional `AND (...)` if present

## History Collection

`JiraSyncService.fetch_issues()`:

- loads issue snapshots through Jira search
- fetches changelog history
- attempts bulk changelog fetch first
- falls back to per-issue history when needed
- resolves user labels for better assignee/author display values

The result is converted into `IssueHistory` objects.

## HTTP API

The local API is served by `AppHandler` in `kanban_metrics/app.py`.

### Configuration routes

- `GET /api/configs`
- `POST /api/configs`
- `PUT /api/configs/{id}`
- `DELETE /api/configs/{id}`

### Sync routes

- `POST /api/configs/{id}/sync`
- `GET /api/jobs/{id}`

### Jira helper routes

- `POST /api/jira/test-connection`
- `POST /api/jira/validate-jql`
- `POST /api/jira/projects`
- `POST /api/jira/project-statuses`
- `GET /api/boards`
- `GET /api/boards/{id}/configuration`

### Metrics routes

- `GET /api/metrics/cycle-time?configId=...`
- `GET /api/metrics/throughput?configId=...`
- `GET /api/metrics/phase-ratio?configId=...`
- `GET /api/metrics/cfd?configId=...&timezone=...`

### Demo route

- `POST /api/demo/bootstrap`

## Why the API is local

The API is not intended as a remote service. It exists to:

- keep backend logic in Python
- keep frontend delivery simple
- support browser and native app modes with the same implementation

## Error handling behavior

The server returns JSON errors for expected failures such as:

- missing config id
- missing project key
- Jira request failures
- unknown job or config
- deletion during a running sync

This gives the SPA enough structured information to update status messages and preserve the local workflow.
