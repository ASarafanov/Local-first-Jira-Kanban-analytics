<p align="center">
  <img src="assets/app_icon_1024.png" alt="Kanban Metrics logo" width="160">
</p>

# Local-first Jira Kanban Analytics

A local-first Jira analytics app that syncs issue history into a local SQLite store and visualizes cycle time, throughput, phase ratio, and CFD without sending your project data to an external analytics backend.

## Project

- Local HTTP server + static dashboard UI
- Jira sync with persisted issue history and changelog events
- Native macOS wrapper for desktop use

## Wiki

- Implementation guide: [docs/github-wiki/Home.md](docs/github-wiki/Home.md)
- AI-friendly source map: [docs/IMPLEMENTATION_AI.md](docs/IMPLEMENTATION_AI.md)

## Screenshots

### Overview

![Kanban Metrics overview](assets/screenshots/hero.png)

### Cycle Time And Status Mix

![Cycle time and status mix](assets/screenshots/cycle_phase.png)

### Throughput And CFD

![Throughput and CFD](assets/screenshots/throughput_cfd.png)
