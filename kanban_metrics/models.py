from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import date, datetime, timezone
from typing import Any


UTC = timezone.utc


def ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


@dataclass(slots=True)
class StatusTransition:
    timestamp: datetime
    from_status_id: str | None
    to_status_id: str
    author_account_id: str | None = None

    def __post_init__(self) -> None:
        self.timestamp = ensure_utc(self.timestamp)


@dataclass(slots=True)
class AssigneeTransition:
    timestamp: datetime
    from_account_id: str | None
    to_account_id: str | None

    def __post_init__(self) -> None:
        self.timestamp = ensure_utc(self.timestamp)


@dataclass(slots=True)
class StatusInterval:
    start: datetime
    end: datetime
    status_id: str

    def __post_init__(self) -> None:
        self.start = ensure_utc(self.start)
        self.end = ensure_utc(self.end)

    @property
    def duration_seconds(self) -> float:
        return max((self.end - self.start).total_seconds(), 0.0)

    def overlaps(self, start: datetime, end: datetime) -> bool:
        return self.start < end and self.end > start


@dataclass(slots=True)
class BoardColumn:
    id: str
    name: str
    status_ids: list[str]


@dataclass(slots=True)
class BoardMapping:
    columns: list[BoardColumn]
    phase_names: dict[str, str] = field(default_factory=dict)
    status_names: dict[str, str] = field(default_factory=dict)

    def status_to_column(self) -> dict[str, BoardColumn]:
        mapping: dict[str, BoardColumn] = {}
        for column in self.columns:
            for status_id in column.status_ids:
                mapping[status_id] = column
        return mapping

    def ordered_phase_names(self) -> list[str]:
        names: list[str] = []
        for column in self.columns:
            names.append(self.phase_names.get(column.id, column.name))
        return names

    def phase_name_for_column(self, column: BoardColumn) -> str:
        return self.phase_names.get(column.id, column.name)

    def status_name(self, status_id: str | None) -> str:
        if not status_id:
            return "Unknown"
        return self.status_names.get(status_id, status_id)

    def label_for_status(self, status_id: str | None) -> str:
        if not status_id:
            return "Unknown"
        column = self.status_to_column().get(status_id)
        if column is not None:
            return self.phase_name_for_column(column)
        return self.status_name(status_id)


@dataclass(slots=True)
class IssueHistory:
    issue_id: str
    issue_key: str
    summary: str
    project_key: str
    issue_type: str
    created_at: datetime
    initial_status_id: str
    current_status_id: str
    initial_assignee_account_id: str | None = None
    transitions: list[StatusTransition] = field(default_factory=list)
    assignee_transitions: list[AssigneeTransition] = field(default_factory=list)
    current_assignee_account_id: str | None = None

    def __post_init__(self) -> None:
        self.created_at = ensure_utc(self.created_at)
        self.transitions = sorted(self.transitions, key=lambda item: item.timestamp)
        self.assignee_transitions = sorted(
            self.assignee_transitions,
            key=lambda item: item.timestamp,
        )


@dataclass(slots=True)
class SyncConfig:
    id: str
    name: str
    jira_base_url: str
    auth_type: str
    verify_ssl: bool
    user_email: str | None
    secret: str | None
    scope_type: str
    board_id: str | None
    project_keys: list[str]
    issue_types: list[str]
    base_jql: str
    extra_jql: str
    date_range_days: int | None
    sync_start_date: str | None
    sync_end_date: str | None
    start_status_ids: list[str]
    done_status_ids: list[str]
    active_status_ids: list[str]
    attribution_mode: str
    board_mapping: BoardMapping | None = None

    def to_dict(self, include_secret: bool = False) -> dict[str, Any]:
        payload = asdict(self)
        payload["has_secret"] = bool(self.secret)
        if not include_secret:
            payload["secret"] = None
        if self.board_mapping is not None:
            payload["board_mapping"] = {
                "columns": [asdict(column) for column in self.board_mapping.columns],
                "phase_names": dict(self.board_mapping.phase_names),
                "status_names": dict(self.board_mapping.status_names),
            }
        return payload


@dataclass(slots=True)
class SyncJob:
    id: str
    config_id: str
    status: str
    started_at: datetime
    finished_at: datetime | None = None
    progress: float = 0.0
    message: str = "Queued"

    def __post_init__(self) -> None:
        self.started_at = ensure_utc(self.started_at)
        if self.finished_at is not None:
            self.finished_at = ensure_utc(self.finished_at)


@dataclass(slots=True)
class DailyCfdPoint:
    day: date
    current: dict[str, int]
    cumulative: dict[str, int]
