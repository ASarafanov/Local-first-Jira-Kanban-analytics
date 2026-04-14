from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator
from uuid import uuid4

from .models import (
    AssigneeTransition,
    BoardColumn,
    BoardMapping,
    IssueHistory,
    StatusTransition,
    SyncConfig,
    SyncJob,
)


UTC = timezone.utc


class Database:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def initialize(self, schema_path: Path) -> None:
        with self.connect() as connection:
            connection.executescript(schema_path.read_text(encoding="utf-8"))
            self._apply_migrations(connection)

    def _apply_migrations(self, connection: sqlite3.Connection) -> None:
        instance_columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(jira_instance)").fetchall()
        }
        if "verify_ssl" not in instance_columns:
            connection.execute("ALTER TABLE jira_instance ADD COLUMN verify_ssl INTEGER NOT NULL DEFAULT 1")
        issue_columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(issue)").fetchall()
        }
        if "initial_assignee_account_id" not in issue_columns:
            connection.execute("ALTER TABLE issue ADD COLUMN initial_assignee_account_id TEXT")
        if "summary" not in issue_columns:
            connection.execute("ALTER TABLE issue ADD COLUMN summary TEXT NOT NULL DEFAULT ''")
        config_columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(config)").fetchall()
        }
        if "project_keys_json" not in config_columns:
            connection.execute("ALTER TABLE config ADD COLUMN project_keys_json TEXT NOT NULL DEFAULT '[]'")
        if "issue_types_json" not in config_columns:
            connection.execute("ALTER TABLE config ADD COLUMN issue_types_json TEXT NOT NULL DEFAULT '[]'")
        if "sync_start_date" not in config_columns:
            connection.execute("ALTER TABLE config ADD COLUMN sync_start_date TEXT")
        if "sync_end_date" not in config_columns:
            connection.execute("ALTER TABLE config ADD COLUMN sync_end_date TEXT")


class ConfigRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def upsert_config(self, config: SyncConfig) -> SyncConfig:
        instance_id = f"instance-{config.id}"
        now = datetime.now(UTC).isoformat()
        board_mapping_json = None
        if config.board_mapping is not None:
            board_mapping_json = json.dumps(
                {
                    "columns": [asdict(column) for column in config.board_mapping.columns],
                    "phase_names": config.board_mapping.phase_names,
                    "status_names": config.board_mapping.status_names,
                }
            )
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO jira_instance
                (id, name, base_url, auth_type, verify_ssl, user_email, secret, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    instance_id,
                    config.name,
                    config.jira_base_url,
                    config.auth_type,
                    1 if config.verify_ssl else 0,
                    config.user_email,
                    config.secret,
                    now,
                ),
            )
            connection.execute(
                """
                INSERT OR REPLACE INTO config
                (
                    id, jira_instance_id, name, scope_type, board_id,
                    project_keys_json, issue_types_json, base_jql, extra_jql, date_range_days,
                    sync_start_date, sync_end_date,
                    start_status_ids_json, done_status_ids_json, active_status_ids_json,
                    attribution_mode, board_mapping_json, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    config.id,
                    instance_id,
                    config.name,
                    config.scope_type,
                    config.board_id,
                    json.dumps(config.project_keys),
                    json.dumps(config.issue_types),
                    config.base_jql,
                    config.extra_jql,
                    config.date_range_days,
                    config.sync_start_date,
                    config.sync_end_date,
                    json.dumps(config.start_status_ids),
                    json.dumps(config.done_status_ids),
                    json.dumps(config.active_status_ids),
                    config.attribution_mode,
                    board_mapping_json,
                    now,
                    now,
                ),
            )
        return config

    def list_configs(self) -> list[SyncConfig]:
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT c.*, i.base_url, i.auth_type, i.verify_ssl, i.user_email, i.secret
                FROM config c
                JOIN jira_instance i ON i.id = c.jira_instance_id
                ORDER BY c.updated_at DESC
                """
            ).fetchall()
        return [self._row_to_config(row) for row in rows]

    def get_config(self, config_id: str) -> SyncConfig | None:
        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT c.*, i.base_url, i.auth_type, i.verify_ssl, i.user_email, i.secret
                FROM config c
                JOIN jira_instance i ON i.id = c.jira_instance_id
                WHERE c.id = ?
                """,
                (config_id,),
            ).fetchone()
        if row is None:
            return None
        return self._row_to_config(row)

    def delete_config(self, config_id: str) -> bool:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT jira_instance_id FROM config WHERE id = ?",
                (config_id,),
            ).fetchone()
            if row is None:
                return False
            connection.execute("DELETE FROM changelog_event WHERE config_id = ?", (config_id,))
            connection.execute("DELETE FROM issue WHERE config_id = ?", (config_id,))
            connection.execute("DELETE FROM sync_job WHERE config_id = ?", (config_id,))
            connection.execute("DELETE FROM config WHERE id = ?", (config_id,))
            connection.execute("DELETE FROM jira_instance WHERE id = ?", (row["jira_instance_id"],))
        return True

    def _row_to_config(self, row: sqlite3.Row) -> SyncConfig:
        mapping = None
        if row["board_mapping_json"]:
            raw_mapping = json.loads(row["board_mapping_json"])
            mapping = BoardMapping(
                columns=[BoardColumn(**column) for column in raw_mapping["columns"]],
                phase_names=raw_mapping.get("phase_names", {}),
                status_names=raw_mapping.get("status_names", {}),
            )
        return SyncConfig(
            id=row["id"],
            name=row["name"],
            jira_base_url=row["base_url"],
            auth_type=row["auth_type"],
            verify_ssl=bool(row["verify_ssl"]),
            user_email=row["user_email"],
            secret=row["secret"],
            scope_type=row["scope_type"],
            board_id=row["board_id"],
            project_keys=json.loads(row["project_keys_json"] or "[]"),
            issue_types=json.loads(row["issue_types_json"] or "[]"),
            base_jql=row["base_jql"],
            extra_jql=row["extra_jql"],
            date_range_days=row["date_range_days"],
            sync_start_date=row["sync_start_date"],
            sync_end_date=row["sync_end_date"],
            start_status_ids=json.loads(row["start_status_ids_json"]),
            done_status_ids=json.loads(row["done_status_ids_json"]),
            active_status_ids=json.loads(row["active_status_ids_json"]),
            attribution_mode=row["attribution_mode"],
            board_mapping=mapping,
        )


class IssueRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    @staticmethod
    def _scoped_issue_id(config_id: str, issue_id: str) -> str:
        return f"{config_id}:{issue_id}"

    @staticmethod
    def _jira_issue_id(stored_issue_id: str) -> str:
        if ":" not in stored_issue_id:
            return stored_issue_id
        return stored_issue_id.split(":", 1)[1]

    def replace_issues(self, config_id: str, issues: list[IssueHistory]) -> None:
        with self.database.connect() as connection:
            connection.execute("DELETE FROM changelog_event WHERE config_id = ?", (config_id,))
            connection.execute("DELETE FROM issue WHERE config_id = ?", (config_id,))

            for issue in issues:
                stored_issue_id = self._scoped_issue_id(config_id, issue.issue_id)
                connection.execute(
                    """
                    INSERT INTO issue
                    (
                        issue_id, config_id, issue_key, summary, project_key, issue_type,
                        created_at, updated_at, initial_status_id, current_status_id,
                        initial_assignee_account_id, current_assignee_account_id, raw_json
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        stored_issue_id,
                        config_id,
                        issue.issue_key,
                        issue.summary,
                        issue.project_key,
                        issue.issue_type,
                        issue.created_at.isoformat(),
                        datetime.now(UTC).isoformat(),
                        issue.initial_status_id,
                        issue.current_status_id,
                        issue.initial_assignee_account_id,
                        issue.current_assignee_account_id,
                        None,
                    ),
                )
                for transition in issue.transitions:
                    connection.execute(
                        """
                        INSERT INTO changelog_event
                        (id, config_id, issue_id, event_type, at, from_id, to_id, author_account_id, raw_json)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            str(uuid4()),
                            config_id,
                            stored_issue_id,
                            "status",
                            transition.timestamp.isoformat(),
                            transition.from_status_id,
                            transition.to_status_id,
                            transition.author_account_id,
                            None,
                        ),
                    )
                for transition in issue.assignee_transitions:
                    connection.execute(
                        """
                        INSERT INTO changelog_event
                        (id, config_id, issue_id, event_type, at, from_id, to_id, author_account_id, raw_json)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            str(uuid4()),
                            config_id,
                            stored_issue_id,
                            "assignee",
                            transition.timestamp.isoformat(),
                            transition.from_account_id,
                            transition.to_account_id,
                            None,
                            None,
                        ),
                    )

    def list_issues(self, config_id: str) -> list[IssueHistory]:
        with self.database.connect() as connection:
            issue_rows = connection.execute(
                """
                SELECT *
                FROM issue
                WHERE config_id = ?
                ORDER BY created_at ASC
                """,
                (config_id,),
            ).fetchall()
            event_rows = connection.execute(
                """
                SELECT *
                FROM changelog_event
                WHERE config_id = ?
                ORDER BY at ASC
                """,
                (config_id,),
            ).fetchall()

        events_by_issue: dict[str, list[StatusTransition]] = {}
        assignee_events_by_issue: dict[str, list[AssigneeTransition]] = {}
        for row in event_rows:
            if row["event_type"] == "status":
                events_by_issue.setdefault(row["issue_id"], []).append(
                    StatusTransition(
                        timestamp=datetime.fromisoformat(row["at"]),
                        from_status_id=row["from_id"],
                        to_status_id=row["to_id"],
                        author_account_id=row["author_account_id"],
                    )
                )
            elif row["event_type"] == "assignee":
                assignee_events_by_issue.setdefault(row["issue_id"], []).append(
                    AssigneeTransition(
                        timestamp=datetime.fromisoformat(row["at"]),
                        from_account_id=row["from_id"],
                        to_account_id=row["to_id"],
                    )
                )

        issues: list[IssueHistory] = []
        for row in issue_rows:
            stored_issue_id = row["issue_id"]
            issues.append(
                IssueHistory(
                    issue_id=self._jira_issue_id(stored_issue_id),
                    issue_key=row["issue_key"],
                    summary=row["summary"],
                    project_key=row["project_key"],
                    issue_type=row["issue_type"],
                    created_at=datetime.fromisoformat(row["created_at"]),
                    initial_status_id=row["initial_status_id"],
                    current_status_id=row["current_status_id"],
                    initial_assignee_account_id=row["initial_assignee_account_id"],
                    transitions=events_by_issue.get(stored_issue_id, []),
                    assignee_transitions=assignee_events_by_issue.get(stored_issue_id, []),
                    current_assignee_account_id=row["current_assignee_account_id"],
                )
            )
        return issues


class JobRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def upsert(self, job: SyncJob) -> None:
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO sync_job
                (id, config_id, status, started_at, finished_at, progress, message)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job.id,
                    job.config_id,
                    job.status,
                    job.started_at.isoformat(),
                    job.finished_at.isoformat() if job.finished_at else None,
                    job.progress,
                    job.message,
                ),
            )

    def get(self, job_id: str) -> SyncJob | None:
        with self.database.connect() as connection:
            row = connection.execute("SELECT * FROM sync_job WHERE id = ?", (job_id,)).fetchone()
        if row is None:
            return None
        return SyncJob(
            id=row["id"],
            config_id=row["config_id"],
            status=row["status"],
            started_at=datetime.fromisoformat(row["started_at"]),
            finished_at=datetime.fromisoformat(row["finished_at"]) if row["finished_at"] else None,
            progress=row["progress"],
            message=row["message"],
        )

    def has_running_for_config(self, config_id: str) -> bool:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT 1 FROM sync_job WHERE config_id = ? AND status = 'running' LIMIT 1",
                (config_id,),
            ).fetchone()
        return row is not None
