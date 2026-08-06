"""Native per-request token usage capture for the admin Usage view.

Claudey records one JSONL line per provider-served request at the final
``message_delta`` usage, then aggregates per model and per provider for the
existing GET /admin/api/usage endpoint (see claudey.api.usage_aggregate).

Known gaps:
- Local intercepts in api/handlers/messages.py:296-345 (web server tools and
  short-circuit optimizations) serve responses without reaching a provider,
  so they bypass capture entirely.
- Responses-path reasoning tokens are not reported in ``message_delta`` usage
  by providers, so they are recorded as 0.
"""

import asyncio
import json
import sys
from collections.abc import AsyncIterator, Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from claudey.config.paths import config_dir_path
from claudey.core.anthropic.stream_contracts import SSEEvent, parse_sse_text
from claudey.core.trace import close_stream_input, trace_event

from .routing import ResolvedModel

USAGE_LOG_FILENAME = "usage.jsonl"
TOKEN_FIELDS = (
    "input_tokens",
    "cached_input_tokens",
    "cache_creation_input_tokens",
    "output_tokens",
    "reasoning_output_tokens",
)
_NORMALIZE_USAGE_KEYS = {
    "cache_read_input_tokens": "cached_input_tokens",
    "reasoning_tokens": "reasoning_output_tokens",
}


def usage_log_path() -> Path:
    """Return the canonical usage log path (lazy; resolves HOME per call)."""
    return config_dir_path() / USAGE_LOG_FILENAME


def _to_int(value: Any) -> int | None:
    try:
        return int(value)
    except TypeError, ValueError:
        return None


def normalize_usage(usage: Mapping[str, Any]) -> dict[str, int]:
    """Map provider usage keys to the canonical five and coerce to ints.

    Unknown keys are dropped; missing or non-numeric values become 0.
    """
    mapped = {
        _NORMALIZE_USAGE_KEYS.get(key, key): value for key, value in usage.items()
    }
    return {field: _to_int(mapped.get(field)) or 0 for field in TOKEN_FIELDS}


def record_usage(
    *,
    request_id: str,
    wire_api: str,
    provider_id: str,
    provider_model: str,
    original_model: str,
    usage: dict[str, Any],
) -> None:
    """Append one usage record to the JSONL log. Never raises."""
    try:
        tokens = normalize_usage(usage)
        record = {
            "ts": datetime.now(UTC).isoformat(),
            "request_id": request_id,
            "wire_api": wire_api,
            "provider_id": provider_id,
            "provider_model": provider_model,
            "original_model": original_model,
            **tokens,
            "total_tokens": sum(tokens.values()),
            "conversations": 1,
        }
        log_path = usage_log_path()
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as stream:
            stream.write(json.dumps(record) + "\n")
    except Exception as exc:
        trace_event(
            stage="usage",
            event="claudey.usage.record_failed",
            source="api",
            request_id=request_id,
            error_type=type(exc).__name__,
        )


async def observe_usage(
    stream: AsyncIterator[str],
    *,
    request_id: str,
    wire_api: str,
    resolved: ResolvedModel,
    on_record: Callable[..., Any] = record_usage,
) -> AsyncIterator[str]:
    """Tee a provider stream, recording usage once at the first message_delta.

    Every chunk is yielded unchanged; the record fires on the first
    ``message_delta`` event carrying a ``usage`` dict (one-shot). A torn
    final chunk (no trailing blank line) is flushed in ``finally`` so it
    still records. ``GeneratorExit``/``CancelledError`` re-raise untouched
    without recording. Parse and record failures are traced, never raised.
    """
    buffer = ""
    recorded = False

    def handle_events(events: list[SSEEvent]) -> None:
        nonlocal recorded
        for event in events:
            if recorded or event.event != "message_delta":
                continue
            usage = event.data.get("usage")
            if not isinstance(usage, dict):
                continue
            try:
                on_record(
                    request_id=request_id,
                    wire_api=wire_api,
                    provider_id=resolved.provider_id,
                    provider_model=resolved.provider_model,
                    original_model=resolved.original_model,
                    usage=usage,
                )
            except Exception as exc:
                trace_event(
                    stage="usage",
                    event="claudey.usage.record_failed",
                    source="api",
                    request_id=request_id,
                    error_type=type(exc).__name__,
                )
            recorded = True

    def parse_and_handle(raw_event: str) -> None:
        try:
            handle_events(parse_sse_text(raw_event + "\n\n"))
        except Exception as exc:
            trace_event(
                stage="usage",
                event="claudey.usage.observer_failed",
                source="api",
                request_id=request_id,
                error_type=type(exc).__name__,
            )

    try:
        async for chunk in stream:
            yield chunk
            buffer += chunk
            while "\n\n" in buffer:
                raw_event, buffer = buffer.split("\n\n", 1)
                parse_and_handle(raw_event)
    except GeneratorExit:
        raise
    except asyncio.CancelledError:
        raise
    finally:
        pending = sys.exception()
        if not isinstance(pending, GeneratorExit | asyncio.CancelledError) and buffer:
            parse_and_handle(buffer)
        await close_stream_input(
            stream,
            owner="usage_observer",
            source="api",
            preserved_error=sys.exception(),
        )
