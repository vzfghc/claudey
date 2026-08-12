"""Failover executor chain traversal + eligibility + streaming-window guards."""

from collections.abc import AsyncIterator, Iterable
from typing import Any
from unittest.mock import MagicMock

import pytest

from claudey.application.failover import FallbackExecutor, format_route_header
from claudey.application.health import HealthRegistry
from claudey.application.routing import ChainResolution, ModelRouter, ResolvedModel
from claudey.config.reasoning import ReasoningPreference
from claudey.config.settings import Settings
from claudey.core.anthropic import Message, MessagesRequest
from claudey.core.failures import ExecutionFailure, FailureKind, find_execution_failure

_NODE_A = ("provider_a", "model-a")
_NODE_B = ("provider_b", "model-b")


class FakeProvider:
    """Provider double that yields chunks, then raises one canonical failure."""

    def __init__(
        self,
        kind: FailureKind,
        *,
        retryable: bool,
        chunks: list[str] | None = None,
        complete: bool = False,
    ) -> None:
        self._kind = kind
        self._retryable = retryable
        self._chunks = chunks or []
        self._complete = complete
        self.preflight_stream = MagicMock()
        self.stream_kwargs: list[dict[str, Any]] = []

    async def stream_response(
        self, _request: object, **kwargs: Any
    ) -> AsyncIterator[str]:
        self.stream_kwargs.append(kwargs)
        for chunk in self._chunks:
            yield chunk
        if self._complete:
            return
        raise ExecutionFailure(
            kind=self._kind,
            status_code=100,
            message=f"{self._kind.value} failure",
            retryable=self._retryable,
        )


def _provider_factory(providers: dict[str, FakeProvider]):
    def resolve(provider_id: str) -> FakeProvider:
        return providers[provider_id]

    return resolve


def _request() -> MessagesRequest:
    return MessagesRequest(
        model="claude-3-opus",
        max_tokens=32,
        messages=[Message(role="user", content="Hello")],
    )


def _resolution(
    nodes: Iterable[tuple[str, str]] = (_NODE_A, _NODE_B),
) -> ChainResolution:
    chain = tuple(
        ResolvedModel(
            original_model="claude-3-opus",
            provider_id=provider,
            provider_model=model,
            provider_model_ref=f"{provider}/{model}",
            reasoning_preference=ReasoningPreference.CLIENT,
        )
        for provider, model in nodes
    )
    return ChainResolution(chain=chain, reasoning=None)


async def _drain(stream: AsyncIterator[str]) -> list[str]:
    return [chunk async for chunk in stream]


async def _run(
    resolution: ChainResolution,
    providers: dict[str, FakeProvider],
    *,
    health: HealthRegistry | None = None,
    chain_identity: str | None = None,
) -> list[str]:
    executor = FallbackExecutor(
        _provider_factory(providers),
        health=health or HealthRegistry(),
    )
    return await _drain(
        executor.stream(
            resolution,
            _request(),
            wire_api="messages",
            raw_log_label="FULL_PAYLOAD",
            raw_log_payload={},
            request_id="req-1",
            chain_identity=chain_identity,
        )
    )


@pytest.mark.asyncio
async def test_failover_to_secondary_on_retryable_post_start_empty():
    primary = FakeProvider(FailureKind.RATE_LIMIT, retryable=True)
    secondary = FakeProvider(
        FailureKind.OVERLOADED, retryable=True, complete=True, chunks=["ok"]
    )

    chunks = await _run(_resolution(), {"provider_a": primary, "provider_b": secondary})

    assert chunks == ["ok"]
    assert len(primary.stream_kwargs) == 1
    assert len(secondary.stream_kwargs) == 1


@pytest.mark.asyncio
async def test_failover_records_health_and_lkgp():
    health = HealthRegistry()
    primary = FakeProvider(FailureKind.OVERLOADED, retryable=True)
    secondary = FakeProvider(
        FailureKind.OVERLOADED, retryable=True, complete=True, chunks=["ok"]
    )

    await _run(
        _resolution(),
        {"provider_a": primary, "provider_b": secondary},
        health=health,
        chain_identity="combo_flagship",
    )

    assert health.should_skip("provider_a/model-a") is True
    assert health.preferred_primary("combo_flagship") == "provider_b/model-b"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "kind",
    [
        FailureKind.AUTHENTICATION,
        FailureKind.PERMISSION,
        FailureKind.INVALID_REQUEST,
        FailureKind.CONTEXT_WINDOW_EXCEEDED,
    ],
)
async def test_non_eligible_failure_does_not_failover(kind):
    primary = FakeProvider(kind, retryable=False)
    secondary = FakeProvider(FailureKind.OVERLOADED, retryable=True, chunks=["ok"])

    with pytest.raises(ExecutionFailure) as exc_info:
        await _run(_resolution(), {"provider_a": primary, "provider_b": secondary})

    assert find_execution_failure(exc_info.value) is not None
    assert exc_info.value.kind is kind
    assert len(secondary.stream_kwargs) == 0  # never tried


@pytest.mark.asyncio
async def test_retryable_false_rate_limit_does_not_failover():
    primary = FakeProvider(FailureKind.RATE_LIMIT, retryable=False)
    secondary = FakeProvider(FailureKind.OVERLOADED, retryable=True, chunks=["ok"])

    with pytest.raises(ExecutionFailure):
        await _run(_resolution(), {"provider_a": primary, "provider_b": secondary})

    assert len(secondary.stream_kwargs) == 0


@pytest.mark.asyncio
async def test_content_emitted_blocks_failover():
    primary = FakeProvider(
        FailureKind.RATE_LIMIT,
        retryable=True,
        chunks=['data: {"type": "message_start"}'],
    )
    secondary = FakeProvider(FailureKind.OVERLOADED, retryable=True, chunks=["ok"])

    with pytest.raises(ExecutionFailure):
        await _run(_resolution(), {"provider_a": primary, "provider_b": secondary})

    assert len(secondary.stream_kwargs) == 0  # content already sent; cannot un-send


@pytest.mark.asyncio
async def test_health_skips_degraded_primary_and_serves_secondary():
    health = HealthRegistry()
    primary = FakeProvider(FailureKind.OVERLOADED, retryable=True)
    secondary = FakeProvider(
        FailureKind.OVERLOADED, retryable=True, complete=True, chunks=["ok"]
    )
    health.record_failure("provider_a/model-a", FailureKind.OVERLOADED)

    chunks = await _run(
        _resolution(),
        {"provider_a": primary, "provider_b": secondary},
        health=health,
    )

    assert chunks == ["ok"]
    assert len(primary.stream_kwargs) == 0  # skipped, never tried


@pytest.mark.asyncio
async def test_all_nodes_skipped_raises_unavailable():
    health = HealthRegistry()
    primary = FakeProvider(FailureKind.OVERLOADED, retryable=True)
    secondary = FakeProvider(FailureKind.OVERLOADED, retryable=True, chunks=["ok"])
    health.record_failure("provider_a/model-a", FailureKind.OVERLOADED)
    health.record_failure("provider_b/model-b", FailureKind.OVERLOADED)

    with pytest.raises(ExecutionFailure) as exc_info:
        await _run(
            _resolution(),
            {"provider_a": primary, "provider_b": secondary},
            health=health,
        )

    assert exc_info.value.kind is FailureKind.UNAVAILABLE
    assert len(primary.stream_kwargs) == 0
    assert len(secondary.stream_kwargs) == 0


@pytest.mark.asyncio
async def test_lkgp_prefers_last_known_good_primary_when_usable():
    health = HealthRegistry()
    primary = FakeProvider(FailureKind.OVERLOADED, retryable=True)
    secondary = FakeProvider(
        FailureKind.OVERLOADED, retryable=True, complete=True, chunks=["ok"]
    )
    health.record_lkgp("combo_flagship", "provider_b/model-b")

    await _run(
        _resolution(),
        {"provider_a": primary, "provider_b": secondary},
        health=health,
        chain_identity="combo_flagship",
    )

    # Secondary (LKG-P) is tried first and succeeds; primary untouched.
    assert len(secondary.stream_kwargs) == 1
    assert len(primary.stream_kwargs) == 0


@pytest.mark.asyncio
async def test_lkgp_ignored_when_preferred_node_became_degraded():
    health = HealthRegistry()
    primary = FakeProvider(
        FailureKind.OVERLOADED, retryable=True, complete=True, chunks=["ok-a"]
    )
    secondary = FakeProvider(
        FailureKind.OVERLOADED, retryable=True, complete=True, chunks=["ok-b"]
    )
    health.record_lkgp("combo_flagship", "provider_b/model-b")
    health.record_failure("provider_b/model-b", FailureKind.OVERLOADED)

    chunks = await _run(
        _resolution(),
        {"provider_a": primary, "provider_b": secondary},
        health=health,
        chain_identity="combo_flagship",
    )

    # Preferred node is degraded, so configured order (primary A) is used.
    assert chunks == ["ok-a"]
    assert len(primary.stream_kwargs) == 1
    assert len(secondary.stream_kwargs) == 0


@pytest.mark.asyncio
async def test_single_node_chain_surfaces_its_failure():
    primary = FakeProvider(FailureKind.OVERLOADED, retryable=True)

    with pytest.raises(ExecutionFailure):
        await _run(_resolution((_NODE_A,)), {"provider_a": primary})

    assert len(primary.stream_kwargs) == 1


def _route_executor(health: HealthRegistry) -> FallbackExecutor:
    return FallbackExecutor(_provider_factory({}), health=health)


def _router() -> ModelRouter:
    return ModelRouter(Settings())


def test_primary_route_returns_healthy_first_node():
    health = HealthRegistry()
    executor = _route_executor(health)

    ref, fail_why = executor.primary_route(_resolution((_NODE_A,)))

    assert ref == "provider_a/model-a"
    assert fail_why is None


def test_primary_route_prefers_unskipped_secondary():
    health = HealthRegistry()
    health.record_failure("provider_a/model-a", FailureKind.OVERLOADED)
    executor = _route_executor(health)

    ref, fail_why = executor.primary_route(_resolution((_NODE_A, _NODE_B)))

    assert ref == "provider_b/model-b"
    assert fail_why is None


def test_primary_route_reports_skip_reason_when_none_usable():
    health = HealthRegistry()
    health.mark_provider_down("provider_a", "probe failed")
    executor = _route_executor(health)

    ref, fail_why = executor.primary_route(_resolution((_NODE_A,)))

    assert ref == "provider_a/model-a"
    assert fail_why == "down"


def test_format_route_header_plain_ref_when_healthy():
    health = HealthRegistry()
    executor = _route_executor(health)

    value = format_route_header(
        executor, _router(), _resolution((_NODE_A,)), "claude-3-opus"
    )

    assert value == "provider_a/model-a"


def test_format_route_header_appends_fail_why_when_primary_skipped():
    health = HealthRegistry()
    health.mark_provider_down("provider_a", "probe failed")
    executor = _route_executor(health)

    value = format_route_header(
        executor, _router(), _resolution((_NODE_A,)), "claude-3-opus"
    )

    assert value == "provider_a/model-a; why=down"
