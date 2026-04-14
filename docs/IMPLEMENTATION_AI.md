# Project Implementation Map / Карта Реализации Проекта

## Metadata / Метаданные

- `project`: `Local-first Jira Kanban Analytics`
- `source_of_truth_ru`: кодовая база проекта и локальная git-история на 2026-04-14
- `source_of_truth_en`: the project codebase and local git history as of 2026-04-14
- `main_language`: Python + vanilla JavaScript
- `ui_runtime`: local HTTP server + static SPA + optional native macOS wrapper
- `persistence`: SQLite + runtime secret store

## 1. Purpose / Назначение

RU:
- Проект нужен для локального анализа Kanban-потока по истории задач Jira.
- Система сохраняет конфигурации синка, загружает историю переходов и строит четыре ключевых представления: cycle time, throughput, phase ratio и CFD.
- Основной дизайн-принцип: local-first, без внешнего backend и без отправки исторических данных в SaaS-аналитику.

EN:
- The project is meant for local Kanban flow analytics over Jira issue history.
- It persists sync configuration, loads issue transition history, and exposes four main views: cycle time, throughput, phase ratio, and CFD.
- The primary design principle is local-first operation with no external backend and no SaaS analytics dependency.

## 2. Development History Reconstructed From Git / История Разработки По Git

RU:
1. `27427e6` создал ядро проекта: backend, SQLite, Jira sync, фронтенд, demo-данные, CFD-адаптацию и тесты.
2. `207e27f` добавил bootstrap-файлы открытого репозитория и лицензию.
3. `2688d2f` добавил native macOS app packaging, `pywebview`, PyInstaller scripts, и вынес user-data в Application Support.
4. `854538a` завершил packaging-историю через `.dmg` и GitHub release workflow.

EN:
1. `27427e6` created the project core: backend, SQLite, Jira sync, frontend, demo data, CFD adaptation, and tests.
2. `207e27f` added public repository bootstrap files and the license.
3. `2688d2f` added native macOS app packaging, `pywebview`, PyInstaller scripts, and moved user data into Application Support.
4. `854538a` completed the packaging story with `.dmg` output and a GitHub release workflow.

## 3. High-Level Architecture / Высокоуровневая Архитектура

```text
Jira REST API
  -> kanban_metrics/jira.py
  -> kanban_metrics/service.py (background sync + metric orchestration)
  -> kanban_metrics/db.py + schema.sql (local persistence)
  -> kanban_metrics/app.py (HTTP API + static file serving)
  -> kanban_metrics/static/app.js (dashboard state + chart rendering)
  -> Browser or kanban_metrics/desktop.py (native macOS shell)
```

RU:
- Весь backend живёт внутри локального процесса Python.
- HTTP API и SPA-сборка являются частью одного runtime.
- Нативное macOS-приложение не заменяет backend: оно просто поднимает тот же локальный сервер и открывает его в `pywebview`.

EN:
- The entire backend lives inside a local Python process.
- The HTTP API and SPA are part of the same runtime.
- The native macOS app does not replace the backend: it launches the same local server and opens it in `pywebview`.

## 4. File Map / Карта Файлов

### Core Backend

- `kanban_metrics/app.py`
  - RU: композиция приложения, инициализация БД, runtime store, HTTP routes, static file serving.
  - EN: application composition, DB initialization, runtime store, HTTP routes, static file serving.
- `kanban_metrics/service.py`
  - RU: сервисный слой между HTTP и вычислительным кодом; запускает sync-job'ы и собирает dashboard payload.
  - EN: service layer between HTTP and the computation code; starts sync jobs and assembles dashboard payloads.
- `kanban_metrics/jira.py`
  - RU: Jira client, retries, pagination, board/project mapping, JQL builder, changelog fetch, user-label resolution.
  - EN: Jira client, retries, pagination, board/project mapping, JQL builder, changelog fetch, user-label resolution.
- `kanban_metrics/metrics.py`
  - RU: чистые расчёты по issue history.
  - EN: pure calculations over issue history.
- `kanban_metrics/db.py`
  - RU: SQLite repositories и простые migrations.
  - EN: SQLite repositories and simple migrations.
- `kanban_metrics/models.py`
  - RU: dataclass-модели домена.
  - EN: domain dataclasses.
- `kanban_metrics/runtime_store.py`
  - RU: хранение секретов в keychain или fallback-файле.
  - EN: secret storage in keychain or a fallback file.

### UI

- `kanban_metrics/static/index.html`
  - RU: каркас dashboard/configuration UI.
  - EN: dashboard/configuration UI shell.
- `kanban_metrics/static/styles.css`
  - RU: статическая визуальная тема и компоненты.
  - EN: static theme and component styling.
- `kanban_metrics/static/app.js`
  - RU: state management, HTTP calls, local filtering, chart rendering, tooltips, hidden-series logic.
  - EN: state management, HTTP calls, local filtering, chart rendering, tooltips, hidden-series logic.

### Packaging

- `kanban_metrics/desktop.py`
  - RU: native macOS window launcher.
  - EN: native macOS window launcher.
- `kanban_metrics/macos_main.py`
  - RU: entrypoint для собранного macOS app bundle.
  - EN: entrypoint for the packaged macOS app bundle.
- `kanban_metrics/paths.py`
  - RU: определение `resource_root()` и `user_data_dir()`.
  - EN: resolution of `resource_root()` and `user_data_dir()`.
- `scripts/build_macos_app.sh`
  - RU: сборка `.app`.
  - EN: `.app` build script.
- `scripts/build_macos_dmg.sh`
  - RU: упаковка `.dmg`.
  - EN: `.dmg` packaging script.

### Validation

- `tests/test_metrics.py`
  - RU: unit tests для расчётной логики, Jira mapping, репозиториев и удалений конфигов.
  - EN: unit tests for computation logic, Jira mappings, repositories, and config deletion.

## 5. Runtime Flow / Поток Выполнения

### Startup

RU:
1. `python3 -m kanban_metrics` вызывает `kanban_metrics.__main__`.
2. `app.py` создаёт `Database`, применяет schema и миграции.
3. Создаются `ConfigRepository`, `IssueRepository`, `JobRepository`, `RuntimeStore`, `DashboardService`.
4. Стартует `ThreadingHTTPServer`, который отдаёт API и static assets.

EN:
1. `python3 -m kanban_metrics` enters `kanban_metrics.__main__`.
2. `app.py` creates the `Database`, applies the schema and migrations.
3. `ConfigRepository`, `IssueRepository`, `JobRepository`, `RuntimeStore`, and `DashboardService` are created.
4. A `ThreadingHTTPServer` starts serving the API and static assets.

### Sync

RU:
1. UI сохраняет `SyncConfig`.
2. По кнопке sync создаётся `SyncJob` со статусом `running`.
3. `JobManager` в отдельном потоке создаёт `JiraClient` и `JiraSyncService`.
4. Если scope = board, сначала подтягивается board configuration и актуализируется `board_mapping`.
5. Затем строится effective JQL, грузятся issue snapshots и changelog history.
6. История задач записывается в локальную БД транзакционно через `replace_issues`.

EN:
1. The UI persists a `SyncConfig`.
2. Pressing sync creates a `SyncJob` in `running` state.
3. `JobManager` starts a background thread with `JiraClient` and `JiraSyncService`.
4. If scope = board, it first loads board configuration and refreshes `board_mapping`.
5. It then builds the effective JQL and downloads issue snapshots plus changelog history.
6. Issue history is written to the local DB transactionally via `replace_issues`.

### Metrics Load

RU:
1. UI делает параллельные запросы к `cycle-time`, `throughput`, `phase-ratio`, `cfd`.
2. Backend достаёт config и список issue histories по `config_id`.
3. `DashboardService.get_metrics()` вызывает все расчётные функции и возвращает сериализованный payload.
4. UI больше не пересчитывает backend-метрики с нуля, а только фильтрует/агрегирует загруженные данные для текущего экрана.

EN:
1. The UI requests `cycle-time`, `throughput`, `phase-ratio`, and `cfd` in parallel.
2. The backend loads the config and its issue histories by `config_id`.
3. `DashboardService.get_metrics()` calls all computation functions and returns serialized payloads.
4. The UI does not recompute backend metrics from scratch; it only filters/aggregates the loaded data for the current view.

## 6. Local Data Model / Локальная Модель Данных

### Domain Types

- `StatusTransition(timestamp, from_status_id, to_status_id, author_account_id)`
- `AssigneeTransition(timestamp, from_account_id, to_account_id)`
- `StatusInterval(start, end, status_id)`
- `BoardMapping(columns, phase_names, status_names)`
- `IssueHistory(...)`
- `SyncConfig(...)`
- `SyncJob(...)`
- `DailyCfdPoint(day, current, cumulative)`

RU:
- `IssueHistory` является главной единицей аналитики.
- Все временные значения нормализуются в UTC через `ensure_utc`.

EN:
- `IssueHistory` is the main analytics unit.
- All timestamps are normalized to UTC via `ensure_utc`.

### SQLite Tables

- `jira_instance`
  - RU: URL Jira, auth type, verify flag, user, secret ref.
  - EN: Jira URL, auth type, verify flag, user, secret ref.
- `config`
  - RU: scope, JQL, даты, status buckets и board mapping.
  - EN: scope, JQL, dates, status buckets, and board mapping.
- `issue`
  - RU: локальный snapshot задач.
  - EN: local issue snapshot.
- `changelog_event`
  - RU: history для status и assignee transitions.
  - EN: history for status and assignee transitions.
- `sync_job`
  - RU: прогресс background sync.
  - EN: background sync progress.

Important invariant / Важный инвариант:

- RU: `IssueRepository` префиксует Jira issue id конфигом (`cfg-id:issue-id`), чтобы один и тот же Jira issue мог безопасно существовать в нескольких конфигурациях.
- EN: `IssueRepository` prefixes Jira issue ids with the config id (`cfg-id:issue-id`) so the same Jira issue can safely exist in multiple configurations.

## 7. Jira Integration / Интеграция С Jira

### Request Strategy

RU:
- Используется `urllib.request`, без внешнего HTTP SDK.
- Есть retries для `429` и сетевых ошибок.
- Поддерживаются fallback path'ы между REST API v3 и v2.

EN:
- The client uses `urllib.request` instead of an external HTTP SDK.
- Retries exist for `429` responses and transport errors.
- It supports fallback paths between REST API v3 and v2.

### Query Building

RU:
- Builder mode строит JQL из `project_keys`, `issue_types`, `sync_start_date`, `sync_end_date`.
- Board mode берёт base filter из Jira board configuration и при необходимости добавляет `subQuery`.
- `extra_jql` всегда добавляется как дополнительный `AND (...)`.

EN:
- Builder mode creates JQL from `project_keys`, `issue_types`, `sync_start_date`, and `sync_end_date`.
- Board mode derives its base filter from Jira board configuration and optionally appends `subQuery`.
- `extra_jql` is always appended as an additional `AND (...)` clause.

### History Fetch

RU:
- Сначала сервис пытается использовать bulk changelog fetch.
- Если bulk endpoint недоступен, включается fallback на per-issue changelog.
- Затем статусные и assignee transitions превращаются в локальные dataclass-структуры.

EN:
- The service first tries bulk changelog fetch.
- If the bulk endpoint is unavailable, it falls back to per-issue changelog requests.
- Status and assignee transitions are then converted into local dataclass structures.

## 8. HTTP API / HTTP API

- `GET /api/configs`
  - RU: список сохранённых конфигов.
  - EN: list of saved configs.
- `POST /api/configs`
  - RU: создать config.
  - EN: create a config.
- `PUT /api/configs/{id}`
  - RU: обновить config.
  - EN: update a config.
- `DELETE /api/configs/{id}`
  - RU: удалить config и связанные локальные данные.
  - EN: delete a config and its related local data.
- `POST /api/configs/{id}/sync`
  - RU: запустить background sync.
  - EN: start a background sync.
- `GET /api/jobs/{id}`
  - RU: статус sync-job.
  - EN: sync job status.
- `POST /api/jira/test-connection`
  - RU: проверить креды Jira.
  - EN: test Jira credentials.
- `POST /api/jira/validate-jql`
  - RU: распарсить и нормализовать JQL.
  - EN: parse and normalize JQL.
- `POST /api/jira/projects`
  - RU: получить список проектов.
  - EN: list projects.
- `POST /api/jira/project-statuses`
  - RU: построить mapping статусов для builder mode.
  - EN: derive a status mapping for builder mode.
- `GET /api/metrics/cycle-time`
- `GET /api/metrics/throughput`
- `GET /api/metrics/phase-ratio`
- `GET /api/metrics/cfd`
- `POST /api/demo/bootstrap`
  - RU: создать demo config и demo issues.
  - EN: create the demo config and demo issues.

## 9. Metric Logic / Логика Метрик

### 9.1 Shared Primitive: Status Intervals

Source:
- `build_status_intervals(issue, report_end)`

RU:
- Для каждой задачи transitions сортируются по времени.
- Между `created_at` и первым transition создаётся первый interval.
- После каждого transition предыдущий статус закрывается и открывается новый.
- Последний interval продлевается до `report_end` или текущего времени.

EN:
- For each issue, transitions are sorted by time.
- The first interval spans from `created_at` to the first transition.
- After every transition, the previous status closes and a new one opens.
- The last interval is extended to `report_end` or the current time.

This primitive feeds:
- cycle-time
- phase-ratio
- status-ratio
- CFD

### 9.2 Cycle Time

Source:
- `find_cycle_segments`
- `compute_elapsed_cycle_time`
- `compute_in_status_cycle_time`
- `cycle_report`

RU:
- `find_cycle_segments()` ищет пары `start_status -> done_status`.
- В default-режиме используется `first_completion`: от первого входа в стартовый статус до первого done.
- Поддержаны и другие reopen semantics: `last_completion` и `sum_of_cycles`, но сервис сейчас вызывает default.
- `cycle_report()` возвращает summary (`median`, `p50`, `p85`, `p95`), trend по месяцам, histogram и per-issue список.

EN:
- `find_cycle_segments()` finds `start_status -> done_status` pairs.
- The default mode is `first_completion`: from the first entry into a start status to the first done.
- Other reopen semantics exist (`last_completion`, `sum_of_cycles`), but the service currently uses the default.
- `cycle_report()` returns summary stats (`median`, `p50`, `p85`, `p95`), monthly trend, histogram, and per-issue details.

UI rendering:
- RU: scatter plot, где `X = issue.end`, `Y = issue.hours`.
- EN: scatter plot where `X = issue.end`, `Y = issue.hours`.
- RU: percentile cards для видимых задач считаются в браузере заново после фильтрации.
- EN: percentile cards for visible issues are recomputed in the browser after filtering.

### 9.3 Throughput

Source:
- `find_completion_event`
- `throughput_report`
- `aggregateThroughputData` in `app.js`

RU:
- Completion event появляется на первом переходе в done.
- Attribution зависит от `attribution_mode`:
  - `assignee_at_done`
  - `transition_author`
- Backend отдаёт список events и monthly aggregates.
- UI повторно bucketizes events по week/month только для выбранного визуального диапазона.

EN:
- A completion event is created at the first transition into done.
- Attribution depends on `attribution_mode`:
  - `assignee_at_done`
  - `transition_author`
- The backend returns event lists and monthly aggregates.
- The UI re-bucketizes events by week/month only for the selected visual range.

### 9.4 Phase Ratio And Status Ratio

Source:
- `clip_intervals`
- `compute_phase_ratio`
- `compute_status_ratio`
- `phase_ratio_report`
- `aggregateCycleStatusSummary` in `app.js`

RU:
- Цикл по задаче сначала ограничивается окном между cycle start и cycle end.
- Затем длительности суммируются:
  - по lane (`phase_name_for_column`)
  - по конкретным статусам (`status_name`)
- `phase_ratio_report()` агрегирует totals, average ratio, median ratio, dominant phase/status и outliers.
- UI сейчас визуализирует именно status-level summary: среднее число дней по каждому статусу внутри выбранного диапазона задач.

EN:
- The issue cycle is first clipped to the window between cycle start and cycle end.
- Durations are then accumulated:
  - by lane (`phase_name_for_column`)
  - by concrete status (`status_name`)
- `phase_ratio_report()` aggregates totals, average ratio, median ratio, dominant phase/status, and outliers.
- The UI currently visualizes the status-level summary: average days per status for the selected issue range.

### 9.5 CFD

Source:
- `resolve_report_timezone`
- `interval_day_span`
- `cfd_series_definition`
- `compute_cfd`
- `cfd_report`
- `renderStackedAreaChart` in `app.js`

Backend algorithm:

1. RU: Построить `StatusInterval` для каждой задачи.
   EN: Build `StatusInterval` objects for each issue.
2. RU: Сопоставить каждый статус CFD-series через `board_mapping`.
   EN: Map each status to a CFD series via `board_mapping`.
3. RU: Перевести interval в диапазон локальных календарных дней для выбранной timezone.
   EN: Convert each interval into a span of local calendar days for the selected timezone.
4. RU: Записать `+1` на `effective_start` и `-1` на `effective_end + 1 day`.
   EN: Write `+1` at `effective_start` and `-1` at `effective_end + 1 day`.
5. RU: Одним проходом по дням поддерживать running counts и собрать snapshots.
   EN: Sweep across days once, maintain running counts, and build snapshots.
6. RU: Для stacked chart дополнительно посчитать cumulative counts от последней lane к первой.
   EN: For the stacked chart, also compute cumulative counts from the last lane back to the first.

Why this matters / Почему это важно:

- RU: корректно обрабатываются reopened issues;
- EN: reopened issues are handled correctly;
- RU: несколько transitions в один день сворачиваются в финальное состояние дня;
- EN: multiple same-day transitions collapse into the final state of that day;
- RU: issue не появляется в CFD до момента создания;
- EN: an issue does not appear in the CFD before it is created;
- RU: snapshot действительно зависит от timezone браузера/пользователя;
- EN: the snapshot really depends on the browser/user timezone.

Series behavior / Поведение рядов:

- RU: если mapping специфичен для board columns, series совпадают с lane'ами доски;
- EN: if the mapping is specific to board columns, the series match the board lanes;
- RU: если mapping обобщённый (`inactive/active/done`) и содержит несколько статусов в одной группе, CFD автоматически разворачивается до individual statuses;
- EN: if the mapping is generic (`inactive/active/done`) and groups multiple statuses together, CFD automatically expands to individual statuses;
- RU: исторически наблюдавшиеся статусы, которых нет в конфиге, могут быть добавлены как series для сохранения непрерывности;
- EN: historically observed statuses not present in the config can be appended as series to preserve continuity;
- RU: `cfd_report()` добавляет warnings и bottleneck hints.
- EN: `cfd_report()` adds warnings and bottleneck hints.

UI rendering:

- RU: `renderCfd()` берёт backend-ready `points`, фильтрует их по выбранному диапазону дат и скрытым сериям, затем отдаёт в `renderStackedAreaChart`.
- EN: `renderCfd()` takes backend-ready `points`, filters them by the selected date range and hidden series, then passes them to `renderStackedAreaChart`.
- RU: порядок stacking берётся из `meta.stackingOrder`, чтобы done-like statuses лежали ближе к baseline.
- EN: stacking order comes from `meta.stackingOrder`, keeping done-like statuses closer to the baseline.

## 10. Frontend Behavior / Поведение Фронтенда

RU:
- UI загружает все метрики параллельно.
- После загрузки dashboard фильтры и локальные interactive actions не требуют повторного API-запроса.
- Пользователь может:
  - менять диапазон дат;
  - ограничивать Y-axis cycle chart;
  - скрывать отдельные точки cycle chart;
  - скрывать отдельные CFD series;
  - переключать throughput между week/month.

EN:
- The UI loads all metrics in parallel.
- After the dashboard loads, filters and local interactive actions do not require additional API requests.
- The user can:
  - change the date range;
  - limit the cycle chart Y-axis;
  - hide individual cycle chart points;
  - hide individual CFD series;
  - switch throughput between week/month.

Important nuance / Важный нюанс:

- RU: selected date range фактически привязан к completed issues из cycle chart, и остальные графики фильтруются относительно того же окна.
- EN: the selected date range is effectively anchored to completed issues from the cycle chart, and the other views are filtered against the same window.

## 11. Demo Mode / Demo-режим

RU:
- `bootstrap_demo()` создаёт demo-config с диапазоном `2026-01-01..2026-04-30`.
- `build_demo_issues()` генерирует восемь задач с разными типами, переходами и отдельными сменами assignee.
- Demo используется для валидации UI и графиков без доступа к Jira.

EN:
- `bootstrap_demo()` creates a demo config with the range `2026-01-01..2026-04-30`.
- `build_demo_issues()` generates eight issues with varying types, transitions, and some assignee changes.
- The demo is used to validate the UI and charts without Jira access.

## 12. Packaging And Distribution / Упаковка И Дистрибуция

RU:
- Development mode: браузер + локальный сервер.
- Desktop mode: `desktop.py` поднимает локальный сервер на свободном порту и показывает его в native window.
- `paths.py` переключает writable data directory в platform-specific location.
- GitHub release workflow собирает `.app` и `.dmg` по тегу.

EN:
- Development mode: browser + local server.
- Desktop mode: `desktop.py` starts the local server on a free port and displays it in a native window.
- `paths.py` switches the writable data directory into a platform-specific location.
- The GitHub release workflow builds `.app` and `.dmg` on tag push.

## 13. Security And Constraints / Безопасность И Ограничения

RU:
- Секреты предпочтительно хранятся в macOS keychain, но возможен file fallback.
- Во всём приложении TLS verification для Jira отключена, что является осознанным, но рискованным упрощением текущей версии.
- Проект рассчитан на single-user local environment.

EN:
- Secrets are preferably stored in the macOS keychain, with a file fallback available.
- TLS verification for Jira is disabled across the app, which is an intentional but risky simplification of the current version.
- The project is designed for a single-user local environment.

## 14. Test Coverage Summary / Сводка Покрытия Тестами

RU:
- Проверяются:
  - status intervals;
  - cycle time с reopen cases;
  - in-status cycle time;
  - throughput и assignee attribution;
  - phase/status ratio;
  - timezone-sensitive CFD;
  - same-day CFD transitions;
  - generic CFD status expansion;
  - project/JQL status mapping;
  - repository scoping;
  - config deletion rules.

EN:
- The tests cover:
  - status intervals;
  - cycle time with reopen cases;
  - in-status cycle time;
  - throughput and assignee attribution;
  - phase/status ratio;
  - timezone-sensitive CFD;
  - same-day CFD transitions;
  - generic CFD status expansion;
  - project/JQL status mapping;
  - repository scoping;
  - config deletion rules.

## 15. Best Next Extensions / Наиболее Полезные Следующие Улучшения

RU:
1. Включить реальную настройку `verify_ssl` вместо жёсткого `False`.
2. Добавить explicit UI для выбора reopen semantics (`first_completion`, `last_completion`, `sum_of_cycles`).
3. Расширить phase-ratio UI до lane-level stacked breakdown.
4. Добавить экспорт snapshot-отчётов в CSV/JSON.

EN:
1. Enable a real `verify_ssl` setting instead of hard-coding `False`.
2. Add explicit UI for reopen semantics (`first_completion`, `last_completion`, `sum_of_cycles`).
3. Extend the phase-ratio UI into a lane-level stacked breakdown.
4. Add CSV/JSON export for snapshot reports.
