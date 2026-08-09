"""Provider health state machine + LKG-P map + exact-model lockout.

In-memory, TTL-based, per-process — never persisted. Models each provider as
**healthy / down / recovery / auth-error** and each ``provider/model`` node for
**model-lockout**, mirroring OmniRoute's ``assessment/`` layer and review #2's
self-heal state machine. Fed by the already-classified :class:`ExecutionFailure`
kinds from the failover executor, the websocket feedback point, and day-0
startup probes.
"""

from collections import OrderedDict
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from enum import StrEnum
from time import monotonic

from claudey.core.failures import FailureKind

# --- cooldowns / lockout tuning (TTL seconds) ---
PROVIDER_DOWN_COOLDOWN = (
    60.0  # degrade a provider for this long after a down-kind failure
)
PROVIDER_AUTH_COOLDOWN = 300.0  # auth errors are rarely transient: cool down longer
MODEL_LOCKOUT_BASE = 60.0  # exact-model lockout floor; escalates (x2, capped)
MODEL_LOCKOUT_MAX_STEPS = 3  # extra doubling steps beyond the base
DAY0_DOWN_COOLDOWN = 120.0  # startup probe failure backs the provider off briefly

# Failover-degrading provider kinds: flip the provider to DOWN.
_PROVIDER_DOWN_KINDS = frozenset(
    {
        FailureKind.RATE_LIMIT,
        FailureKind.OVERLOADED,
        FailureKind.TIMEOUT,
        FailureKind.UPSTREAM,
        FailureKind.UNAVAILABLE,
    }
)

# Model-specific rejects that should not poison the whole provider: lock the node.
_MODEL_LOCK_KINDS = frozenset(
    {
        FailureKind.INVALID_REQUEST,
        FailureKind.CONTEXT_WINDOW_EXCEEDED,
        FailureKind.PERMISSION,
    }
)


class ProviderHealthState(StrEnum):
    """Reputation states a provider (or node) can occupy."""

    HEALTHY = "healthy"
    DOWN = "down"
    RECOVERY = "recovery"
    AUTH_ERROR = "auth-error"


@dataclass(frozen=True, slots=True)
class ProviderMark:
    """One provider's reputation state until a monotonic timestamp."""

    state: ProviderHealthState
    until: float
    reason: str


@dataclass(frozen=True, slots=True)
class ModelLock:
    """An exact ``provider/model`` lockout with an escalating TTL."""

    until: float
    attempts: int

    @property
    def escalated_until(self) -> float:
        """Return the next lockout expiry after one more NACK (x2, capped)."""
        step = min(self.attempts, MODEL_LOCKOUT_MAX_STEPS)
        return self.until + MODEL_LOCKOUT_BASE * (2**step)


class HealthRegistry:
    """Process-wide health view consulted before each chain node is tried."""

    def __init__(
        self,
        *,
        now: Callable[[], float] = monotonic,
        provider_down_cooldown: float = PROVIDER_DOWN_COOLDOWN,
        provider_auth_cooldown: float = PROVIDER_AUTH_COOLDOWN,
        day0_cooldown: float = DAY0_DOWN_COOLDOWN,
        model_lockout_base: float = MODEL_LOCKOUT_BASE,
        lkgp_capacity: int = 256,
    ) -> None:
        self._now = now
        self._provider_down_cooldown = provider_down_cooldown
        self._provider_auth_cooldown = provider_auth_cooldown
        self._day0_cooldown = day0_cooldown
        self._model_lockout_base = model_lockout_base
        self._provider_marks: dict[str, ProviderMark] = {}
        self._model_locks: OrderedDict[tuple[str, str], ModelLock] = OrderedDict()
        self._lkgp: OrderedDict[str, str] = OrderedDict()
        self._lkgp_capacity = lkgp_capacity

    # === helpers ===

    @staticmethod
    def _split(ref: str) -> tuple[str, str]:
        provider, _, model = ref.partition("/")
        return provider, model

    def _provider_mark(self, provider: str) -> ProviderMark | None:
        return self._provider_marks.get(provider)

    def _lock(self, provider: str, model: str) -> ModelLock | None:
        return self._model_locks.get((provider, model))

    # === feedback recording ===

    def record_success(self, ref: str) -> None:
        """Clear degradation marks for a node that just succeeded."""
        provider, _ = self._split(ref)
        self._provider_marks.pop(provider, None)
        self._model_locks.pop((provider, _), None)

    def record_failure(self, ref: str, kind: FailureKind) -> None:
        """Fold one finalized failure into the reputation state.

        Provider-level: auth errors go to ``AUTH_ERROR``; transiency failures go
        to ``DOWN``. Node-level: model-specific rejects lock the exact
        ``provider/model`` so future chains skip it without trying.
        """
        provider, model = self._split(ref)
        now = self._now()
        if kind is FailureKind.AUTHENTICATION:
            self._provider_marks[provider] = ProviderMark(
                state=ProviderHealthState.AUTH_ERROR,
                until=now + self._provider_auth_cooldown,
                reason="authentication failure",
            )
        elif kind in _PROVIDER_DOWN_KINDS:
            self._provider_marks[provider] = ProviderMark(
                state=ProviderHealthState.DOWN,
                until=now + self._provider_down_cooldown,
                reason=f"{kind.value} failure",
            )

        if kind in _MODEL_LOCK_KINDS:
            key = (provider, model)
            existing = self._model_locks.get(key)
            if existing is None:
                self._model_locks[key] = ModelLock(
                    until=now + self._model_lockout_base, attempts=1
                )
            else:
                self._model_locks[key] = ModelLock(
                    until=existing.escalated_until, attempts=existing.attempts + 1
                )
            self._model_locks.move_to_end(key)

    # === querying (used by the failover executor) ===

    def should_skip(self, ref: str) -> bool:
        """Return whether a chain node should be skipped without trying it.

        Skips when the provider is currently degraded (down / auth-error within
        its TTL) or the exact model is under lockout (within its TTL).
        """
        provider, model = self._split(ref)
        mark = self._provider_mark(provider)
        if (
            mark is not None
            and self._now() < mark.until
            and mark.state in (ProviderHealthState.DOWN, ProviderHealthState.AUTH_ERROR)
        ):
            return True
        lock = self._lock(provider, model)
        return lock is not None and self._now() < lock.until

    def effective_state(self, ref: str) -> ProviderHealthState:
        """Return the live state after TTL expiry is considered."""
        provider, model = self._split(ref)
        mark = self._provider_mark(provider)
        if mark is not None and self._now() < mark.until:
            if mark.state is ProviderHealthState.RECOVERY:
                return ProviderHealthState.RECOVERY
            return mark.state
        lock = self._lock(provider, model)
        if lock is not None and self._now() < lock.until:
            return ProviderHealthState.RECOVERY
        return ProviderHealthState.HEALTHY

    # === last-known-good path (LKG-P) ===

    def record_lkgp(self, chain_identity: str, ref: str) -> None:
        """Remember the node that most recently served a chain successfully."""
        self._lkgp[chain_identity] = ref
        self._lkgp.move_to_end(chain_identity)
        while len(self._lkgp) > self._lkgp_capacity:
            self._lkgp.popitem(last=False)

    def preferred_primary(self, chain_identity: str) -> str | None:
        """Return the LKG-P primary for a chain identity, else None."""
        return self._lkgp.get(chain_identity)

    # === day-0 startup validation ===

    def mark_provider_down(self, provider: str, reason: str) -> None:
        """Force a provider down (e.g. a day-0 probe failed)."""
        self._provider_marks[provider] = ProviderMark(
            state=ProviderHealthState.DOWN,
            until=self._now() + self._day0_cooldown,
            reason=reason,
        )

    def validate_providers(
        self,
        refs: Iterable[str],
        probe: Callable[[str], object],
    ) -> None:
        """Probe each distinct provider once and back off unverifiable ones.

        ``probe(provider_id)`` should raise or return a falsy value when the
        provider cannot be reached today. Reuses the connectivity logic from
        :mod:`custom_provider_check` (invoked by startup wiring).
        """
        seen: set[str] = set()
        for ref in refs:
            provider, _ = self._split(ref)
            if provider in seen:
                continue
            seen.add(provider)
            try:
                ok = probe(provider)
            except Exception as error:
                self.mark_provider_down(provider, f"startup probe raised: {error}")
                continue
            if not ok:
                self.mark_provider_down(provider, "startup probe could not verify")


_registry = HealthRegistry()


def health_registry() -> HealthRegistry:
    """Return the process-wide health registry."""
    return _registry
