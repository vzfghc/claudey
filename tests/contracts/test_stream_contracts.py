"""Stream/SSE contract tests. Strict transcript *ordering* is covered here for
``AnthropicStreamLedger`` output; for integration ordering, add messaging or API
integration tests.
"""

import asyncio
from collections.abc import AsyncIterator, Iterable
from typing import Any

from claudey.application.failover import FallbackExecutor
from claudey.application.routing import ChainResolution, ResolvedModel
from claudey.config.reasoning import ReasoningPreference
from claudey.core.anthropic import (
    AnthropicStreamLedger,
    ContentType,
    HeuristicToolParser,
    Message,
    MessagesRequest,
    ThinkTagParser,
)
from claudey.core.anthropic.stream_contracts import (
    assert_anthropic_stream_contract,
    event_names,
    parse_sse_text,
    text_content,
    thinking_content,
)
from claudey.core.anthropic.streaming import format_sse_event
from claudey.core.failures import ExecutionFailure, FailureKind


def test_interleaved_thinking_text_blocks_are_valid() -> None:
    events = _parse_builder_events(
        _interleaved_thinking_text_events(
            ("first thought", "first answer", "second thought", "final answer")
        )
    )
    assert_anthropic_stream_contract(events)
    assert event_names(events).count("content_block_start") == 4
    assert thinking_content(events) == "first thoughtsecond thought"
    assert text_content(events) == "first answerfinal answer"


def test_split_think_tags_preserve_text_and_thinking() -> None:
    events = _parse_builder_events(
        _events_from_text_chunks(["before <thi", "nk>hidden", "</think> after"])
    )
    assert_anthropic_stream_contract(events)
    assert thinking_content(events) == "hidden"
    assert text_content(events) == "before  after"


def test_mixed_reasoning_content_and_think_tags_keep_order() -> None:
    builder = AnthropicStreamLedger("msg_contract", "contract-model")
    chunks = [builder.message_start()]
    chunks.extend(builder.ensure_thinking_block())
    chunks.append(builder.emit_thinking_delta("reasoning field"))
    chunks.extend(
        _events_from_text_chunks([" visible <think>tagged</think> done"], builder)
    )
    chunks.extend(builder.close_all_blocks())
    chunks.append(builder.message_delta("end_turn", 10))
    chunks.append(builder.message_stop())

    events = parse_sse_text("".join(chunks))
    assert_anthropic_stream_contract(events)
    assert thinking_content(events) == "reasoning fieldtagged"
    assert text_content(events) == " visible  done"


def test_redacted_thinking_block_start_stop_is_valid() -> None:
    """Native redacted_thinking uses start/stop only (no deltas)."""
    chunks = [
        format_sse_event(
            "message_start",
            {
                "type": "message_start",
                "message": {
                    "id": "msg_r",
                    "type": "message",
                    "role": "assistant",
                    "content": [],
                    "model": "m",
                    "stop_reason": None,
                    "stop_sequence": None,
                    "usage": {"input_tokens": 1, "output_tokens": 1},
                },
            },
        ),
        format_sse_event(
            "content_block_start",
            {
                "type": "content_block_start",
                "index": 0,
                "content_block": {"type": "redacted_thinking", "data": "opaque"},
            },
        ),
        format_sse_event(
            "content_block_stop",
            {"type": "content_block_stop", "index": 0},
        ),
        format_sse_event(
            "message_delta",
            {
                "type": "message_delta",
                "delta": {"stop_reason": "end_turn", "stop_sequence": None},
                "usage": {"input_tokens": 1, "output_tokens": 2},
            },
        ),
        format_sse_event("message_stop", {"type": "message_stop"}),
    ]
    events = parse_sse_text("".join(chunks))
    assert_anthropic_stream_contract(events)


def test_enable_thinking_false_suppresses_reasoning_only() -> None:
    events = _parse_builder_events(
        _events_from_text_chunks(
            ["hello <think>secret</think> world"], enable_thinking=False
        )
    )
    assert_anthropic_stream_contract(events)
    assert "secret" not in thinking_content(events)
    assert text_content(events) == "hello  world"


def test_task_tool_arguments_force_foreground_execution() -> None:
    parser = HeuristicToolParser()
    filtered, detected = parser.feed(
        "● <function=Task><parameter=description>Inspect</parameter>"
        "<parameter=run_in_background>true</parameter> trailing"
    )
    detected.extend(parser.flush())
    assert "trailing" in filtered
    task = detected[0]
    assert task["name"] == "Task"
    if isinstance(task.get("input"), dict):
        task["input"]["run_in_background"] = False
    assert task["input"]["run_in_background"] is False


_GATEWAY_MODEL = "claude-3-opus"
_NODE_A = ("provider_a", "model-a")
_NODE_B = ("provider_b", "model-b")


class _FailingThenServingProvider:
    """Provider double: yields a failure (or a full SSE transcript)."""

    def __init__(
        self, *, kind: FailureKind | None = None, chunks: list[str] | None = None
    ) -> None:
        self._kind = kind
        self._transcript = chunks
        self.calls: list[dict[str, Any]] = []

    def preflight_stream(self, _request: object, **kwargs: Any) -> None:
        return None

    async def stream_response(
        self, _request: object, **kwargs: Any
    ) -> AsyncIterator[str]:
        self.calls.append(kwargs)
        if self._kind is not None:
            raise ExecutionFailure(
                kind=self._kind,
                status_code=100,
                message=f"{self._kind.value} failure",
                retryable=True,
            )
        if self._transcript is not None:
            for chunk in self._transcript:
                yield chunk
            return
        response_model = kwargs.get("response_model", _GATEWAY_MODEL)
        ledger = AnthropicStreamLedger("msg_fallback", response_model)
        yield ledger.message_start()
        for chunk in ledger.ensure_text_block():
            yield chunk
        yield ledger.emit_text_delta("served by fallback")
        for chunk in ledger.close_all_blocks():
            yield chunk
        yield ledger.message_delta("end_turn", 6)
        yield ledger.message_stop()


def _contracted_nodes() -> ChainResolution:
    chain = tuple(
        ResolvedModel(
            original_model=_GATEWAY_MODEL,
            provider_id=provider,
            provider_model=model,
            provider_model_ref=f"{provider}/{model}",
            reasoning_preference=ReasoningPreference.CLIENT,
        )
        for provider, model in (_NODE_A, _NODE_B)
    )
    return ChainResolution(chain=chain, reasoning=None)


def _provider_factory(providers: dict[str, _FailingThenServingProvider]):
    def resolve(provider_id: str):
        return providers[provider_id]

    return resolve


async def _drain_failover_transcript(
    providers: dict[str, _FailingThenServingProvider],
) -> list[str]:
    executor = FallbackExecutor(_provider_factory(providers))
    return [
        chunk
        async for chunk in executor.stream(
            _contracted_nodes(),
            MessagesRequest(
                model=_GATEWAY_MODEL,
                max_tokens=32,
                messages=[Message(role="user", content="hi")],
            ),
            wire_api="messages",
            raw_log_label="FULL_PAYLOAD",
            raw_log_payload={},
            request_id="req-contract",
            chain_identity="combo_flagship",
        )
    ]


def test_failover_transcript_model_stays_gateway_across_nodes() -> None:
    """After a pre-content failover, the served transcript keeps the gateway
    model in every event, never the failing provider's model."""
    primary = _FailingThenServingProvider(kind=FailureKind.RATE_LIMIT)
    secondary = _FailingThenServingProvider()

    transcript = asyncio.run(
        _drain_failover_transcript({"provider_a": primary, "provider_b": secondary})
    )

    events = parse_sse_text("".join(transcript))
    assert_anthropic_stream_contract(events)
    start = next(event for event in events if event.event == "message_start")
    assert start.data["message"]["model"] == _GATEWAY_MODEL
    assert text_content(events) == "served by fallback"
    # The primary handled zero (it failed before content); the secondary served.
    assert primary.calls, "primary was attempted"
    assert secondary.calls, "secondary must serve after failover"
    for call in secondary.calls:
        assert call["response_model"] == _GATEWAY_MODEL


def test_failover_transcript_is_still_valid_with_thinking() -> None:
    """Southern nodes may emit thinking blocks; the gateway transcript stays
    contract-valid and the model remains the gateway model."""
    ledger = AnthropicStreamLedger("msg_fallback", _GATEWAY_MODEL)
    thinking_transcript = [
        ledger.message_start(),
        *ledger.ensure_thinking_block(),
        ledger.emit_thinking_delta("analysis"),
        *ledger.ensure_text_block(),
        ledger.emit_text_delta("result"),
        *ledger.close_all_blocks(),
        ledger.message_delta("end_turn", 9),
        ledger.message_stop(),
    ]
    primary = _FailingThenServingProvider(kind=FailureKind.OVERLOADED)
    secondary = _FailingThenServingProvider(chunks=thinking_transcript)

    transcript = asyncio.run(
        _drain_failover_transcript({"provider_a": primary, "provider_b": secondary})
    )

    events = parse_sse_text("".join(transcript))
    assert_anthropic_stream_contract(events)
    assert thinking_content(events) == "analysis"
    assert text_content(events) == "result"
    start = next(event for event in events if event.event == "message_start")
    assert start.data["message"]["model"] == _GATEWAY_MODEL


def test_failover_trace_emits_failover_event(caplog) -> None:
    """A chain advance emits the ``claudey.api.route.failover`` trace row."""
    caplog.set_level("DEBUG")
    primary = _FailingThenServingProvider(kind=FailureKind.RATE_LIMIT)
    secondary = _FailingThenServingProvider()

    asyncio.run(
        _drain_failover_transcript({"provider_a": primary, "provider_b": secondary})
    )

    assert "claudey.api.route.failover" in caplog.text


def _interleaved_thinking_text_events(
    parts: tuple[str, str, str, str],
) -> Iterable[str]:
    builder = AnthropicStreamLedger("msg_contract", "contract-model")
    yield builder.message_start()
    yield from builder.ensure_thinking_block()
    yield builder.emit_thinking_delta(parts[0])
    yield from builder.ensure_text_block()
    yield builder.emit_text_delta(parts[1])
    yield from builder.ensure_thinking_block()
    yield builder.emit_thinking_delta(parts[2])
    yield from builder.ensure_text_block()
    yield builder.emit_text_delta(parts[3])
    yield from builder.close_all_blocks()
    yield builder.message_delta("end_turn", 20)
    yield builder.message_stop()


def _events_from_text_chunks(
    chunks: list[str],
    builder: AnthropicStreamLedger | None = None,
    *,
    enable_thinking: bool = True,
) -> list[str]:
    sse = builder or AnthropicStreamLedger("msg_contract", "contract-model")
    out: list[str] = [] if builder else [sse.message_start()]
    parser = ThinkTagParser()

    for chunk in chunks:
        out.extend(_emit_parser_parts(sse, parser.feed(chunk), enable_thinking))

    remaining = parser.flush()
    if remaining is not None:
        out.extend(_emit_parser_parts(sse, [remaining], enable_thinking))

    if builder is None:
        out.extend(sse.close_all_blocks())
        out.append(sse.message_delta("end_turn", 20))
        out.append(sse.message_stop())
    return out


def _emit_parser_parts(
    builder: AnthropicStreamLedger,
    parts: Iterable,
    enable_thinking: bool,
) -> list[str]:
    out: list[str] = []
    for part in parts:
        if part.type == ContentType.THINKING:
            if enable_thinking:
                out.extend(builder.ensure_thinking_block())
                out.append(builder.emit_thinking_delta(part.content))
            continue
        out.extend(builder.ensure_text_block())
        out.append(builder.emit_text_delta(part.content))
    return out


def _parse_builder_events(chunks: Iterable[str]):
    return parse_sse_text("".join(chunks))
