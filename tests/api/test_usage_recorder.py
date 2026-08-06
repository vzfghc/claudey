"""Unit tests for the native usage recorder."""

import json
from pathlib import Path

import pytest

from claudey.application import usage_recorder
from claudey.application.routing import ResolvedModel
from claudey.config.reasoning import ReasoningPreference
from claudey.core.anthropic.streaming import format_sse_event

_TEST_RESOLVED = ResolvedModel(
    original_model="nvidia_nim/test-model",
    provider_id="nvidia_nim",
    provider_model="test-model",
    provider_model_ref="nvidia_nim/test-model",
    reasoning_preference=ReasoningPreference.CLIENT,
)


def _set_home(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.chdir(tmp_path)


def _log_records(tmp_path: Path) -> list[dict]:
    log = tmp_path / ".claudey" / "usage.jsonl"
    return [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]


def test_record_usage_appends_one_jsonl_line_with_all_fields(monkeypatch, tmp_path):
    _set_home(monkeypatch, tmp_path)

    usage_recorder.record_usage(
        request_id="req_1",
        wire_api="messages",
        provider_id="nvidia_nim",
        provider_model="test-model",
        original_model="nvidia_nim/test-model",
        usage={
            "input_tokens": 10,
            "output_tokens": 5,
            "cache_read_input_tokens": 2,
        },
    )

    records = _log_records(tmp_path)
    assert len(records) == 1
    record = records[0]
    assert record["ts"]
    assert record["request_id"] == "req_1"
    assert record["wire_api"] == "messages"
    assert record["provider_id"] == "nvidia_nim"
    assert record["provider_model"] == "test-model"
    assert record["original_model"] == "nvidia_nim/test-model"
    assert record["input_tokens"] == 10
    assert record["cached_input_tokens"] == 2
    assert record["cache_creation_input_tokens"] == 0
    assert record["output_tokens"] == 5
    assert record["reasoning_output_tokens"] == 0
    assert record["total_tokens"] == 17
    assert record["conversations"] == 1


def test_normalize_usage_maps_aliases_and_coerces():
    normalized = usage_recorder.normalize_usage(
        {
            "input_tokens": 10,
            "output_tokens": "5",
            "cache_read_input_tokens": 2,
            "reasoning_tokens": 3,
            "unknown_key": "ignored",
        }
    )

    assert normalized == {
        "input_tokens": 10,
        "cached_input_tokens": 2,
        "cache_creation_input_tokens": 0,
        "output_tokens": 5,
        "reasoning_output_tokens": 3,
    }
    assert sum(normalized.values()) == 20


def test_normalize_usage_zeroes_missing_and_invalid_values():
    assert usage_recorder.normalize_usage({}) == {
        "input_tokens": 0,
        "cached_input_tokens": 0,
        "cache_creation_input_tokens": 0,
        "output_tokens": 0,
        "reasoning_output_tokens": 0,
    }
    assert usage_recorder.normalize_usage({"output_tokens": None})["output_tokens"] == 0
    assert (
        usage_recorder.normalize_usage({"output_tokens": "abc"})["output_tokens"] == 0
    )
    assert usage_recorder.normalize_usage({"output_tokens": 3.9})["output_tokens"] == 3


def test_record_usage_never_raises_when_log_path_unwritable(monkeypatch, tmp_path):
    missing_dir = tmp_path / "no" / "such" / "dir"
    monkeypatch.setattr(
        usage_recorder,
        "usage_log_path",
        lambda: missing_dir / "usage.jsonl",
    )

    # Must not raise: open() fails with an OSError and is traced, not raised.
    usage_recorder.record_usage(
        request_id="req_1",
        wire_api="messages",
        provider_id="p",
        provider_model="m",
        original_model="p/m",
        usage={"input_tokens": 1},
    )


@pytest.mark.asyncio
async def test_observe_usage_passes_chunks_through_and_records_once(
    monkeypatch, tmp_path
):
    _set_home(monkeypatch, tmp_path)
    chunks = [
        format_sse_event("message_start", {"type": "message_start"}),
        format_sse_event(
            "content_block_delta",
            {
                "type": "content_block_delta",
                "index": 0,
                "delta": {"type": "text_delta", "text": "hi"},
            },
        ),
        format_sse_event(
            "message_delta",
            {
                "type": "message_delta",
                "delta": {"stop_reason": "end_turn", "stop_sequence": None},
                "usage": {
                    "input_tokens": 10,
                    "output_tokens": 5,
                    "cache_read_input_tokens": 2,
                },
            },
        ),
        format_sse_event("message_stop", {"type": "message_stop"}),
    ]

    async def stream():
        for chunk in chunks:
            yield chunk

    collected = [
        chunk
        async for chunk in usage_recorder.observe_usage(
            stream(),
            request_id="req_1",
            wire_api="messages",
            resolved=_TEST_RESOLVED,
        )
    ]

    assert collected == chunks
    records = _log_records(tmp_path)
    assert len(records) == 1
    record = records[0]
    assert record["request_id"] == "req_1"
    assert record["wire_api"] == "messages"
    assert record["provider_id"] == "nvidia_nim"
    assert record["provider_model"] == "test-model"
    assert record["cached_input_tokens"] == 2
    assert record["input_tokens"] == 10
    assert record["total_tokens"] == 17


@pytest.mark.asyncio
async def test_observe_usage_records_only_once_across_two_message_deltas(
    monkeypatch, tmp_path
):
    _set_home(monkeypatch, tmp_path)
    chunks = [
        format_sse_event(
            "message_delta",
            {
                "type": "message_delta",
                "delta": {"stop_reason": "end_turn"},
                "usage": {"input_tokens": 10},
            },
        ),
        format_sse_event(
            "message_delta",
            {
                "type": "message_delta",
                "delta": {"stop_reason": "end_turn"},
                "usage": {"input_tokens": 99},
            },
        ),
    ]

    async def stream():
        for chunk in chunks:
            yield chunk

    collected = [
        chunk
        async for chunk in usage_recorder.observe_usage(
            stream(),
            request_id="req_1",
            wire_api="messages",
            resolved=_TEST_RESOLVED,
        )
    ]

    assert collected == chunks
    records = _log_records(tmp_path)
    assert len(records) == 1
    assert records[0]["input_tokens"] == 10


@pytest.mark.asyncio
async def test_observe_usage_with_no_usage_never_records():
    chunks = [
        format_sse_event("message_start", {"type": "message_start"}),
        format_sse_event(
            "message_delta",
            {"type": "message_delta", "delta": {"stop_reason": "end_turn"}},
        ),
        format_sse_event("message_stop", {"type": "message_stop"}),
    ]

    async def stream():
        for chunk in chunks:
            yield chunk

    calls = []

    def on_record(**kwargs):
        calls.append(kwargs)

    collected = [
        chunk
        async for chunk in usage_recorder.observe_usage(
            stream(),
            request_id="req_1",
            wire_api="messages",
            resolved=_TEST_RESOLVED,
            on_record=on_record,
        )
    ]

    assert collected == chunks
    assert calls == []


@pytest.mark.asyncio
async def test_observe_usage_torn_final_chunk_still_records(monkeypatch, tmp_path):
    _set_home(monkeypatch, tmp_path)
    chunks = [
        format_sse_event("message_start", {"type": "message_start"}),
        # No trailing blank line: the event is torn mid-write.
        'event: message_delta\ndata: {"type":"message_delta","usage":{"input_tokens":7}}',
    ]

    async def stream():
        for chunk in chunks:
            yield chunk

    collected = [
        chunk
        async for chunk in usage_recorder.observe_usage(
            stream(),
            request_id="req_1",
            wire_api="messages",
            resolved=_TEST_RESOLVED,
        )
    ]

    assert collected == chunks
    records = _log_records(tmp_path)
    assert len(records) == 1
    assert records[0]["input_tokens"] == 7


@pytest.mark.asyncio
async def test_observe_usage_garbage_chunks_pass_through_without_raising():
    chunks = ["this is not sse at all", "no blank line here", "{"]

    async def stream():
        for chunk in chunks:
            yield chunk

    calls = []

    def on_record(**kwargs):
        calls.append(kwargs)

    collected = [
        chunk
        async for chunk in usage_recorder.observe_usage(
            stream(),
            request_id="req_1",
            wire_api="messages",
            resolved=_TEST_RESOLVED,
            on_record=on_record,
        )
    ]

    assert collected == chunks
    assert calls == []
