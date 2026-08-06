"""Token usage data collected by TokenTracker (~/.tokentracker/queue.jsonl).

TokenTracker (github.com/xiufengsun/TokenTracker) records token burn from
coding tools into an append-only JSONL queue of 30-minute UTC buckets:

    {"hour_start": "2026-08-06T10:00:00Z", "source": "claude-code",
     "model": "anthropic/claude-sonnet-4-5", "input_tokens": ..., ...,
     "total_tokens": ..., "conversation_count": ...}

This module turns that queue into the aggregates the admin "Usage" view
renders: window totals, a daily series, per-model/per-source breakdowns,
and a 52-week heatmap. Every source is optional — a machine without
TokenTracker has no queue file, a torn line may appear mid-write, and the
queue grows unbounded — so each lookup degrades to empty values instead of
raising, and the view always renders.

Cost (USD) is computed by TokenTracker's sidecar API, not stored in the
queue, so v1 reports tokens only.
"""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

QUEUE_PATH = Path(".tokentracker/queue.jsonl")
MAX_QUEUE_BYTES = 10_000_000  # read only the recent tail of the queue

WINDOW_HOURS = {
    "24h": timedelta(hours=24),
    "7d": timedelta(hours=168),
    "30d": timedelta(hours=720),
}
DAILY_DAYS = 30
HEATMAP_WEEKS = 52

TOKEN_FIELDS = (
    "input_tokens",
    "cached_input_tokens",
    "cache_creation_input_tokens",
    "output_tokens",
    "reasoning_output_tokens",
)


def _to_int(value: Any) -> int | None:
    try:
        return int(value)
    except TypeError, ValueError:
        return None


def _parse_hour_start(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        when = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if when.tzinfo is None:
        return when.replace(tzinfo=UTC)
    return when.astimezone(UTC)


def parse_line(line: str) -> dict[str, Any] | None:
    """Parse one queue line into a normalized entry, or None when unusable."""
    try:
        raw = json.loads(line)
    except json.JSONDecodeError:
        return None
    if not isinstance(raw, dict):
        return None
    hour_start = _parse_hour_start(raw.get("hour_start"))
    source = raw.get("source")
    model = raw.get("model")
    if hour_start is None or not isinstance(source, str) or not source:
        return None
    if not isinstance(model, str) or not model:
        return None

    tokens = {field: _to_int(raw.get(field)) or 0 for field in TOKEN_FIELDS}
    total_tokens = _to_int(raw.get("total_tokens"))
    if total_tokens is None:
        total_tokens = sum(tokens.values())
    return {
        "hour_start": hour_start,
        "source": source,
        "model": model,
        **tokens,
        "total_tokens": total_tokens,
        "conversations": _to_int(raw.get("conversation_count")) or 0,
    }


def parse_entries(home: Path) -> list[dict[str, Any]]:
    """Parse the queue, deduplicating to the latest line per source/model/hour.

    The queue is append-only, so a repeated (source, model, hour_start) key
    means TokenTracker superseded an earlier write; the last line wins. File
    order is preserved for everything else.
    """
    queue = home / QUEUE_PATH
    if not queue.is_file():
        return []
    try:
        data = queue.read_text(encoding="utf-8")
    except OSError:
        return []
    if len(data) > MAX_QUEUE_BYTES:
        data = data[-MAX_QUEUE_BYTES:]

    entries: dict[tuple[str, str, datetime], dict[str, Any]] = {}
    for line in data.splitlines():
        entry = parse_line(line)
        if entry is None:
            continue
        key = (entry["source"], entry["model"], entry["hour_start"])
        entries[key] = entry
    return list(entries.values())


def _sum_tokens(
    entries: list[dict[str, Any]], *, lower: datetime, upper: datetime
) -> int:
    return sum(
        entry.get("total_tokens", 0)
        for entry in entries
        if lower < entry["hour_start"] <= upper
    )


def _daily_series(entries: list[dict[str, Any]], now: datetime) -> list[dict[str, Any]]:
    """Per-UTC-date totals for the last DAILY_DAYS days, oldest first."""
    today = now.date()
    buckets: dict[Any, dict[str, int]] = {}
    for entry in entries:
        day = entry["hour_start"].date()
        if day > today:
            continue
        bucket = buckets.setdefault(day, {"total_tokens": 0, "conversations": 0})
        bucket["total_tokens"] += entry["total_tokens"]
        bucket["conversations"] += entry["conversations"]
    first_day = today - timedelta(days=DAILY_DAYS - 1)
    days = [first_day + timedelta(days=offset) for offset in range(DAILY_DAYS)]
    return [
        {
            "date": day.isoformat(),
            "total_tokens": buckets.get(day, {"total_tokens": 0})["total_tokens"],
            "conversations": buckets.get(day, {"conversations": 0})["conversations"],
        }
        for day in days
    ]


def _breakdown(entries: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    """Aggregate total_tokens/conversations per `key`, largest first."""
    rows: dict[str, dict[str, int]] = {}
    for entry in entries:
        name = entry[key]
        row = rows.setdefault(name, {"total_tokens": 0, "conversations": 0})
        row["total_tokens"] += entry["total_tokens"]
        row["conversations"] += entry["conversations"]
    label = "model" if key == "model" else "source"
    return sorted(
        ({label: name, **row} for name, row in rows.items()),
        key=lambda row: (-row["total_tokens"], row[label]),
    )


def _heatmap(entries: list[dict[str, Any]], now: datetime) -> dict[str, Any]:
    """GitHub-style 52-week heatmap, Sunday-first, ending at now's week."""
    today = now.date()
    final_sunday = today - timedelta(days=today.weekday() + 1)
    first_sunday = final_sunday - timedelta(days=(HEATMAP_WEEKS - 1) * 7)

    days_by_date: dict[Any, int] = {}
    for entry in entries:
        day = entry["hour_start"].date()
        if first_sunday <= day <= today:
            days_by_date[day] = days_by_date.get(day, 0) + entry.get("total_tokens", 0)

    weeks: list[dict[str, Any]] = []
    max_day_tokens = 0
    for week_index in range(HEATMAP_WEEKS):
        start = first_sunday + timedelta(weeks=week_index)
        day_values: list[int] = []
        for day_offset in range(7):
            value = days_by_date.get(start + timedelta(days=day_offset), 0)
            day_values.append(value)
            max_day_tokens = max(max_day_tokens, value)
        weeks.append({"start": start.isoformat(), "days": day_values})

    return {
        "start": first_sunday.isoformat(),
        "max_day_tokens": max_day_tokens,
        "weeks": weeks,
    }


def aggregate_usage(
    entries: list[dict[str, Any]], *, now: datetime | None = None
) -> dict[str, Any]:
    """Aggregate parsed entries into the payload the Usage view renders.

    `now` is injectable for deterministic tests; all windows, the daily
    series, and the heatmap are bounded by it in UTC. Totals and breakdowns
    cover every parsed entry regardless of age.
    """
    now = now or datetime.now(UTC)
    totals = {
        field: sum(entry.get(field, 0) for entry in entries) for field in TOKEN_FIELDS
    }
    totals["total_tokens"] = sum(entry.get("total_tokens", 0) for entry in entries)
    totals["conversations"] = sum(entry.get("conversations", 0) for entry in entries)
    return {
        "total_entries": len(entries),
        "last_updated": (
            max(entry["hour_start"] for entry in entries).isoformat()
            if entries
            else None
        ),
        "totals": totals,
        "windows": {
            name: _sum_tokens(entries, lower=now - span, upper=now)
            for name, span in WINDOW_HOURS.items()
        },
        "daily": _daily_series(entries, now) if entries else [],
        "models": _breakdown(entries, "model"),
        "sources": _breakdown(entries, "source"),
        "heatmap": _heatmap(entries, now),
    }


def usage_payload(home: Path | None = None) -> dict[str, Any]:
    """Assemble everything the admin Usage view renders."""
    home = home or Path.home()
    entries = parse_entries(home)
    return {
        "available": (home / QUEUE_PATH).is_file(),
        **aggregate_usage(entries),
    }
