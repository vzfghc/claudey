"""Tests for the Scaleway OpenAI-chat provider."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from claudey.config.provider_catalog import SCALEWAY_DEFAULT_BASE
from claudey.core.anthropic.models import Message, MessagesRequest
from claudey.core.model_metadata import ProviderModelInfo
from claudey.providers.base import ProviderConfig
from claudey.providers.openai_chat import OpenAIChatProvider
from tests.providers.support import (
    immediate_admission,
    profiled_provider,
    reasoning_for,
)


@pytest.fixture
def scaleway_provider():
    return profiled_provider(
        "scaleway",
        ProviderConfig(
            api_key="test_scaleway_key",
            base_url=SCALEWAY_DEFAULT_BASE,
            rate_limit=10,
            rate_window=60,
        ),
        admission=immediate_admission(),
    )


def test_init_uses_openai_chat_provider(scaleway_provider):
    assert isinstance(scaleway_provider, OpenAIChatProvider)
    assert scaleway_provider._api_key == "test_scaleway_key"
    assert scaleway_provider._base_url == "https://api.scaleway.ai/v1"


def test_build_request_body_openai_chat(scaleway_provider):
    request = MessagesRequest(
        model="llama-3.3-70b",
        max_tokens=50,
        messages=[Message(role="user", content="hi")],
    )

    body = scaleway_provider._build_request_body(
        request, reasoning=reasoning_for(request)
    )

    assert body["model"] == "llama-3.3-70b"
    assert body["max_tokens"] == 50
    assert body["messages"] == [{"role": "user", "content": "hi"}]
    assert "extra_body" not in body


@pytest.mark.asyncio
async def test_model_list_uses_openai_client_models_endpoint(scaleway_provider):
    scaleway_provider._client.models.list = AsyncMock(
        return_value=SimpleNamespace(data=[SimpleNamespace(id="llama-3.3-70b")])
    )

    assert await scaleway_provider.list_model_infos() == frozenset(
        {ProviderModelInfo("llama-3.3-70b")}
    )

    scaleway_provider._client.models.list.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_cleanup_closes_openai_client(scaleway_provider):
    scaleway_provider._client = MagicMock()
    scaleway_provider._client.close = AsyncMock()

    await scaleway_provider.cleanup()

    scaleway_provider._client.close.assert_awaited_once()
