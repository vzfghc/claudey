"""Tests for the Routeway OpenAI-chat provider."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from claudey.config.provider_catalog import ROUTEWAY_DEFAULT_BASE
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
def routeway_provider():
    return profiled_provider(
        "routeway",
        ProviderConfig(
            api_key="test_routeway_key",
            base_url=ROUTEWAY_DEFAULT_BASE,
            rate_limit=10,
            rate_window=60,
        ),
        admission=immediate_admission(),
    )


def test_init_uses_openai_chat_provider(routeway_provider):
    assert isinstance(routeway_provider, OpenAIChatProvider)
    assert routeway_provider._api_key == "test_routeway_key"
    assert routeway_provider._base_url == "https://api.routeway.ai/v1"


def test_build_request_body_openai_chat(routeway_provider):
    request = MessagesRequest(
        model="grok-3-mini",
        max_tokens=50,
        messages=[Message(role="user", content="hi")],
    )

    body = routeway_provider._build_request_body(
        request, reasoning=reasoning_for(request)
    )

    assert body["model"] == "grok-3-mini"
    assert body["max_tokens"] == 50
    assert body["messages"] == [{"role": "user", "content": "hi"}]
    assert "extra_body" not in body


@pytest.mark.asyncio
async def test_model_list_uses_openai_client_models_endpoint(routeway_provider):
    routeway_provider._client.models.list = AsyncMock(
        return_value=SimpleNamespace(data=[SimpleNamespace(id="grok-3-mini")])
    )

    assert await routeway_provider.list_model_infos() == frozenset(
        {ProviderModelInfo("grok-3-mini")}
    )

    routeway_provider._client.models.list.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_cleanup_closes_openai_client(routeway_provider):
    routeway_provider._client = MagicMock()
    routeway_provider._client.close = AsyncMock()

    await routeway_provider.cleanup()

    routeway_provider._client.close.assert_awaited_once()
