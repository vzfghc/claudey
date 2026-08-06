"""Unit tests for the native usage log aggregation module."""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from claudey.api import usage_aggregate

NOW = datetime(2026, 8, 6, 12, 0, tzinfo=UTC)


def _write_log(home: Path, lines: list[str]) -> Path:
    log = home / ".claudey" / "usage.jsonl"
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return log


def _line(
    ts: str,
    *,
    provider_id: str = "nvidia_nim",
    provider_model: str = "test-model",
    input_tokens: int | None = 10,
    output_tokens: int | None = 5,
    total_tokens: int | None = None,
    conversations: int = 1,
) -> str:
    payload = {
        "ts": ts,
        "provider_id": provider_id,
        "provider_model": provider_model,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "conversations": conversations,
    }
    if total_tokens is not None:
        payload["total_tokens"] = total_tokens
    return json.dumps(payload)


def _entry(
    ts,
    total_tokens: int,
    conversations: int = 1,
    *,
    provider_id: str = "nvidia_nim",
    model: str = "m1",
) -> dict:
    return {
        "ts": ts,
        "provider_id": provider_id,
        "model": model,
        "total_tokens": total_tokens,
        "conversations": conversations,
    }


def test_parse_line_accepts_full_record():
    line = json.dumps(
        {
            "ts": "2026-08-06T10:00:00+00:00",
            "request_id": "req_1",
            "wire_api": "messages",
            "provider_id": "nvidia_nim",
            "provider_model": "test-model",
            "original_model": "nvidia_nim/test-model",
            "input_tokens": 100,
            "cached_input_tokens": 10,
            "cache_creation_input_tokens": 5,
            "output_tokens": 50,
            "reasoning_output_tokens": 20,
            "total_tokens": 185,
            "conversations": 2,
        }
    )

    entry = usage_aggregate.parse_line(line)

    assert entry is not None
    assert entry["ts"] == datetime(2026, 8, 6, 10, 0, tzinfo=UTC)
    assert entry["provider_id"] == "nvidia_nim"
    assert entry["model"] == "test-model"
    assert entry["input_tokens"] == 100
    assert entry["cached_input_tokens"] == 10
    assert entry["cache_creation_input_tokens"] == 5
    assert entry["output_tokens"] == 50
    assert entry["reasoning_output_tokens"] == 20
    assert entry["total_tokens"] == 185
    assert entry["conversations"] == 2


def test_parse_line_handles_z_suffix_and_naive_timestamps():
    z_entry = usage_aggregate.parse_line(_line("2026-08-05T04:00:00Z"))
    naive_entry = usage_aggregate.parse_line(_line("2026-08-05T04:00:00"))

    assert z_entry is not None
    assert naive_entry is not None
    assert z_entry["ts"] == datetime(2026, 8, 5, 4, 0, tzinfo=UTC)
    assert naive_entry["ts"] == datetime(2026, 8, 5, 4, 0, tzinfo=UTC)


def test_parse_line_accepts_millisecond_timestamps():
    entry = usage_aggregate.parse_line(_line("2026-08-05T09:30:00.123Z"))

    assert entry is not None
    assert entry["ts"] == datetime(2026, 8, 5, 9, 30, 0, 123000, tzinfo=UTC)


def test_parse_line_rejects_records_missing_ts_or_provider_id():
    assert usage_aggregate.parse_line("{not json") is None
    assert usage_aggregate.parse_line("") is None
    assert usage_aggregate.parse_line(_line("not-a-timestamp")) is None
    missing_ts = json.dumps({"provider_id": "p", "provider_model": "m"})
    assert usage_aggregate.parse_line(missing_ts) is None
    missing_provider = json.dumps({"ts": "2026-08-05T04:00:00Z", "provider_model": "m"})
    assert usage_aggregate.parse_line(missing_provider) is None
    missing_model = json.dumps({"ts": "2026-08-05T04:00:00Z", "provider_id": "p"})
    assert usage_aggregate.parse_line(missing_model) is None
    blank_provider = json.dumps(
        {"ts": "2026-08-05T04:00:00Z", "provider_id": "", "provider_model": "m"}
    )
    assert usage_aggregate.parse_line(blank_provider) is None


def test_parse_line_coerces_missing_numbers_and_defaults_conversations():
    line = json.dumps(
        {
            "ts": "2026-08-05T04:00:00Z",
            "provider_id": "p",
            "provider_model": "m",
            "input_tokens": None,
            "output_tokens": 30,
            "total_tokens": 40,
        }
    )

    entry = usage_aggregate.parse_line(line)

    assert entry is not None
    assert entry["input_tokens"] == 0
    assert entry["cached_input_tokens"] == 0
    assert entry["output_tokens"] == 30
    assert entry["conversations"] == 1


def test_parse_line_falls_back_to_component_sum_when_total_missing():
    entry = usage_aggregate.parse_line(
        _line("2026-08-05T04:00:00Z", input_tokens=10, output_tokens=20)
    )

    assert entry is not None
    assert entry["total_tokens"] == 30


def test_parse_line_prefers_explicit_total_tokens():
    entry = usage_aggregate.parse_line(
        _line(
            "2026-08-05T04:00:00Z",
            input_tokens=10,
            output_tokens=20,
            total_tokens=999,
        )
    )

    assert entry is not None
    assert entry["total_tokens"] == 999


def test_parse_entries_skips_torn_and_garbage_lines(tmp_path):
    _write_log(
        tmp_path,
        [
            _line("2026-08-05T04:00:00Z"),
            "not json at all",
            _line("2026-08-05T05:00:00Z", provider_model="m2"),
            "{torn json",
            "",
        ],
    )

    entries = usage_aggregate.parse_entries(tmp_path)

    assert [entry["ts"] for entry in entries] == [
        datetime(2026, 8, 5, 4, 0, tzinfo=UTC),
        datetime(2026, 8, 5, 5, 0, tzinfo=UTC),
    ]


def test_parse_entries_preserves_file_order_without_dedup(tmp_path):
    _write_log(
        tmp_path,
        [
            _line("2026-08-05T04:00:00Z", provider_model="m1", input_tokens=10),
            _line("2026-08-05T04:00:00Z", provider_model="m1", input_tokens=20),
        ],
    )

    entries = usage_aggregate.parse_entries(tmp_path)

    assert [entry["total_tokens"] for entry in entries] == [15, 25]


def test_parse_entries_reads_only_tail_when_file_large(tmp_path, monkeypatch):
    monkeypatch.setattr(usage_aggregate, "MAX_LOG_BYTES", 250)
    lines = [_line(f"2026-08-05T0{i}:00:00Z", provider_model=f"m{i}") for i in range(5)]
    log = _write_log(tmp_path, lines)
    assert log.stat().st_size > 250

    entries = usage_aggregate.parse_entries(tmp_path)

    # Only the tail survived; the line cut by the cap fails to parse.
    assert 0 < len(entries) < 5
    assert entries[-1]["ts"] == datetime(2026, 8, 5, 4, 0, tzinfo=UTC)
    assert all(entry["ts"].hour >= 1 for entry in entries)


def test_usage_payload_degrades_when_empty(tmp_path):
    payload = usage_aggregate.usage_payload(home=tmp_path)

    assert payload["available"] is False
    assert payload["total_entries"] == 0
    assert payload["last_updated"] is None
    assert payload["totals"] == {
        "input_tokens": 0,
        "cached_input_tokens": 0,
        "cache_creation_input_tokens": 0,
        "output_tokens": 0,
        "reasoning_output_tokens": 0,
        "total_tokens": 0,
        "conversations": 0,
    }
    assert payload["windows"] == {"24h": 0, "7d": 0, "30d": 0}
    assert len(payload["daily"]) == 30
    assert all(row["total_tokens"] == 0 for row in payload["daily"])
    assert payload["models"] == []
    assert payload["providers"] == []
    heatmap = payload["heatmap"]
    assert len(heatmap["weeks"]) == 52
    assert all(len(week["days"]) == 7 for week in heatmap["weeks"])
    assert all(cell == 0 for week in heatmap["weeks"] for cell in week["days"])
    assert heatmap["max_day_tokens"] == 0


def test_usage_payload_distinguishes_empty_file(tmp_path):
    _write_log(tmp_path, [])

    payload = usage_aggregate.usage_payload(home=tmp_path)

    assert payload["available"] is True
    assert payload["total_entries"] == 0


def test_usage_payload_unreadable_file_degrades_without_raising(tmp_path):
    log = tmp_path / ".claudey" / "usage.jsonl"
    log.parent.mkdir(parents=True)
    log.mkdir()  # a directory named usage.jsonl cannot be read as a file

    payload = usage_aggregate.usage_payload(home=tmp_path)

    assert payload["available"] is False
    assert payload["total_entries"] == 0


def test_aggregate_windows_use_exclusive_lower_and_inclusive_upper_bounds():
    entries = [
        _entry(NOW, 10),
        _entry(NOW - timedelta(hours=24), 20),
        _entry(NOW - timedelta(hours=24, seconds=1), 40),
    ]

    payload = usage_aggregate.aggregate_usage(entries, now=NOW)

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

    payload = usage_aggregate.aggregate_usage(entries, now=NOW)

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

    payload = usage_aggregate.aggregate_usage(entries, now=NOW)

    assert len(payload["daily"]) == 30
    assert payload["daily"][0] == {
        "date": "2026-07-08",
        "input_tokens": 0,
        "cached_input_tokens": 0,
        "cache_creation_input_tokens": 0,
        "output_tokens": 0,
        "reasoning_output_tokens": 0,
        "total_tokens": 20,
        "conversations": 2,
    }
    assert payload["daily"][28] == {
        "date": "2026-08-05",
        "input_tokens": 0,
        "cached_input_tokens": 0,
        "cache_creation_input_tokens": 0,
        "output_tokens": 0,
        "reasoning_output_tokens": 0,
        "total_tokens": 10,
        "conversations": 1,
    }
    assert payload["daily"][-1] == {
        "date": "2026-08-06",
        "input_tokens": 0,
        "cached_input_tokens": 0,
        "cache_creation_input_tokens": 0,
        "output_tokens": 0,
        "reasoning_output_tokens": 0,
        "total_tokens": 0,
        "conversations": 0,
    }
    dates = [row["date"] for row in payload["daily"]]
    assert dates == sorted(dates)
    # Future-dated entry must not appear anywhere in the series.
    assert all(row["total_tokens"] != 9999 for row in payload["daily"])


def test_aggregate_models_and_providers_grouped_and_sorted():
    entries = [
        _entry(NOW, 40, provider_id="p2", model="m2"),
        _entry(NOW, 50, conversations=2, provider_id="p1", model="m2"),
        _entry(NOW, 50, conversations=3, provider_id="p1", model="m1"),
        _entry(NOW, 50, provider_id="p1", model="m0"),
        _entry(NOW, 10, provider_id="p1", model="m3"),
    ]

    payload = usage_aggregate.aggregate_usage(entries, now=NOW)

    # Descending by tokens; ties broken by model name ascending.
    assert payload["models"] == [
        {"model": "m0", "provider_id": "p1", "total_tokens": 50, "conversations": 1},
        {"model": "m1", "provider_id": "p1", "total_tokens": 50, "conversations": 3},
        {"model": "m2", "provider_id": "p1", "total_tokens": 50, "conversations": 2},
        {"model": "m2", "provider_id": "p2", "total_tokens": 40, "conversations": 1},
        {"model": "m3", "provider_id": "p1", "total_tokens": 10, "conversations": 1},
    ]
    assert payload["providers"] == [
        {"provider": "p1", "total_tokens": 160, "conversations": 7, "model_count": 4},
        {"provider": "p2", "total_tokens": 40, "conversations": 1, "model_count": 1},
    ]


def test_aggregate_heatmap_52_weeks_sunday_first():
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

    payload = usage_aggregate.aggregate_usage(entries, now=NOW)

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


def test_aggregate_heatmap_final_week_contains_now_on_sunday():
    sunday_now = datetime(2026, 8, 9, 6, 0, tzinfo=UTC)  # a Sunday

    payload = usage_aggregate.aggregate_usage([], now=sunday_now)

    heatmap = payload["heatmap"]
    assert heatmap["weeks"][-1]["start"] == "2026-08-09"


def test_aggregate_last_updated_is_max_ts():
    entries = [
        _entry(datetime(2026, 8, 1, 4, 0, tzinfo=UTC), 1, conversations=0),
        _entry(datetime(2026, 8, 5, 4, 0, tzinfo=UTC), 1, conversations=0),
        _entry(datetime(2026, 8, 3, 4, 0, tzinfo=UTC), 1, conversations=0),
    ]

    payload = usage_aggregate.aggregate_usage(entries, now=NOW)

    assert payload["last_updated"] == "2026-08-05T04:00:00+00:00"
    assert payload["total_entries"] == 3


def test_aggregate_sums_conversations():
    entries = [
        _entry(NOW, 1, conversations=5),
        _entry(NOW - timedelta(hours=1), 1, conversations=7),
    ]

    payload = usage_aggregate.aggregate_usage(entries, now=NOW)

    assert payload["totals"]["conversations"] == 12
