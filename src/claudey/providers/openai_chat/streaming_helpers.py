"""Focused event conversion helpers for OpenAI-chat streaming."""

from collections.abc import Iterator
from typing import Any, Protocol

from claudey.core.anthropic import ContentType, HeuristicToolParser, ThinkTagParser
from claudey.core.anthropic.streaming import AnthropicStreamLedger

from .reasoning_details import StructuredReasoningStream
from .streaming_types import OpenAIChatStreamProfile
from .tool_calls import (
    OpenAIToolCallAssembler,
    iter_heuristic_tool_use_sse,
    tool_call_extra_content,
)


class ExtraReasoningHandler(Protocol):
    """Provider-specific extra reasoning hook used by the stream converter."""

    def __call__(
        self,
        delta: Any,
        ledger: AnthropicStreamLedger,
        *,
        output_reasoning: bool,
    ) -> Iterator[str]: ...


def reasoning_events(
    profile: OpenAIChatStreamProfile,
    handle_extra_reasoning: ExtraReasoningHandler,
    delta: Any,
    ledger: AnthropicStreamLedger,
    *,
    output_reasoning: bool,
    structured_reasoning: StructuredReasoningStream | None,
) -> Iterator[str]:
    """Emit reasoning content and extra-reasoning events for one delta."""
    reasoning = profile.reasoning_delta(delta)
    if output_reasoning and structured_reasoning is not None:
        yield from structured_reasoning.events(
            delta, ledger, native_reasoning=reasoning
        )
    elif output_reasoning and reasoning is not None:
        yield from ledger.ensure_thinking_block()
        if reasoning:
            yield ledger.emit_thinking_delta(reasoning)
    yield from handle_extra_reasoning(delta, ledger, output_reasoning=output_reasoning)


def content_events(
    delta_content: str,
    ledger: AnthropicStreamLedger,
    *,
    think_parser: ThinkTagParser,
    heuristic_parser: HeuristicToolParser,
    output_reasoning: bool,
    tool_names: Any,
) -> Iterator[str]:
    for part in think_parser.feed(delta_content):
        if part.type == ContentType.THINKING:
            if output_reasoning:
                yield from ledger.ensure_thinking_block()
                yield ledger.emit_thinking_delta(part.content)
            continue
        filtered_text, detected_tools = heuristic_parser.feed(part.content)
        if filtered_text:
            yield from ledger.ensure_text_block()
            yield ledger.emit_text_delta(filtered_text)
        for tool_use in detected_tools:
            yield from iter_heuristic_tool_use_sse(
                ledger, tool_use, tool_names=tool_names
            )


def tool_call_events(
    assembler: OpenAIToolCallAssembler,
    tool_calls: Any,
    ledger: AnthropicStreamLedger,
    *,
    tool_names: Any,
    tool_name_buffers: dict[int, str],
    tool_argument_aliases: dict[str, dict[str, str]],
    tool_argument_alias_buffers: dict[int, str],
) -> Iterator[str]:
    yield from ledger.close_content_blocks()
    for tool_call in tool_calls:
        extra_content = tool_call_extra_content(tool_call)
        tool_call_info = {
            "index": tool_call.index,
            "id": tool_call.id,
            "function": {
                "name": tool_call.function.name,
                "arguments": tool_call.function.arguments,
            },
        }
        if extra_content:
            tool_call_info["extra_content"] = extra_content
        yield from assembler.process_tool_call(
            tool_call_info,
            ledger,
            tool_names=tool_names,
            tool_name_buffers=tool_name_buffers,
            tool_argument_aliases=tool_argument_aliases,
            tool_argument_alias_buffers=tool_argument_alias_buffers,
        )
