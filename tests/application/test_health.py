"""Unit tests for the provider health state machine + LKG-P + model lockout."""

import pytest

from claudey.application.health import (
    MODEL_LOCKOUT_BASE,
    HealthRegistry,
    ProviderHealthState,
)
from claudey.core.failures import FailureKind


def _registry(now_holder: list[float]) -> HealthRegistry:
    return HealthRegistry(now=lambda: now_holder[0])


def test_healthy_node_is_not_skipped():
    registry = HealthRegistry()
    assert registry.should_skip("llm7/meta-llama/llama-3.1-70b") is False
    assert (
        registry.effective_state("llm7/meta-llama/llama-3.1-70b")
        is ProviderHealthState.HEALTHY
    )


def test_auth_failure_marks_provider_auth_error(now_holder):
    registry = _registry(now_holder)
    registry.record_failure("llm7/meta-llama/llama-3.1-70b", FailureKind.AUTHENTICATION)

    assert (
        registry.effective_state("llm7/meta-llama/llama-3.1-70b")
        is ProviderHealthState.AUTH_ERROR
    )
    assert registry.should_skip("llm7/meta-llama/llama-3.1-70b") is True


def test_auth_failure_degrades_whole_provider():
    now_holder = [0.0]
    registry = _registry(now_holder)
    registry.record_failure("llm7/a", FailureKind.AUTHENTICATION)

    # Any node on that provider is skipped, not just the failing one.
    assert registry.should_skip("llm7/b") is True


@pytest.mark.parametrize(
    "kind",
    [
        FailureKind.RATE_LIMIT,
        FailureKind.OVERLOADED,
        FailureKind.TIMEOUT,
        FailureKind.UPSTREAM,
        FailureKind.UNAVAILABLE,
    ],
)
def test_transiency_failures_mark_provider_down(now_holder, kind):
    registry = _registry(now_holder)
    registry.record_failure("novita/deepseek/x", kind)

    assert registry.effective_state("novita/deepseek/x") is ProviderHealthState.DOWN
    assert registry.should_skip("novita/deepseek/x") is True


def test_provider_mark_expires_by_ttl(now_holder):
    registry = _registry(now_holder)
    registry.record_failure("novita/a", FailureKind.RATE_LIMIT)
    assert registry.should_skip("novita/a") is True

    now_holder[0] += 1000.0  # past the 60s cooldown
    assert registry.should_skip("novita/a") is False
    assert registry.effective_state("novita/a") is ProviderHealthState.HEALTHY


def test_model_specific_reject_locks_exact_node_not_provider(now_holder):
    registry = _registry(now_holder)
    registry.record_failure("open_router/a/bad", FailureKind.INVALID_REQUEST)

    # Only the exact bad model is skipped; other models on open_router are fine.
    assert registry.should_skip("open_router/a/bad") is True
    assert registry.should_skip("open_router/a/good") is False
    assert registry.effective_state("open_router/a/bad") is ProviderHealthState.RECOVERY


@pytest.mark.parametrize(
    "kind",
    [
        FailureKind.INVALID_REQUEST,
        FailureKind.CONTEXT_WINDOW_EXCEEDED,
        FailureKind.PERMISSION,
    ],
)
def test_model_lock_kinds_lock_exact_node(now_holder, kind):
    registry = _registry(now_holder)
    registry.record_failure("open_router/a/bad", kind)
    assert registry.should_skip("open_router/a/bad") is True


def test_model_lockout_escalates_ttl(now_holder):
    registry = _registry(now_holder)
    registry.record_failure("open_router/a/bad", FailureKind.INVALID_REQUEST)
    lock1 = registry._lock("open_router", "a/bad")
    assert lock1 is not None
    registry.record_failure("open_router/a/bad", FailureKind.INVALID_REQUEST)
    lock2 = registry._lock("open_router", "a/bad")
    assert lock2 is not None
    assert lock2.attempts == 2
    assert lock2.until > lock1.until
    assert lock2.until - lock1.until >= MODEL_LOCKOUT_BASE * 2


def test_record_success_clears_provider_and_model_marks(now_holder):
    registry = _registry(now_holder)
    registry.record_failure("open_router/a/bad", FailureKind.INVALID_REQUEST)
    registry.record_failure("open_router/a/bad", FailureKind.RATE_LIMIT)
    assert registry.should_skip("open_router/a/bad") is True

    registry.record_success("open_router/a/bad")
    assert registry.should_skip("open_router/a/bad") is False


def test_lkgp_preferred_primary_round_trip():
    registry = HealthRegistry()
    assert registry.preferred_primary("combo_flagship") is None
    registry.record_lkgp("combo_flagship", "llm7/meta-llama/llama-3.1-70b")
    assert (
        registry.preferred_primary("combo_flagship") == "llm7/meta-llama/llama-3.1-70b"
    )


def test_lkgp_updates_to_most_recent():
    registry = HealthRegistry()
    registry.record_lkgp("tier:opus", "llm7/a")
    registry.record_lkgp("tier:opus", "novita/b")
    assert registry.preferred_primary("tier:opus") == "novita/b"


def test_lkgp_bounded_by_capacity():
    registry = HealthRegistry(lkgp_capacity=2)
    registry.record_lkgp("combo_a", "llm7/a")
    registry.record_lkgp("combo_b", "novita/b")
    registry.record_lkgp("combo_c", "deepseek/c")

    assert registry.preferred_primary("combo_a") is None
    assert registry.preferred_primary("combo_b") == "novita/b"
    assert registry.preferred_primary("combo_c") == "deepseek/c"


def test_validate_providers_backs_off_raising_probe(now_holder):
    registry = _registry(now_holder)

    def probe(provider: str) -> object:
        raise RuntimeError("unreachable")

    registry.validate_providers(["llm7/a", "llm7/b"], probe)
    assert registry.effective_state("llm7/a") is ProviderHealthState.DOWN
    assert registry.should_skip("llm7/b") is True


def test_validate_providers_backs_off_falsy_probe(now_holder):
    registry = _registry(now_holder)
    registry.validate_providers(["novita/x"], lambda _provider: None)
    assert registry.should_skip("novita/x") is True


def test_validate_providers_keeps_verified_provider_healthy(now_holder):
    registry = _registry(now_holder)
    calls: list[str] = []

    def probe(provider: str) -> object:
        calls.append(provider)
        return True

    registry.validate_providers(["llm7/a", "llm7/b", "novita/c"], probe)

    assert calls == ["llm7", "novita"]  # each provider probed once
    assert registry.should_skip("llm7/a") is False
    assert registry.should_skip("novita/c") is False


def test_mark_provider_down(now_holder):
    registry = _registry(now_holder)
    registry.mark_provider_down("deepseek", "day-0 probe failed")
    assert registry.should_skip("deepseek/deepseek-chat") is True


@pytest.fixture
def now_holder() -> list[float]:
    return [0.0]
