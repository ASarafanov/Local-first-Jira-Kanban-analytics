# Kanban Metrics Wiki

This wiki documents the implementation of `Local-first Jira Kanban Analytics` in a GitHub-friendly, human-readable format.

## Scope

The repository contains a local-first analytics app that:

- syncs issue history from Jira
- persists data locally in SQLite
- serves a local dashboard over HTTP
- optionally wraps the dashboard in a native macOS window
- calculates cycle time, throughput, phase ratio, and CFD

The detailed AI-friendly project map still lives in the repository under [`docs/IMPLEMENTATION_AI.md`](https://github.com/ASarafanov/Local-first-Jira-Kanban-analytics/blob/main/docs/IMPLEMENTATION_AI.md).

## Wiki Index

- [Architecture](Architecture)
- [Data Model and Persistence](Data-Model-and-Persistence)
- [Jira Sync and HTTP API](Jira-Sync-and-HTTP-API)
- [Metrics and Chart Logic](Metrics-and-Chart-Logic)
- [Development History and Packaging](Development-History-and-Packaging)

## Design Summary

- The app is intentionally local-first: data is pulled from Jira, stored locally, and analyzed on the user's machine.
- The backend is a single Python process that owns storage, sync orchestration, and metric calculation.
- The frontend is a static SPA built with plain JavaScript and custom SVG chart rendering.
- The macOS desktop app is a wrapper around the same local server, not a separate backend implementation.

## Main Runtime Path

```text
Jira REST API
  -> jira.py
  -> service.py
  -> db.py / schema.sql
  -> app.py HTTP routes
  -> static/app.js
  -> browser or native macOS window
```

## Key Project Traits

- No external analytics backend
- Local SQLite persistence
- Local secret storage with keychain preference
- Demo mode for offline exploration
- GitHub release flow for `.app` and `.dmg`
