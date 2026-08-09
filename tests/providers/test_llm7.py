"""Tests for the LLM7 OpenAI-chat provider."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from claudey.application.model_metadata import ProviderModelInfo
from claudey.config.provider_catalog import (
    LLM7_DEFAULT_BASE,
    LLM7_STATIC_CREDENTIAL,
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
def llm7_provider():
    return profiled_provider(
        "llm7",
        ProviderConfig(
            api_key=LLM7_STATIC_CREDENTIAL,
            base_url=LLM7_DEFAULT_BASE,
            rate_limit=10,
            rate_window=60,
        ),
        admission=immediate_admission(),
    )


def test_init_uses_openai_chat_provider(llm7_provider):
    assert isinstance(llm7_provider, OpenAIChatProvider)
    assert llm7_provider._api_key == "llm7"
    assert llm7_provider._base_url == "https://api.llm7.io/v1"


def test_build_request_body_openai_chat(llm7_provider):
    request = MessagesRequest(
        model="meta-llama/llama-3.1-70b-instruct",
        max_tokens=50,
        messages=[Message(role="user", content="hi")],
    )

    body = llm7_provider._build_request_body(request, reasoning=reasoning_for(request))

    assert body["model"] == "meta-llama/llama-3.1-70b-instruct"
    assert body["max_tokens"] == 50
    assert body["messages"] == [{"role": "user", "content": "hi"}]
    assert "extra_body" not in body


@pytest.mark.asyncio
async def test_model_list_uses_openai_client_models_endpoint(llm7_provider):
    llm7_provider._client.models.list = AsyncMock(
        return_value=SimpleNamespace(
            data=[SimpleNamespace(id="meta-llama/llama-3.1-70b")]
        )
    )

    assert await llm7_provider.list_model_infos() == frozenset(
        {ProviderModelInfo("meta-llama/llama-3.1-70b")}
    )

    llm7_provider._client.models.list.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_cleanup_closes_openai_client(llm7_provider):
    llm7_provider._client = MagicMock()
    llm7_provider._client.close = AsyncMock()

    await llm7_provider.cleanup()

    llm7_provider._client.close.assert_awaited_once()
