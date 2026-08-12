"""Anthropic SSE parsing used by the Responses stream adapter."""

import json
import sys
from collections.abc import AsyncIterable, AsyncIterator
from dataclasses import dataclass
from typing import Any

from claudey.core.anthropic.sse_parser import iter_raw_sse_events
from claudey.core.trace import close_stream_input


@dataclass(slots=True)
class AnthropicSseEvent:
    event: str
    data: dict[str, Any]


async def iter_sse_events(
    chunks: AsyncIterable[Any],
) -> AsyncIterator[AnthropicSseEvent]:
    iterator = aiter(chunks)
    try:
        async for raw in iter_raw_sse_events(iterator, flush_trailing=True):
            event = parse_sse_event(raw)
            if event is not None:
                yield event
    finally:
        await close_stream_input(
            iterator,
            owner="openai_responses.anthropic_sse",
            source="core",
            preserved_error=sys.exception(),
        )


def parse_sse_event(raw: str) -> AnthropicSseEvent | None:
    event_type = ""
    data_parts: list[str] = []
    for line in raw.splitlines():
        stripped = line.rstrip("\r")
        if stripped.startswith("event:"):
            event_type = stripped.split(":", 1)[1].strip()
        elif stripped.startswith("data:"):
            data_parts.append(stripped.split(":", 1)[1].strip())
    if not event_type and not data_parts:
        return None
    data_text = "\n".join(data_parts)
    if data_text == "[DONE]":
        return None
    try:
        parsed = json.loads(data_text) if data_text else {}
    except json.JSONDecodeError:
        parsed = {"raw": data_text}
    if not isinstance(parsed, dict):
        parsed = {"value": parsed}
    return AnthropicSseEvent(event=event_type, data=parsed)
