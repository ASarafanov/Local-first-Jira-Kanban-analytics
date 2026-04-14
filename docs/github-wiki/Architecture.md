# Architecture

[Home](Home.md)

## Overview

The project is organized as a compact local application with a clear separation between:

- transport and HTTP delivery
- Jira integration and sync orchestration
- persistence
- pure metric calculation
- client-side rendering and dashboard interaction

## Main Modules

### `kanban_metrics/app.py`

Responsible for:

- application bootstrap
- database initialization
- runtime secret store initialization
- HTTP route handling
- static file serving

This file is the entrypoint for the browser-based runtime.

### `kanban_metrics/service.py`

Responsible for:

- saving and loading sync configurations
- starting background sync jobs
- reading persisted issue history
- assembling metric payloads for the dashboard

`DashboardService.get_metrics()` is the main orchestration method for analytics responses.

### `kanban_metrics/jira.py`

Responsible for:

- Jira HTTP requests
- pagination and retry behavior
- query construction
- loading boards, projects, statuses, and changelog history
- mapping Jira workflow data into the local domain model

The sync service is built on top of `JiraClient` and `JiraSyncService`.

### `kanban_metrics/db.py`

Responsible for:

- SQLite access
- schema initialization
- lightweight migrations
- repositories for configs, issues, and jobs

### `kanban_metrics/metrics.py`

Responsible for:

- converting raw issue history into intervals
- cycle time calculations
- throughput calculations
- phase/status ratio calculations
- CFD generation and serialization

This module holds the purest logic in the project.

### `kanban_metrics/static/app.js`

Responsible for:

- page state management
- API calls
- configuration form behavior
- local dashboard filtering
- chart drawing using SVG
- interaction logic like tooltips and hidden-series controls

## Runtime Modes

### Browser Development Mode

Launched through:

```bash
python3 -m kanban_metrics
```

Behavior:

- starts the local HTTP server
- opens the UI in the default browser

### Native macOS Mode

Launched through the packaged app or `macos_main.py`.

Behavior:

- starts the same local server on a local port
- waits until it is reachable
- opens the UI inside a native `pywebview` window

Important: the macOS app is not a second implementation of the product. It is just a shell around the same backend and SPA.

## Data Flow

```text
UI action
  -> HTTP route in app.py
  -> service.py orchestration
  -> db.py and/or jira.py
  -> metrics.py if analytics requested
  -> JSON response
  -> app.js render/update
```

## Architectural Decisions

### Why a local server exists

The local server keeps the product simple:

- one backend codepath
- one frontend codepath
- easy browser debugging
- easy reuse from the native macOS shell

### Why the metrics live on the backend

The calculation logic depends on:

- full issue history
- timezone-aware interval handling
- consistent interpretation of board mapping

Keeping the source-of-truth calculations on the backend avoids drift across different clients.

### Why some filtering still happens in the browser

Once the full metric payload is loaded, the dashboard supports lightweight local operations such as:

- date-window filtering
- week/month throughput rebucketing
- hiding individual cycle points
- hiding CFD series

That keeps the dashboard responsive without re-syncing Jira or re-fetching the full dataset on each interaction.
