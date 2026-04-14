from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from threading import Lock, Thread
from uuid import uuid4

from .db import ConfigRepository, IssueRepository, JobRepository
from .jira import JiraClient, JiraCredentials, JiraSyncService, board_mapping_from_configuration
from .metrics import cfd_report, compute_cfd, cycle_report, phase_ratio_report, throughput_report
from .models import AssigneeTransition, BoardColumn, BoardMapping, IssueHistory, StatusTransition, SyncConfig, SyncJob
from .runtime_store import RuntimeStore


UTC = timezone.utc


def _config_dashboard_range(config: SyncConfig) -> tuple[date, date]:
    if config.sync_start_date and config.sync_end_date:
        return date.fromisoformat(config.sync_start_date), date.fromisoformat(config.sync_end_date)
    if config.sync_start_date:
        return date.fromisoformat(config.sync_start_date), datetime.now(UTC).date()
    if config.sync_end_date:
        end_day = date.fromisoformat(config.sync_end_date)
        return end_day - timedelta(days=max(config.date_range_days or 90, 1)), end_day
    end_day = datetime.now(UTC).date()
    return end_day - timedelta(days=max(config.date_range_days or 90, 1)), end_day


class JobManager:
    def __init__(
        self,
        job_repository: JobRepository,
        issue_repository: IssueRepository,
        runtime_store: RuntimeStore,
    ) -> None:
        self.job_repository = job_repository
        self.issue_repository = issue_repository
        self.runtime_store = runtime_store
        self._lock = Lock()

    def start_sync(self, config: SyncConfig) -> SyncJob:
        job = SyncJob(
            id=str(uuid4()),
            config_id=config.id,
            status="running",
            started_at=datetime.now(UTC),
            progress=0.05,
            message="Preparing Jira synchronization",
        )
        self.job_repository.upsert(job)

        worker = Thread(target=self._run_sync, args=(job, config), daemon=True)
        worker.start()
        return job

    def _run_sync(self, job: SyncJob, config: SyncConfig) -> None:
        try:
            credentials = JiraCredentials(
                base_url=config.jira_base_url,
                auth_type="bearer_pat",
                verify_ssl=False,
                user_email=None,
                secret=self.runtime_store.get(config.secret),
            )
            client = JiraClient(credentials)
            sync_service = JiraSyncService(client)

            job.progress = 0.12
            job.message = "Connecting to Jira"
            self.job_repository.upsert(job)

            if config.scope_type == "board" and config.board_id:
                board_configuration = client.get_board_configuration(config.board_id)
                config.board_mapping = board_mapping_from_configuration(
                    board_configuration,
                    status_names=client.list_statuses(),
                )
                job.progress = 0.24
                job.message = "Board mapping loaded"
                self.job_repository.upsert(job)

            job.progress = 0.4
            job.message = "Fetching issues and changelog history from Jira"
            self.job_repository.upsert(job)
            issues = sync_service.fetch_issues(config)
            job.progress = 0.78
            job.message = f"Fetched {len(issues)} issues"
            self.job_repository.upsert(job)

            job.progress = 0.9
            job.message = "Saving synced issues locally"
            self.job_repository.upsert(job)
            self.issue_repository.replace_issues(config.id, issues)
            if config.board_mapping is not None:
                job.progress = 0.96
                job.message = "Saving updated configuration"
                self.job_repository.upsert(job)
                ConfigRepository(self.issue_repository.database).upsert_config(config)

            job.progress = 1.0
            job.status = "completed"
            job.finished_at = datetime.now(UTC)
            job.message = "Synchronization finished"
            self.job_repository.upsert(job)
        except Exception as exc:  # pragma: no cover - defensive path
            job.status = "failed"
            job.finished_at = datetime.now(UTC)
            job.message = str(exc)
            self.job_repository.upsert(job)

    def has_running_sync(self, config_id: str) -> bool:
        return self.job_repository.has_running_for_config(config_id)


class DashboardService:
    def __init__(
        self,
        config_repository: ConfigRepository,
        issue_repository: IssueRepository,
        job_manager: JobManager,
        runtime_store: RuntimeStore,
    ) -> None:
        self.config_repository = config_repository
        self.issue_repository = issue_repository
        self.job_manager = job_manager
        self.runtime_store = runtime_store

    def save_config(self, config: SyncConfig) -> SyncConfig:
        existing = self.config_repository.get_config(config.id)
        if config.secret:
            config.secret = self.runtime_store.put(config.id, config.secret)
        elif existing is not None:
            config.secret = existing.secret
        return self.config_repository.upsert_config(config)

    def list_configs(self) -> list[SyncConfig]:
        return self.config_repository.list_configs()

    def start_sync(self, config_id: str) -> SyncJob:
        config = self.config_repository.get_config(config_id)
        if config is None:
            raise ValueError(f"Config {config_id} not found")
        return self.job_manager.start_sync(config)

    def get_runtime_config(self, config_id: str) -> SyncConfig:
        config = self.config_repository.get_config(config_id)
        if config is None:
            raise ValueError(f"Config {config_id} not found")
        config.secret = self.runtime_store.get(config.secret)
        return config

    def delete_config(self, config_id: str) -> SyncConfig:
        config = self.config_repository.get_config(config_id)
        if config is None:
            raise ValueError(f"Config {config_id} not found")
        if self.job_manager.has_running_sync(config_id):
            raise RuntimeError("Cannot delete config while synchronization is running")
        deleted = self.config_repository.delete_config(config_id)
        if not deleted:
            raise ValueError(f"Config {config_id} not found")
        self.runtime_store.delete(config.secret)
        return config

    def get_metrics(self, config_id: str, timezone_name: str | None = None) -> dict[str, object]:
        config = self.config_repository.get_config(config_id)
        if config is None:
            raise ValueError(f"Config {config_id} not found")
        issues = self.issue_repository.list_issues(config_id)
        board_mapping = config.board_mapping
        if board_mapping is None:
            board_mapping = board_mapping_from_configuration(
                {
                    "columnConfig": {
                        "columns": [
                            {"name": "To Do", "statuses": [{"id": status_id} for status_id in config.start_status_ids]},
                            {"name": "In Progress", "statuses": [{"id": status_id} for status_id in config.active_status_ids]},
                            {"name": "Done", "statuses": [{"id": status_id} for status_id in config.done_status_ids]},
                        ]
                    }
                }
            )
        start_day, end_day = _config_dashboard_range(config)
        return {
            "cycleTime": cycle_report(
                issues,
                set(config.start_status_ids),
                set(config.done_status_ids),
                set(config.active_status_ids),
            ),
            "phaseRatio": phase_ratio_report(
                issues,
                board_mapping,
                set(config.start_status_ids),
                set(config.done_status_ids),
            ),
            "throughput": throughput_report(
                issues,
                set(config.done_status_ids),
                attribution_mode=config.attribution_mode,
            ),
            "cfd": cfd_report(
                compute_cfd(issues, board_mapping, start_day, end_day, timezone_name=timezone_name),
                board_mapping,
                issues,
                timezone_name=timezone_name,
                start_day=start_day,
                end_day=end_day,
            ),
        }

    def bootstrap_demo(self) -> SyncConfig:
        config = SyncConfig(
            id=str(uuid4()),
            name="Demo workspace",
            jira_base_url="https://demo.invalid",
            auth_type="bearer_pat",
            verify_ssl=False,
            user_email=None,
            secret=None,
            scope_type="builder",
            board_id=None,
            project_keys=["DEMO"],
            issue_types=["Story", "Bug", "Task"],
            base_jql="project = DEMO ORDER BY created ASC",
            extra_jql="",
            date_range_days=120,
            sync_start_date="2026-01-01",
            sync_end_date="2026-04-30",
            start_status_ids=["in-progress", "review"],
            done_status_ids=["done"],
            active_status_ids=["in-progress", "review", "qa"],
            attribution_mode="assignee_at_done",
            board_mapping=BoardMapping(
                columns=[
                    BoardColumn(id="todo", name="To Do", status_ids=["todo"]),
                    BoardColumn(id="doing", name="In Progress", status_ids=["in-progress", "review", "qa"]),
                    BoardColumn(id="done", name="Done", status_ids=["done"]),
                ]
            ),
        )
        self.save_config(config)
        self.issue_repository.replace_issues(config.id, build_demo_issues(config.id))
        return config


def build_demo_issues(seed: str = "demo") -> list[IssueHistory]:
    base = datetime(2026, 1, 6, 9, 0, tzinfo=UTC)
    templates = [
        ("DEMO-1", "Story", "owner-1", [("todo", "in-progress", 1), ("in-progress", "review", 3), ("review", "done", 5)]),
        ("DEMO-2", "Bug", "owner-2", [("todo", "in-progress", 8), ("in-progress", "qa", 11), ("qa", "done", 15)]),
        ("DEMO-3", "Task", "owner-1", [("todo", "in-progress", 20), ("in-progress", "review", 23), ("review", "done", 31)]),
        ("DEMO-4", "Story", "owner-3", [("todo", "in-progress", 36), ("in-progress", "qa", 42), ("qa", "done", 48)]),
        ("DEMO-5", "Bug", "owner-4", [("todo", "in-progress", 53), ("in-progress", "review", 61), ("review", "done", 70)]),
        ("DEMO-6", "Task", "owner-5", [("todo", "in-progress", 74), ("in-progress", "qa", 79), ("qa", "done", 88)]),
        ("DEMO-7", "Story", "owner-1", [("todo", "in-progress", 92), ("in-progress", "review", 97), ("review", "done", 104)]),
        ("DEMO-8", "Task", "owner-2", [("todo", "in-progress", 106), ("in-progress", "review", 110), ("review", "qa", 114), ("qa", "done", 121)]),
    ]
    issues: list[IssueHistory] = []
    for index, (key, issue_type, owner, transitions) in enumerate(templates, start=1):
        created_at = base + timedelta(days=index * 2)
        status_transitions = []
        assignee_transitions = []
        current_status = "todo"
        for from_status, to_status, day_offset in transitions:
            status_transitions.append(
                StatusTransition(
                    timestamp=base + timedelta(days=day_offset, hours=index),
                    from_status_id=from_status,
                    to_status_id=to_status,
                    author_account_id=owner,
                )
            )
            current_status = to_status
        if index % 3 == 0:
            assignee_transitions.append(
                AssigneeTransition(
                    timestamp=created_at + timedelta(days=3),
                    from_account_id=owner,
                    to_account_id=f"{owner}-reviewer",
                )
            )
        issues.append(
            IssueHistory(
                issue_id=f"{seed}-{10_000 + index}",
                issue_key=key,
                summary=f"Demo issue {index}",
                project_key="DEMO",
                issue_type=issue_type,
                created_at=created_at,
                initial_status_id="todo",
                current_status_id=current_status,
                initial_assignee_account_id=owner,
                transitions=status_transitions,
                assignee_transitions=assignee_transitions,
                current_assignee_account_id=assignee_transitions[-1].to_account_id if assignee_transitions else owner,
            )
        )
    return issues
