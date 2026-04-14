# Data Model and Persistence

[Home](Home.md)

## Domain Model

The project uses explicit dataclasses in `kanban_metrics/models.py`.

### `StatusTransition`

Represents a workflow status change:

- `timestamp`
- `from_status_id`
- `to_status_id`
- `author_account_id`

### `AssigneeTransition`

Represents an assignee change:

- `timestamp`
- `from_account_id`
- `to_account_id`

### `StatusInterval`

Represents time spent in a single status between two timestamps.

This type is foundational for:

- cycle time
- phase ratio
- status ratio
- CFD

### `BoardMapping`

Captures the workflow model used for analytics:

- ordered board columns
- optional phase names
- optional status display names

### `IssueHistory`

The core analytics entity. It stores:

- issue identity
- project and type
- creation time
- initial and current status
- initial and current assignee
- ordered status transitions
- ordered assignee transitions

### `SyncConfig`

Defines a saved analytics scope:

- Jira base URL
- board or builder mode
- project filters
- issue type filters
- JQL fragments
- date window
- start/done/active status buckets
- attribution mode
- board mapping

### `SyncJob`

Tracks background synchronization state:

- running/completed/failed
- progress
- status message
- start and finish timestamps

## SQLite Schema

The schema lives in `kanban_metrics/schema.sql`.

### `jira_instance`

Stores Jira connection metadata:

- base URL
- auth type
- verify flag
- user
- secret reference

### `config`

Stores saved workspace configuration:

- Jira instance link
- scope type
- board id
- project keys
- issue types
- base and extra JQL
- date range
- status bucket configuration
- board mapping JSON

### `issue`

Stores the current local issue snapshot for a config.

### `changelog_event`

Stores history items for:

- `status`
- `assignee`

### `sync_job`

Stores background sync progress.

## Persistence Strategy

### Scoped Issue IDs

The repository prefixes issue ids with the config id when saving:

```text
config-id:jira-issue-id
```

This matters because the same Jira issue can appear in multiple saved configurations without colliding in SQLite.

### Replace-on-sync

`IssueRepository.replace_issues()` removes previous issue and changelog rows for a config, then writes the new synced snapshot.

This keeps the persisted dataset simple and config-scoped.

### Migrations

`Database._apply_migrations()` performs incremental schema evolution for fields such as:

- `verify_ssl`
- `initial_assignee_account_id`
- `summary`
- JSON fields for projects and issue types
- sync date bounds

The migration approach is intentionally lightweight.

## Secret Storage

Secrets are handled by `kanban_metrics/runtime_store.py`.

### Preferred path

- macOS keychain via the `security` CLI

### Fallback path

- local JSON file with `0600` permissions

The stored config only keeps a reference like:

- `keychain:<key>`
- `file:<key>`

The raw token is resolved at runtime only when needed.

## Important Constraints

- All timestamps are normalized to UTC in the domain layer.
- The app is single-user and local-machine oriented.
- SQLite is used as a local snapshot store, not as a collaborative system of record.
