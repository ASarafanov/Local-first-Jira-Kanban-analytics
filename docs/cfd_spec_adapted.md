# CFD specification adapted to this project

## Why adaptation is needed

The source specification describes a standalone CFD API with `todo / in_progress / done`
lanes. This project already has an established architecture:

- backend metrics are calculated in `kanban_metrics/metrics.py`
- orchestration lives in `kanban_metrics/service.py`
- HTTP access is exposed through `GET /api/metrics/<metric>?configId=...`
- workflow mapping is already stored in `SyncConfig.board_mapping`

Because of that, CFD is implemented as a specialized `cfd` metric inside the existing
metrics pipeline instead of a new standalone `/api/flow/cfd` endpoint.

## Mapping from source spec to project architecture

### Source data

Source spec:

- issue creation time
- current status
- full status history

Project mapping:

- `IssueHistory.created_at`
- `IssueHistory.current_status_id`
- `IssueHistory.transitions`

### Status mapping

Source spec:

- explicit status -> `todo / in_progress / done`

Project mapping:

- `SyncConfig.board_mapping.columns`
- builder mode maps statuses into `inactive / active / done`
- board mode reuses the real Jira board columns

Implication:

- in builder mode the implementation behaves like the original `todo / in_progress / done` CFD
- in board mode the same algorithm works with more granular workflow lanes while preserving configured board order

### API contract

Source spec:

- `GET /api/flow/cfd`

Project mapping:

- `GET /api/metrics/cfd?configId=<id>&timezone=<iana_timezone>`

Rationale:

- keeps the existing metrics routing model intact
- reuses saved config scope instead of passing project filters ad hoc
- uses the browser timezone for end-of-day snapshots

### Date range

Source spec:

- `date_from`, `date_to`

Project mapping:

- default range comes from the saved config via `_config_dashboard_range`
- dashboard date inputs filter the already loaded CFD points in the UI

### Output

Source spec:

- daily counts per lane

Project mapping:

- `data.meta`: resolved timezone, range, lane order, stacking order
- `data.series`: configured CFD lanes
- `data.points`: one end-of-day snapshot per day
- `data.warnings`: unmapped statuses and timezone fallback warnings
- `data.bottlenecks`: trend hints for widening lanes

## Algorithm

The implementation uses event-based accumulation instead of checking every issue for every day:

1. Build status intervals from issue history.
2. Convert each interval into a local-day span for the requested timezone.
3. Write `+1/-1` deltas for the mapped CFD lane.
4. Sweep through days once and build stacked snapshots.

This preserves:

- reopened issue handling
- final state for multiple transitions within one day
- correct appearance only after creation
- timezone-aware end-of-day snapshots

