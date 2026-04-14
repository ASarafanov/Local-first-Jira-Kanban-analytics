from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import asdict
from datetime import date, datetime, time, timedelta, timezone, tzinfo
from statistics import median
from typing import Iterable, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .models import BoardMapping, DailyCfdPoint, IssueHistory, StatusInterval, ensure_utc


UTC = timezone.utc
CycleElapsedMode = Literal["first_completion", "last_completion", "sum_of_cycles"]


def build_status_intervals(issue: IssueHistory, report_end: datetime | None = None) -> list[StatusInterval]:
    end_time = ensure_utc(report_end or datetime.now(UTC))
    transitions = sorted(issue.transitions, key=lambda item: item.timestamp)
    intervals: list[StatusInterval] = []
    current_status = issue.initial_status_id
    current_start = issue.created_at

    for transition in transitions:
        if transition.timestamp < current_start:
            continue
        if transition.timestamp > current_start:
            intervals.append(
                StatusInterval(
                    start=current_start,
                    end=transition.timestamp,
                    status_id=current_status,
                )
            )
        current_status = transition.to_status_id
        current_start = transition.timestamp

    final_status = issue.current_status_id or current_status
    if end_time > current_start:
        intervals.append(StatusInterval(start=current_start, end=end_time, status_id=final_status))

    return intervals


def resolve_report_timezone(timezone_name: str | None) -> tuple[tzinfo, str, bool]:
    if not timezone_name:
        return UTC, "UTC", False
    try:
        return ZoneInfo(timezone_name), timezone_name, False
    except ZoneInfoNotFoundError:
        return UTC, "UTC", True


def local_day_start_utc(day: date, report_timezone: tzinfo) -> datetime:
    return datetime.combine(day, time.min, tzinfo=report_timezone).astimezone(UTC)


def interval_day_span(interval: StatusInterval, report_timezone: tzinfo) -> tuple[date, date] | None:
    if interval.end <= interval.start:
        return None
    first_day = interval.start.astimezone(report_timezone).date()
    last_day = interval.end.astimezone(report_timezone).date() - timedelta(days=1)
    if last_day < first_day:
        return None
    return first_day, last_day


def should_expand_cfd_to_statuses(board_mapping: BoardMapping) -> bool:
    if not board_mapping.columns:
        return False
    generic_column_ids = {"inactive", "active", "done", "todo", "doing"}
    return (
        all(column.id in generic_column_ids for column in board_mapping.columns)
        and any(len(column.status_ids) > 1 for column in board_mapping.columns)
    )


def issue_status_ids_in_observed_order(issues: Iterable[IssueHistory]) -> list[str]:
    ordered_status_ids: list[str] = []
    seen_status_ids: set[str] = set()
    for issue in issues:
        candidates = [issue.initial_status_id]
        candidates.extend(
            status_id
            for transition in issue.transitions
            for status_id in (transition.from_status_id, transition.to_status_id)
            if status_id
        )
        candidates.append(issue.current_status_id)
        for status_id in candidates:
            if not status_id or status_id in seen_status_ids:
                continue
            seen_status_ids.add(status_id)
            ordered_status_ids.append(status_id)
    return ordered_status_ids


def cfd_series_definition(
    board_mapping: BoardMapping,
    issues: Iterable[IssueHistory] | None = None,
) -> list[dict[str, object]]:
    if not should_expand_cfd_to_statuses(board_mapping):
        return [
            {
                "id": column.id,
                "name": board_mapping.phase_name_for_column(column),
                "statusIds": list(column.status_ids),
                "groupId": column.id,
                "groupName": board_mapping.phase_name_for_column(column),
            }
            for column in board_mapping.columns
        ]

    status_to_column = board_mapping.status_to_column()
    ordered_status_ids = list(board_mapping.status_names.keys())
    if not ordered_status_ids:
        ordered_status_ids = []
        for column in board_mapping.columns:
            ordered_status_ids.extend(column.status_ids)
    for status_id in issue_status_ids_in_observed_order(issues or []):
        if status_id not in ordered_status_ids:
            ordered_status_ids.append(status_id)

    seen_status_ids: set[str] = set()
    used_names: set[str] = set()
    series: list[dict[str, object]] = []
    for status_id in ordered_status_ids:
        if status_id in seen_status_ids:
            continue
        column = status_to_column.get(status_id)
        group_id = column.id if column is not None else "historical"
        group_name = board_mapping.phase_name_for_column(column) if column is not None else "Historical statuses"
        seen_status_ids.add(status_id)
        display_name = board_mapping.status_name(status_id)
        if display_name in used_names:
            display_name = f"{display_name} ({status_id})"
        used_names.add(display_name)
        series.append(
            {
                "id": status_id,
                "name": display_name,
                "statusIds": [status_id],
                "groupId": group_id,
                "groupName": group_name,
            }
        )
    return series


def clip_intervals(intervals: Iterable[StatusInterval], start: datetime, end: datetime) -> list[StatusInterval]:
    clipped: list[StatusInterval] = []
    for interval in intervals:
        if not interval.overlaps(start, end):
            continue
        clipped.append(
            StatusInterval(
                start=max(interval.start, start),
                end=min(interval.end, end),
                status_id=interval.status_id,
            )
        )
    return clipped


def percentile(values: list[float], percentile_value: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    index = (len(ordered) - 1) * percentile_value
    lower = int(index)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = index - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def bucketize(values: list[float], bucket_count: int = 6) -> list[dict[str, float | int]]:
    if not values:
        return []
    low = min(values)
    high = max(values)
    if low == high:
        return [{"min": low, "max": high, "count": len(values), "label": f"{round(low / 3600)}h"}]

    step = max((high - low) / bucket_count, 1.0)
    buckets = []
    for index in range(bucket_count):
        bucket_min = low + index * step
        bucket_max = high if index == bucket_count - 1 else low + (index + 1) * step
        if index == bucket_count - 1:
            count = sum(1 for value in values if bucket_min <= value <= bucket_max)
        else:
            count = sum(1 for value in values if bucket_min <= value < bucket_max)
        buckets.append(
            {
                "min": bucket_min,
                "max": bucket_max,
                "count": count,
                "label": f"{round(bucket_min / 3600)}-{round(bucket_max / 3600)}h",
            }
        )
    return buckets


def find_cycle_segments(
    issue: IssueHistory,
    start_status_ids: set[str],
    done_status_ids: set[str],
) -> list[tuple[datetime, datetime]]:
    segments: list[tuple[datetime, datetime]] = []
    cycle_start: datetime | None = None

    for transition in sorted(issue.transitions, key=lambda item: item.timestamp):
        if cycle_start is None and transition.to_status_id in start_status_ids:
            cycle_start = transition.timestamp
        elif cycle_start is not None and transition.to_status_id in done_status_ids:
            segments.append((cycle_start, transition.timestamp))
            cycle_start = None

    return segments


def compute_elapsed_cycle_time(
    issue: IssueHistory,
    start_status_ids: set[str],
    done_status_ids: set[str],
    reopen_mode: CycleElapsedMode = "first_completion",
) -> dict[str, object] | None:
    segments = find_cycle_segments(issue, start_status_ids, done_status_ids)
    if not segments:
        return None

    if reopen_mode == "first_completion":
        start, end = segments[0]
        return {"seconds": (end - start).total_seconds(), "start": start, "end": end}

    if reopen_mode == "last_completion":
        start, _ = segments[0]
        _, end = segments[-1]
        return {"seconds": (end - start).total_seconds(), "start": start, "end": end}

    total_seconds = sum((end - start).total_seconds() for start, end in segments)
    return {
        "seconds": total_seconds,
        "start": segments[0][0],
        "end": segments[-1][1],
        "segments": [{"start": start.isoformat(), "end": end.isoformat()} for start, end in segments],
    }


def compute_in_status_cycle_time(
    issue: IssueHistory,
    active_status_ids: set[str],
    report_end: datetime | None = None,
) -> dict[str, object] | None:
    intervals = build_status_intervals(issue, report_end=report_end)
    active = [interval for interval in intervals if interval.status_id in active_status_ids]
    if not active:
        return None
    start = active[0].start
    end = active[-1].end
    total_seconds = sum(interval.duration_seconds for interval in active)
    return {"seconds": total_seconds, "start": start, "end": end}


def summarize_cycle_times(cycle_times: Iterable[float]) -> dict[str, float | None]:
    values = [value for value in cycle_times if value is not None]
    if not values:
        return {"count": 0, "median": None, "p50": None, "p85": None, "p95": None}
    return {
        "count": len(values),
        "median": median(values),
        "p50": percentile(values, 0.50),
        "p85": percentile(values, 0.85),
        "p95": percentile(values, 0.95),
    }


def compute_phase_ratio(
    issue: IssueHistory,
    board_mapping: BoardMapping,
    cycle_start: datetime,
    cycle_end: datetime,
    report_end: datetime | None = None,
) -> dict[str, dict[str, float]]:
    intervals = clip_intervals(build_status_intervals(issue, report_end=report_end), cycle_start, cycle_end)
    status_to_column = board_mapping.status_to_column()
    totals = defaultdict(float)
    overall_seconds = 0.0
    for interval in intervals:
        column = status_to_column.get(interval.status_id)
        column_name = board_mapping.phase_name_for_column(column) if column is not None else board_mapping.status_name(interval.status_id)
        totals[column_name] += interval.duration_seconds
        overall_seconds += interval.duration_seconds

    ratios: dict[str, dict[str, float]] = {}
    for key, seconds in totals.items():
        ratios[key] = {
            "seconds": seconds,
            "ratio": 0.0 if overall_seconds == 0 else seconds / overall_seconds,
        }
    return ratios


def compute_status_ratio(
    issue: IssueHistory,
    board_mapping: BoardMapping,
    cycle_start: datetime,
    cycle_end: datetime,
    report_end: datetime | None = None,
) -> dict[str, dict[str, float]]:
    intervals = clip_intervals(build_status_intervals(issue, report_end=report_end), cycle_start, cycle_end)
    totals = defaultdict(float)
    overall_seconds = 0.0
    for interval in intervals:
        status_name = board_mapping.status_name(interval.status_id)
        totals[status_name] += interval.duration_seconds
        overall_seconds += interval.duration_seconds

    ratios: dict[str, dict[str, float]] = {}
    for key, seconds in totals.items():
        ratios[key] = {
            "seconds": seconds,
            "ratio": 0.0 if overall_seconds == 0 else seconds / overall_seconds,
        }
    return ratios


def compute_monthly_throughput(
    issues: Iterable[IssueHistory],
    done_status_ids: set[str],
) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for issue in issues:
        for transition in sorted(issue.transitions, key=lambda item: item.timestamp):
            if transition.to_status_id in done_status_ids:
                bucket = transition.timestamp.strftime("%Y-%m")
                counts[bucket] += 1
                break
    return dict(sorted(counts.items()))


def assignee_at_completion(issue: IssueHistory, completed_at: datetime) -> str:
    assignee = issue.initial_assignee_account_id
    for transition in issue.assignee_transitions:
        if transition.timestamp <= completed_at:
            assignee = transition.to_account_id
        else:
            break
    if assignee:
        return assignee
    return issue.current_assignee_account_id or "unassigned"


def find_completion_event(
    issue: IssueHistory,
    done_status_ids: set[str],
    attribution_mode: str = "assignee_at_done",
) -> dict[str, str] | None:
    for transition in sorted(issue.transitions, key=lambda item: item.timestamp):
        if transition.to_status_id not in done_status_ids:
            continue
        assignee = assignee_at_completion(issue, transition.timestamp)
        owner = (
            assignee
            if attribution_mode == "assignee_at_done"
            else (transition.author_account_id or "unknown")
        )
        return {
            "completedAt": transition.timestamp.isoformat(),
            "month": transition.timestamp.strftime("%Y-%m"),
            "owner": owner,
            "assignee": assignee,
            "projectKey": issue.project_key,
            "issueKey": issue.issue_key,
        }
    return None


def throughput_report(
    issues: Iterable[IssueHistory],
    done_status_ids: set[str],
    attribution_mode: str = "assignee_at_done",
) -> dict[str, object]:
    monthly: Counter[str] = Counter()
    by_person: dict[str, Counter[str]] = defaultdict(Counter)
    by_project: dict[str, Counter[str]] = defaultdict(Counter)
    events: list[dict[str, str]] = []

    for issue in issues:
        event = find_completion_event(issue, done_status_ids, attribution_mode)
        if event is None:
            continue
        month = event["month"]
        monthly[month] += 1
        by_person[month][event["owner"]] += 1
        by_project[month][event["projectKey"]] += 1
        events.append(event)

    return {
        "monthly": dict(sorted(monthly.items())),
        "byPerson": {month: dict(counter.most_common()) for month, counter in sorted(by_person.items())},
        "byProject": {month: dict(counter.most_common()) for month, counter in sorted(by_project.items())},
        "attributionMode": attribution_mode,
        "events": events,
    }


def cfd_bottleneck_insights(points: list[DailyCfdPoint]) -> list[dict[str, float | str]]:
    if not points:
        return []
    phases = list(points[0].current.keys())
    window = max(len(points) // 3, 1)
    insights = []
    for phase in phases:
        start_values = [point.current.get(phase, 0) for point in points[:window]]
        end_values = [point.current.get(phase, 0) for point in points[-window:]]
        start_avg = sum(start_values) / len(start_values)
        end_avg = sum(end_values) / len(end_values)
        delta = end_avg - start_avg
        insights.append(
            {
                "phase": phase,
                "startAverage": round(start_avg, 2),
                "endAverage": round(end_avg, 2),
                "delta": round(delta, 2),
                "direction": "up" if delta > 0 else "down" if delta < 0 else "flat",
            }
        )
    insights.sort(key=lambda item: item["delta"], reverse=True)
    return insights


def compute_cfd(
    issues: Iterable[IssueHistory],
    board_mapping: BoardMapping,
    start_day: date,
    end_day: date,
    timezone_name: str | None = None,
) -> list[DailyCfdPoint]:
    report_timezone, _, _ = resolve_report_timezone(timezone_name)
    series = cfd_series_definition(board_mapping, issues)
    series_names = [str(item["name"]) for item in series]
    status_to_series_name = {
        status_id: str(item["name"])
        for item in series
        for status_id in item["statusIds"]
    }
    report_end = local_day_start_utc(end_day + timedelta(days=1), report_timezone)
    deltas: dict[date, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    for issue in issues:
        intervals = build_status_intervals(issue, report_end=report_end)
        for interval in intervals:
            series_name = status_to_series_name.get(interval.status_id)
            if series_name is None:
                continue
            span = interval_day_span(interval, report_timezone)
            if span is None:
                continue
            interval_start_day, interval_end_day = span
            effective_start = max(interval_start_day, start_day)
            effective_end = min(interval_end_day, end_day)
            if effective_start > effective_end:
                continue
            deltas[effective_start][series_name] += 1
            deltas[effective_end + timedelta(days=1)][series_name] -= 1

    snapshots: list[DailyCfdPoint] = []
    running = {name: 0 for name in series_names}
    day = start_day
    while day <= end_day:
        for series_name, delta in deltas.get(day, {}).items():
            running[series_name] += delta

        current = {name: running[name] for name in series_names}
        cumulative: dict[str, int] = {}
        cumulative_total = 0
        for series_name in reversed(series_names):
            cumulative_total += current[series_name]
            cumulative[series_name] = cumulative_total
        snapshots.append(DailyCfdPoint(day=day, current=current, cumulative=cumulative))
        day += timedelta(days=1)
    return snapshots


def serialize_cfd(points: Iterable[DailyCfdPoint]) -> list[dict[str, object]]:
    return [
        {
            "day": point.day.isoformat(),
            "current": dict(point.current),
            "cumulative": dict(point.cumulative),
            "totalIssues": sum(point.current.values()),
            "wipTotal": sum(point.current.values()),
        }
        for point in points
    ]


def serialize_issue_histories(issues: Iterable[IssueHistory]) -> list[dict[str, object]]:
    return [
        {
            "issueKey": issue.issue_key,
            "createdAt": issue.created_at.isoformat(),
            "initialStatusId": issue.initial_status_id,
            "currentStatusId": issue.current_status_id,
            "transitions": [
                {
                    "timestamp": transition.timestamp.isoformat(),
                    "fromStatusId": transition.from_status_id,
                    "toStatusId": transition.to_status_id,
                }
                for transition in issue.transitions
            ],
        }
        for issue in issues
    ]


def cycle_report(
    issues: Iterable[IssueHistory],
    start_status_ids: set[str],
    done_status_ids: set[str],
    active_status_ids: set[str],
    mode: str = "elapsed",
) -> dict[str, object]:
    per_issue: list[dict[str, object]] = []
    raw_values: list[float] = []
    by_month: dict[str, list[float]] = defaultdict(list)
    for issue in issues:
        if mode == "in_status_sum":
            result = compute_in_status_cycle_time(issue, active_status_ids)
        else:
            result = compute_elapsed_cycle_time(issue, start_status_ids, done_status_ids)
        if result is None:
            continue
        seconds = float(result["seconds"])
        completion_month = result["end"].strftime("%Y-%m")
        raw_values.append(seconds)
        by_month[completion_month].append(seconds)
        per_issue.append(
            {
                "issueKey": issue.issue_key,
                "summary": issue.summary,
                "projectKey": issue.project_key,
                "seconds": seconds,
                "hours": round(seconds / 3600, 2),
                "start": result["start"].isoformat(),
                "end": result["end"].isoformat(),
                "completionMonth": completion_month,
            }
        )

    per_issue.sort(key=lambda item: item["seconds"], reverse=True)
    trend = []
    for month, values in sorted(by_month.items()):
        trend.append(
            {
                "month": month,
                "count": len(values),
                "medianHours": round((percentile(values, 0.5) or 0.0) / 3600, 2),
            }
        )
    return {
        "summary": summarize_cycle_times(raw_values),
        "trend": trend,
        "histogram": bucketize(raw_values),
        "issues": per_issue,
        "outliers": per_issue[:10],
    }


def phase_ratio_report(
    issues: Iterable[IssueHistory],
    board_mapping: BoardMapping,
    start_status_ids: set[str],
    done_status_ids: set[str],
) -> dict[str, object]:
    aggregate_seconds = defaultdict(float)
    aggregate_ratios = defaultdict(list)
    aggregate_status_seconds = defaultdict(float)
    aggregate_status_ratios = defaultdict(list)
    details = []
    outliers = []
    status_outliers = []

    for issue in issues:
        cycle = compute_elapsed_cycle_time(issue, start_status_ids, done_status_ids)
        if cycle is None:
            continue
        ratios = compute_phase_ratio(issue, board_mapping, cycle["start"], cycle["end"])
        status_ratios = compute_status_ratio(issue, board_mapping, cycle["start"], cycle["end"])
        dominant_phase = None
        dominant_status = None
        if ratios:
            dominant_phase = max(ratios.items(), key=lambda item: item[1]["seconds"])
            outliers.append(
                {
                    "issueKey": issue.issue_key,
                    "phase": dominant_phase[0],
                    "seconds": dominant_phase[1]["seconds"],
                    "hours": round(dominant_phase[1]["seconds"] / 3600, 2),
                    "ratio": dominant_phase[1]["ratio"],
                }
            )
        if status_ratios:
            dominant_status = max(status_ratios.items(), key=lambda item: item[1]["seconds"])
            status_outliers.append(
                {
                    "issueKey": issue.issue_key,
                    "status": dominant_status[0],
                    "seconds": dominant_status[1]["seconds"],
                    "hours": round(dominant_status[1]["seconds"] / 3600, 2),
                    "ratio": dominant_status[1]["ratio"],
                }
            )
        details.append(
            {
                "issueKey": issue.issue_key,
                "phases": ratios,
                "statuses": status_ratios,
                "dominantPhase": dominant_phase[0] if dominant_phase else None,
                "dominantStatus": dominant_status[0] if dominant_status else None,
            }
        )
        for phase_name, data in ratios.items():
            aggregate_seconds[phase_name] += data["seconds"]
            aggregate_ratios[phase_name].append(data["ratio"])
        for status_name, data in status_ratios.items():
            aggregate_status_seconds[status_name] += data["seconds"]
            aggregate_status_ratios[status_name].append(data["ratio"])

    summary = {}
    for phase_name, total_seconds in aggregate_seconds.items():
        values = aggregate_ratios[phase_name]
        summary[phase_name] = {
            "totalSeconds": total_seconds,
            "totalHours": round(total_seconds / 3600, 2),
            "averageRatio": sum(values) / len(values) if values else 0.0,
            "medianRatio": percentile(values, 0.5) if values else None,
        }
    summary = dict(
        sorted(summary.items(), key=lambda item: item[1]["totalSeconds"], reverse=True)
    )

    status_summary = {}
    for status_name, total_seconds in aggregate_status_seconds.items():
        values = aggregate_status_ratios[status_name]
        status_summary[status_name] = {
            "totalSeconds": total_seconds,
            "totalHours": round(total_seconds / 3600, 2),
            "averageRatio": sum(values) / len(values) if values else 0.0,
            "medianRatio": percentile(values, 0.5) if values else None,
        }
    status_summary = dict(
        sorted(status_summary.items(), key=lambda item: item[1]["totalSeconds"], reverse=True)
    )
    outliers.sort(key=lambda item: item["seconds"], reverse=True)
    status_outliers.sort(key=lambda item: item["seconds"], reverse=True)
    return {
        "summary": summary,
        "statusSummary": status_summary,
        "issues": details,
        "outliers": outliers[:10],
        "statusOutliers": status_outliers[:10],
    }


def cfd_unmapped_status_warnings(
    issues: Iterable[IssueHistory],
    board_mapping: BoardMapping,
    series: list[dict[str, object]] | None = None,
    timezone_name: str | None = None,
    end_day: date | None = None,
) -> list[dict[str, object]]:
    report_timezone, _, _ = resolve_report_timezone(timezone_name)
    report_end = local_day_start_utc(end_day + timedelta(days=1), report_timezone) if end_day else None
    known_status_ids = {
        status_id
        for item in (series or cfd_series_definition(board_mapping, issues))
        for status_id in item["statusIds"]
    }
    warnings_by_status: dict[str, set[str]] = defaultdict(set)

    for issue in issues:
        for interval in build_status_intervals(issue, report_end=report_end):
            if interval.status_id in known_status_ids:
                continue
            warnings_by_status[interval.status_id].add(issue.issue_key)

    warnings: list[dict[str, object]] = []
    for status_id, issue_keys in sorted(warnings_by_status.items(), key=lambda item: (-len(item[1]), item[0])):
        issue_list = sorted(issue_keys)
        warnings.append(
            {
                "type": "unmapped_status",
                "statusId": status_id,
                "statusName": board_mapping.status_name(status_id),
                "issueCount": len(issue_list),
                "issueKeys": issue_list[:5],
                "message": (
                    f"Skipped status {board_mapping.status_name(status_id)} ({status_id}) "
                    f"for {len(issue_list)} issue{'s' if len(issue_list) != 1 else ''} because it is not mapped to a CFD lane."
                ),
            }
        )
    return warnings


def cfd_report(
    points: list[DailyCfdPoint],
    board_mapping: BoardMapping,
    issues: Iterable[IssueHistory] | None = None,
    timezone_name: str | None = None,
    start_day: date | None = None,
    end_day: date | None = None,
) -> dict[str, object]:
    serialized = serialize_cfd(points)
    latest = serialized[-1] if serialized else None
    report_timezone, resolved_timezone_name, used_fallback_timezone = resolve_report_timezone(timezone_name)
    del report_timezone
    issue_list = list(issues or [])
    series = cfd_series_definition(board_mapping, issue_list)
    warnings = cfd_unmapped_status_warnings(
        issue_list,
        board_mapping,
        series=series,
        timezone_name=resolved_timezone_name,
        end_day=end_day,
    )
    if used_fallback_timezone and timezone_name:
        warnings.insert(
            0,
            {
                "type": "timezone_fallback",
                "requestedTimezone": timezone_name,
                "resolvedTimezone": resolved_timezone_name,
                "message": (
                    f"Timezone {timezone_name} is not available on the server, so CFD snapshots were calculated in {resolved_timezone_name}."
                ),
            },
        )

    return {
        "meta": {
            "dateFrom": start_day.isoformat() if start_day else (serialized[0]["day"] if serialized else None),
            "dateTo": end_day.isoformat() if end_day else (serialized[-1]["day"] if serialized else None),
            "timezone": resolved_timezone_name,
            "snapshot": "end_of_day",
            "seriesOrder": [item["name"] for item in series],
            "stackingOrder": [item["name"] for item in reversed(series)],
            "breakdown": "status" if should_expand_cfd_to_statuses(board_mapping) else "lane",
            "source": "configured_board_mapping",
        },
        "series": series,
        "points": serialized,
        "latest": latest,
        "issues": serialize_issue_histories(issue_list),
        "warnings": warnings,
        "bottlenecks": cfd_bottleneck_insights(points)[:5],
        "methodology": {
            "xAxis": "Calendar day",
            "series": "Issues in each configured board lane at end of day",
            "stacking": "Render series as a stacked area chart from the last board lane to the first so done-like states stay near the baseline",
            "notes": [
                "Snapshots use local end-of-day boundaries in the selected timezone.",
                "This project reuses configured issue type statuses as the preferred CFD series order for builder mode.",
                "Historical statuses found in synced issue history are appended automatically so the chart keeps full flow continuity.",
            ],
        },
    }
