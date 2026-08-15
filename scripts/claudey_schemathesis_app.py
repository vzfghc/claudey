"""Live FastAPI app for Schemathesis nightly fuzzing.

The nightly QA job never touches real credentials: provider resolution is
backed by in-memory fakes and the custom-provider/combo stores are redirected
to a throwaway temp dir before the app is constructed.
"""

import json
import os
import tempfile

from claudey.core.anthropic.models import MessagesRequest
from claudey.core.model_metadata import ProviderModelInfo
from claudey.core.reasoning import DEFAULT_REASONING_POLICY, ReasoningPolicy
from claudey.providers.base import BaseProvider, ProviderConfig
from tests.api.support import create_test_app

_TMP = tempfile.mkdtemp(prefix="claudey-schemathesis-")
os.environ["CLAUDEY_CUSTOM_PROVIDERS_PATH"] = os.path.join(
    _TMP, "custom-providers.json"
)
os.environ["CLAUDEY_COMBOS_PATH"] = os.path.join(_TMP, "combos.json")


def _sse(event_type: str, data: dict[str, object]) -> str:
    return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"


def _anthropic_text_stream() -> list[str]:
    return [
        _sse(
            "message_start",
            {"type": "message_start", "message": {"id": "msg_1", "role": "assistant"}},
        ),
        _sse(
            "content_block_start",
            {
                "type": "content_block_start",
                "index": 0,
                "content_block": {"type": "text", "text": ""},
            },
        ),
        _sse(
            "content_block_delta",
            {
                "type": "content_block_delta",
                "index": 0,
                "delta": {"type": "text_delta", "text": "Hello"},
            },
        ),
        _sse("content_block_stop", {"type": "content_block_stop", "index": 0}),
        _sse(
            "message_delta",
            {
                "type": "message_delta",
                "delta": {"stop_reason": "end_turn", "stop_sequence": None},
            },
        ),
        _sse("message_stop", {"type": "message_stop"}),
    ]


class _FakeProvider(BaseProvider):
    """Minimal BaseProvider that streams a canned Anthropic SSE response."""

    def __init__(self) -> None:
        super().__init__(
            ProviderConfig(api_key="test-fake", base_url="https://fake.invalid")
        )

    def preflight_stream(
        self,
        request: MessagesRequest,
        *,
        reasoning: ReasoningPolicy = DEFAULT_REASONING_POLICY,
    ) -> None:
        return None

    async def cleanup(self) -> None:
        return None

    async def list_model_infos(self) -> frozenset[ProviderModelInfo]:
        return frozenset({ProviderModelInfo(model_id="gpt-4o-mini")})

    async def stream_response(
        self,
        request: MessagesRequest,
        input_tokens: int = 0,
        *,
        request_id: str | None = None,
        response_model: str | None = None,
        reasoning: ReasoningPolicy = DEFAULT_REASONING_POLICY,
    ):
        for chunk in _anthropic_text_stream():
            yield chunk


app = create_test_app(
    providers={
        "nvidia_nim": _FakeProvider(),
        "openrouter": _FakeProvider(),
    }
)
