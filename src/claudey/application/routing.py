"""Model routing for Claude-compatible requests."""

from dataclasses import dataclass

from loguru import logger

from claudey.application.errors import UnknownProviderError
from claudey.config.custom_providers import custom_provider_ids
from claudey.config.model_refs import (
    parse_chain_refs,
    parse_model_name,
    parse_provider_type,
)
from claudey.config.provider_catalog import (
    PROVIDER_CATALOG,
    SUPPORTED_PROVIDER_IDS,
)
from claudey.config.reasoning import ReasoningPreference
from claudey.config.settings import Settings
from claudey.core.anthropic import MessagesRequest, TokenCountRequest
from claudey.core.gateway_model_ids import (
    decode_gateway_model_id,
    strip_context_window_suffix,
)
from claudey.core.reasoning import ReasoningPolicy

from .reasoning import resolve_reasoning_policy

_ROUTE_SETTINGS = (
    ("fable", "model_fable", "reasoning_fable"),
    ("opus", "model_opus", "reasoning_opus"),
    ("haiku", "model_haiku", "reasoning_haiku"),
    ("sonnet", "model_sonnet", "reasoning_sonnet"),
)


def _runtime_provider_ids() -> frozenset[str]:
    """Ids considered routable: static catalog plus admin-defined custom providers.

    Custom providers are added and removed at runtime (``custom_providers.json``),
    never statically, so this must be consulted live rather than folded into
    ``SUPPORTED_PROVIDER_IDS``.
    """
    return frozenset(custom_provider_ids())


def _is_runtime_provider_id(provider_id: str) -> bool:
    return (
        provider_id in SUPPORTED_PROVIDER_IDS or provider_id in _runtime_provider_ids()
    )


@dataclass(frozen=True, slots=True)
class ResolvedModel:
    original_model: str
    provider_id: str
    provider_model: str
    provider_model_ref: str
    reasoning_preference: ReasoningPreference


@dataclass(frozen=True, slots=True)
class RoutedMessagesRequest:
    request: MessagesRequest
    resolved: ResolvedModel
    reasoning: ReasoningPolicy


@dataclass(frozen=True, slots=True)
class ChainResolution:
    """An ordered failover chain for one incoming model name.

    ``chain[0]`` is the primary node, mirroring ``resolve()``. All nodes share the
    gateway ``original_model`` and the primary node's reasoning preference; the
    reasoning *policy* is resolved once from the primary (chains are a routing
    concern, not a reasoning concern).
    """

    chain: tuple[ResolvedModel, ...]
    reasoning: ReasoningPolicy | None

    @property
    def primary(self) -> ResolvedModel:
        """Return the primary (first) chain node."""
        return self.chain[0]


@dataclass(frozen=True, slots=True)
class RoutedTokenCountRequest:
    request: TokenCountRequest
    resolved: ResolvedModel


class ModelRouter:
    """Resolve incoming Claude model names to configured provider/model pairs."""

    def __init__(self, settings: Settings):
        self._settings = settings

    def resolve(self, claude_model_name: str) -> ResolvedModel:
        (
            direct_provider_id,
            direct_provider_model,
            force_reasoning_off,
        ) = self._direct_provider_model(claude_model_name)
        if direct_provider_id is not None and direct_provider_model is not None:
            reasoning_preference = (
                ReasoningPreference.OFF
                if force_reasoning_off
                else self._settings.reasoning_policy
            )
            logger.debug(
                "MODEL DIRECT: '{}' -> provider='{}' model='{}' reasoning={}",
                claude_model_name,
                direct_provider_id,
                direct_provider_model,
                reasoning_preference.value,
            )
            return ResolvedModel(
                original_model=claude_model_name,
                provider_id=direct_provider_id,
                provider_model=strip_context_window_suffix(direct_provider_model),
                provider_model_ref=claude_model_name,
                reasoning_preference=reasoning_preference,
            )

        provider_model_ref = self._resolve_model_ref(claude_model_name)
        reasoning_preference = self._resolve_reasoning_preference(claude_model_name)
        provider_id = parse_provider_type(provider_model_ref)
        self._validate_provider_id(provider_id)
        provider_model = parse_model_name(provider_model_ref)
        if provider_model != claude_model_name:
            logger.debug(
                "MODEL MAPPING: '{}' -> '{}'", claude_model_name, provider_model
            )
        return ResolvedModel(
            original_model=claude_model_name,
            provider_id=provider_id,
            provider_model=strip_context_window_suffix(provider_model),
            provider_model_ref=provider_model_ref,
            reasoning_preference=reasoning_preference,
        )

    @staticmethod
    def _validate_provider_id(provider_id: str) -> None:
        if (
            provider_id not in PROVIDER_CATALOG
            and provider_id not in _runtime_provider_ids()
        ):
            raise UnknownProviderError.for_provider(provider_id, PROVIDER_CATALOG)

    def _direct_provider_model(
        self, model_name: str
    ) -> tuple[str | None, str | None, bool]:
        decoded = decode_gateway_model_id(model_name)
        if decoded is not None:
            if not _is_runtime_provider_id(decoded.provider_id):
                return None, None, False
            return (
                decoded.provider_id,
                decoded.provider_model,
                decoded.force_reasoning_off,
            )

        provider_id, separator, provider_model = model_name.partition("/")
        if not separator:
            return None, None, False
        if not _is_runtime_provider_id(provider_id):
            return None, None, False
        if not provider_model:
            return None, None, False
        return provider_id, provider_model, False

    def _resolve_model_ref(self, claude_model_name: str) -> str:
        """Resolve a Claude model name to the primary configured provider/model ref.

        The primary node is the first item of the tier's chain (a single ref, the
        first node of an inline chain, or the top-priority combo node).
        """
        return self._resolve_chain_refs(claude_model_name)[0]

    def _resolve_chain_refs(self, claude_model_name: str) -> tuple[str, ...]:
        """Return the ordered provider/model refs for a tier chain.

        Combines the matched route's (or default) tier setting — expanded through
        the chain grammar — with ``global_fallback_model`` appended last when set
        and not already present. Direct provider/model overrides are detected by
        the caller, not here.
        """
        value = self._chain_model_setting(claude_model_name)
        refs = list(parse_chain_refs(value))
        fallback = getattr(self._settings, "global_fallback_model", None)
        if fallback and fallback not in refs:
            refs.append(fallback)
        return tuple(refs)

    def _chain_model_setting(self, claude_model_name: str) -> str:
        """Return the raw tier setting value (single ref, chain, or @combo:)."""
        route = self._matched_route(claude_model_name)
        if route is not None:
            model = getattr(self._settings, route[1])
            if isinstance(model, str):
                return model
        return self._settings.model

    def resolve_chain(
        self,
        claude_model_name: str,
        *,
        request: MessagesRequest | None = None,
    ) -> ChainResolution:
        """Return the ordered failover chain for a Claude model name.

        For explicit provider/model overrides (a direct provider id or gateway-
        encoded id) the chain is a single node, matching ``resolve()``. Otherwise
        it is the tier's expanded chain (inline or ``@combo:``) plus the global
        fallback as a terminal hop. Reasoning is resolved once from the primary
        node; pass ``request`` to derive the concrete :class:`ReasoningPolicy`.
        """
        primary = self.resolve(claude_model_name)
        if primary.provider_model_ref == claude_model_name:
            refs = (primary.provider_model_ref,)
        else:
            refs = self._resolve_chain_refs(claude_model_name)

        chain = tuple(
            ResolvedModel(
                original_model=claude_model_name,
                provider_id=parse_provider_type(ref),
                provider_model=strip_context_window_suffix(parse_model_name(ref)),
                provider_model_ref=ref,
                reasoning_preference=primary.reasoning_preference,
            )
            for ref in refs
        )

        reasoning: ReasoningPolicy | None = None
        if request is not None:
            routed = request.model_copy(
                update={"model": primary.provider_model}, deep=True
            )
            reasoning = resolve_reasoning_policy(routed, primary.reasoning_preference)
        return ChainResolution(chain=chain, reasoning=reasoning)

    def _resolve_reasoning_preference(
        self, claude_model_name: str
    ) -> ReasoningPreference:
        """Resolve a route override without inspecting the provider model."""

        route = self._matched_route(claude_model_name)
        if route is not None:
            preference = getattr(self._settings, route[2])
            if preference is not ReasoningPreference.INHERIT:
                return preference
        return self._settings.reasoning_policy

    @staticmethod
    def _matched_route(model_name: str) -> tuple[str, str, str] | None:
        normalized = model_name.lower()
        return next(
            (route for route in _ROUTE_SETTINGS if route[0] in normalized),
            None,
        )

    def resolve_messages_request(
        self, request: MessagesRequest
    ) -> RoutedMessagesRequest:
        """Return an internal routed request context."""
        resolved = self.resolve(request.model)
        routed = request.model_copy(deep=True)
        routed.model = resolved.provider_model
        return RoutedMessagesRequest(
            request=routed,
            resolved=resolved,
            reasoning=resolve_reasoning_policy(
                routed,
                resolved.reasoning_preference,
            ),
        )

    def resolve_token_count_request(
        self, request: TokenCountRequest
    ) -> RoutedTokenCountRequest:
        """Return an internal token-count request context."""
        resolved = self.resolve(request.model)
        routed = request.model_copy(
            update={"model": resolved.provider_model}, deep=True
        )
        return RoutedTokenCountRequest(request=routed, resolved=resolved)
