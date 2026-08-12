"""Unit tests for the shared incremental SSE parser."""

import pytest

from claudey.core.anthropic.sse_parser import SseEventSplitter, iter_raw_sse_events


async def _aiter(chunks: list[bytes | str]):
    for chunk in chunks:
        yield chunk


async def _collect(
    chunks: list[bytes | str], *, flush_trailing: bool = False
) -> list[str]:
    return [
        raw
        async for raw in iter_raw_sse_events(
            _aiter(chunks), flush_trailing=flush_trailing
        )
    ]


@pytest.mark.asyncio
async def test_one_event_per_chunk():
    events = await _collect(["event: a\ndata: 1\n\n"])
    assert events == ["event: a\ndata: 1"]


@pytest.mark.asyncio
async def test_many_events_per_chunk():
    events = await _collect(["e1\n\ne2\n\ne3\n\n"])
    assert events == ["e1", "e2", "e3"]


@pytest.mark.asyncio
async def test_events_split_across_chunk_boundaries():
    events = await _collect(["event: a\nda", "ta: 1\n\nevent: b\ndata: 2\n\n"])
    assert events == ["event: a\ndata: 1", "event: b\ndata: 2"]


@pytest.mark.asyncio
async def test_empty_chunks_are_ignored():
    events = await _collect(["", "event: a\n\n", "", "event: b\n\n"])
    assert events == ["event: a", "event: b"]


@pytest.mark.asyncio
async def test_bytes_and_str_chunks_mix():
    events = await _collect([b"event: a\n\n", "event: b\n\n"])
    assert events == ["event: a", "event: b"]


@pytest.mark.asyncio
async def test_bytes_chunk_decoded_with_replacement():
    events = await _collect([b"event: a\n\xff\n\n"])
    assert events == ["event: a\n�"]


@pytest.mark.asyncio
async def test_trailing_partial_dropped_without_flush():
    events = await _collect(["event: a\n\n", "event: partial"])
    assert events == ["event: a"]


@pytest.mark.asyncio
async def test_trailing_partial_flushed_when_requested():
    events = await _collect(["event: a\n\n", "event: partial"], flush_trailing=True)
    assert events == ["event: a", "event: partial"]


@pytest.mark.asyncio
async def test_whitespace_only_trailing_dropped_even_with_flush():
    events = await _collect(["event: a\n\n", "   \n"], flush_trailing=True)
    assert events == ["event: a"]


def test_splitter_feed_returns_completed_events_and_keeps_partial():
    splitter = SseEventSplitter()
    assert splitter.feed("event: a\n\nevent: b\n\nevent: c") == [
        "event: a",
        "event: b",
    ]
    assert splitter.trailing() == "event: c"


def test_splitter_keeps_partial_across_chunks():
    splitter = SseEventSplitter()
    assert splitter.feed("event: a\nda") == []
    assert splitter.feed("ta: 1\n\n") == ["event: a\ndata: 1"]
    assert splitter.trailing() is None
