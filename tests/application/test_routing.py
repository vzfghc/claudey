from unittest.mock import patch

import pytest

from claudey.application.routing import ModelRouter
from claudey.config.combos import (
    COMBOS_PATH_ENV,
    ComboNode,
    ComboRecord,
    combo_store,
)
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
from claudey.core.errors import UnknownProviderError
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
def seeded_combo(monkeypatch, tmp_path):
    """Seed one ``flagship`` combo in an isolated-path store."""
    monkeypatch.setenv(COMBOS_PATH_ENV, str(tmp_path / "combos.json"))
    combo_store().upsert(
        ComboRecord(
            combo_id="flagship",
            display_name="Flagship",
            nodes=(
                ComboNode("open_router/**/deepseek/deepseek-r1", priority=1),
                ComboNode("routeway/meta-llama/llama-3.1-70b", priority=0),
            ),
        )
    )
    yield


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


@pytest.mark.parametrize(
    "model_name",
    [
        "anthropic/claude-sonnet-5",
        "anthropic/claude-opus-4-20250514",
    ],
)
def test_model_router_anthropic_overrides_fall_through_to_chain(settings, model_name):
    """Bare ``anthropic/`` overrides must not route to the phantom provider.

    ``anthropic`` is a connected-account id with no injected client or factory;
    routing ``anthropic/<model>`` to it used to explode with an internal
    KeyError (500 server_error). Such overrides fall through to the configured
    tier chain instead.
    """
    resolved = ModelRouter(settings).resolve(model_name)

    assert resolved.provider_id == "nvidia_nim"
    assert resolved.provider_model == "fallback-model"
    assert resolved.provider_model_ref == "nvidia_nim/fallback-model"


def test_model_router_openai_override_routes_direct(settings):
    """``openai/<model>`` stays a direct override: openai is runtime-injected.

    The OpenAI/ChatGPT connected account has a construction path, so a bare
    ``openai/`` prefix must not fall through to the tier chain.
    """
    resolved = ModelRouter(settings).resolve("openai/gpt-4o")

    assert resolved.provider_id == "openai"
    assert resolved.provider_model == "gpt-4o"
    assert resolved.provider_model_ref == "openai/gpt-4o"


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


# --- resolve_chain (failover chains) ---


def _chain_refs(settings, model_name):
    return [
        node.provider_model_ref
        for node in ModelRouter(settings).resolve_chain(model_name).chain
    ]


def test_resolve_chain_single_ref_is_single_node(settings):
    chain = ModelRouter(settings).resolve_chain("claude-3-opus")

    assert [node.provider_model_ref for node in chain.chain] == [
        "nvidia_nim/fallback-model"
    ]
    assert chain.primary is chain.chain[0]
    assert chain.primary.provider_id == "nvidia_nim"
    assert chain.primary.original_model == "claude-3-opus"


def test_resolve_chain_expands_inline_chain(settings):
    settings.model_opus = "open_router/a,novita/b"

    assert _chain_refs(settings, "claude-opus-4-20250514") == [
        "open_router/a",
        "novita/b",
    ]
    chain = ModelRouter(settings).resolve_chain("claude-opus-4-20250514")
    assert chain.primary.provider_id == "open_router"
    assert chain.primary.provider_model == "a"
    assert all(node.original_model == "claude-opus-4-20250514" for node in chain.chain)


def test_resolve_chain_appends_global_fallback_last(settings):
    settings.global_fallback_model = "open_router/openrouter/free"

    assert _chain_refs(settings, "claude-3-opus") == [
        "nvidia_nim/fallback-model",
        "open_router/openrouter/free",
    ]


def test_resolve_chain_inline_plus_fallback(settings):
    settings.model_haiku = "open_router/a,novita/b"
    settings.global_fallback_model = "deepseek/deepseek-chat"

    assert _chain_refs(settings, "claude-3-haiku-20240307") == [
        "open_router/a",
        "novita/b",
        "deepseek/deepseek-chat",
    ]


def test_resolve_chain_expands_combo(settings, seeded_combo):
    settings.model_sonnet = "@combo:flagship"

    assert _chain_refs(settings, "claude-sonnet-4-20250514") == [
        "routeway/meta-llama/llama-3.1-70b",  # priority 0 first
        "open_router/**/deepseek/deepseek-r1",
    ]


def test_resolve_chain_combo_plus_fallback(settings, seeded_combo):
    settings.model_sonnet = "@combo:flagship"
    settings.global_fallback_model = "nvidia_nim/fallback-model"

    assert _chain_refs(settings, "claude-sonnet-4-20250514") == [
        "routeway/meta-llama/llama-3.1-70b",
        "open_router/**/deepseek/deepseek-r1",
        "nvidia_nim/fallback-model",
    ]


def test_resolve_chain_direct_override_is_single_node(settings):
    assert _chain_refs(settings, "deepseek/deepseek-chat") == ["deepseek/deepseek-chat"]


def test_resolve_chain_gateway_encoded_direct_override_keeps_decoded_provider(settings):
    """Gateway-encoded direct overrides reuse the decoded primary node.

    Regression: re-parsing the raw model name mis-split
    ``claude-3-claudey-no-thinking/<provider>/<model>`` (and
    ``anthropic/<provider>/<model>``) into a non-existent provider type,
    breaking the failover chain for every Claude Code-discoverable gateway /
    no-thinking model.
    """
    no_thinking = ModelRouter(settings).resolve_chain(
        "claude-3-claudey-no-thinking/nvidia_nim/deepseek-ai/deepseek-v4-pro"
    )
    assert [node.provider_model_ref for node in no_thinking.chain] == [
        "claude-3-claudey-no-thinking/nvidia_nim/deepseek-ai/deepseek-v4-pro"
    ]
    assert no_thinking.primary.provider_id == "nvidia_nim"
    assert no_thinking.primary.provider_model == "deepseek-ai/deepseek-v4-pro"
    assert no_thinking.primary.reasoning_preference is ReasoningPreference.OFF

    gateway = ModelRouter(settings).resolve_chain(
        "anthropic/nvidia_nim/deepseek-ai/deepseek-v4-pro"
    )
    assert [node.provider_model_ref for node in gateway.chain] == [
        "anthropic/nvidia_nim/deepseek-ai/deepseek-v4-pro"
    ]
    assert gateway.primary.provider_id == "nvidia_nim"
    assert gateway.primary.provider_model == "deepseek-ai/deepseek-v4-pro"
    assert gateway.primary.reasoning_preference is not ReasoningPreference.OFF


def test_resolve_chain_reasoning_derived_from_primary_when_request_given(settings):
    settings.reasoning_policy = ReasoningPreference.HIGH
    request = MessagesRequest(
        model="claude-opus-4-20250514",
        max_tokens=100,
        messages=[Message(role="user", content="hello")],
    )

    resolution = ModelRouter(settings).resolve_chain(
        "claude-opus-4-20250514", request=request
    )

    assert resolution.reasoning is not None
    assert resolution.reasoning.effort is ReasoningEffort.HIGH
    assert request.model == "claude-opus-4-20250514"


def test_resolve_chain_without_request_has_no_reasoning_policy(settings):
    resolution = ModelRouter(settings).resolve_chain("claude-3-opus")

    assert resolution.reasoning is None
