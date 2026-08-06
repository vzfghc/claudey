"""Unit tests for the TokenTracker usage aggregation module."""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from claudey.api import tokentracker_usage

NOW = datetime(2026, 8, 6, 12, 0, tzinfo=UTC)


def _write_queue(home: Path, lines: list[str]) -> Path:
    queue = home / ".tokentracker" / "queue.jsonl"
    queue.parent.mkdir(parents=True, exist_ok=True)
    queue.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return queue


def _line(
    hour_start: str,
    *,
    source: str = "claude-code",
    model: str = "anthropic/claude-sonnet-4-5",
    input_tokens: int | None = 100,
    output_tokens: int | None = 50,
    total_tokens: int | None = None,
    conversations: int = 1,
) -> str:
    payload = {
        "hour_start": hour_start,
        "source": source,
        "model": model,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "conversation_count": conversations,
    }
    if total_tokens is not None:
        payload["total_tokens"] = total_tokens
    return json.dumps(payload)


def _entry(
    hour_start,
    total_tokens: int,
    conversations: int = 1,
    *,
    source: str = "claude-code",
    model: str = "m1",
) -> dict:
    return {
        "hour_start": hour_start,
        "source": source,
        "model": model,
        "total_tokens": total_tokens,
        "conversations": conversations,
    }


def test_parse_line_accepts_full_entry():
    line = json.dumps(
        {
            "hour_start": "2026-08-06T10:00:00Z",
            "source": "claude-code",
            "model": "anthropic/claude-sonnet-4-5",
            "input_tokens": 100,
            "cached_input_tokens": 10,
            "cache_creation_input_tokens": 5,
            "output_tokens": 50,
            "reasoning_output_tokens": 20,
            "total_tokens": 185,
            "conversation_count": 2,
        }
    )

    entry = tokentracker_usage.parse_line(line)

    assert entry is not None
    assert entry["hour_start"] == datetime(2026, 8, 6, 10, 0, tzinfo=UTC)
    assert entry["source"] == "claude-code"
    assert entry["model"] == "anthropic/claude-sonnet-4-5"
    assert entry["input_tokens"] == 100
    assert entry["cached_input_tokens"] == 10
    assert entry["cache_creation_input_tokens"] == 5
    assert entry["output_tokens"] == 50
    assert entry["reasoning_output_tokens"] == 20
    assert entry["total_tokens"] == 185
    assert entry["conversations"] == 2


def test_parse_line_handles_z_suffix_and_naive_timestamps():
    z_entry = tokentracker_usage.parse_line(_line("2026-08-05T04:00:00Z"))
    naive_entry = tokentracker_usage.parse_line(_line("2026-08-05T04:00:00"))

    assert z_entry is not None
    assert naive_entry is not None
    assert z_entry["hour_start"] == datetime(2026, 8, 5, 4, 0, tzinfo=UTC)
    assert naive_entry["hour_start"] == datetime(2026, 8, 5, 4, 0, tzinfo=UTC)


def test_parse_line_rejects_corrupt_json_and_missing_keys():
    assert tokentracker_usage.parse_line("{not json") is None
    assert tokentracker_usage.parse_line("") is None
    assert tokentracker_usage.parse_line(_line("not-a-timestamp")) is None
    assert (
        tokentracker_usage.parse_line(_line("2026-08-05T04:00:00Z", source="")) is None
    )
    assert (
        tokentracker_usage.parse_line(_line("2026-08-05T04:00:00Z", model="")) is None
    )
    missing_hour = json.dumps({"source": "claude-code", "model": "m"})
    assert tokentracker_usage.parse_line(missing_hour) is None


def test_parse_line_coerces_missing_numeric_fields_to_zero():
    line = json.dumps(
        {
            "hour_start": "2026-08-05T04:00:00Z",
            "source": "claude-code",
            "model": "m",
            "input_tokens": None,
            "output_tokens": 30,
            "total_tokens": 40,
        }
    )

    entry = tokentracker_usage.parse_line(line)

    assert entry is not None
    assert entry["input_tokens"] == 0
    assert entry["cached_input_tokens"] == 0
    assert entry["output_tokens"] == 30
    assert entry["conversations"] == 0


def test_parse_line_falls_back_to_component_sum_when_total_missing():
    line = _line("2026-08-05T04:00:00Z", input_tokens=10, output_tokens=20)

    entry = tokentracker_usage.parse_line(line)

    assert entry is not None
    assert entry["total_tokens"] == 30


def test_parse_line_prefers_explicit_total_tokens():
    line = _line(
        "2026-08-05T04:00:00Z", input_tokens=10, output_tokens=20, total_tokens=999
    )

    entry = tokentracker_usage.parse_line(line)

    assert entry is not None
    assert entry["total_tokens"] == 999


def test_parse_entries_dedupes_latest_per_source_model_hour(tmp_path):
    queue = _write_queue(
        tmp_path,
        [
            _line("2026-08-05T04:00:00Z", model="m1", input_tokens=10),
            _line("2026-08-05T04:00:00Z", model="m1", input_tokens=20),
            _line("2026-08-05T04:00:00Z", model="m2", input_tokens=30),
            _line("2026-08-05T05:00:00Z", model="m1", input_tokens=40),
        ],
    )
    assert queue.is_file()

    entries = tokentracker_usage.parse_entries(tmp_path)

    assert [entry["input_tokens"] for entry in entries] == [20, 30, 40]


def test_parse_entries_skips_corrupt_lines(tmp_path):
    _write_queue(
        tmp_path,
        [
            _line("2026-08-05T04:00:00Z"),
            "not json at all",
            _line("2026-08-05T05:00:00Z"),
            "",
        ],
    )

    entries = tokentracker_usage.parse_entries(tmp_path)

    assert len(entries) == 2
    assert entries[0]["hour_start"] == datetime(2026, 8, 5, 4, 0, tzinfo=UTC)
    assert entries[1]["hour_start"] == datetime(2026, 8, 5, 5, 0, tzinfo=UTC)


def test_parse_entries_reads_only_tail_when_file_large(tmp_path, monkeypatch):
    monkeypatch.setattr(tokentracker_usage, "MAX_QUEUE_BYTES", 250)
    lines = [
        _line(f"2026-08-05T0{i}:00:00Z", model=f"m{i}", input_tokens=100)
        for i in range(5)
    ]
    queue = _write_queue(tmp_path, lines)
    assert queue.stat().st_size > 250

    entries = tokentracker_usage.parse_entries(tmp_path)

    # Only the tail survived; the line cut by the cap fails to parse.
    assert 0 < len(entries) < 5
    assert entries[-1]["hour_start"] == datetime(2026, 8, 5, 4, 0, tzinfo=UTC)
    assert all(entry["hour_start"].hour >= 1 for entry in entries)


def test_usage_payload_degrades_when_file_missing(tmp_path):
    payload = tokentracker_usage.usage_payload(home=tmp_path)

    assert payload["available"] is False
    assert payload["total_entries"] == 0
    assert payload["last_updated"] is None
    assert payload["totals"]["total_tokens"] == 0
    assert payload["windows"] == {"24h": 0, "7d": 0, "30d": 0}
    assert payload["daily"] == []
    assert payload["models"] == []
    assert payload["sources"] == []
    assert payload["heatmap"]["weeks"]


def test_usage_payload_distinguishes_empty_file(tmp_path):
    _write_queue(tmp_path, [])

    payload = tokentracker_usage.usage_payload(home=tmp_path)

    assert payload["available"] is True
    assert payload["total_entries"] == 0
    assert payload["last_updated"] is None


def test_aggregate_windows_use_exclusive_lower_and_inclusive_upper_bounds():
    entries = [
        _entry(NOW, 10),
        _entry(NOW - timedelta(hours=24), 20),
        _entry(NOW - timedelta(hours=24, seconds=1), 40),
    ]

    payload = tokentracker_usage.aggregate_usage(entries, now=NOW)

    # Exactly `now` is included; exactly `now - 24h` is excluded (open lower bound).
    assert payload["windows"]["24h"] == 10
    assert payload["windows"]["7d"] == 70
    assert payload["windows"]["30d"] == 70


def test_aggregate_totals_and_windows():
    entries = [
        {
            **_entry(NOW - timedelta(hours=2), 15),
            "input_tokens": 10,
            "output_tokens": 5,
        },
        {
            **_entry(NOW - timedelta(days=2), 150, conversations=2),
            "input_tokens": 100,
            "output_tokens": 50,
        },
        {
            **_entry(NOW - timedelta(days=20), 1500, conversations=3),
            "input_tokens": 1000,
            "output_tokens": 500,
        },
        {
            **_entry(NOW - timedelta(days=100), 15000, conversations=4),
            "input_tokens": 10000,
            "output_tokens": 5000,
        },
    ]

    payload = tokentracker_usage.aggregate_usage(entries, now=NOW)

    assert payload["windows"] == {"24h": 15, "7d": 165, "30d": 1665}
    assert payload["totals"]["input_tokens"] == 11110
    assert payload["totals"]["output_tokens"] == 5555
    assert payload["totals"]["total_tokens"] == 16665
    assert payload["totals"]["conversations"] == 10


def test_aggregate_daily_series_covers_last_30_utc_dates_ascending():
    entries = [
        _entry(NOW - timedelta(days=1), 10),
        _entry(NOW - timedelta(days=29), 20, conversations=2),
        _entry(NOW + timedelta(days=1), 9999, conversations=9),
    ]

    payload = tokentracker_usage.aggregate_usage(entries, now=NOW)

    assert len(payload["daily"]) == 30
    assert payload["daily"][0] == {
        "date": "2026-07-08",
        "total_tokens": 20,
        "conversations": 2,
    }
    assert payload["daily"][28] == {
        "date": "2026-08-05",
        "total_tokens": 10,
        "conversations": 1,
    }
    assert payload["daily"][-1] == {
        "date": "2026-08-06",
        "total_tokens": 0,
        "conversations": 0,
    }
    dates = [row["date"] for row in payload["daily"]]
    assert dates == sorted(dates)
    # Future-dated entry must not appear anywhere in the series.
    assert all(row["total_tokens"] != 9999 for row in payload["daily"])


def test_aggregate_model_and_source_breakdowns_sorted():
    entries = [
        _entry(NOW, 40, source="claude-code", model="m2"),
        _entry(NOW, 50, conversations=2, source="cursor", model="m2"),
        _entry(NOW, 50, conversations=3, source="claude-code", model="m1"),
        _entry(NOW, 50, source="cursor", model="m0"),
        _entry(NOW, 10, source="cursor", model="m3"),
    ]

    payload = tokentracker_usage.aggregate_usage(entries, now=NOW)

    # Descending by tokens; m0/m1 tie broken by name ascending.
    assert payload["models"] == [
        {"model": "m2", "total_tokens": 90, "conversations": 3},
        {"model": "m0", "total_tokens": 50, "conversations": 1},
        {"model": "m1", "total_tokens": 50, "conversations": 3},
        {"model": "m3", "total_tokens": 10, "conversations": 1},
    ]
    assert payload["sources"] == [
        {"source": "cursor", "total_tokens": 110, "conversations": 4},
        {"source": "claude-code", "total_tokens": 90, "conversations": 4},
    ]


def test_aggregate_heatmap_52_weeks_sunday_start():
    entries = [
        # 2026-08-03 is the Monday of the week starting 2026-08-02.
        _entry(datetime(2026, 8, 3, 4, 0, tzinfo=UTC), 100),
        # 2026-08-06 is the Thursday of that same week.
        _entry(datetime(2026, 8, 6, 4, 0, tzinfo=UTC), 200),
        # One full week earlier: Monday 2026-07-27.
        _entry(datetime(2026, 7, 27, 4, 0, tzinfo=UTC), 300),
        # Future-dated, must be excluded from the heatmap.
        _entry(datetime(2026, 8, 7, 4, 0, tzinfo=UTC), 9999),
    ]

    payload = tokentracker_usage.aggregate_usage(entries, now=NOW)

    heatmap = payload["heatmap"]
    assert len(heatmap["weeks"]) == 52
    assert all(len(week["days"]) == 7 for week in heatmap["weeks"])
    assert heatmap["start"] == "2025-08-10"
    assert heatmap["weeks"][0]["start"] == "2025-08-10"
    # Last week starts on the Sunday of the week containing `now`.
    assert heatmap["weeks"][-1]["start"] == "2026-08-02"
    # Sunday-first: Monday is index 1, Thursday is index 4.
    assert heatmap["weeks"][-1]["days"][1] == 100
    assert heatmap["weeks"][-1]["days"][4] == 200
    assert heatmap["weeks"][-2]["days"][1] == 300
    assert heatmap["max_day_tokens"] == 300
    assert all(cell != 9999 for week in heatmap["weeks"] for cell in week["days"])


def test_aggregate_last_updated_is_max_hour_start():
    entries = [
        _entry(datetime(2026, 8, 1, 4, 0, tzinfo=UTC), 1, conversations=0),
        _entry(datetime(2026, 8, 5, 4, 0, tzinfo=UTC), 1, conversations=0),
        _entry(datetime(2026, 8, 3, 4, 0, tzinfo=UTC), 1, conversations=0),
    ]

    payload = tokentracker_usage.aggregate_usage(entries, now=NOW)

    assert payload["last_updated"] == "2026-08-05T04:00:00+00:00"
    assert payload["total_entries"] == 3


def test_aggregate_sums_conversations():
    entries = [
        _entry(NOW, 1, conversations=5),
        _entry(NOW - timedelta(hours=1), 1, conversations=7),
    ]

    payload = tokentracker_usage.aggregate_usage(entries, now=NOW)

    assert payload["totals"]["conversations"] == 12
