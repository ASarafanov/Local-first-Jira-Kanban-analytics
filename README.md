# Local-first Jira Kanban Analytics

RU: Локальное desktop/web-приложение для загрузки истории задач из Jira и расчёта Kanban-метрик без отправки данных во внешние аналитические сервисы.

EN: A local-first desktop/web app that imports Jira issue history and calculates Kanban metrics without sending your data to external analytics services.

## Documentation

- RU: Подробная AI-friendly документация по реализации проекта находится в [docs/IMPLEMENTATION_AI.md](docs/IMPLEMENTATION_AI.md).
- EN: Detailed AI-friendly implementation documentation lives in [docs/IMPLEMENTATION_AI.md](docs/IMPLEMENTATION_AI.md).

## What The Project Does / Что Делает Проект

- RU: Хранит конфигурации синка и историю задач в локальном SQLite.
- EN: Stores sync configuration and issue history in a local SQLite database.
- RU: Поднимает локальный HTTP-сервер и отдаёт одностраничный интерфейс из `kanban_metrics/static/`.
- EN: Runs a local HTTP server and serves a single-page UI from `kanban_metrics/static/`.
- RU: Поддерживает demo-режим без подключения к Jira.
- EN: Supports a demo mode that works without Jira credentials.
- RU: Имеет нативную macOS-обёртку на `pywebview`.
- EN: Includes a native macOS wrapper built with `pywebview`.

## Implementation Overview / Обзор Реализации

### Runtime Architecture / Архитектура рантайма

- RU: `kanban_metrics/app.py` собирает SQLite, runtime-store, сервисный слой и HTTP API.
- EN: `kanban_metrics/app.py` wires SQLite, the runtime secret store, the service layer, and the HTTP API.
- RU: `kanban_metrics/service.py` оркестрирует сохранение конфигов, фоновые sync-job'ы и построение всех метрик.
- EN: `kanban_metrics/service.py` orchestrates config persistence, background sync jobs, and metric assembly.
- RU: `kanban_metrics/jira.py` реализует Jira-клиент, пагинацию, retries, JQL builder и парсинг changelog history.
- EN: `kanban_metrics/jira.py` implements the Jira client, pagination, retries, JQL building, and changelog parsing.
- RU: `kanban_metrics/metrics.py` содержит чистую вычислительную логику для cycle time, phase ratio, throughput и CFD.
- EN: `kanban_metrics/metrics.py` contains the pure computation logic for cycle time, phase ratio, throughput, and CFD.
- RU: `kanban_metrics/static/app.js` отрисовывает графики и применяет локальные фильтры без повторного sync.
- EN: `kanban_metrics/static/app.js` renders the charts and applies local dashboard filters without re-syncing.

### Development History / История Разработки

The local git history shows four implementation stages:

1. `27427e6`:
   RU: Базовая публичная версия с backend, frontend, SQLite, Jira sync, demo-данными, CFD-спеком и тестами.
   EN: Public foundation with backend, frontend, SQLite, Jira sync, demo data, CFD spec, and tests.
2. `207e27f`:
   RU: Слияние bootstrap-файлов и добавление лицензии.
   EN: Merge of bootstrap files and license addition.
3. `2688d2f`:
   RU: Нативная macOS-упаковка, пути Application Support, иконки, `pywebview`, PyInstaller scripts.
   EN: Native macOS packaging, Application Support paths, icons, `pywebview`, and PyInstaller scripts.
4. `854538a`:
   RU: Сборка `.dmg` и GitHub Release workflow.
   EN: `.dmg` packaging and a GitHub Release workflow.

## Chart Calculation Logic / Логика Расчёта Графиков

### Cycle Time

- RU: Для каждой задачи цикл начинается при первом переходе в один из `start_status_ids` и заканчивается при первом переходе в один из `done_status_ids`.
- EN: For each issue, the cycle starts at the first transition into any `start_status_ids` and ends at the first transition into any `done_status_ids`.
- RU: Отчёт `cycle_report()` строит список completed issues, summary-перцентили, тренд по месяцам и histogram по длительности.
- EN: `cycle_report()` builds the completed-issue list, summary percentiles, monthly trend, and a duration histogram.
- RU: В UI scatter plot использует `X = done date`, `Y = cycle time`, а фильтры по оси X и Y применяются локально.
- EN: In the UI, the scatter plot uses `X = done date`, `Y = cycle time`, and X/Y filters are applied locally.

### Throughput

- RU: Throughput считается по первому переходу задачи в done-статус.
- EN: Throughput is counted from the first transition of an issue into a done status.
- RU: Backend формирует completion events и агрегирует их по месяцам, исполнителю и проекту.
- EN: The backend creates completion events and aggregates them by month, assignee/owner, and project.
- RU: UI умеет переагрегировать те же события по неделям или месяцам внутри выбранного диапазона дат.
- EN: The UI re-aggregates the same events into weekly or monthly buckets inside the selected date range.

### Phase Ratio

- RU: Для каждой completed issue интервал цикла режется от старта цикла до завершения, затем время суммируется по board lane и по отдельным статусам.
- EN: For each completed issue, the cycle window is clipped from cycle start to completion, then time is accumulated by board lane and by individual statuses.
- RU: UI показывает среднее количество дней в каждом status внутри выбранного диапазона completed issues.
- EN: The UI shows average days spent in each status for the completed issues inside the selected date range.

### CFD

- RU: Backend сначала строит непрерывные status intervals из changelog history.
- EN: The backend first builds continuous status intervals from changelog history.
- RU: Затем каждый interval переводится в локальные календарные дни выбранной timezone.
- EN: Each interval is then converted into local calendar-day spans for the selected timezone.
- RU: Алгоритм не итерируется по всем задачам на каждый день, а пишет `+1/-1` deltas на границы интервала и делает один проход по дням.
- EN: Instead of iterating over every issue for every day, the algorithm writes `+1/-1` deltas at interval boundaries and performs a single sweep across days.
- RU: Snapshot делается на конец дня, поэтому несколько переходов внутри одного дня сворачиваются в финальное состояние дня.
- EN: Snapshots are end-of-day based, so multiple same-day transitions collapse into that day’s final state.
- RU: Если mapping обобщённый (`inactive/active/done`), CFD разворачивается до отдельных исторически наблюдавшихся статусов, чтобы не терять детализацию.
- EN: If the mapping is generic (`inactive/active/done`), CFD expands into individual observed statuses so the chart does not lose detail.

## Local Data Model / Локальная Модель Данных

- `jira_instance`: RU: параметры Jira-инстанса и секрет-ссылка. EN: Jira instance settings and secret reference.
- `config`: RU: сохранённая область синка, JQL, диапазоны дат и mapping доски. EN: persisted sync scope, JQL, date range, and board mapping.
- `issue`: RU: локальный snapshot задач. EN: local issue snapshot.
- `changelog_event`: RU: история status/assignee transitions. EN: status/assignee transition history.
- `sync_job`: RU: прогресс фоновой синхронизации. EN: background sync job progress.

## Run / Запуск

```bash
python3 -m kanban_metrics
```

RU: В development-режиме приложение поднимает локальный сервер на `http://127.0.0.1:8765` и открывает браузер.

EN: In development mode the app starts a local server on `http://127.0.0.1:8765` and opens your browser.

## First Use / Первый Запуск

- RU: Нажмите `Load demo`, чтобы посмотреть полный dashboard без Jira credentials.
- EN: Click `Load demo` to inspect a complete dashboard without Jira credentials.
- RU: Или укажите Jira URL и personal access token, затем выполните `Test connection`.
- EN: Or provide a Jira URL and personal access token, then run `Test connection`.
- RU: Секреты сохраняются в macOS Keychain, а при недоступности keychain в локальный файл fallback.
- EN: Secrets are stored in the macOS Keychain, with a local file fallback if the keychain is unavailable.

## macOS App Bundle

```bash
./scripts/build_macos_app.sh
```

- RU: Результат сборки создаётся в `dist/Kanban Metrics.app`.
- EN: The build output is written to `dist/Kanban Metrics.app`.
- RU: Нативное приложение использует `~/Library/Application Support/Kanban Metrics/` как writable data directory.
- EN: The native app uses `~/Library/Application Support/Kanban Metrics/` as its writable data directory.

## macOS DMG

```bash
./scripts/build_macos_dmg.sh
```

- RU: Инсталлятор создаётся в `dist/Kanban Metrics.dmg`.
- EN: The installer image is created at `dist/Kanban Metrics.dmg`.

## Release Flow / Release-процесс

RU: Тег вида `v0.1.0` запускает `.github/workflows/release.yml`, который выполняет тесты, собирает `.app`, упаковывает `.dmg` и публикует GitHub Release.

EN: A tag like `v0.1.0` triggers `.github/workflows/release.yml`, which runs tests, builds the `.app`, packages the `.dmg`, and publishes a GitHub Release.

## Test / Тесты

```bash
python3 -m unittest discover -s tests
```

## Current Constraints / Текущие Ограничения

- RU: В текущей сборке Jira TLS verification всегда отключена (`verify_ssl=False` по всему приложению).
- EN: In the current build, Jira TLS verification is always disabled (`verify_ssl=False` throughout the app).
- RU: UI рассчитывает отображение графиков локально поверх уже загруженного набора данных; для новых issue histories нужен новый sync.
- EN: The UI recalculates chart views locally on top of the already loaded dataset; new issue histories still require a new sync.
- RU: Проект ориентирован на локальный desktop/workstation сценарий, а не на multi-user server deployment.
- EN: The project is designed for local desktop/workstation usage, not multi-user server deployment.
