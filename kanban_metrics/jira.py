from __future__ import annotations

import concurrent.futures
import json
import random
import re
import ssl
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any
from urllib import error, parse, request

from .models import AssigneeTransition, BoardColumn, BoardMapping, IssueHistory, StatusTransition, SyncConfig


UTC = timezone.utc


class JiraClientError(RuntimeError):
    pass


@dataclass(slots=True)
class JiraCredentials:
    base_url: str
    auth_type: str
    verify_ssl: bool = False
    user_email: str | None = None
    secret: str | None = None


class JiraClient:
    def __init__(self, credentials: JiraCredentials, max_attempts: int = 5, timeout: float = 30.0) -> None:
        self.credentials = credentials
        self.max_attempts = max_attempts
        self.timeout = timeout

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        if self.credentials.secret:
            headers["Authorization"] = f"Bearer {self.credentials.secret}"
        return headers

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
        url = self.credentials.base_url.rstrip("/") + path
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        headers = self._headers()

        context = ssl._create_unverified_context()

        for attempt in range(1, self.max_attempts + 1):
            try:
                req = request.Request(url=url, method=method, data=data, headers=headers)
                with request.urlopen(req, timeout=self.timeout, context=context) as response:
                    body = response.read()
                    if not body:
                        return {}
                    try:
                        return json.loads(body.decode("utf-8"))
                    except json.JSONDecodeError as exc:
                        snippet = body.decode("utf-8", errors="ignore")[:200]
                        raise JiraClientError(f"Jira returned non-JSON payload: {snippet}") from exc
            except error.HTTPError as exc:
                if exc.code == 429 and attempt < self.max_attempts:
                    retry_after = exc.headers.get("Retry-After")
                    wait_seconds = float(retry_after) if retry_after else min(2**attempt, 30) + random.random()
                    time.sleep(wait_seconds)
                    continue
                body = exc.read().decode("utf-8", errors="ignore")
                raise JiraClientError(f"Jira request failed: {exc.code} {body}") from exc
            except error.URLError as exc:
                if attempt < self.max_attempts:
                    time.sleep(min(2**attempt, 30) + random.random())
                    continue
                raise JiraClientError(f"Jira request failed: {exc.reason}") from exc
        raise JiraClientError("Jira request failed after retries")

    def test_connection(self) -> dict[str, Any]:
        try:
            return self._request("GET", "/rest/api/3/myself")
        except JiraClientError:
            return self._request("GET", "/rest/api/2/myself")

    def validate_jql(self, jql: str) -> dict[str, Any]:
        try:
            return self._request("POST", "/rest/api/3/jql/parse", {"queries": [jql]})
        except JiraClientError:
            return self._request("POST", "/rest/api/2/search", {"jql": jql, "maxResults": 0, "validateQuery": True})

    def pdcleaner(self, jql: str) -> dict[str, Any]:
        try:
            return self._request("POST", "/rest/api/3/jql/pdcleaner", {"queryStrings": [jql]})
        except JiraClientError:
            return {"queryStrings": [jql]}

    def list_boards(self) -> list[dict[str, Any]]:
        data = self._request("GET", "/rest/agile/1.0/board?maxResults=50")
        return data.get("values", [])

    def get_board_configuration(self, board_id: str) -> dict[str, Any]:
        return self._request("GET", f"/rest/agile/1.0/board/{board_id}/configuration")

    def list_statuses(self) -> dict[str, str]:
        try:
            payload = self._request("GET", "/rest/api/3/status")
        except JiraClientError:
            payload = self._request("GET", "/rest/api/2/status")
        return {
            str(status["id"]): status.get("name", str(status["id"]))
            for status in payload
            if status.get("id") is not None
        }

    def get_filter(self, filter_id: str) -> dict[str, Any]:
        try:
            return self._request("GET", f"/rest/api/3/filter/{filter_id}")
        except JiraClientError:
            return self._request("GET", f"/rest/api/2/filter/{filter_id}")

    def get_project_statuses(self, project_key: str) -> list[dict[str, Any]]:
        encoded_key = parse.quote(project_key)
        try:
            return self._request("GET", f"/rest/api/3/project/{encoded_key}/statuses")
        except JiraClientError:
            return self._request("GET", f"/rest/api/2/project/{encoded_key}/statuses")

    def list_projects(self) -> list[dict[str, Any]]:
        try:
            payload = self._request("GET", "/rest/api/3/project/search?maxResults=1000")
            values = payload.get("values", payload if isinstance(payload, list) else [])
        except JiraClientError:
            values = self._request("GET", "/rest/api/2/project")
        return normalize_projects(values)

    def enhanced_search(self, jql: str, fields: list[str] | None = None, max_results: int = 100) -> list[dict[str, Any]]:
        try:
            all_issues: list[dict[str, Any]] = []
            next_page_token: str | None = None
            while True:
                payload: dict[str, Any] = {"jql": jql, "maxResults": max_results}
                if fields:
                    payload["fields"] = fields
                if next_page_token:
                    payload["nextPageToken"] = next_page_token
                data = self._request("POST", "/rest/api/3/search/jql", payload)
                all_issues.extend(data.get("issues", []))
                next_page_token = data.get("nextPageToken")
                if not next_page_token:
                    break
            return all_issues
        except JiraClientError:
            all_issues = []
            start_at = 0
            while True:
                query = f"/rest/api/2/search?jql={parse.quote(jql)}&startAt={start_at}&maxResults={max_results}"
                if fields:
                    query += "&fields=" + parse.quote(",".join(fields))
                data = self._request("GET", query)
                issues = data.get("issues", [])
                all_issues.extend(issues)
                start_at += len(issues)
                if start_at >= data.get("total", 0) or not issues:
                    break
            return all_issues

    def bulk_fetch_changelogs(self, issue_ids: list[str]) -> dict[str, Any]:
        try:
            return self._request(
                "POST",
                "/rest/api/3/changelog/bulkfetch",
                {"issueIdsOrKeys": issue_ids, "fieldIds": ["status", "assignee"]},
            )
        except JiraClientError:
            return {}

    def issue_changelog(self, issue_id_or_key: str) -> list[dict[str, Any]]:
        start_at = 0
        items: list[dict[str, Any]] = []
        while True:
            try:
                data = self._request(
                    "GET",
                    f"/rest/api/3/issue/{parse.quote(issue_id_or_key)}/changelog?startAt={start_at}&maxResults=100",
                )
            except JiraClientError:
                issue = self._request(
                    "GET",
                    f"/rest/api/2/issue/{parse.quote(issue_id_or_key)}?expand=changelog&fields=key",
                )
                changelog = issue.get("changelog", {})
                return changelog.get("histories", [])
            values = data.get("values", [])
            items.extend(values)
            start_at += len(values)
            if start_at >= data.get("total", 0):
                break
        return items

    def get_user(self, identifier: str) -> dict[str, Any]:
        normalized = str(identifier or "").strip()
        if not normalized:
            raise JiraClientError("User identifier is required")

        encoded = parse.quote(normalized)
        attempts = [
            f"/rest/api/3/user?accountId={encoded}",
            f"/rest/api/2/user?accountId={encoded}",
            f"/rest/api/2/user?username={encoded}",
            f"/rest/api/2/user?key={encoded}",
            f"/rest/api/latest/user?username={encoded}",
        ]
        last_error: JiraClientError | None = None
        for path in attempts:
            try:
                payload = self._request("GET", path)
            except JiraClientError as exc:
                last_error = exc
                continue
            if isinstance(payload, dict) and payload:
                return payload
        if last_error is not None:
            raise last_error
        raise JiraClientError(f"Jira user lookup returned no data for {normalized}")


def board_mapping_from_configuration(payload: dict[str, Any], status_names: dict[str, str] | None = None) -> BoardMapping:
    columns = []
    resolved_status_names = dict(status_names or {})
    for raw_column in payload.get("columnConfig", {}).get("columns", []):
        for status in raw_column.get("statuses", []):
            status_id = str(status.get("id", ""))
            if status_id:
                resolved_status_names.setdefault(status_id, status.get("name") or status_id)
        columns.append(
            BoardColumn(
                id=raw_column["name"].lower().replace(" ", "-"),
                name=raw_column["name"],
                status_ids=[status["id"] for status in raw_column.get("statuses", [])],
            )
        )
    return BoardMapping(columns=columns, status_names=resolved_status_names)


def board_mapping_from_project_statuses(
    payload: list[dict[str, Any]],
    issue_types: list[str] | None = None,
) -> dict[str, Any]:
    selected_types = {item.casefold() for item in (issue_types or []) if item}
    status_names: dict[str, str] = {}
    columns = {
        "todo": {"id": "todo", "name": "To Do", "status_ids": []},
        "doing": {"id": "doing", "name": "In Progress", "status_ids": []},
        "done": {"id": "done", "name": "Done", "status_ids": []},
    }
    seen_status_ids: set[str] = set()
    workflow_by_issue_type: list[dict[str, Any]] = []
    all_statuses: list[dict[str, str]] = []

    for issue_type in payload:
        issue_type_name = issue_type.get("name") or issue_type.get("issueType", {}).get("name") or "Unknown"
        if selected_types and issue_type_name.casefold() not in selected_types:
            continue

        normalized_statuses: list[dict[str, str]] = []
        for status in issue_type.get("statuses", []):
            status_id = str(status.get("id", "")).strip()
            if not status_id:
                continue
            status_name = status.get("name") or status_id
            category = status.get("statusCategory") or {}
            category_key = (category.get("key") or "indeterminate").lower()
            category_name = category.get("name") or category_key.title()
            status_names[status_id] = status_name
            normalized_statuses.append(
                {
                    "id": status_id,
                    "name": status_name,
                    "categoryKey": category_key,
                    "categoryName": category_name,
                }
            )
            if status_id in seen_status_ids:
                continue
            seen_status_ids.add(status_id)
            all_statuses.append(
                {
                    "id": status_id,
                    "name": status_name,
                    "categoryKey": category_key,
                    "categoryName": category_name,
                }
            )
            if category_key == "done":
                columns["done"]["status_ids"].append(status_id)
            elif category_key == "new":
                columns["todo"]["status_ids"].append(status_id)
            else:
                columns["doing"]["status_ids"].append(status_id)

        workflow_by_issue_type.append({"issueType": issue_type_name, "statuses": normalized_statuses})

    mapping = BoardMapping(
        columns=[BoardColumn(**columns["todo"]), BoardColumn(**columns["doing"]), BoardColumn(**columns["done"])],
        status_names=status_names,
    )
    return {
        "mapping": mapping,
        "statuses": all_statuses,
        "issueTypeStatuses": workflow_by_issue_type,
        "startStatusIds": list(columns["doing"]["status_ids"]),
        "activeStatusIds": list(columns["doing"]["status_ids"]),
        "doneStatusIds": list(columns["done"]["status_ids"]),
    }


def board_mapping_from_jql_issues(payload: list[dict[str, Any]]) -> dict[str, Any]:
    columns = {
        "inactive": {"id": "inactive", "name": "Inactive statuses", "status_ids": []},
        "active": {"id": "active", "name": "Active statuses", "status_ids": []},
        "done": {"id": "done", "name": "Done statuses", "status_ids": []},
    }
    status_names: dict[str, str] = {}
    statuses: list[dict[str, str]] = []
    seen_status_ids: set[str] = set()

    for issue in payload:
        status = (issue.get("fields") or {}).get("status") or {}
        status_id = str(status.get("id", "")).strip()
        if not status_id or status_id in seen_status_ids:
            continue
        seen_status_ids.add(status_id)

        status_name = status.get("name") or status_id
        category = status.get("statusCategory") or {}
        category_key = (category.get("key") or "indeterminate").lower()
        category_name = category.get("name") or category_key.title()

        status_names[status_id] = status_name
        statuses.append(
            {
                "id": status_id,
                "name": status_name,
                "categoryKey": category_key,
                "categoryName": category_name,
            }
        )

        if category_key == "done":
            columns["done"]["status_ids"].append(status_id)
        elif category_key == "new":
            columns["inactive"]["status_ids"].append(status_id)
        else:
            columns["active"]["status_ids"].append(status_id)

    mapping = BoardMapping(
        columns=[
            BoardColumn(**columns["inactive"]),
            BoardColumn(**columns["active"]),
            BoardColumn(**columns["done"]),
        ],
        status_names=status_names,
    )
    return {
        "mapping": mapping,
        "statuses": statuses,
        "startStatusIds": list(columns["active"]["status_ids"]),
        "activeStatusIds": list(columns["active"]["status_ids"]),
        "doneStatusIds": list(columns["done"]["status_ids"]),
    }


def normalize_projects(payload: list[dict[str, Any]]) -> list[dict[str, Any]]:
    projects = []
    for item in payload:
        key = str(item.get("key", "")).strip()
        if not key:
            continue
        projects.append(
            {
                "id": str(item.get("id", "")),
                "key": key,
                "name": item.get("name") or key,
                "projectTypeKey": item.get("projectTypeKey"),
                "archived": bool(item.get("archived", False)),
            }
        )
    projects.sort(key=lambda item: (item["archived"], item["name"].casefold(), item["key"].casefold()))
    return projects


def _normalized_user_value(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _preferred_user_label(user_payload: dict[str, Any] | None) -> str | None:
    if not isinstance(user_payload, dict):
        return None
    for field_name in ("name", "emailAddress", "displayName", "accountId", "key"):
        value = _normalized_user_value(user_payload.get(field_name))
        if value:
            return value
    return None


def _user_identifier_from_payload(user_payload: dict[str, Any] | None) -> str | None:
    if not isinstance(user_payload, dict):
        return None
    for field_name in ("accountId", "name", "key", "emailAddress", "displayName"):
        value = _normalized_user_value(user_payload.get(field_name))
        if value:
            return value
    return None


def _history_user_value(identifier: Any, display_value: Any) -> str | None:
    display = _normalized_user_value(display_value)
    raw_identifier = _normalized_user_value(identifier)
    return raw_identifier or display


def _needs_user_resolution(value: str | None) -> bool:
    normalized = _normalized_user_value(value)
    if not normalized or normalized in {"unknown", "unassigned"}:
        return False
    if "@" in normalized or " " in normalized:
        return False
    return True


def _resolved_user_label(value: str | None, resolved_labels: dict[str, str]) -> str | None:
    normalized = _normalized_user_value(value)
    if not normalized:
        return None
    return resolved_labels.get(normalized, normalized)


def _user_aliases(user_payload: dict[str, Any] | None, identifier: str | None = None) -> set[str]:
    aliases: set[str] = set()
    seed = _normalized_user_value(identifier)
    if seed:
        aliases.add(seed)
    if not isinstance(user_payload, dict):
        return aliases
    for field_name in ("accountId", "name", "key", "emailAddress", "displayName"):
        value = _normalized_user_value(user_payload.get(field_name))
        if value:
            aliases.add(value)
    return aliases


def _history_user_identifiers(history: dict[str, Any]) -> set[str]:
    identifiers: set[str] = set()
    initial_assignee = _normalized_user_value(history.get("initial_assignee_account_id"))
    if initial_assignee and _needs_user_resolution(initial_assignee):
        identifiers.add(initial_assignee)
    for transition in history.get("assignee_transitions", []):
        for value in (transition.from_account_id, transition.to_account_id):
            normalized = _normalized_user_value(value)
            if normalized and _needs_user_resolution(normalized):
                identifiers.add(normalized)
    for transition in history.get("status_transitions", []):
        normalized = _normalized_user_value(transition.author_account_id)
        if normalized and _needs_user_resolution(normalized):
            identifiers.add(normalized)
    return identifiers


def _apply_resolved_user_labels(history: dict[str, Any], resolved_labels: dict[str, str]) -> dict[str, Any]:
    status_transitions = [
        StatusTransition(
            timestamp=transition.timestamp,
            from_status_id=transition.from_status_id,
            to_status_id=transition.to_status_id,
            author_account_id=_resolved_user_label(transition.author_account_id, resolved_labels),
        )
        for transition in history.get("status_transitions", [])
    ]
    assignee_transitions = [
        AssigneeTransition(
            timestamp=transition.timestamp,
            from_account_id=_resolved_user_label(transition.from_account_id, resolved_labels),
            to_account_id=_resolved_user_label(transition.to_account_id, resolved_labels),
        )
        for transition in history.get("assignee_transitions", [])
    ]
    return {
        "initial_status_id": history.get("initial_status_id"),
        "initial_assignee_account_id": _resolved_user_label(history.get("initial_assignee_account_id"), resolved_labels),
        "status_transitions": status_transitions,
        "assignee_transitions": assignee_transitions,
    }


class JiraSyncService:
    def __init__(self, client: JiraClient) -> None:
        self.client = client

    @staticmethod
    def _strip_order_by(jql: str) -> str:
        return re.sub(r"(?is)\border\s+by\b.*$", "", jql).strip()

    @staticmethod
    def _quote_jql_literal(value: str) -> str:
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'

    @classmethod
    def _build_list_clause(cls, field_name: str, values: list[str]) -> str:
        normalized = [value.strip() for value in values if value and value.strip()]
        if not normalized:
            return ""
        if len(normalized) == 1:
            return f"{field_name} = {cls._quote_jql_literal(normalized[0])}"
        joined = ", ".join(cls._quote_jql_literal(value) for value in normalized)
        return f"{field_name} in ({joined})"

    @staticmethod
    def _parse_iso_date(value: str | None) -> date | None:
        if not value:
            return None
        return date.fromisoformat(value)

    @classmethod
    def build_query_from_filters(cls, config: SyncConfig) -> str:
        clauses = [
            cls._build_list_clause("project", config.project_keys),
            cls._build_list_clause("issuetype", config.issue_types),
        ]
        start_date = cls._parse_iso_date(config.sync_start_date)
        end_date = cls._parse_iso_date(config.sync_end_date)
        if start_date is not None:
            clauses.append(f'updated >= "{start_date.isoformat()}"')
        if end_date is not None:
            clauses.append(f'updated < "{(end_date + timedelta(days=1)).isoformat()}"')
        return " AND ".join(clause for clause in clauses if clause)

    def build_effective_jql(self, config: SyncConfig) -> str:
        builder_jql = self.build_query_from_filters(config)
        if builder_jql:
            base = builder_jql
        elif config.scope_type == "jql":
            base = self._strip_order_by(config.base_jql.strip())
        else:
            if not config.board_id:
                raise JiraClientError("Board scope requires board_id")
            board_configuration = self.client.get_board_configuration(config.board_id)
            filter_id = board_configuration.get("filter", {}).get("id")
            if not filter_id:
                raise JiraClientError("Board configuration does not contain filter id")
            filter_payload = self.client.get_filter(str(filter_id))
            pieces = [f"({self._strip_order_by(filter_payload.get('jql', ''))})"]
            sub_query = board_configuration.get("subQuery")
            if sub_query:
                query_text = sub_query.get("query", "") if isinstance(sub_query, dict) else str(sub_query)
                pieces.append(f"({self._strip_order_by(query_text)})")
            base = " AND ".join(piece for piece in pieces if piece and piece != "()")
        if not base:
            raise JiraClientError("JQL builder requires at least one filter or a legacy base JQL")
        if config.extra_jql.strip():
            return f"({base}) AND ({config.extra_jql.strip()})"
        return base

    def fetch_issues(self, config: SyncConfig) -> list[IssueHistory]:
        jql = self.build_effective_jql(config)
        raw_issues = self.client.enhanced_search(
            jql=jql,
            fields=["summary", "status", "assignee", "issuetype", "project", "created", "updated"],
        )

        histories_by_issue: dict[str, dict[str, Any]] = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
            future_map = {
                executor.submit(self._fetch_issue_history, str(raw_issue["id"])): str(raw_issue["id"])
                for raw_issue in raw_issues
            }
            for future in concurrent.futures.as_completed(future_map):
                issue_id = future_map[future]
                try:
                    histories_by_issue[issue_id] = future.result()
                except JiraClientError:
                    histories_by_issue[issue_id] = {
                        "initial_status_id": None,
                        "initial_assignee_account_id": None,
                        "status_transitions": [],
                        "assignee_transitions": [],
                    }

        identifiers_to_resolve: set[str] = set()
        resolved_user_labels: dict[str, str] = {}
        for raw_issue in raw_issues:
            assignee_payload = (raw_issue.get("fields", {}) or {}).get("assignee") or {}
            direct_label = _preferred_user_label(assignee_payload)
            if direct_label:
                for alias in _user_aliases(assignee_payload):
                    resolved_user_labels.setdefault(alias, direct_label)
            assignee_identifier = _user_identifier_from_payload(assignee_payload)
            if assignee_identifier and _needs_user_resolution(assignee_identifier):
                identifiers_to_resolve.add(assignee_identifier)
        for history in histories_by_issue.values():
            identifiers_to_resolve.update(_history_user_identifiers(history))

        resolved_user_labels.update(self._resolve_user_labels(identifiers_to_resolve))
        issues: list[IssueHistory] = []
        for raw_issue in raw_issues:
            fields = raw_issue.get("fields", {})
            status = fields.get("status", {})
            assignee = fields.get("assignee") or {}
            history = _apply_resolved_user_labels(histories_by_issue.get(str(raw_issue["id"]), {}), resolved_user_labels)
            assignee_identifier = _user_identifier_from_payload(assignee)
            direct_assignee_label = _preferred_user_label(assignee)
            current_assignee = _resolved_user_label(direct_assignee_label, resolved_user_labels)
            if not current_assignee:
                current_assignee = _resolved_user_label(assignee_identifier, resolved_user_labels)
            issues.append(
                IssueHistory(
                    issue_id=str(raw_issue["id"]),
                    issue_key=raw_issue["key"],
                    summary=fields.get("summary", raw_issue["key"]),
                    project_key=fields.get("project", {}).get("key", "UNKNOWN"),
                    issue_type=fields.get("issuetype", {}).get("name", "Unknown"),
                    created_at=datetime.fromisoformat(fields["created"].replace("Z", "+00:00")),
                    initial_status_id=history.get("initial_status_id") or str(status.get("id", "unknown")),
                    current_status_id=str(status.get("id", "unknown")),
                    initial_assignee_account_id=history.get("initial_assignee_account_id"),
                    assignee_transitions=history.get("assignee_transitions", []),
                    current_assignee_account_id=current_assignee,
                    transitions=history.get("status_transitions", []),
                )
            )
        return issues

    def _resolve_user_labels(self, identifiers: set[str]) -> dict[str, str]:
        if not identifiers:
            return {}

        resolved: dict[str, str] = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
            future_map = {
                executor.submit(self.client.get_user, identifier): identifier
                for identifier in identifiers
                if _needs_user_resolution(identifier)
            }
            for future in concurrent.futures.as_completed(future_map):
                identifier = future_map[future]
                try:
                    user_payload = future.result()
                except JiraClientError:
                    continue
                label = _preferred_user_label(user_payload)
                if label:
                    for alias in _user_aliases(user_payload, identifier):
                        resolved[alias] = label
        return resolved

    def _fetch_issue_history(self, issue_id: str) -> dict[str, Any]:
        try:
            bulk_payload = self.client.bulk_fetch_changelogs([issue_id])
            values = bulk_payload.get("issueChangeLogs", [])
            if values:
                histories = values[0].get("changeHistories", [])
                return _parse_issue_history(histories)
        except JiraClientError:
            pass

        histories = self.client.issue_changelog(issue_id)
        return _parse_issue_history(histories)


def _parse_issue_history(histories: list[dict[str, Any]]) -> dict[str, Any]:
    status_transitions: list[StatusTransition] = []
    assignee_transitions: list[AssigneeTransition] = []
    initial_status_id: str | None = None
    initial_assignee_account_id: str | None = None

    for history in histories:
        timestamp = datetime.fromisoformat(history["created"].replace("Z", "+00:00")).astimezone(UTC)
        author_data = history.get("author") or {}
        author = _user_identifier_from_payload(author_data) or _preferred_user_label(author_data)
        for item in history.get("items", []):
            field_name = item.get("field") or item.get("fieldId")
            if field_name == "status":
                if initial_status_id is None and item.get("from"):
                    initial_status_id = item.get("from")
                status_transitions.append(
                    StatusTransition(
                        timestamp=timestamp,
                        from_status_id=item.get("from"),
                        to_status_id=item.get("to") or "",
                        author_account_id=author,
                    )
                )
            elif field_name == "assignee":
                previous_assignee = _history_user_value(item.get("from"), item.get("fromString"))
                next_assignee = _history_user_value(item.get("to"), item.get("toString"))
                if initial_assignee_account_id is None and previous_assignee:
                    initial_assignee_account_id = previous_assignee
                assignee_transitions.append(
                    AssigneeTransition(
                        timestamp=timestamp,
                        from_account_id=previous_assignee,
                        to_account_id=next_assignee,
                    )
                )
    status_transitions.sort(key=lambda item: item.timestamp)
    assignee_transitions.sort(key=lambda item: item.timestamp)
    return {
        "initial_status_id": initial_status_id,
        "initial_assignee_account_id": initial_assignee_account_id,
        "status_transitions": status_transitions,
        "assignee_transitions": assignee_transitions,
    }
