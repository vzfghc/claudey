from unittest.mock import patch

import pytest

from claudey.application.errors import UnknownProviderError
from claudey.application.routing import ModelRouter
from claudey.config.custom_providers import (
    CUSTOM_PROVIDERS_PATH_ENV,
    CustomProviderRecord,
    custom_provider_store,
)
from claudey.config.provider_catalog import PROVIDER_CATALOG
from claudey.config.reasoning import ReasoningPreference
from claudey.config.settings import Settings
from claudey.core.anthropic.models import (
    Message,
    MessagesRequest,
    TokenCountRequest,
)
from claudey.core.reasoning import ReasoningControl, ReasoningEffort


@pytest.fixture
def custom_provider(monkeypatch, tmp_path):
    """Register one custom provider in an isolated store, then clear it."""
    monkeypatch.setenv(
        CUSTOM_PROVIDERS_PATH_ENV, str(tmp_path / "custom-providers.json")
    )
    store = custom_provider_store()
    store.upsert(
        CustomProviderRecord(
            provider_id="custom_acme",
            display_name="Acme",
            compatible="openai",
            base_url="https://api.acme.example/v1",
            api_key="sk-acme",
            created_at="2026-01-01T00:00:00+00:00",
        )
    )
    yield
    store.remove("custom_acme")


@pytest.fixture
def settings():
    settings = Settings()
    settings.model = "nvidia_nim/fallback-model"
    settings.model_fable = None
    settings.model_opus = None
    settings.model_sonnet = None
    settings.model_haiku = None
    settings.reasoning_policy = ReasoningPreference.CLIENT
    settings.reasoning_fable = ReasoningPreference.INHERIT
    settings.reasoning_opus = ReasoningPreference.INHERIT
    settings.reasoning_sonnet = ReasoningPreference.INHERIT
    settings.reasoning_haiku = ReasoningPreference.INHERIT
    return settings


def test_model_router_resolves_default_model(settings):
    resolved = ModelRouter(settings).resolve("claude-3-opus")

    assert resolved.original_model == "claude-3-opus"
    assert resolved.provider_id == "nvidia_nim"
    assert resolved.provider_model == "fallback-model"
    assert resolved.provider_model_ref == "nvidia_nim/fallback-model"
    assert resolved.reasoning_preference is ReasoningPreference.CLIENT


def test_model_router_applies_opus_override(settings):
    settings.model_opus = "open_router/deepseek/deepseek-r1"

    request = MessagesRequest(
        model="claude-opus-4-20250514",
        max_tokens=100,
        messages=[Message(role="user", content="hello")],
    )
    routed = ModelRouter(settings).resolve_messages_request(request)

    assert routed.request.model == "deepseek/deepseek-r1"
    assert routed.resolved.provider_model_ref == "open_router/deepseek/deepseek-r1"
    assert routed.resolved.original_model == "claude-opus-4-20250514"
    assert routed.reasoning.control is ReasoningControl.DEFAULT
    assert request.model == "claude-opus-4-20250514"


def test_model_router_applies_fable_override(settings):
    settings.model_fable = "open_router/anthropic/claude-fable-5"

    routed = ModelRouter(settings).resolve_messages_request(
        MessagesRequest(
            model="claude-fable-5",
            max_tokens=100,
            messages=[Message(role="user", content="hello")],
        )
    )

    assert routed.request.model == "anthropic/claude-fable-5"
    assert routed.resolved.provider_model_ref == "open_router/anthropic/claude-fable-5"
    assert routed.resolved.original_model == "claude-fable-5"


def test_model_router_resolves_route_reasoning_preferences(settings):
    settings.reasoning_policy = ReasoningPreference.OFF
    settings.reasoning_fable = ReasoningPreference.HIGH
    settings.reasoning_opus = ReasoningPreference.MAX
    settings.reasoning_haiku = ReasoningPreference.OFF

    router = ModelRouter(settings)

    assert (
        router.resolve("claude-fable-5").reasoning_preference
        is ReasoningPreference.HIGH
    )
    assert (
        router.resolve("claude-opus-4-20250514").reasoning_preference
        is ReasoningPreference.MAX
    )
    assert (
        router.resolve("claude-sonnet-4-20250514").reasoning_preference
        is ReasoningPreference.OFF
    )
    assert (
        router.resolve("claude-3-haiku-20240307").reasoning_preference
        is ReasoningPreference.OFF
    )
    assert router.resolve("claude-2.1").reasoning_preference is ReasoningPreference.OFF


def test_model_router_applies_haiku_override(settings):
    settings.model_haiku = "lmstudio/qwen2.5-7b"

    routed = ModelRouter(settings).resolve_messages_request(
        MessagesRequest(
            model="claude-3-haiku-20240307",
            max_tokens=100,
            messages=[Message(role="user", content="hello")],
        )
    )

    assert routed.request.model == "qwen2.5-7b"
    assert routed.resolved.provider_model_ref == "lmstudio/qwen2.5-7b"


def test_model_router_applies_sonnet_override(settings):
    settings.model_sonnet = "nvidia_nim/meta/llama-3.3-70b-instruct"

    routed = ModelRouter(settings).resolve_messages_request(
        MessagesRequest(
            model="claude-sonnet-4-20250514",
            max_tokens=100,
            messages=[Message(role="user", content="hello")],
        )
    )

    assert routed.request.model == "meta/llama-3.3-70b-instruct"
    assert (
        routed.resolved.provider_model_ref == "nvidia_nim/meta/llama-3.3-70b-instruct"
    )


def test_model_router_routes_prefixed_provider_model_directly(settings):
    routed = ModelRouter(settings).resolve_messages_request(
        MessagesRequest(
            model="deepseek/deepseek-chat",
            max_tokens=100,
            messages=[Message(role="user", content="hello")],
        )
    )

    assert routed.request.model == "deepseek-chat"
    assert routed.resolved.original_model == "deepseek/deepseek-chat"
    assert routed.resolved.provider_id == "deepseek"
    assert routed.resolved.provider_model == "deepseek-chat"
    assert routed.resolved.provider_model_ref == "deepseek/deepseek-chat"


def test_model_router_routes_wafer_provider_model_directly(settings):
    routed = ModelRouter(settings).resolve_messages_request(
        MessagesRequest(
            model="wafer/DeepSeek-V4-Pro",
            max_tokens=100,
            messages=[Message(role="user", content="hello")],
        )
    )

    assert routed.request.model == "DeepSeek-V4-Pro"
    assert routed.resolved.provider_id == "wafer"
    assert routed.resolved.provider_model == "DeepSeek-V4-Pro"
    assert routed.resolved.provider_model_ref == "wafer/DeepSeek-V4-Pro"


def test_model_router_routes_minimax_provider_model_directly(settings):
    routed = ModelRouter(settings).resolve_messages_request(
        MessagesRequest(
            model="minimax/MiniMax-M3",
            max_tokens=100,
            messages=[Message(role="user", content="hello")],
        )
    )

    assert routed.request.model == "MiniMax-M3"
    assert routed.resolved.provider_id == "minimax"
    assert routed.resolved.provider_model == "MiniMax-M3"
    assert routed.resolved.provider_model_ref == "minimax/MiniMax-M3"


def test_model_router_routes_gateway_encoded_provider_model_directly(settings):
    routed = ModelRouter(settings).resolve_messages_request(
        MessagesRequest(
            model="anthropic/nvidia_nim/deepseek-ai/deepseek-v4-pro",
            max_tokens=100,
            messages=[Message(role="user", content="hello")],
        )
    )

    assert routed.request.model == "deepseek-ai/deepseek-v4-pro"
    assert (
        routed.resolved.original_model
        == "anthropic/nvidia_nim/deepseek-ai/deepseek-v4-pro"
    )
    assert routed.resolved.provider_id == "nvidia_nim"
    assert routed.resolved.provider_model == "deepseek-ai/deepseek-v4-pro"
    assert (
        routed.resolved.provider_model_ref
        == "anthropic/nvidia_nim/deepseek-ai/deepseek-v4-pro"
    )


def test_model_router_routes_no_thinking_gateway_model_directly(settings):
    routed = ModelRouter(settings).resolve_messages_request(
        MessagesRequest(
            model="claude-3-claudey-no-thinking/nvidia_nim/deepseek-ai/deepseek-v4-pro",
            max_tokens=100,
            messages=[Message(role="user", content="hello")],
        )
    )

    assert routed.request.model == "deepseek-ai/deepseek-v4-pro"
    assert (
        routed.resolved.original_model
        == "claude-3-claudey-no-thinking/nvidia_nim/deepseek-ai/deepseek-v4-pro"
    )
    assert routed.resolved.provider_id == "nvidia_nim"
    assert routed.resolved.provider_model == "deepseek-ai/deepseek-v4-pro"
    assert routed.reasoning.control is ReasoningControl.OFF


def test_direct_provider_model_uses_root_policy_without_model_name_guessing(settings):
    settings.reasoning_policy = ReasoningPreference.LOW
    settings.reasoning_opus = ReasoningPreference.MAX

    routed = ModelRouter(settings).resolve_messages_request(
        MessagesRequest(
            model="open_router/anthropic/claude-opus-4",
            messages=[Message(role="user", content="hello")],
        )
    )

    assert routed.resolved.provider_id == "open_router"
    assert routed.resolved.provider_model == "anthropic/claude-opus-4"
    assert routed.reasoning.effort is ReasoningEffort.LOW


def test_model_router_routes_token_count_request(settings):
    settings.model_haiku = "lmstudio/qwen2.5-7b"

    request = TokenCountRequest(
        model="claude-3-haiku-20240307",
        messages=[Message(role="user", content="hello")],
    )
    routed = ModelRouter(settings).resolve_token_count_request(request)

    assert routed.request.model == "qwen2.5-7b"
    assert request.model == "claude-3-haiku-20240307"


def test_model_router_logs_mapping(settings):
    with patch("claudey.application.routing.logger.debug") as mock_log:
        ModelRouter(settings).resolve("claude-2.1")

    mock_log.assert_called()
    args = mock_log.call_args[0]
    assert "MODEL MAPPING" in args[0]
    assert args[1] == "claude-2.1"
    assert args[2] == "fallback-model"


def test_model_router_preserves_typed_error_for_unknown_mapped_provider(settings):
    settings.model = "unknown/model"

    with pytest.raises(UnknownProviderError) as exc_info:
        ModelRouter(settings).resolve("claude-2.1")

    supported = "', '".join(PROVIDER_CATALOG)
    assert str(exc_info.value) == (
        f"Unknown provider_type: 'unknown'. Supported: '{supported}'"
    )


@pytest.mark.parametrize("suffix", ["1m", "5m", "128k", "200k"])
def test_model_router_strips_context_window_suffix_from_gateway_model(settings, suffix):
    resolved = ModelRouter(settings).resolve(
        f"anthropic/deepseek/deepseek-v4-flash[{suffix}]"
    )

    assert resolved.provider_model == "deepseek-v4-flash"
    assert resolved.original_model == f"anthropic/deepseek/deepseek-v4-flash[{suffix}]"
    assert resolved.provider_id == "deepseek"


def test_model_router_strips_suffix_from_no_thinking_gateway_model(settings):
    routed = ModelRouter(settings).resolve_messages_request(
        MessagesRequest(
            model="claude-3-claudey-no-thinking/deepseek/deepseek-v4-flash[1m]",
            max_tokens=100,
            messages=[Message(role="user", content="hello")],
        )
    )

    assert routed.request.model == "deepseek-v4-flash"
    assert routed.resolved.provider_model == "deepseek-v4-flash"
    assert (
        routed.resolved.original_model
        == "claude-3-claudey-no-thinking/deepseek/deepseek-v4-flash[1m]"
    )
    assert routed.reasoning.control is ReasoningControl.OFF


def test_model_router_strips_suffix_from_prefixed_provider_model(settings):
    resolved = ModelRouter(settings).resolve("deepseek/deepseek-v4-flash[1m]")

    assert resolved.provider_model == "deepseek-v4-flash"
    assert resolved.original_model == "deepseek/deepseek-v4-flash[1m]"
    assert resolved.provider_id == "deepseek"
    assert resolved.provider_model_ref == "deepseek/deepseek-v4-flash[1m]"


def test_model_router_strips_suffix_from_settings_model_ref(settings):
    settings.model = "deepseek/deepseek-v4-flash[1m]"

    resolved = ModelRouter(settings).resolve("claude-2.1")

    assert resolved.provider_model == "deepseek-v4-flash"
    assert resolved.original_model == "claude-2.1"
    assert resolved.provider_id == "deepseek"
    assert resolved.provider_model_ref == "deepseek/deepseek-v4-flash[1m]"


def test_model_router_leaves_model_without_suffix_unchanged(settings):
    resolved = ModelRouter(settings).resolve("anthropic/deepseek/deepseek-v4-flash")

    assert resolved.provider_model == "deepseek-v4-flash"
    assert resolved.original_model == "anthropic/deepseek/deepseek-v4-flash"
    assert resolved.provider_id == "deepseek"


def test_model_router_strips_suffix_for_token_count_request(settings):
    request = TokenCountRequest(
        model="anthropic/deepseek/deepseek-v4-flash[1m]",
        messages=[Message(role="user", content="hello")],
    )
    routed = ModelRouter(settings).resolve_token_count_request(request)

    assert routed.request.model == "deepseek-v4-flash"
    assert routed.resolved.original_model == "anthropic/deepseek/deepseek-v4-flash[1m]"
    assert request.model == "anthropic/deepseek/deepseek-v4-flash[1m]"


def test_model_router_resolves_direct_custom_provider_model(settings, custom_provider):
    resolved = ModelRouter(settings).resolve("custom_acme/acme-model")

    assert resolved.provider_id == "custom_acme"
    assert resolved.provider_model == "acme-model"
    assert resolved.provider_model_ref == "custom_acme/acme-model"


def test_model_router_resolves_custom_provider_from_settings_ref(
    settings, custom_provider
):
    settings.model = "custom_acme/acme-model"
    resolved = ModelRouter(settings).resolve("claude-sonnet-4")

    assert resolved.provider_id == "custom_acme"
    assert resolved.provider_model == "acme-model"


def test_model_router_rejects_unknown_custom_provider(settings):
    settings.model = "custom_nope/acme-model"
    with pytest.raises(UnknownProviderError):
        ModelRouter(settings).resolve("claude-sonnet-4")


def test_model_router_treats_unregistered_custom_ref_as_client_model(settings):
    # An unregistered custom_-prefixed ref in the client model name is not a
    # routable provider id; it maps through the configured fallback model just
    # like any other unknown prefixed model name.
    resolved = ModelRouter(settings).resolve("custom_absent/model")

    assert resolved.provider_id == "nvidia_nim"
    assert resolved.provider_model == "fallback-model"
