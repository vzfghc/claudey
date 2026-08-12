"""Tests for the Novita AI OpenAI-chat provider."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from claudey.config.provider_catalog import NOVITA_DEFAULT_BASE
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
def novita_provider():
    return profiled_provider(
        "novita",
        ProviderConfig(
            api_key="test_novita_key",
            base_url=NOVITA_DEFAULT_BASE,
            rate_limit=10,
            rate_window=60,
        ),
        admission=immediate_admission(),
    )


def test_init_uses_openai_chat_provider(novita_provider):
    assert isinstance(novita_provider, OpenAIChatProvider)
    assert novita_provider._api_key == "test_novita_key"
    assert novita_provider._base_url == "https://api.novita.ai/openai/v1"


def test_build_request_body_openai_chat(novita_provider):
    request = MessagesRequest(
        model="deepseek/deepseek-r1-0528",
        max_tokens=50,
        messages=[Message(role="user", content="hi")],
    )

    body = novita_provider._build_request_body(
        request, reasoning=reasoning_for(request)
    )

    assert body["model"] == "deepseek/deepseek-r1-0528"
    assert body["max_tokens"] == 50
    assert body["messages"] == [{"role": "user", "content": "hi"}]
    assert "extra_body" not in body


@pytest.mark.asyncio
async def test_model_list_uses_openai_client_models_endpoint(novita_provider):
    novita_provider._client.models.list = AsyncMock(
        return_value=SimpleNamespace(
            data=[SimpleNamespace(id="deepseek/deepseek-r1-0528")]
        )
    )

    assert await novita_provider.list_model_infos() == frozenset(
        {ProviderModelInfo("deepseek/deepseek-r1-0528")}
    )

    novita_provider._client.models.list.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_cleanup_closes_openai_client(novita_provider):
    novita_provider._client = MagicMock()
    novita_provider._client.close = AsyncMock()

    await novita_provider.cleanup()

    novita_provider._client.close.assert_awaited_once()
