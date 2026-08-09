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
    ResolvedModel,
    RoutedMessagesRequest,
)
from claudey.core.anthropic import MessagesRequest, get_token_count
from claudey.core.failures import ExecutionFailure, FailureKind, find_execution_failure
from claudey.core.reasoning import ReasoningPolicy
from claudey.core.trace import trace_event
from claudey.providers.health import HealthRegistry, health_registry

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
    ) -> AsyncIterator[str]:
        """Stream the first healthy chain node, failing over before content."""

        async def _stream() -> AsyncIterator[str]:
            nodes = self._ordered_nodes(resolution, chain_identity)
            content_emitted = False
            node_count = len(nodes)

            for attempt, node in enumerate(nodes, start=1):
                if self._health.should_skip(node.provider_model_ref):
                    self._trace_skip(node, attempt, request_id)
                    continue

                routed = self._routed_node(request, node, resolution.reasoning)
                try:
                    async for chunk in self._provider_executor.stream(
                        routed,
                        wire_api=wire_api,
                        raw_log_label=raw_log_label,
                        raw_log_payload=raw_log_payload,
                        request_id=request_id,
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
                    self._trace_failover(node, failure.kind, attempt, request_id)
                    logger.warning(
                        "FAILOVER: node '{}' failed ({}) -> next of {} (attempt {})",
                        node.provider_model_ref,
                        failure.kind.value,
                        node_count - 1,
                        attempt,
                    )

            raise ExecutionFailure(
                kind=NO_USABLE_NODE_KIND,
                status_code=NO_USABLE_NODE_STATUS,
                message="No usable failover node for the request chain.",
                retryable=False,
            )

        return _stream()

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
