"""Tests for the OVHcloud AI Endpoints OpenAI-chat provider."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from claudey.application.model_metadata import ProviderModelInfo
from claudey.config.provider_catalog import (
    OVHCLOUD_DEFAULT_BASE,
    OVHCLOUD_STATIC_CREDENTIAL,
)
from claudey.core.anthropic.models import Message, MessagesRequest
from claudey.providers.base import ProviderConfig
from claudey.providers.openai_chat import OpenAIChatProvider
from tests.providers.support import (
    immediate_admission,
    profiled_provider,
    reasoning_for,
)


@pytest.fixture
def ovhcloud_provider():
    return profiled_provider(
        "ovhcloud",
        ProviderConfig(
            api_key=OVHCLOUD_STATIC_CREDENTIAL,
            base_url=OVHCLOUD_DEFAULT_BASE,
            rate_limit=10,
            rate_window=60,
        ),
        admission=immediate_admission(),
    )


def test_init_uses_openai_chat_provider(ovhcloud_provider):
    assert isinstance(ovhcloud_provider, OpenAIChatProvider)
    assert ovhcloud_provider._api_key == "ovh-sandbox"
    assert (
        ovhcloud_provider._base_url
        == "https://oai.endpoints.kepler.ai.cloud.ovh.net/v1"
    )


def test_build_request_body_openai_chat(ovhcloud_provider):
    request = MessagesRequest(
        model="Meta-Llama-3.1-8B-Instruct",
        max_tokens=50,
        messages=[Message(role="user", content="hi")],
    )

    body = ovhcloud_provider._build_request_body(
        request, reasoning=reasoning_for(request)
    )

    assert body["model"] == "Meta-Llama-3.1-8B-Instruct"
    assert body["max_tokens"] == 50
    assert body["messages"] == [{"role": "user", "content": "hi"}]
    assert "extra_body" not in body


@pytest.mark.asyncio
async def test_model_list_uses_openai_client_models_endpoint(ovhcloud_provider):
    ovhcloud_provider._client.models.list = AsyncMock(
        return_value=SimpleNamespace(
            data=[SimpleNamespace(id="Meta-Llama-3.1-8B-Instruct")]
        )
    )

    assert await ovhcloud_provider.list_model_infos() == frozenset(
        {ProviderModelInfo("Meta-Llama-3.1-8B-Instruct")}
    )

    ovhcloud_provider._client.models.list.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_cleanup_closes_openai_client(ovhcloud_provider):
    ovhcloud_provider._client = MagicMock()
    ovhcloud_provider._client.close = AsyncMock()

    await ovhcloud_provider.cleanup()

    ovhcloud_provider._client.close.assert_awaited_once()
