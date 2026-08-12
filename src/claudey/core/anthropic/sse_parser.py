"""Incremental SSE event-boundary splitting shared across claudey layers.

Only chunk buffering and ``\\n\\n`` boundary splitting live here. Each
consumer keeps its own event interpretation (``parse_sse_text``,
``parse_sse_event``, ...): this module turns a chunk stream into raw event
texts and leaves parsing to each call site.
"""

from collections.abc import AsyncIterable, AsyncIterator

__all__ = ["SseEventSplitter", "iter_raw_sse_events"]


class SseEventSplitter:
    """Accumulate SSE chunks and split them on ``\\n\\n`` event boundaries.

    Chunks may be bytes or str; bytes are decoded as UTF-8 with replacement
    (matching the wire adapters). Each :meth:`feed` returns the raw event
    texts completed by that chunk, keeping any trailing partial buffered for
    the next chunk. A partial event left at the end of the stream is exposed
    via :meth:`trailing`.
    """

    def __init__(self) -> None:
        self._chunks: list[str] = []

    def feed(self, chunk: bytes | str) -> list[str]:
        """Return the raw event texts (without ``\\n\\n``) completed by chunk."""
        if isinstance(chunk, bytes):
            text = chunk.decode("utf-8", errors="replace")
        elif isinstance(chunk, str):
            text = chunk
        else:
            text = str(chunk)
        if not text:
            return []
        self._chunks.append(text)
        joined = "".join(self._chunks)
        self._chunks = []
        parts = joined.split("\n\n")
        if parts[-1]:
            self._chunks.append(parts[-1])
        return parts[:-1]

    def trailing(self) -> str | None:
        """Return the buffered partial event, or ``None`` when blank.

        A buffer holding only whitespace yields ``None``; every consumer's
        event parser treats a whitespace-only tail as an empty event, so the
        distinction is unobservable downstream.
        """
        if not self._chunks:
            return None
        raw = "".join(self._chunks)
        return raw if raw.strip() else None


async def iter_raw_sse_events(
    chunks: AsyncIterable[bytes | str],
    *,
    flush_trailing: bool = False,
) -> AsyncIterator[str]:
    """Split an SSE chunk stream on ``\\n\\n`` boundaries and yield raw events.

    Handles one event per chunk, many events per chunk, events split across
    chunk boundaries, and empty chunks. When ``flush_trailing`` is true, a
    trailing partial event (no closing ``\\n\\n``) is yielded once the source
    is exhausted — the torn-final-chunk semantics of the ``iter_sse_events``
    adapter. A trailing buffer holding only whitespace is dropped.
    """
    splitter = SseEventSplitter()
    async for chunk in chunks:
        for raw in splitter.feed(chunk):
            yield raw
    if flush_trailing:
        raw = splitter.trailing()
        if raw is not None:
            yield raw
