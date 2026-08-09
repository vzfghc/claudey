"""Tests for the OpenCode OpenAI-compatible provider."""

import pytest

from claudey.core.anthropic.models import MessagesRequest
from claudey.providers.base import ProviderConfig
from tests.providers.support import (
    immediate_admission,
    profiled_provider,
    reasoning_for,
)


@pytest.mark.parametrize("provider_id", ["opencode", "opencode_go"])
def test_build_request_body_preserves_empty_reasoning_content(
    provider_id: str,
) -> None:
    provider = profiled_provider(
        provider_id,
        ProviderConfig(
            api_key="test_opencode_key",
            base_url="https://example.invalid/v1",
            rate_limit=1,
            rate_window=1,
        ),
        admission=immediate_admission(),
    )
    request = MessagesRequest.model_validate(
        {
            "model": "m",
            "messages": [
                {
                    "role": "assistant",
                    "content": "visible",
                    "reasoning_content": "",
                }
            ],
            "thinking": {"type": "enabled"},
        }
    )

    body = provider._build_request_body(request, reasoning=reasoning_for(request))

    assert body["messages"][0] == {
        "role": "assistant",
        "content": "visible",
        "reasoning_content": "",
    }


@pytest.mark.parametrize("provider_id", ["opencode", "opencode_go"])
def test_build_request_body_replays_tool_reasoning_natively(
    provider_id: str,
) -> None:
    provider = profiled_provider(
        provider_id,
        ProviderConfig(
            api_key="test_opencode_key",
            base_url="https://example.invalid/v1",
            rate_limit=1,
            rate_window=1,
        ),
        admission=immediate_admission(),
    )
    request = MessagesRequest.model_validate(
        {
            "model": "m",
            "messages": [
                {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "thinking",
                            "thinking": "I should inspect the file.",
                            "signature": "sig",
                        },
                        {
                            "type": "tool_use",
                            "id": "call_1",
                            "name": "Read",
                            "input": {"path": "README.md"},
                        },
                    ],
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": "call_1",
                            "content": "file contents",
                        }
                    ],
                },
            ],
            "thinking": {"type": "enabled"},
        }
    )

    body = provider._build_request_body(request, reasoning=reasoning_for(request))

    assistant = body["messages"][0]
    assert assistant["content"] == ""
    assert assistant["reasoning_content"] == "I should inspect the file."
    assert "<think>" not in assistant["content"]
    assert assistant["tool_calls"][0]["id"] == "call_1"
    assert body["messages"][1] == {
        "role": "tool",
        "tool_call_id": "call_1",
        "content": "file contents",
    }


@pytest.mark.parametrize("provider_id", ["opencode", "opencode_go", "pecut"])
def test_build_request_body_presences_reasoning_for_missing_history(
    provider_id: str,
) -> None:
    """DeepSeek thinking mode needs the wire field present even when empty."""
    provider = profiled_provider(
        provider_id,
        ProviderConfig(
            api_key="test_opencode_key",
            base_url="https://example.invalid/v1",
            rate_limit=1,
            rate_window=1,
        ),
        admission=immediate_admission(),
    )
    request = MessagesRequest.model_validate(
        {
            "model": "m",
            "messages": [
                {"role": "user", "content": "hello"},
                {"role": "assistant", "content": "plain reply"},
                {"role": "user", "content": "continue"},
            ],
        }
    )

    body = provider._build_request_body(request, reasoning=reasoning_for(request))

    assistant = body["messages"][1]
    assert assistant["role"] == "assistant"
    assert assistant["content"] == "plain reply"
    assert assistant["reasoning_content"] == ""


@pytest.mark.parametrize("provider_id", ["opencode", "opencode_go", "pecut"])
def test_build_request_disables_upstream_thinking_when_client_off(
    provider_id: str,
) -> None:
    """Thinking disabled client-side must keep the upstream out of thinking
    mode so it never demands a reasoning pass-back the client never captured."""
    provider = profiled_provider(
        provider_id,
        ProviderConfig(
            api_key="test_opencode_key",
            base_url="https://example.invalid/v1",
            rate_limit=1,
            rate_window=1,
        ),
        admission=immediate_admission(),
    )
    request = MessagesRequest.model_validate(
        {
            "model": "m",
            "messages": [
                {"role": "user", "content": "hello"},
                {"role": "assistant", "content": "plain reply"},
                {"role": "user", "content": "continue"},
            ],
            "thinking": {"type": "disabled"},
        }
    )

    body = provider._build_request_body(request, reasoning=reasoning_for(request))

    assert body["extra_body"]["thinking"] == {"type": "disabled"}
    assert "reasoning_content" not in body["messages"][1]
