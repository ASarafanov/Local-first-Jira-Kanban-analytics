from __future__ import annotations

import json
import mimetypes
from dataclasses import asdict
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

from .db import ConfigRepository, Database, IssueRepository, JobRepository
from .jira import (
    JiraClient,
    JiraCredentials,
    JiraClientError,
    board_mapping_from_configuration,
    board_mapping_from_project_statuses,
)
from .models import BoardColumn, BoardMapping, SyncConfig
from .runtime_store import RuntimeStore
from .service import DashboardService, JobManager


BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "kanban_metrics" / "static"
DATA_DIR = BASE_DIR / ".local"
DATABASE_PATH = DATA_DIR / "kanban_metrics.db"
SCHEMA_PATH = BASE_DIR / "kanban_metrics" / "schema.sql"
RUNTIME_STORE_PATH = DATA_DIR / "runtime-store.json"


database = Database(DATABASE_PATH)
database.initialize(SCHEMA_PATH)
runtime_store = RuntimeStore("kanban-metrics", RUNTIME_STORE_PATH)
config_repository = ConfigRepository(database)
issue_repository = IssueRepository(database)
job_repository = JobRepository(database)
service = DashboardService(
    config_repository,
    issue_repository,
    JobManager(job_repository, issue_repository, runtime_store),
    runtime_store,
)


def _json_response(handler: BaseHTTPRequestHandler, status: int, payload: dict | list) -> None:
    body = json.dumps(payload).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _read_json(handler: BaseHTTPRequestHandler) -> dict:
    length = int(handler.headers.get("Content-Length", "0"))
    raw = handler.rfile.read(length).decode("utf-8") if length else "{}"
    return json.loads(raw or "{}")


class AppHandler(BaseHTTPRequestHandler):
    server_version = "KanbanMetrics/0.1"

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/api/configs":
            configs = [config.to_dict() for config in service.list_configs()]
            _json_response(self, HTTPStatus.OK, {"configs": configs})
            return

        if parsed.path == "/api/boards":
            query = parse_qs(parsed.query)
            credentials = self._credentials_from_query(query)
            try:
                boards = JiraClient(credentials).list_boards()
                _json_response(self, HTTPStatus.OK, {"boards": boards})
            except JiraClientError as exc:
                _json_response(self, HTTPStatus.BAD_GATEWAY, {"error": str(exc)})
            return

        if parsed.path.startswith("/api/boards/") and parsed.path.endswith("/configuration"):
            board_id = parsed.path.split("/")[3]
            query = parse_qs(parsed.query)
            credentials = self._credentials_from_query(query)
            try:
                client = JiraClient(credentials)
                raw = client.get_board_configuration(board_id)
                mapping = board_mapping_from_configuration(raw, status_names=client.list_statuses())
                _json_response(
                    self,
                    HTTPStatus.OK,
                    {
                        "configuration": raw,
                        "mapping": {
                            "columns": [asdict(column) for column in mapping.columns],
                            "phase_names": mapping.phase_names,
                            "status_names": mapping.status_names,
                        },
                    },
                )
            except JiraClientError as exc:
                _json_response(self, HTTPStatus.BAD_GATEWAY, {"error": str(exc)})
            return

        if parsed.path.startswith("/api/jobs/"):
            job_id = parsed.path.split("/")[3]
            job = job_repository.get(job_id)
            if job is None:
                _json_response(self, HTTPStatus.NOT_FOUND, {"error": "Job not found"})
                return
            _json_response(
                self,
                HTTPStatus.OK,
                {
                    "job": {
                        "id": job.id,
                        "configId": job.config_id,
                        "status": job.status,
                        "startedAt": job.started_at.isoformat(),
                        "finishedAt": job.finished_at.isoformat() if job.finished_at else None,
                        "progress": job.progress,
                        "message": job.message,
                    }
                },
            )
            return

        if parsed.path.startswith("/api/metrics/"):
            query = parse_qs(parsed.query)
            config_id = query.get("configId", [None])[0]
            timezone_name = query.get("timezone", [None])[0]
            if not config_id:
                _json_response(self, HTTPStatus.BAD_REQUEST, {"error": "configId is required"})
                return
            try:
                metrics = service.get_metrics(config_id, timezone_name=timezone_name)
            except ValueError as exc:
                _json_response(self, HTTPStatus.NOT_FOUND, {"error": str(exc)})
                return

            metric_name = parsed.path.rsplit("/", 1)[-1]
            metric_map = {
                "cycle-time": metrics["cycleTime"],
                "phase-ratio": metrics["phaseRatio"],
                "throughput": metrics["throughput"],
                "cfd": metrics["cfd"],
            }
            if metric_name not in metric_map:
                _json_response(self, HTTPStatus.NOT_FOUND, {"error": "Metric not found"})
                return
            _json_response(self, HTTPStatus.OK, {"data": metric_map[metric_name]})
            return

        self._serve_static(parsed.path)

    def do_POST(self) -> None:  # noqa: N802
        if self.path == "/api/jira/test-connection":
            payload = _read_json(self)
            credentials = self._credentials_from_payload(payload)
            try:
                profile = JiraClient(credentials).test_connection()
                _json_response(
                    self,
                    HTTPStatus.OK,
                    {
                        "ok": True,
                        "profile": {
                            "accountId": profile.get("accountId"),
                            "displayName": profile.get("displayName"),
                        },
                    },
                )
            except JiraClientError as exc:
                _json_response(self, HTTPStatus.BAD_GATEWAY, {"ok": False, "error": str(exc)})
            return

        if self.path == "/api/jira/validate-jql":
            payload = _read_json(self)
            credentials = self._credentials_from_payload(payload)
            client = JiraClient(credentials)
            jql = payload.get("jql", "")
            try:
                parsed = client.validate_jql(jql)
                cleaned = client.pdcleaner(jql)
                cleaned_queries = cleaned.get("queryStrings") or cleaned.get("queries") or []
                _json_response(
                    self,
                    HTTPStatus.OK,
                    {
                        "ok": True,
                        "parsed": parsed,
                        "cleanedJql": cleaned_queries[0] if cleaned_queries else jql,
                    },
                )
            except JiraClientError as exc:
                _json_response(self, HTTPStatus.BAD_GATEWAY, {"ok": False, "error": str(exc)})
            return

        if self.path == "/api/jira/project-statuses":
            payload = _read_json(self)
            credentials = self._credentials_from_payload(payload)
            project_key = (payload.get("projectKey") or "").strip()
            issue_types = [str(item).strip() for item in (payload.get("issueTypes") or []) if str(item).strip()]
            if not project_key:
                _json_response(self, HTTPStatus.BAD_REQUEST, {"error": "projectKey is required"})
                return
            try:
                project_statuses = JiraClient(credentials).get_project_statuses(project_key)
                derived = board_mapping_from_project_statuses(project_statuses, issue_types)
                mapping = derived["mapping"]
                _json_response(
                    self,
                    HTTPStatus.OK,
                    {
                        "projectKey": project_key,
                        "issueTypes": issue_types,
                        "statuses": derived["statuses"],
                        "startStatusIds": derived["startStatusIds"],
                        "activeStatusIds": derived["activeStatusIds"],
                        "doneStatusIds": derived["doneStatusIds"],
                        "mapping": {
                            "columns": [asdict(column) for column in mapping.columns],
                            "phase_names": mapping.phase_names,
                            "status_names": mapping.status_names,
                        },
                    },
                )
            except JiraClientError as exc:
                _json_response(self, HTTPStatus.BAD_GATEWAY, {"error": str(exc)})
            return

        if self.path == "/api/jira/projects":
            payload = _read_json(self)
            credentials = self._credentials_from_payload(payload)
            try:
                projects = JiraClient(credentials).list_projects()
                _json_response(self, HTTPStatus.OK, {"projects": projects})
            except JiraClientError as exc:
                _json_response(self, HTTPStatus.BAD_GATEWAY, {"error": str(exc)})
            return

        if self.path == "/api/configs":
            payload = _read_json(self)
            config = payload_to_config(payload)
            service.save_config(config)
            _json_response(self, HTTPStatus.CREATED, {"config": config.to_dict()})
            return

        if self.path == "/api/demo/bootstrap":
            config = service.bootstrap_demo()
            _json_response(self, HTTPStatus.CREATED, {"config": config.to_dict()})
            return

        if self.path.endswith("/sync") and self.path.startswith("/api/configs/"):
            config_id = self.path.split("/")[3]
            try:
                job = service.start_sync(config_id)
            except ValueError as exc:
                _json_response(self, HTTPStatus.NOT_FOUND, {"error": str(exc)})
                return
            _json_response(
                self,
                HTTPStatus.ACCEPTED,
                {
                    "job": {
                        "id": job.id,
                        "configId": job.config_id,
                        "status": job.status,
                        "progress": job.progress,
                        "message": job.message,
                    }
                },
            )
            return

        _json_response(self, HTTPStatus.NOT_FOUND, {"error": "Not found"})

    def do_PUT(self) -> None:  # noqa: N802
        if self.path.startswith("/api/configs/"):
            config_id = self.path.split("/")[3]
            payload = _read_json(self)
            payload["id"] = config_id
            config = payload_to_config(payload)
            service.save_config(config)
            _json_response(self, HTTPStatus.OK, {"config": config.to_dict()})
            return
        _json_response(self, HTTPStatus.NOT_FOUND, {"error": "Not found"})

    def do_DELETE(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/configs/"):
            config_id = parsed.path.split("/")[3]
            try:
                config = service.delete_config(config_id)
            except ValueError as exc:
                _json_response(self, HTTPStatus.NOT_FOUND, {"error": str(exc)})
                return
            except RuntimeError as exc:
                _json_response(self, HTTPStatus.CONFLICT, {"error": str(exc)})
                return
            _json_response(self, HTTPStatus.OK, {"deleted": True, "config": config.to_dict()})
            return
        _json_response(self, HTTPStatus.NOT_FOUND, {"error": "Not found"})

    def log_message(self, format: str, *args: object) -> None:
        return

    def _serve_static(self, path: str) -> None:
        target = "index.html" if path in {"/", ""} else path.lstrip("/")
        file_path = (STATIC_DIR / target).resolve()
        if not str(file_path).startswith(str(STATIC_DIR.resolve())) or not file_path.exists():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        content = file_path.read_bytes()
        content_type, _ = mimetypes.guess_type(file_path.name)
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type or "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def _credentials_from_query(self, query: dict[str, list[str]]) -> JiraCredentials:
        config_id = query.get("configId", [None])[0]
        runtime_config = service.get_runtime_config(config_id) if config_id else None
        return JiraCredentials(
            base_url=query.get("baseUrl", [runtime_config.jira_base_url if runtime_config else ""])[0],
            auth_type="bearer_pat",
            verify_ssl=False,
            user_email=None,
            secret=query.get("secret", [runtime_config.secret if runtime_config else None])[0],
        )

    def _credentials_from_payload(self, payload: dict) -> JiraCredentials:
        config_id = payload.get("configId")
        runtime_config = service.get_runtime_config(config_id) if config_id else None
        return JiraCredentials(
            base_url=payload.get("baseUrl", runtime_config.jira_base_url if runtime_config else ""),
            auth_type="bearer_pat",
            verify_ssl=False,
            user_email=None,
            secret=payload.get("secret") or (runtime_config.secret if runtime_config else None),
        )


def payload_to_config(payload: dict) -> SyncConfig:
    mapping = None
    raw_mapping = payload.get("board_mapping")
    if raw_mapping and raw_mapping.get("columns"):
        mapping = BoardMapping(
            columns=[BoardColumn(**column) for column in raw_mapping["columns"]],
            phase_names=raw_mapping.get("phase_names", {}),
            status_names=raw_mapping.get("status_names", {}),
        )
    return SyncConfig(
        id=payload.get("id") or str(uuid4()),
        name=payload.get("name") or "Kanban metrics config",
        jira_base_url=payload.get("jira_base_url", "").strip(),
        auth_type="bearer_pat",
        verify_ssl=False,
        user_email=None,
        secret=payload.get("secret"),
        scope_type=payload.get("scope_type", "builder"),
        board_id=payload.get("board_id"),
        project_keys=payload.get("project_keys", []),
        issue_types=payload.get("issue_types", []),
        base_jql=payload.get("base_jql", ""),
        extra_jql=payload.get("extra_jql", ""),
        date_range_days=payload.get("date_range_days"),
        sync_start_date=payload.get("sync_start_date"),
        sync_end_date=payload.get("sync_end_date"),
        start_status_ids=payload.get("start_status_ids", []),
        done_status_ids=payload.get("done_status_ids", []),
        active_status_ids=payload.get("active_status_ids", []),
        attribution_mode=payload.get("attribution_mode", "assignee_at_done"),
        board_mapping=mapping,
    )


def run(host: str = "127.0.0.1", port: int = 8765) -> None:
    server = ThreadingHTTPServer((host, port), AppHandler)
    print(f"Kanban Metrics running on http://{host}:{port}")
    server.serve_forever()
