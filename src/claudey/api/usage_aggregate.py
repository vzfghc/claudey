"""Native usage log aggregation for the admin "Usage" view.

Claudey's recorder (claudey.application.usage_recorder) appends one JSONL
line per provider-served request at the final message_delta usage:

    {"ts": "2026-08-06T10:00:00+00:00", "request_id": "req_...",
     "wire_api": "messages", "provider_id": "nvidia_nim",
     "provider_model": "test-model", "original_model": "...",
     "input_tokens": ..., "cached_input_tokens": ..., ...,
     "total_tokens": ..., "conversations": 1}

This module turns that log into the aggregates the admin "Usage" view
renders: window totals, a daily series, per-model/per-provider breakdowns,
and a 52-week heatmap. Every source is optional — a machine with no traffic
has no log file, a torn line may appear mid-write, and the log grows
unbounded — so each lookup degrades to empty values instead of raising, and
the view always renders.
"""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from claudey.application.usage_recorder import TOKEN_FIELDS, USAGE_LOG_FILENAME
from claudey.config.paths import CLAUDEY_CONFIG_DIRNAME

MAX_LOG_BYTES = 10_000_000  # read only the recent tail of the usage log

WINDOW_HOURS = {
    "24h": timedelta(hours=24),
    "7d": timedelta(hours=168),
    "30d": timedelta(hours=720),
}
DAILY_DAYS = 30
HEATMAP_WEEKS = 52

_DAY_FIELDS = (*TOKEN_FIELDS, "total_tokens", "conversations")


def _to_int(value: Any) -> int | None:
    try:
        return int(value)
    except TypeError, ValueError:
        return None


def _parse_ts(value: Any) -> datetime | None:
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
    """Parse one usage-log line into a normalized entry, or None when unusable."""
    try:
        raw = json.loads(line)
    except json.JSONDecodeError:
        return None
    if not isinstance(raw, dict):
        return None
    ts = _parse_ts(raw.get("ts"))
    provider_id = raw.get("provider_id")
    provider_model = raw.get("provider_model")
    if ts is None or not isinstance(provider_id, str) or not provider_id:
        return None
    if not isinstance(provider_model, str) or not provider_model:
        return None

    tokens = {field: _to_int(raw.get(field)) or 0 for field in TOKEN_FIELDS}
    total_tokens = _to_int(raw.get("total_tokens"))
    if total_tokens is None:
        total_tokens = sum(tokens.values())
    conversations = _to_int(raw.get("conversations"))
    return {
        "ts": ts,
        "provider_id": provider_id,
        "model": provider_model,
        **tokens,
        "total_tokens": total_tokens,
        "conversations": conversations if conversations is not None else 1,
    }


def _usage_file(home: Path) -> Path:
    return home / CLAUDEY_CONFIG_DIRNAME / USAGE_LOG_FILENAME


def parse_entries(home: Path) -> list[dict[str, Any]]:
    """Parse the usage log, reading only its recent tail when oversized.

    Each line is one request record, so no dedup is needed; file order is
    preserved. Torn or unparsable lines are skipped.
    """
    log = _usage_file(home)
    try:
        data = log.read_text(encoding="utf-8")
    except OSError:
        return []
    if len(data) > MAX_LOG_BYTES:
        data = data[-MAX_LOG_BYTES:]

    entries: list[dict[str, Any]] = []
    for line in data.splitlines():
        entry = parse_line(line)
        if entry is None:
            continue
        entries.append(entry)
    return entries


def _sum_tokens(
    entries: list[dict[str, Any]], *, lower: datetime, upper: datetime
) -> int:
    return sum(
        entry.get("total_tokens", 0)
        for entry in entries
        if lower < entry["ts"] <= upper
    )


def _empty_day() -> dict[str, int]:
    return dict.fromkeys(_DAY_FIELDS, 0)


def _daily_series(entries: list[dict[str, Any]], now: datetime) -> list[dict[str, Any]]:
    """Per-UTC-date totals for the last DAILY_DAYS days, oldest first."""
    today = now.date()
    buckets: dict[Any, dict[str, int]] = {}
    for entry in entries:
        day = entry["ts"].date()
        if day > today:
            continue
        bucket = buckets.setdefault(day, _empty_day())
        for field in _DAY_FIELDS:
            bucket[field] += entry.get(field, 0)
    first_day = today - timedelta(days=DAILY_DAYS - 1)
    days = [first_day + timedelta(days=offset) for offset in range(DAILY_DAYS)]
    return [{"date": day.isoformat(), **buckets.get(day, _empty_day())} for day in days]


def _models_breakdown(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Aggregate total_tokens/conversations per (model, provider), largest first."""
    rows: dict[tuple[str, str], dict[str, int]] = {}
    for entry in entries:
        key = (entry["model"], entry["provider_id"])
        row = rows.setdefault(key, {"total_tokens": 0, "conversations": 0})
        row["total_tokens"] += entry["total_tokens"]
        row["conversations"] += entry["conversations"]
    return sorted(
        (
            {"model": model, "provider_id": provider_id, **row}
            for (model, provider_id), row in rows.items()
        ),
        key=lambda row: (-row["total_tokens"], row["model"]),
    )


def _providers_breakdown(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Aggregate per provider with distinct-model counts, largest first."""
    totals: dict[str, dict[str, int]] = {}
    models: dict[str, set[str]] = {}
    for entry in entries:
        provider = entry["provider_id"]
        row = totals.setdefault(provider, {"total_tokens": 0, "conversations": 0})
        row["total_tokens"] += entry["total_tokens"]
        row["conversations"] += entry["conversations"]
        models.setdefault(provider, set()).add(entry["model"])
    return sorted(
        (
            {"provider": provider, **row, "model_count": len(models[provider])}
            for provider, row in totals.items()
        ),
        key=lambda row: (-row["total_tokens"], row["provider"]),
    )


def _heatmap(entries: list[dict[str, Any]], now: datetime) -> dict[str, Any]:
    """GitHub-style 52-week heatmap, Sunday-first, ending at now's week."""
    today = now.date()
    final_sunday = today - timedelta(days=(today.weekday() + 1) % 7)
    first_sunday = final_sunday - timedelta(days=(HEATMAP_WEEKS - 1) * 7)

    days_by_date: dict[Any, int] = {}
    for entry in entries:
        day = entry["ts"].date()
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
            max(entry["ts"] for entry in entries).isoformat() if entries else None
        ),
        "totals": totals,
        "windows": {
            name: _sum_tokens(entries, lower=now - span, upper=now)
            for name, span in WINDOW_HOURS.items()
        },
        "daily": _daily_series(entries, now),
        "models": _models_breakdown(entries),
        "providers": _providers_breakdown(entries),
        "heatmap": _heatmap(entries, now),
    }


def _log_is_readable(log: Path) -> bool:
    """True when the log exists and can actually be opened for reading."""
    if not log.is_file():
        return False
    try:
        with log.open(encoding="utf-8") as stream:
            stream.read(1)
    except OSError:
        return False
    return True


def usage_payload(home: Path | None = None) -> dict[str, Any]:
    """Assemble everything the admin Usage view renders."""
    home = home or Path.home()
    return {
        "available": _log_is_readable(_usage_file(home)),
        **aggregate_usage(parse_entries(home)),
    }
