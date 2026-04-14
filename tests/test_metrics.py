from __future__ import annotations

import unittest
from datetime import date, datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from kanban_metrics.db import ConfigRepository, Database, IssueRepository, JobRepository
from kanban_metrics.metrics import (
    assignee_at_completion,
    build_status_intervals,
    cfd_bottleneck_insights,
    cfd_report,
    cycle_report,
    compute_cfd,
    compute_elapsed_cycle_time,
    compute_in_status_cycle_time,
    compute_monthly_throughput,
    compute_phase_ratio,
    compute_status_ratio,
    find_completion_event,
    phase_ratio_report,
    throughput_report,
)
from kanban_metrics.jira import (
    JiraClientError,
    JiraSyncService,
    board_mapping_from_jql_issues,
    board_mapping_from_project_statuses,
    normalize_projects,
)
from kanban_metrics.models import AssigneeTransition, BoardColumn, BoardMapping, IssueHistory, StatusTransition, SyncConfig, SyncJob
from kanban_metrics.runtime_store import RuntimeStore
from kanban_metrics.service import DashboardService, JobManager, _config_dashboard_range, build_demo_issues


UTC = timezone.utc


class MetricsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.mapping = BoardMapping(
            columns=[
                BoardColumn(id="todo", name="To Do", status_ids=["todo"]),
                BoardColumn(id="doing", name="In Progress", status_ids=["in-progress", "review"]),
                BoardColumn(id="done", name="Done", status_ids=["done"]),
            ],
            status_names={"todo": "To Do", "in-progress": "In Progress", "review": "Review", "done": "Done"},
        )

    def make_issue(self) -> IssueHistory:
        return IssueHistory(
            issue_id="10001",
            issue_key="KM-1",
            summary="Primary story",
            project_key="KM",
            issue_type="Story",
            created_at=datetime(2026, 3, 1, 9, 0, tzinfo=UTC),
            initial_status_id="todo",
            current_status_id="done",
            transitions=[
                StatusTransition(datetime(2026, 3, 2, 9, 0, tzinfo=UTC), "todo", "in-progress"),
                StatusTransition(datetime(2026, 3, 3, 12, 0, tzinfo=UTC), "in-progress", "review"),
                StatusTransition(datetime(2026, 3, 4, 15, 0, tzinfo=UTC), "review", "done"),
            ],
        )

    def test_build_status_intervals(self) -> None:
        issue = self.make_issue()
        intervals = build_status_intervals(issue, report_end=datetime(2026, 3, 5, 0, 0, tzinfo=UTC))
        self.assertEqual([interval.status_id for interval in intervals], ["todo", "in-progress", "review", "done"])
        self.assertEqual(intervals[1].duration_seconds, 27 * 3600)

    def test_elapsed_cycle_time_first_completion(self) -> None:
        result = compute_elapsed_cycle_time(self.make_issue(), {"in-progress"}, {"done"})
        self.assertIsNotNone(result)
        self.assertEqual(result["seconds"], (datetime(2026, 3, 4, 15, 0, tzinfo=UTC) - datetime(2026, 3, 2, 9, 0, tzinfo=UTC)).total_seconds())

    def test_elapsed_cycle_time_sum_of_cycles_for_reopen(self) -> None:
        issue = IssueHistory(
            issue_id="10002",
            issue_key="KM-2",
            summary="Reopened bug",
            project_key="KM",
            issue_type="Bug",
            created_at=datetime(2026, 3, 1, 9, 0, tzinfo=UTC),
            initial_status_id="todo",
            current_status_id="done",
            transitions=[
                StatusTransition(datetime(2026, 3, 2, 9, 0, tzinfo=UTC), "todo", "in-progress"),
                StatusTransition(datetime(2026, 3, 3, 9, 0, tzinfo=UTC), "in-progress", "done"),
                StatusTransition(datetime(2026, 3, 4, 9, 0, tzinfo=UTC), "done", "in-progress"),
                StatusTransition(datetime(2026, 3, 5, 12, 0, tzinfo=UTC), "in-progress", "done"),
            ],
        )
        result = compute_elapsed_cycle_time(issue, {"in-progress"}, {"done"}, reopen_mode="sum_of_cycles")
        self.assertIsNotNone(result)
        self.assertEqual(result["seconds"], 51 * 3600)

    def test_in_status_cycle_time(self) -> None:
        result = compute_in_status_cycle_time(self.make_issue(), {"in-progress", "review"})
        self.assertIsNotNone(result)
        self.assertEqual(result["seconds"], 54 * 3600)

    def test_phase_ratio(self) -> None:
        issue = self.make_issue()
        cycle = compute_elapsed_cycle_time(issue, {"in-progress"}, {"done"})
        assert cycle is not None
        ratio = compute_phase_ratio(issue, self.mapping, cycle["start"], cycle["end"])
        self.assertAlmostEqual(ratio["In Progress"]["ratio"], 1.0, places=3)
        self.assertEqual(ratio["In Progress"]["seconds"], 54 * 3600)

    def test_status_ratio_uses_status_names(self) -> None:
        issue = self.make_issue()
        cycle = compute_elapsed_cycle_time(issue, {"in-progress"}, {"done"})
        assert cycle is not None
        ratio = compute_status_ratio(issue, self.mapping, cycle["start"], cycle["end"])
        self.assertEqual(set(ratio), {"In Progress", "Review"})
        self.assertEqual(ratio["Review"]["seconds"], 27 * 3600)

    def test_monthly_throughput(self) -> None:
        issue = self.make_issue()
        throughput = compute_monthly_throughput([issue], {"done"})
        self.assertEqual(throughput, {"2026-03": 1})

    def test_assignee_at_completion(self) -> None:
        issue = self.make_issue()
        issue.initial_assignee_account_id = "user-a"
        issue.assignee_transitions = [
            AssigneeTransition(datetime(2026, 3, 4, 14, 0, tzinfo=UTC), "user-a", "user-b"),
        ]
        self.assertEqual(
            assignee_at_completion(issue, datetime(2026, 3, 4, 15, 0, tzinfo=UTC)),
            "user-b",
        )

    def test_throughput_report_by_person(self) -> None:
        issue = self.make_issue()
        issue.initial_assignee_account_id = "user-a"
        issue.assignee_transitions = [
            AssigneeTransition(datetime(2026, 3, 4, 14, 0, tzinfo=UTC), "user-a", "user-b"),
        ]
        report = throughput_report([issue], {"done"}, attribution_mode="assignee_at_done")
        self.assertEqual(report["monthly"], {"2026-03": 1})
        self.assertEqual(report["byPerson"]["2026-03"], {"user-b": 1})
        self.assertEqual(report["events"][0]["assignee"], "user-b")

    def test_completion_event_by_transition_author(self) -> None:
        issue = self.make_issue()
        issue.initial_assignee_account_id = "user-a"
        issue.transitions[-1].author_account_id = "actor-1"
        event = find_completion_event(issue, {"done"}, attribution_mode="transition_author")
        self.assertIsNotNone(event)
        self.assertEqual(event["owner"], "actor-1")
        self.assertEqual(event["assignee"], "user-a")

    def test_cycle_report_contains_histogram_and_trend(self) -> None:
        report = cycle_report([self.make_issue()], {"in-progress"}, {"done"}, {"in-progress", "review"})
        self.assertEqual(report["summary"]["count"], 1)
        self.assertEqual(report["trend"][0]["month"], "2026-03")
        self.assertTrue(report["histogram"])
        self.assertEqual(report["outliers"][0]["issueKey"], "KM-1")
        self.assertEqual(report["outliers"][0]["summary"], "Primary story")

    def test_cfd_handles_backward_motion(self) -> None:
        issue = IssueHistory(
            issue_id="10003",
            issue_key="KM-3",
            summary="Back and forth task",
            project_key="KM",
            issue_type="Task",
            created_at=datetime(2026, 3, 1, 9, 0, tzinfo=UTC),
            initial_status_id="todo",
            current_status_id="in-progress",
            transitions=[
                StatusTransition(datetime(2026, 3, 2, 9, 0, tzinfo=UTC), "todo", "in-progress"),
                StatusTransition(datetime(2026, 3, 3, 9, 0, tzinfo=UTC), "in-progress", "review"),
                StatusTransition(datetime(2026, 3, 4, 9, 0, tzinfo=UTC), "review", "in-progress"),
            ],
        )
        points = compute_cfd([issue], self.mapping, date(2026, 3, 2), date(2026, 3, 4))
        self.assertEqual(points[1].current["Review"], 1)
        self.assertEqual(points[1].current["Done"], 0)
        self.assertEqual(points[2].current["In Progress"], 1)
        self.assertEqual(points[2].cumulative["In Progress"], 1)

    def test_cfd_uses_requested_timezone_for_day_boundaries(self) -> None:
        issue = IssueHistory(
            issue_id="10004",
            issue_key="KM-4",
            summary="Late night task",
            project_key="KM",
            issue_type="Task",
            created_at=datetime(2026, 3, 1, 22, 30, tzinfo=UTC),
            initial_status_id="todo",
            current_status_id="todo",
        )
        points = compute_cfd(
            [issue],
            self.mapping,
            date(2026, 3, 1),
            date(2026, 3, 2),
            timezone_name="Europe/Moscow",
        )
        self.assertEqual(points[0].current["To Do"], 0)
        self.assertEqual(points[1].current["To Do"], 1)

    def test_cfd_uses_final_state_when_multiple_transitions_happen_same_day(self) -> None:
        issue = IssueHistory(
            issue_id="10005",
            issue_key="KM-5",
            summary="Same day transitions",
            project_key="KM",
            issue_type="Task",
            created_at=datetime(2026, 3, 1, 9, 0, tzinfo=UTC),
            initial_status_id="todo",
            current_status_id="done",
            transitions=[
                StatusTransition(datetime(2026, 3, 2, 10, 0, tzinfo=UTC), "todo", "in-progress"),
                StatusTransition(datetime(2026, 3, 2, 12, 0, tzinfo=UTC), "in-progress", "done"),
            ],
        )
        points = compute_cfd([issue], self.mapping, date(2026, 3, 2), date(2026, 3, 2))
        self.assertEqual(points[0].current["Done"], 1)
        self.assertEqual(points[0].current["In Progress"], 0)

    def test_cfd_report_contains_bottleneck_hints(self) -> None:
        issue_a = IssueHistory(
            issue_id="10010",
            issue_key="KM-10",
            summary="WIP item A",
            project_key="KM",
            issue_type="Task",
            created_at=datetime(2026, 3, 1, 9, 0, tzinfo=UTC),
            initial_status_id="todo",
            current_status_id="in-progress",
            transitions=[
                StatusTransition(datetime(2026, 3, 2, 9, 0, tzinfo=UTC), "todo", "in-progress"),
            ],
        )
        issue_b = IssueHistory(
            issue_id="10011",
            issue_key="KM-11",
            summary="WIP item B",
            project_key="KM",
            issue_type="Task",
            created_at=datetime(2026, 3, 3, 9, 0, tzinfo=UTC),
            initial_status_id="todo",
            current_status_id="in-progress",
            transitions=[
                StatusTransition(datetime(2026, 3, 4, 9, 0, tzinfo=UTC), "todo", "in-progress"),
            ],
        )
        points = compute_cfd([issue_a, issue_b], self.mapping, date(2026, 3, 2), date(2026, 3, 5))
        report = cfd_report(
            points,
            self.mapping,
            [issue_a, issue_b],
            timezone_name="Europe/Moscow",
            start_day=date(2026, 3, 2),
            end_day=date(2026, 3, 5),
        )
        self.assertTrue(report["points"])
        self.assertEqual(len(report["issues"]), 2)
        self.assertEqual(report["issues"][0]["issueKey"], "KM-10")
        self.assertTrue(report["bottlenecks"])
        self.assertEqual(report["latest"]["wipTotal"], sum(report["latest"]["current"].values()))
        self.assertEqual(report["latest"]["totalIssues"], report["latest"]["wipTotal"])
        self.assertEqual(report["meta"]["timezone"], "Europe/Moscow")
        self.assertEqual(report["meta"]["stackingOrder"], ["Done", "Review", "In Progress", "To Do"])
        self.assertEqual(report["methodology"]["xAxis"], "Calendar day")

    def test_cfd_report_surfaces_unmapped_statuses(self) -> None:
        generic_mapping = BoardMapping(
            columns=[
                BoardColumn(id="inactive", name="Inactive statuses", status_ids=["todo", "backlog"]),
                BoardColumn(id="active", name="Active statuses", status_ids=["in-progress"]),
                BoardColumn(id="done", name="Done statuses", status_ids=["done"]),
            ],
            status_names={"todo": "To Do", "backlog": "Backlog", "in-progress": "In Progress", "done": "Done"},
        )
        issue = IssueHistory(
            issue_id="10012",
            issue_key="KM-12",
            summary="Blocked task",
            project_key="KM",
            issue_type="Task",
            created_at=datetime(2026, 3, 1, 9, 0, tzinfo=UTC),
            initial_status_id="blocked",
            current_status_id="blocked",
        )
        points = compute_cfd([issue], generic_mapping, date(2026, 3, 1), date(2026, 3, 2))
        report = cfd_report(points, generic_mapping, [issue], start_day=date(2026, 3, 1), end_day=date(2026, 3, 2))
        self.assertEqual(report["points"][0]["totalIssues"], 1)
        self.assertFalse(report["warnings"])
        self.assertIn("blocked", [item["id"] for item in report["series"]])

    def test_cfd_uses_individual_statuses_for_generic_bucket_mapping(self) -> None:
        generic_mapping = BoardMapping(
            columns=[
                BoardColumn(id="inactive", name="Inactive statuses", status_ids=["todo", "backlog"]),
                BoardColumn(id="active", name="Active statuses", status_ids=["in-progress", "review"]),
                BoardColumn(id="done", name="Done statuses", status_ids=["done"]),
            ],
            status_names={
                "backlog": "Backlog",
                "review": "Review",
                "todo": "To Do",
                "done": "Done",
                "in-progress": "In Progress",
            },
        )
        issue = IssueHistory(
            issue_id="10013",
            issue_key="KM-13",
            summary="Status detail task",
            project_key="KM",
            issue_type="Task",
            created_at=datetime(2026, 3, 1, 9, 0, tzinfo=UTC),
            initial_status_id="todo",
            current_status_id="review",
            transitions=[
                StatusTransition(datetime(2026, 3, 2, 9, 0, tzinfo=UTC), "todo", "in-progress"),
                StatusTransition(datetime(2026, 3, 3, 9, 0, tzinfo=UTC), "in-progress", "review"),
            ],
        )
        points = compute_cfd([issue], generic_mapping, date(2026, 3, 1), date(2026, 3, 3))
        report = cfd_report(points, generic_mapping, [issue], start_day=date(2026, 3, 1), end_day=date(2026, 3, 3))
        self.assertEqual(report["meta"]["breakdown"], "status")
        self.assertEqual([item["name"] for item in report["series"]], ["Backlog", "Review", "To Do", "Done", "In Progress"])
        self.assertEqual(points[2].current["Review"], 1)
        self.assertNotIn("Active statuses", points[2].current)

    def test_phase_ratio_report_contains_status_summary(self) -> None:
        report = phase_ratio_report([self.make_issue()], self.mapping, {"in-progress"}, {"done"})
        self.assertIn("In Progress", report["summary"])
        self.assertIn("Review", report["statusSummary"])
        self.assertEqual(report["issues"][0]["dominantStatus"], "In Progress")

    def test_demo_issues_are_completed_and_varied(self) -> None:
        issues = build_demo_issues()
        self.assertGreaterEqual(len(issues), 8)
        self.assertTrue(all(issue.project_key == "DEMO" for issue in issues))
        self.assertTrue(any(issue.assignee_transitions for issue in issues))

    def test_config_dict_hides_secret(self) -> None:
        config = SyncConfig(
            id="cfg-1",
            name="Cfg",
            jira_base_url="https://example.atlassian.net",
            auth_type="bearer_pat",
            verify_ssl=False,
            user_email=None,
            secret="keychain:cfg-1",
            scope_type="builder",
            board_id=None,
            project_keys=["TEST"],
            issue_types=["Story"],
            base_jql="project = TEST",
            extra_jql="",
            date_range_days=30,
            sync_start_date="2026-03-01",
            sync_end_date="2026-03-31",
            start_status_ids=["in-progress"],
            done_status_ids=["done"],
            active_status_ids=["in-progress"],
            attribution_mode="assignee_at_done",
        )
        payload = config.to_dict()
        self.assertIsNone(payload["secret"])
        self.assertTrue(payload["has_secret"])

    def test_builder_jql_uses_project_issue_type_and_date_range(self) -> None:
        config = SyncConfig(
            id="cfg-2",
            name="Cfg",
            jira_base_url="https://example.atlassian.net",
            auth_type="bearer_pat",
            verify_ssl=False,
            user_email=None,
            secret=None,
            scope_type="builder",
            board_id=None,
            project_keys=["KM", "OPS"],
            issue_types=["Story", "Bug"],
            base_jql="",
            extra_jql="priority = High",
            date_range_days=None,
            sync_start_date="2026-03-01",
            sync_end_date="2026-03-31",
            start_status_ids=[],
            done_status_ids=[],
            active_status_ids=[],
            attribution_mode="assignee_at_done",
        )
        jql = JiraSyncService.build_query_from_filters(config)
        self.assertEqual(
            jql,
            'project in ("KM", "OPS") AND issuetype in ("Story", "Bug") AND updated >= "2026-03-01" AND updated < "2026-04-01"',
        )
        effective = JiraSyncService(client=None).build_effective_jql(config)  # type: ignore[arg-type]
        self.assertIn("(priority = High)", effective)

    def test_project_status_mapping_uses_issue_type_filter(self) -> None:
        raw = [
            {
                "name": "Story",
                "statuses": [
                    {"id": "1", "name": "To Do", "statusCategory": {"key": "new", "name": "To Do"}},
                    {"id": "2", "name": "In Progress", "statusCategory": {"key": "indeterminate", "name": "In Progress"}},
                    {"id": "3", "name": "Done", "statusCategory": {"key": "done", "name": "Done"}},
                ],
            },
            {
                "name": "Bug",
                "statuses": [
                    {"id": "4", "name": "Triage", "statusCategory": {"key": "new", "name": "To Do"}},
                    {"id": "5", "name": "Fixed", "statusCategory": {"key": "done", "name": "Done"}},
                ],
            },
        ]
        derived = board_mapping_from_project_statuses(raw, ["Story"])
        self.assertEqual([item["issueType"] for item in derived["issueTypeStatuses"]], ["Story"])
        self.assertEqual([item["id"] for item in derived["statuses"]], ["1", "2", "3"])
        self.assertEqual(derived["startStatusIds"], ["2"])
        self.assertEqual(derived["doneStatusIds"], ["3"])
        self.assertEqual(derived["mapping"].status_names["2"], "In Progress")

    def test_fetch_issues_prefers_email_or_username_for_hover_labels(self) -> None:
        class FakeClient:
            def enhanced_search(self, jql: str, fields: list[str] | None = None, max_results: int = 100) -> list[dict[str, object]]:
                return [
                    {
                        "id": "10001",
                        "key": "KM-1",
                        "fields": {
                            "summary": "Primary story",
                            "status": {"id": "done"},
                            "assignee": {"accountId": "acc-1", "displayName": "User One"},
                            "issuetype": {"name": "Task"},
                            "project": {"key": "KM"},
                            "created": "2026-03-01T09:00:00+00:00",
                        },
                    }
                ]

            def bulk_fetch_changelogs(self, issue_ids: list[str]) -> dict[str, object]:
                return {
                    "issueChangeLogs": [
                        {
                            "changeHistories": [
                                {
                                    "created": "2026-03-02T10:00:00+00:00",
                                    "author": {"accountId": "author-1", "displayName": "User Two"},
                                    "items": [
                                        {"field": "assignee", "from": "jirauser", "fromString": "User One", "to": "acc-1", "toString": "User One"}
                                    ],
                                },
                                {
                                    "created": "2026-03-03T11:00:00+00:00",
                                    "author": {"accountId": "author-1", "displayName": "User Two"},
                                    "items": [
                                        {"field": "status", "from": "todo", "to": "done"}
                                    ],
                                },
                            ]
                        }
                    ]
                }

            def issue_changelog(self, issue_id_or_key: str) -> list[dict[str, object]]:
                return []

            def get_user(self, identifier: str) -> dict[str, str]:
                payloads = {
                    "acc-1": {"name": "user-one", "emailAddress": "user.one@example.invalid", "displayName": "User One"},
                    "jirauser": {"name": "user-one", "displayName": "User One"},
                    "author-1": {"name": "user-two", "emailAddress": "user.two@example.invalid", "displayName": "User Two"},
                }
                if identifier not in payloads:
                    raise JiraClientError("missing user")
                return payloads[identifier]

        config = SyncConfig(
            id="cfg-fetch",
            name="Cfg",
            jira_base_url="https://example.atlassian.net",
            auth_type="bearer_pat",
            verify_ssl=False,
            user_email=None,
            secret=None,
            scope_type="builder",
            board_id=None,
            project_keys=["KM"],
            issue_types=["Task"],
            base_jql="",
            extra_jql="",
            date_range_days=30,
            sync_start_date="2026-03-01",
            sync_end_date="2026-03-31",
            start_status_ids=["in-progress"],
            done_status_ids=["done"],
            active_status_ids=["in-progress"],
            attribution_mode="assignee_at_done",
        )

        issues = JiraSyncService(FakeClient()).fetch_issues(config)

        self.assertEqual(len(issues), 1)
        issue = issues[0]
        self.assertEqual(issue.current_assignee_account_id, "user-one")
        self.assertEqual(issue.initial_assignee_account_id, "user-one")
        self.assertEqual(issue.assignee_transitions[0].from_account_id, "user-one")
        self.assertEqual(issue.assignee_transitions[0].to_account_id, "user-one")
        self.assertEqual(issue.transitions[0].author_account_id, "user-two")

    def test_jql_issue_status_mapping_uses_only_found_issue_statuses(self) -> None:
        raw_issues = [
            {
                "fields": {
                    "status": {
                        "id": "10",
                        "name": "Selected",
                        "statusCategory": {"key": "new", "name": "To Do"},
                    }
                }
            },
            {
                "fields": {
                    "status": {
                        "id": "20",
                        "name": "In Progress",
                        "statusCategory": {"key": "indeterminate", "name": "In Progress"},
                    }
                }
            },
            {
                "fields": {
                    "status": {
                        "id": "30",
                        "name": "Closed",
                        "statusCategory": {"key": "done", "name": "Done"},
                    }
                }
            },
        ]
        derived = board_mapping_from_jql_issues(raw_issues)
        self.assertEqual([item["id"] for item in derived["statuses"]], ["10", "20", "30"])
        self.assertEqual(derived["activeStatusIds"], ["20"])
        self.assertEqual(derived["doneStatusIds"], ["30"])
        self.assertEqual(derived["mapping"].columns[0].status_ids, ["10"])

    def test_config_dashboard_range_prefers_absolute_dates(self) -> None:
        config = SyncConfig(
            id="cfg-3",
            name="Cfg",
            jira_base_url="https://example.atlassian.net",
            auth_type="bearer_pat",
            verify_ssl=False,
            user_email=None,
            secret=None,
            scope_type="builder",
            board_id=None,
            project_keys=["KM"],
            issue_types=["Task"],
            base_jql="",
            extra_jql="",
            date_range_days=15,
            sync_start_date="2026-02-01",
            sync_end_date="2026-02-14",
            start_status_ids=[],
            done_status_ids=[],
            active_status_ids=[],
            attribution_mode="assignee_at_done",
        )
        self.assertEqual(_config_dashboard_range(config), (date(2026, 2, 1), date(2026, 2, 14)))

    def test_normalize_projects_sorts_and_keeps_visible_fields(self) -> None:
        normalized = normalize_projects(
            [
                {"id": 2, "key": "OPS", "name": "Operations", "projectTypeKey": "software"},
                {"id": 1, "key": "APP", "name": "Application", "projectTypeKey": "software", "archived": True},
                {"id": 3, "key": "KM", "name": "Kanban Metrics", "projectTypeKey": "business"},
            ]
        )
        self.assertEqual([item["key"] for item in normalized], ["KM", "OPS", "APP"])
        self.assertEqual(normalized[0]["name"], "Kanban Metrics")
        self.assertTrue(normalized[-1]["archived"])

    def test_issue_repository_scopes_duplicate_jira_issue_ids_by_config(self) -> None:
        schema_path = Path(__file__).resolve().parents[1] / "kanban_metrics" / "schema.sql"
        with TemporaryDirectory() as tmpdir:
            database = Database(Path(tmpdir) / "test.db")
            database.initialize(schema_path)
            repository = IssueRepository(database)

            issue_a = IssueHistory(
                issue_id="10001",
                issue_key="BANK-1",
                summary="Shared Jira issue",
                project_key="BANK",
                issue_type="Task",
                created_at=datetime(2026, 4, 1, 9, 0, tzinfo=UTC),
                initial_status_id="todo",
                current_status_id="done",
            )
            issue_b = IssueHistory(
                issue_id="10001",
                issue_key="BANK-1",
                summary="Shared Jira issue",
                project_key="BANK",
                issue_type="Task",
                created_at=datetime(2026, 4, 1, 9, 0, tzinfo=UTC),
                initial_status_id="todo",
                current_status_id="done",
            )

            repository.replace_issues("cfg-a", [issue_a])
            repository.replace_issues("cfg-b", [issue_b])

            loaded_a = repository.list_issues("cfg-a")
            loaded_b = repository.list_issues("cfg-b")

            self.assertEqual(loaded_a[0].issue_id, "10001")
            self.assertEqual(loaded_b[0].issue_id, "10001")
            with database.connect() as connection:
                stored_issue_ids = [
                    row["issue_id"]
                    for row in connection.execute("SELECT issue_id FROM issue ORDER BY config_id, issue_id").fetchall()
                ]
            self.assertEqual(stored_issue_ids, ["cfg-a:10001", "cfg-b:10001"])

    def test_delete_config_removes_related_rows_and_secret(self) -> None:
        schema_path = Path(__file__).resolve().parents[1] / "kanban_metrics" / "schema.sql"
        with TemporaryDirectory() as tmpdir:
            temp_path = Path(tmpdir)
            database = Database(temp_path / "test.db")
            database.initialize(schema_path)
            config_repository = ConfigRepository(database)
            issue_repository = IssueRepository(database)
            job_repository = JobRepository(database)
            runtime_store = RuntimeStore("kanban-metrics-test", temp_path / "runtime-store.json")
            service = DashboardService(
                config_repository,
                issue_repository,
                JobManager(job_repository, issue_repository, runtime_store),
                runtime_store,
            )

            config = SyncConfig(
                id="cfg-delete",
                name="Delete me",
                jira_base_url="https://example.atlassian.net",
                auth_type="bearer_pat",
                verify_ssl=False,
                user_email=None,
                secret="file:cfg-delete",
                scope_type="builder",
                board_id=None,
                project_keys=["KM"],
                issue_types=["Task"],
                base_jql="",
                extra_jql="",
                date_range_days=30,
                sync_start_date=None,
                sync_end_date=None,
                start_status_ids=["in-progress"],
                done_status_ids=["done"],
                active_status_ids=["in-progress"],
                attribution_mode="assignee_at_done",
            )
            config_repository.upsert_config(config)
            (temp_path / "runtime-store.json").write_text('{\n  "cfg-delete": "top-secret"\n}', encoding="utf-8")

            issue = IssueHistory(
                issue_id="10001",
                issue_key="KM-1",
                summary="Shared Jira issue",
                project_key="KM",
                issue_type="Task",
                created_at=datetime(2026, 4, 1, 9, 0, tzinfo=UTC),
                initial_status_id="todo",
                current_status_id="done",
            )
            issue_repository.replace_issues("cfg-delete", [issue])
            job_repository.upsert(
                SyncJob(
                    id="job-1",
                    config_id="cfg-delete",
                    status="completed",
                    started_at=datetime(2026, 4, 2, 9, 0, tzinfo=UTC),
                    finished_at=datetime(2026, 4, 2, 9, 30, tzinfo=UTC),
                    progress=1.0,
                    message="Done",
                )
            )

            deleted = service.delete_config("cfg-delete")

            self.assertEqual(deleted.id, "cfg-delete")
            self.assertIsNone(config_repository.get_config("cfg-delete"))
            self.assertEqual(issue_repository.list_issues("cfg-delete"), [])
            self.assertNotIn("cfg-delete", (temp_path / "runtime-store.json").read_text(encoding="utf-8"))
            with database.connect() as connection:
                self.assertIsNone(connection.execute("SELECT 1 FROM sync_job WHERE config_id = 'cfg-delete'").fetchone())
                self.assertIsNone(connection.execute("SELECT 1 FROM jira_instance WHERE id = 'instance-cfg-delete'").fetchone())

    def test_delete_config_rejects_running_sync(self) -> None:
        schema_path = Path(__file__).resolve().parents[1] / "kanban_metrics" / "schema.sql"
        with TemporaryDirectory() as tmpdir:
            temp_path = Path(tmpdir)
            database = Database(temp_path / "test.db")
            database.initialize(schema_path)
            config_repository = ConfigRepository(database)
            issue_repository = IssueRepository(database)
            job_repository = JobRepository(database)
            runtime_store = RuntimeStore("kanban-metrics-test", temp_path / "runtime-store.json")
            service = DashboardService(
                config_repository,
                issue_repository,
                JobManager(job_repository, issue_repository, runtime_store),
                runtime_store,
            )

            config_repository.upsert_config(
                SyncConfig(
                    id="cfg-running",
                    name="Running sync",
                    jira_base_url="https://example.atlassian.net",
                    auth_type="bearer_pat",
                    verify_ssl=False,
                    user_email=None,
                    secret=None,
                    scope_type="builder",
                    board_id=None,
                    project_keys=["KM"],
                    issue_types=["Task"],
                    base_jql="",
                    extra_jql="",
                    date_range_days=30,
                    sync_start_date=None,
                    sync_end_date=None,
                    start_status_ids=["in-progress"],
                    done_status_ids=["done"],
                    active_status_ids=["in-progress"],
                    attribution_mode="assignee_at_done",
                )
            )
            job_repository.upsert(
                SyncJob(
                    id="job-running",
                    config_id="cfg-running",
                    status="running",
                    started_at=datetime(2026, 4, 2, 9, 0, tzinfo=UTC),
                    progress=0.5,
                    message="Syncing",
                )
            )

            with self.assertRaisesRegex(RuntimeError, "synchronization is running"):
                service.delete_config("cfg-running")


if __name__ == "__main__":
    unittest.main()
