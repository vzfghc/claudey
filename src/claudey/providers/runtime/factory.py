"""Provider construction from declarative profiles and exceptional adapters."""

from collections.abc import Callable, Mapping

from claudey.config.custom_providers import (
    CustomProviderRecord,
    effective_api_key,
    find_custom_provider,
)
from claudey.config.provider_catalog import (
    INJECTED_PROVIDER_IDS,
    PROVIDER_CATALOG,
    ProviderAuthKind,
)
from claudey.config.settings import Settings
from claudey.core.errors import (
    ApplicationUnavailableError,
    UnknownProviderError,
)
from claudey.providers.admission import ProviderAdmissionController
from claudey.providers.base import BaseProvider, ProviderConfig
from claudey.providers.openai_chat import (
    OPENAI_CHAT_PROFILES,
    OpenAIChatProvider,
    create_openai_chat_provider,
    custom_openai_chat_profile,
)

from .config import build_provider_config

ProviderFactory = Callable[
    [ProviderConfig, Settings, ProviderAdmissionController], BaseProvider
]


def _create_nvidia_nim(
    config: ProviderConfig,
    settings: Settings,
    admission: ProviderAdmissionController,
) -> BaseProvider:
    from claudey.providers.nvidia_nim import NvidiaNimProvider

    return NvidiaNimProvider(
        config,
        nim_settings=settings.nim,
        admission=admission,
    )


def _create_open_router(
    config: ProviderConfig,
    _settings: Settings,
    admission: ProviderAdmissionController,
) -> BaseProvider:
    from claudey.providers.open_router import OpenRouterProvider

    return OpenRouterProvider(config, admission=admission)


def _create_mistral(
    config: ProviderConfig,
    _settings: Settings,
    admission: ProviderAdmissionController,
) -> BaseProvider:
    from claudey.providers.mistral import MistralProvider

    return MistralProvider(config, admission=admission)


def _create_kilo(
    config: ProviderConfig,
    _settings: Settings,
    admission: ProviderAdmissionController,
) -> BaseProvider:
    from claudey.providers.kilo import KiloProvider

    return KiloProvider(config, admission=admission)


def _create_deepseek(
    config: ProviderConfig,
    _settings: Settings,
    admission: ProviderAdmissionController,
) -> BaseProvider:
    from claudey.providers.deepseek import DeepSeekProvider

    return DeepSeekProvider(config, admission=admission)


def _create_lmstudio(
    config: ProviderConfig,
    _settings: Settings,
    admission: ProviderAdmissionController,
) -> BaseProvider:
    from claudey.providers.lmstudio import LMStudioProvider

    return LMStudioProvider(config, admission=admission)


def _create_cloudflare(
    config: ProviderConfig,
    settings: Settings,
    admission: ProviderAdmissionController,
) -> BaseProvider:
    from claudey.providers.cloudflare import CloudflareProvider

    return CloudflareProvider(
        config,
        account_id=settings.cloudflare_account_id,
        admission=admission,
    )


def _create_gemini(
    config: ProviderConfig,
    _settings: Settings,
    admission: ProviderAdmissionController,
) -> BaseProvider:
    from claudey.providers.gemini import GeminiProvider

    return GeminiProvider(config, admission=admission)


def _create_vertex(
    config: ProviderConfig,
    settings: Settings,
    admission: ProviderAdmissionController,
) -> BaseProvider:
    from claudey.providers.vertex import VertexProvider

    return VertexProvider(
        config,
        project_id=settings.vertex_project_id,
        location=settings.vertex_location,
        admission=admission,
    )


def _create_github_models(
    config: ProviderConfig,
    _settings: Settings,
    admission: ProviderAdmissionController,
) -> BaseProvider:
    from claudey.providers.github_models import GitHubModelsProvider

    return GitHubModelsProvider(config, admission=admission)


_SPECIAL_PROVIDER_FACTORIES: dict[str, ProviderFactory] = {
    "nvidia_nim": _create_nvidia_nim,
    "open_router": _create_open_router,
    "mistral": _create_mistral,
    "kilo": _create_kilo,
    "deepseek": _create_deepseek,
    "lmstudio": _create_lmstudio,
    "cloudflare": _create_cloudflare,
    "gemini": _create_gemini,
    "vertex": _create_vertex,
    "github_models": _create_github_models,
}
_connected_account_ids = {
    pid
    for pid, desc in PROVIDER_CATALOG.items()
    if desc.auth_kind == ProviderAuthKind.CONNECTED_ACCOUNT
}

_profiled_ids = set(OPENAI_CHAT_PROFILES)
_special_ids = set(_SPECIAL_PROVIDER_FACTORIES)
_construction_ids = (
    _profiled_ids | _special_ids | INJECTED_PROVIDER_IDS | _connected_account_ids
)
if (
    _profiled_ids & _special_ids
    or _profiled_ids & INJECTED_PROVIDER_IDS
    or _special_ids & INJECTED_PROVIDER_IDS
    or _construction_ids != set(PROVIDER_CATALOG)
):
    raise AssertionError(
        "Every provider must have exactly one construction owner: "
        f"profiles={_profiled_ids!r} special={_special_ids!r} "
        f"injected={INJECTED_PROVIDER_IDS!r} catalog={set(PROVIDER_CATALOG)!r}"
    )


def create_provider(
    provider_id: str,
    settings: Settings,
    *,
    injected_factories: Mapping[str, ProviderFactory] | None = None,
) -> BaseProvider:
    """Create a provider instance for a supported provider id."""
    custom = find_custom_provider(provider_id)
    if custom is not None:
        return _create_custom_provider(custom, settings)

    descriptor = PROVIDER_CATALOG.get(provider_id)
    if descriptor is None:
        raise UnknownProviderError.for_provider(provider_id, PROVIDER_CATALOG)

    config = build_provider_config(descriptor, settings)
    admission = ProviderAdmissionController(
        provider_name=provider_id,
        rate_limit=config.rate_limit or 40,
        rate_window=config.rate_window or 60.0,
        max_concurrency=config.max_concurrency,
    )
    factory = (injected_factories or {}).get(provider_id)
    if provider_id in INJECTED_PROVIDER_IDS and factory is None:
        raise ApplicationUnavailableError(
            f"Provider {provider_id!r} is unavailable in this runtime."
        )
    factory = factory or _SPECIAL_PROVIDER_FACTORIES.get(provider_id)
    if factory is not None:
        return factory(config, settings, admission)
    if provider_id in _connected_account_ids:
        # Connected-account ids only own OAuth/login state; without an injected
        # or special factory they have no construction owner. Fall through to a
        # clean user-facing error instead of an internal KeyError from the
        # OpenAI-chat profile dispatch.
        raise ApplicationUnavailableError(
            f"Provider {provider_id!r} is an OAuth connected account with no "
            "runtime provider; route requests through a tier model instead of "
            "a direct override."
        )
    return create_openai_chat_provider(provider_id, config, admission)


def _create_custom_provider(
    record: CustomProviderRecord,
    settings: Settings,
) -> BaseProvider:
    """Construct a provider for an admin-defined custom provider record.

    The record's base URL and API key come from the user, so the provider config
    is built directly from the record rather than from the static catalog.
    ``openai`` records reuse the generic ``OpenAIChatProvider`` (the same
    transport Pecut uses); ``anthropic`` records forward the Anthropic wire
    protocol to the compatible endpoint.
    """
    config = ProviderConfig(
        api_key=effective_api_key(record),
        base_url=record.base_url,
        rate_limit=settings.provider_rate_limit,
        rate_window=settings.provider_rate_window,
        max_concurrency=settings.provider_max_concurrency,
        http_read_timeout=settings.http_read_timeout,
        http_write_timeout=settings.http_write_timeout,
        http_connect_timeout=settings.http_connect_timeout,
        proxy="",
        log_raw_sse_events=settings.log_raw_sse_events,
        log_api_error_tracebacks=settings.log_api_error_tracebacks,
    )
    admission = ProviderAdmissionController(
        provider_name=record.provider_id,
        rate_limit=config.rate_limit or 40,
        rate_window=config.rate_window or 60.0,
        max_concurrency=config.max_concurrency,
    )
    if record.compatible == "anthropic":
        from claudey.providers.anthropic.messages import AnthropicMessagesProvider

        return AnthropicMessagesProvider(config, admission=admission)
    return OpenAIChatProvider(
        config,
        profile=custom_openai_chat_profile(record.provider_id),
        admission=admission,
    )
