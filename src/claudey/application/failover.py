"""Cross-node failover executor wrapping :class:`ProviderExecutor`.

Tries each node of a :class:`ChainResolution` in order, consulting the health
registry to skip degraded/locked nodes, failing over only on **eligible,
retryable** failures *before any user-visible content chunk is emitted*, and
surfacing ineligible/after-content failures immediately. Mirrors OmniRoute's
failover semantics on top of Claude's existing per-node admission/recovery ring.
"""

from collections.abc import AsyncIterator
from typing import Literal

from loguru import logger

from claudey.application.execution import ProviderExecutor, TokenCounter
from claudey.application.ports import ProviderResolver
from claudey.application.routing import (
    ChainResolution,
    ModelRouter,
    ResolvedModel,
    RoutedMessagesRequest,
)
from claudey.core.anthropic import MessagesRequest, get_token_count
from claudey.core.failures import ExecutionFailure, FailureKind, find_execution_failure
from claudey.core.reasoning import ReasoningPolicy
from claudey.core.trace import trace_event

from .health import HealthRegistry, health_registry
from .reasoning import resolve_reasoning_policy

WireApi = Literal["messages", "responses"]

# Failover-eligible kinds (gated on ``retryable=True``); a fallback never helps
# for auth, permissions, or invalid requests.
FAILOVER_ELIGIBLE_KINDS = frozenset(
    {
        FailureKind.RATE_LIMIT,
        FailureKind.OVERLOADED,
        FailureKind.TIMEOUT,
        FailureKind.UPSTREAM,
        FailureKind.UNAVAILABLE,
    }
)

NO_USABLE_NODE_KIND = FailureKind.UNAVAILABLE
NO_USABLE_NODE_STATUS = 503


def _failover_eligible(failure: ExecutionFailure) -> bool:
    """Return whether a finalized failure may trigger chain failover."""
    return failure.kind in FAILOVER_ELIGIBLE_KINDS and failure.retryable


def format_route_header(
    executor: FallbackExecutor,
    router: ModelRouter,
    resolution: ChainResolution,
    model_ref: str,
) -> str:
    """Build the ``x-claudey-route`` value for a failover chain.

    Returns a ``provider/model`` reference, appending ``; why=<reason>`` when
    the primary was skipped by the health registry.
    """
    provider_model_ref, fail_why = executor.primary_route(
        resolution, chain_identity=router.chain_identity(model_ref)
    )
    if fail_why is not None:
        return f"{provider_model_ref}; why={fail_why}"
    return provider_model_ref


def is_content_start(chunk: str) -> bool:
    """Return whether an SSE chunk begins user-visible content.

    ``message_start`` / ``content_block_start`` are the point of no return: once
    either has been emitted we cannot un-send it, so failover is illegal.
    """
    return "message_start" in chunk or "content_block_start" in chunk


class FallbackExecutor:
    """Executor that owns a whole failover chain for one outgoing request."""

    def __init__(
        self,
        provider_resolver: ProviderResolver,
        *,
        token_counter: TokenCounter = get_token_count,
        generation_id: int | None = None,
        log_raw_payloads: bool = False,
        health: HealthRegistry | None = None,
    ) -> None:
        self._provider_resolver = provider_resolver
        self._token_counter = token_counter
        self._generation_id = generation_id
        self._log_raw_payloads = log_raw_payloads
        self._health = health or health_registry()
        self._provider_executor = ProviderExecutor(
            provider_resolver,
            token_counter=token_counter,
            generation_id=generation_id,
            log_raw_payloads=log_raw_payloads,
        )

    def primary_route(
        self,
        resolution: ChainResolution,
        chain_identity: str | None = None,
    ) -> tuple[str, str | None]:
        """Return ``(provider_model_ref, fail_why)`` for the initial usable node.

        Mirrors :meth:`stream`'s traversal so an API handler can present the
        chosen route (e.g. as an ``x-claudey-route`` header) before streaming
        begins. ``fail_why`` is None when the primary serves, else the reason it
        was skipped.
        """
        nodes = self._ordered_nodes(resolution, chain_identity)
        if not nodes:
            return "", "no-usable"
        for node in nodes:
            if self._health.should_skip(node.provider_model_ref):
                continue
            return node.provider_model_ref, None
        return nodes[0].provider_model_ref, self._health.effective_state(
            nodes[0].provider_model_ref
        ).value

    def stream(
        self,
        resolution: ChainResolution,
        request: MessagesRequest,
        *,
        wire_api: WireApi,
        raw_log_label: str,
        raw_log_payload: object,
        request_id: str,
        chain_identity: str | None = None,
        reasoning: ReasoningPolicy | None = None,
    ) -> AsyncIterator[str]:
        """Stream the first healthy chain node, failing over before content.

        ``reasoning`` lets callers override every node's policy after inbound
        routing policies have been applied (e.g. safety-classifier no-thinking).
        When omitted, each node derives its policy from the chain's primary.
        """
        nodes = self._ordered_nodes(resolution, chain_identity)
        self._preflight_first(nodes, request, reasoning)
        chain_refs: list[str] = [node.provider_model_ref for node in nodes]

        async def _stream() -> AsyncIterator[str]:
            content_emitted = False
            tried_any = False

            for attempt, node in enumerate(nodes, start=1):
                if self._health.should_skip(node.provider_model_ref):
                    self._trace_skip(node, attempt, request_id)
                    continue

                tried_any = True
                node_reasoning = reasoning or resolution.reasoning
                routed = self._routed_node(request, node, node_reasoning)
                route_trace_extra: dict[str, object] = {
                    "chain": chain_refs,
                    "node_index": attempt,
                }
                if chain_identity is not None:
                    route_trace_extra["chain_identity"] = chain_identity
                try:
                    async for chunk in self._provider_executor.stream(
                        routed,
                        wire_api=wire_api,
                        raw_log_label=raw_log_label,
                        raw_log_payload=raw_log_payload,
                        request_id=request_id,
                        preflight=False,
                        route_trace_extra=route_trace_extra,
                    ):
                        if is_content_start(chunk):
                            content_emitted = True
                        yield chunk
                    self._record_success(node, chain_identity)
                    return
                except Exception as exc:
                    failure = find_execution_failure(exc)
                    if failure is None:
                        raise
                    self._health.record_failure(node.provider_model_ref, failure.kind)
                    if not _failover_eligible(failure) or content_emitted:
                        raise
                    if self._next_tryable_index(nodes, attempt) is None:
                        # Eligible, but nothing left to try: surface the failure.
                        raise
                    self._trace_failover(node, failure.kind, attempt, request_id)
                    logger.warning(
                        "FAILOVER: node '{}' failed ({}) -> advancing (attempt {})",
                        node.provider_model_ref,
                        failure.kind.value,
                        attempt,
                    )

            if not tried_any:
                raise ExecutionFailure(
                    kind=NO_USABLE_NODE_KIND,
                    status_code=NO_USABLE_NODE_STATUS,
                    message="No usable failover node for the request chain.",
                    retryable=False,
                )

        return _stream()

    def _next_tryable_index(
        self, nodes: tuple[ResolvedModel, ...], start: int
    ) -> int | None:
        """Index of the next node after ``start`` that health says is usable."""
        for index in range(start, len(nodes)):
            if not self._health.should_skip(nodes[index].provider_model_ref):
                return index
        return None

    def _ordered_nodes(
        self, resolution: ChainResolution, chain_identity: str | None
    ) -> tuple[ResolvedModel, ...]:
        """Return chain nodes, preferring the LKG-P primary when usable."""
        nodes = list(resolution.chain)
        if chain_identity:
            preferred = self._health.preferred_primary(chain_identity)
            if preferred and not self._health.should_skip(preferred):
                for index, node in enumerate(nodes):
                    if node.provider_model_ref == preferred:
                        nodes.insert(0, nodes.pop(index))
                        break
        return tuple(nodes)

    def _preflight_first(
        self,
        nodes: tuple[ResolvedModel, ...],
        request: MessagesRequest,
        reasoning: ReasoningPolicy | None,
    ) -> None:
        """Preflight the first usable node synchronously.

        Mirrors :meth:`ProviderExecutor.stream`, which preflights before returning
        its iterator, so application-level validation errors (e.g. invalid
        requests) surface to the caller synchronously rather than lazily inside
        the stream.
        """
        for node in nodes:
            if self._health.should_skip(node.provider_model_ref):
                continue
            node_reasoning = reasoning or self._resolve_policy(node, request)
            routed = self._routed_node(request, node, node_reasoning)
            provider = self._provider_resolver(node.provider_id)
            provider.preflight_stream(routed.request, reasoning=routed.reasoning)
            return

    def _resolve_policy(
        self, node: ResolvedModel, request: MessagesRequest
    ) -> ReasoningPolicy:
        routed_request = request.model_copy(
            update={"model": node.provider_model}, deep=True
        )
        return resolve_reasoning_policy(routed_request, node.reasoning_preference)

    def _routed_node(
        self,
        request: MessagesRequest,
        node: ResolvedModel,
        reasoning: ReasoningPolicy | None,
    ) -> RoutedMessagesRequest:
        """Build a rerouted request pointing at one specific chain node."""
        routed_request = request.model_copy(
            update={"model": node.provider_model}, deep=True
        )
        if reasoning is None:
            reasoning = resolve_reasoning_policy(
                routed_request, node.reasoning_preference
            )
        return RoutedMessagesRequest(
            request=routed_request,
            resolved=node,
            reasoning=reasoning,
        )

    def _record_success(self, node: ResolvedModel, chain_identity: str | None) -> None:
        self._health.record_success(node.provider_model_ref)
        if chain_identity:
            self._health.record_lkgp(chain_identity, node.provider_model_ref)

    def _trace_skip(self, node: ResolvedModel, attempt: int, request_id: str) -> None:
        trace_event(
            stage="routing",
            event="claudey.api.route.node_skipped",
            source="api",
            request_id=request_id,
            node=node.provider_model_ref,
            provider_id=node.provider_id,
            reason=self._health.effective_state(node.provider_model_ref).value,
            attempt=attempt,
        )

    def _trace_failover(
        self, node: ResolvedModel, kind: FailureKind, attempt: int, request_id: str
    ) -> None:
        trace_event(
            stage="routing",
            event="claudey.api.route.failover",
            source="api",
            request_id=request_id,
            node_tried=node.provider_model_ref,
            provider_id=node.provider_id,
            reason=kind.value,
            attempt=attempt,
        )
