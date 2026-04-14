# Metrics and Chart Logic

## Overview

The project exposes four metric groups:

- cycle time
- throughput
- phase ratio
- cumulative flow diagram (CFD)

The backend source of truth lives in `kanban_metrics/metrics.py`.

The frontend in `kanban_metrics/static/app.js` is responsible for:

- rendering charts
- applying local filters
- recalculating some view-specific summaries from already loaded payloads

## Shared Primitive: Status Intervals

Most metrics are built on top of `build_status_intervals(issue, report_end)`.

The algorithm:

1. Sort transitions by time.
2. Start from `issue.created_at` and `issue.initial_status_id`.
3. Close the current interval at each transition timestamp.
4. Open the next interval in the transitioned status.
5. Extend the final interval to `report_end`.

This converts event history into continuous time segments.

## Cycle Time

### Backend logic

Relevant functions:

- `find_cycle_segments`
- `compute_elapsed_cycle_time`
- `compute_in_status_cycle_time`
- `cycle_report`

Default behavior:

- cycle starts at first transition into any configured start status
- cycle ends at first transition into any configured done status

Supported reopen semantics in code:

- `first_completion`
- `last_completion`
- `sum_of_cycles`

The service currently uses the default elapsed mode.

### Report payload

`cycle_report()` returns:

- per-issue cycle records
- summary statistics
- histogram buckets
- monthly trend
- longest outliers

### Frontend rendering

The cycle chart is a scatter plot:

- X axis = completion date
- Y axis = cycle duration

The UI then supports:

- date-window clipping
- Y-axis cap control
- percentile cards recalculated for visible issues only
- hiding specific issue points

## Throughput

### Backend logic

Relevant functions:

- `find_completion_event`
- `throughput_report`

A throughput event is created at the first transition into a done status.

Each event contains:

- completion timestamp
- month bucket
- owner
- assignee
- project key
- issue key

Attribution modes:

- `assignee_at_done`
- `transition_author`

### Frontend rendering

The backend returns completion events and monthly aggregates.

The frontend can rebucket the raw event list into:

- weekly bars
- monthly bars

This rebucketing happens only inside the already selected dashboard date range.

## Phase Ratio

### Backend logic

Relevant functions:

- `clip_intervals`
- `compute_phase_ratio`
- `compute_status_ratio`
- `phase_ratio_report`

For every completed issue:

1. Find its cycle start and cycle end.
2. Clip status intervals to that window only.
3. Sum time by board lane.
4. Sum time by status.
5. Compute ratios against the total cycle duration.

The report returns:

- total seconds by phase
- average ratio by phase
- median ratio by phase
- status-level totals
- per-issue dominant phase and status
- outlier lists

### Frontend rendering

The current UI emphasizes the status-level view.

It calculates:

- average days per status
- issue count contributing to each status
- color emphasis for longer average statuses

## CFD

### Why CFD is special

CFD needs:

- full history
- correct status ordering
- correct board mapping
- timezone-aware end-of-day snapshots

### Backend logic

Relevant functions:

- `resolve_report_timezone`
- `interval_day_span`
- `cfd_series_definition`
- `compute_cfd`
- `cfd_report`

Algorithm:

1. Build continuous status intervals per issue.
2. Resolve the report timezone.
3. Convert each interval into a local-day span.
4. Write `+1` on the effective start day and `-1` on the day after the effective end.
5. Sweep once across the calendar range and maintain running counts.
6. Build `current` and `cumulative` snapshots for each day.

Why the delta sweep is used:

- avoids re-evaluating every issue on every day
- handles reopened flow correctly
- respects creation time
- preserves final state for multiple same-day transitions

### Series definition behavior

CFD can operate in two modes:

1. lane-level mode
   - series match configured board columns
2. expanded status mode
   - used when generic buckets like `inactive/active/done` would otherwise hide detail
   - individual statuses become series

Historical statuses observed in synced issue history can also be appended so that the chart remains continuous.

### Report payload

`cfd_report()` returns:

- `meta`
- `series`
- `points`
- `latest`
- `issues`
- `warnings`
- `bottlenecks`
- `methodology`

### Frontend rendering

The CFD chart is rendered as a custom stacked SVG area chart.

The UI:

- filters points by the dashboard date range
- honors hidden series
- uses the backend-provided stacking order when available
- renders a legend with per-series hide controls

### Important CFD implementation details

- snapshots are end-of-day
- timezone comes from the browser request
- done-like states are kept near the baseline through stacking order
- generic mappings can expand into concrete statuses automatically

## Demo data

The demo dataset is intentionally shaped to exercise:

- completed issues
- multiple status sequences
- different issue types
- assignee changes
- realistic chart rendering without Jira access
