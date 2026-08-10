"""x-claudey-route response-header telemetry across both wire APIs."""

import json
from collections.abc import AsyncIterator, Callable
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from claudey.config.settings import Settings
from tests.api.support import create_test_app


def _sse(event_type: str, data: object) -> str:
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
        _sse(
            "content_block_stop",
            {"type": "content_block_stop", "index": 0},
        ),
        _sse(
            "message_delta",
            {
                "type": "message_delta",
                "delta": {"stop_reason": "end_turn", "stop_sequence": None},
            },
        ),
        _sse("message_stop", {"type": "message_stop"}),
    ]


class FakeProvider:
    """Provider double that streams a canned Anthropic text response."""

    def __init__(self, chunks: list[str] | None = None) -> None:
        self.chunks = chunks or _anthropic_text_stream()
        self.preflight_stream = MagicMock()

    async def stream_response(
        self, _request_data: object, **_kwargs: Any
    ) -> AsyncIterator[str]:
        for chunk in self.chunks:
            yield chunk


PD = "/v1/messages"
RD = "/v1/responses"
_MODEL_JSON = "nvidia_nim/test-model"


def _messages_payload(stream: bool = True) -> dict[str, object]:
    return {
        "model": _MODEL_JSON,
        "max_tokens": 32,
        "stream": stream,
        "messages": [{"role": "user", "content": "Hello"}],
    }


def _responses_payload() -> dict[str, object]:
    return {"model": _MODEL_JSON, "input": "Hello", "max_output_tokens": 32}


PayloadBuilder = Callable[[], dict[str, object]]


_INPUTS = [
    pytest.param(PD, _messages_payload, id="messages-stream"),
    pytest.param(RD, _responses_payload, id="responses-stream"),
]


@pytest.mark.parametrize("path,payload", _INPUTS, ids=[p.id for p in _INPUTS])
def test_route_header_present_by_default(path: str, payload: PayloadBuilder) -> None:
    provider = FakeProvider()
    app = create_test_app()
    with (
        patch("claudey.api.routes.resolve_provider", return_value=provider),
        TestClient(app) as client,
    ):
        response = client.post(path, json=payload())

    assert response.status_code == 200
    assert response.headers.get("x-claudey-route") == _MODEL_JSON


@pytest.mark.parametrize("path,payload", _INPUTS, ids=[p.id for p in _INPUTS])
def test_route_header_disabled_by_toggle(path: str, payload: PayloadBuilder) -> None:
    provider = FakeProvider()
    app = create_test_app(
        settings=Settings(X_CLAUDEY_ROUTE_HEADER=False),
    )
    with (
        patch("claudey.api.routes.resolve_provider", return_value=provider),
        TestClient(app) as client,
    ):
        response = client.post(path, json=payload())

    assert response.status_code == 200
    assert "x-claudey-route" not in response.headers


def test_messages_non_stream_json_carries_route_header() -> None:
    provider = FakeProvider()
    app = create_test_app()
    with (
        patch("claudey.api.routes.resolve_provider", return_value=provider),
        TestClient(app) as client,
    ):
        response = client.post(PD, json=_messages_payload(stream=False))

    assert response.status_code == 200
    assert response.headers.get("x-claudey-route") == _MODEL_JSON
    assert response.json()["content"][0]["text"] == "Hello"
