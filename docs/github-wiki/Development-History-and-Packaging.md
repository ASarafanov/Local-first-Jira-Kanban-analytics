# Development History and Packaging

## Git History Summary

The visible local history shows four main stages.

### `27427e6` - Public foundation

This commit introduced the primary implementation:

- Python backend
- SQLite persistence
- Jira integration
- metric engine
- static dashboard UI
- CFD adaptation notes
- tests

### `207e27f` - Repository bootstrap merge

This stage added the public repository bootstrap pieces and license material.

### `2688d2f` - Native macOS app packaging

This stage introduced:

- `pywebview` desktop wrapper
- app icon assets
- PyInstaller build script
- dedicated user data directory handling

### `854538a` - DMG packaging and release workflow

This stage added:

- `.dmg` packaging script
- GitHub Actions release workflow

## Packaging Strategy

### Browser-first development

The easiest developer path is:

```bash
python3 -m kanban_metrics
```

This starts the local server and opens the browser UI.

### Native app packaging

The native macOS path exists for distribution to end users who should not need a Python environment or a terminal session.

Build script:

```bash
./scripts/build_macos_app.sh
```

Result:

- `dist/Kanban Metrics.app`

### DMG packaging

Build script:

```bash
./scripts/build_macos_dmg.sh
```

Result:

- `dist/Kanban Metrics.dmg`

## Runtime data location

The project uses platform-sensitive paths through `kanban_metrics/paths.py`.

On macOS, packaged builds store writable data under:

```text
~/Library/Application Support/Kanban Metrics/
```

This includes:

- SQLite database
- runtime secret fallback file

## GitHub Release Flow

The repository includes `.github/workflows/release.yml`.

On a version tag push, the workflow:

- runs tests
- builds the macOS app
- packages the DMG
- publishes a GitHub Release

## Testing Strategy

The test suite in `tests/test_metrics.py` primarily covers:

- interval construction
- cycle time behavior
- throughput attribution
- phase and status ratio calculations
- CFD edge cases
- board/status mapping logic
- repository scoping rules
- config deletion rules

## Current Technical Tradeoffs

- local-first simplicity over multi-user deployment
- standard library HTTP client over a richer Jira SDK
- lightweight repository/migration layer over a full ORM
- custom SVG charts over a charting library
- native desktop shell reuse over a dedicated desktop backend
