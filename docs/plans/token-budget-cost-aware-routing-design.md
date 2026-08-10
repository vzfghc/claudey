# Design — Token-budget / cost-aware routing (P2-C3)

> **Status:** Design only (gates a future MINOR). Not implemented. This doc is
> the P2-C3 deliverable referenced by
> [`omniroute-fcm-integration-plan.md`](./omniroute-fcm-integration-plan.md),
> card *"Per-model token-budget / cost-aware routing (review #3) — separate
> design, land after Phase B."* Phase B has landed; this design is now actionable.

## 1. Problem

Claudey routes a request through an ordered failover chain (the tier chain —
inline refs or `@combo:<id>`, expanded by `application/routing.py`'s
`ModelRouter.resolve_chain` into a `ChainResolution` of `ResolvedModel` nodes).
Today the chain order is **declaration order**, and `application/failover.py`'s
`FallbackExecutor._ordered_nodes` only re-orders to surface the LKG-P primary
first and skip nodes the `providers/health.py` registry has marked down/locked.

There is **no cost or context-budget consideration**:

- `messaging/limiter.py` (`MessagingRateLimiter`, `SlidingWindowLimiter`) is
  rate-limiting + task-compaction/dedup only — verified, no cost logic.
- `application/model_metadata.py`'s `ProviderModelInfo` carries only `model_id`
  and `supports_thinking`. No price, no context window, no latency tier.
- `core/gateway_model_ids.py` **already encodes** a per-model context-window
  scalar via the trailing `[<n>m|k]` suffix
  (`_CONTEXT_WINDOW_SUFFIX_RE = re.compile(r"\[(\d+)(m|k)\]$")`,
  `strip_context_window_suffix`), but routing strips and discards it —
  the signal is present, just unconsumed.
- `providers/failure_policy.py` already defines
  `context_window_exceeded_provider_failure` — i.e. we *react* to an
  over-budget node by failing, instead of *avoiding* it upfront.

The gap: when a chain mixes a small-context cheap node and a large-context
expensive node, the primary is chosen by declaration order, not by "does this
request even need the big window / premium token price." A trivially small
request can pin a premium primary and only fall back to the cheap node after
a (recoverable) failure.

## 2. Goals / non-goals

**Goals**

1. Let a chain prefer the **cheapest healthy node that satisfies a token-budget
   estimate** for the current request, instead of pure declaration order.
2. Consume the **already-present** `[<n>m|k]` context-window suffix as the
   zero-config budget signal; allow an optional structured overlay for price
   (free-tier vs paid) and latency tier.
3. Compose with — not replace — the health registry (`should_skip`,
   `effective_state`, LKG-P `preferred_primary`) and the failover executor's
   eligibility/content-start rules.
4. Be **opt-in and default-off** so today's declaration-order behavior is
   bit-identical until a settings knob is enabled (back-compat is mandatory;
   this is a PATCH-or-MINOR, never a silent behavior change).
5. Fail-safe to **declaration order** whenever cost metadata is missing,
   stale, or the budget estimate is unavailable (volatile free-tier catalog —
   see §7 Risks).

**Non-goals**

- Real-time billing / spend accounting across sessions (out of scope; this is
  *routing preference*, not metering — that lives in the TokenTracker/admin
  dashboard layer, not the hot path).
- Mid-stream re-routing on cost grounds (mid-stream failover is out of scope
  by design, per the plan's risks section; cost-aware selection happens at
  **primary-route decision time only**, before content start).
- Marker-based or token-precise budgeting (we estimate bounded buckets, not
  exact token counts — see §4).
- Mutating the existing `[1m]`-suffix contract or the gateway model-id
  encoding (`gateway_model_id` / `decode_gateway_model_id`). Budget metadata
  is read-only overlay consumed at selection time.

## 3. Integration points (existing symbols)

All paths are `src/claudey/...` unless noted.

| Concern | Symbol | Role in this design |
|--------|--------|---------------------|
| Chain expansion | `application/routing.py::ModelRouter.resolve_chain` → `ChainResolution` (`nodes: tuple[ResolvedModel, ...]`) | Source of the ordered nodes to re-rank. |
| Node identity | `application/routing.py::ResolvedModel` (`provider_model_ref`, `provider_id`, `provider_model`) | Key under which per-model budget metadata is looked up. |
| Re-rank hook | `application/failover.py::FallbackExecutor._ordered_nodes` | Insertion point: today applies LKG-P-first + skip-unhealthy; a budget selector re-ranks **within** already-eligible nodes. |
| Healthy filter | `providers/health.py::HealthRegistry.should_skip` / `effective_state` / `preferred_primary` (LKG-P) | Selector must compose: cheaper-but-down never wins over healthy. |
| Context budget signal (zero-config) | `core/gateway_model_ids.py::strip_context_window_suffix` + `_CONTEXT_WINDOW_SUFFIX_RE` | Already parses `[1m]`→1_000_000, `[200k]`→200_000; expose (don't strip) at selection time. |
| Over-budget failure kind | `providers/failure_policy.py::context_window_exceeded_provider_failure` | The failure we **avoid** by pre-filtering over-budget nodes. |
| Rate/compaction (unchanged) | `messaging/limiter.py::MessagingRateLimiter` | Untouched — this design adds nothing to the limiter. |
| Model metadata | `application/model_metadata.py::ProviderModelInfo` | Candidate to extend (additive, optional fields) **or** keep frozen + add a sidecar overlay (see §5). |
| Settings surface | `config/settings.py` (no tier/budget fields today) | Add opt-in `CLAUDEY_*` toggle + optional static overlay path. |

## 4. Budget estimate

Selection-time budget is an **estimated bounded bucket**, never a precise token
count (precision requires a tokenizer in the hot path; rejected for KISS).

- **Estimate source:** `MessagesRequest` already carries message bodies. A
  cheap upper bound is `sum(len(text) // CHARS_PER_TOKEN for text in message_texts)`
  plus a fixed overhead per message/tool-call, capped at the chain's declared
  max. `CHARS_PER_TOKEN` is a named constant (≈4, the de-facto BPE heuristic),
  not magic.
- **What the estimate gates:** a node is *budget-eligible* iff its context
  budget (from `[<n>m|k]` suffix or overlay) `>= estimated_tokens + RESERVE`.
  `RESERVE` is a small safety margin so we don't hop to a node that fits by
  one token then overflows mid-request.
- **What the estimate does NOT gate:** price/latency tier — those are
  tie-breakers *among* budget-eligible nodes, not hard filters (a paid node
  is still eligible if it's the only budget-fit; cost is a preference).

## 5. Proposed shape (two layers, additive)

### 5.1 Per-model budget metadata — a sidecar overlay, not a core field edit

Keep `ProviderModelInfo` frozen and minimal (catalog enumeration + contract
tests depend on its exact shape; widening it touches every provider). Instead
introduce a read-only overlay resolved at selection time:

```
# new: application/cost_tiers.py  (NOT added by this design doc — proposed only)
@dataclass(frozen=True, slots=True)
class BudgetTier:
    context_budget: int | None        # tokens; None = "unknown, allowed"
    price_class: str | None           # "free" | "paid" | None
    latency_class: str | None         # "fast" | "balanced" | None  (advisory)

def resolve_budget_tier(provider_model_ref: str) -> BudgetTier: ...
```

Resolution order (first wins; each layer is **optional** and missing = unknown):

1. **Static overlay file** (opt-in, `CLAUDEY_COST_OVERLAY_PATH`) — a JSON map
   of `"<provider>/<model>"` → `{context_budget, price_class, latency_class}`.
   Power-user override; overrides everything below.
2. **Env static** — `CLAUDEY_MODEL_BUDGET_<PROVIDER>_<MODEL>=200000` style
   keys (sanitized; matches the existing env-override idiom in settings).
3. **`[<n>m|k]` suffix** already on the ref — zero-config, parsed by the
   existing `_CONTEXT_WINDOW_SUFFIX_RE`. This alone makes context-budget-aware
   selection work for any chain that advertises suffixes, with **no new
   config from the user**.
4. **Unknown** — `BudgetTier(None, None, None)`. The selector treats unknown
   budget as "allowed but never preferred" (falls back to declaration order
   among unknowns), so a missing overlay never blocks routing.

### 5.2 Selector hook — failover, not routing

The re-rank belongs in `FallbackExecutor._ordered_nodes` (selection time,
post-health-filter), **not** in `ModelRouter.resolve_chain` (which models the
*declared* chain and is shared with the catalog/admin surfaces that must show
declaration order). Concretely, `_ordered_nodes` today does:

```
LKG-P preferred (if healthy) → declaration order, skipping unhealthy
```

With budget-aware enabled (default-off), it becomes:

```
healthy nodes → partition: budget-eligible | unknown | over-budget
budget-eligible: sort by (price_class rank, latency_class rank, declaration index)
unknown:         tie-break by price_class rank, then declaration index   (never first unless no eligible)
over-budget:     appended last (still reachable, matching today's fail-through)
LKG-P still first *within its budget class* (cheap + LKG-P beats cheap + non-LKG-P)
```

Key invariants preserved:

- **LKG-P is never dead.** It remains first *among nodes of equal cost rank*;
  cost never demotes LKG-P below an unknown-cost node. This is the critical
  composition rule with health's LKG-P path.
- **Health wins over cost.** `should_skip(ref)` filtering happens *before*
  cost re-rank — a cheap-down node is never preferred over a healthy-paid one.
- **Fail-through is unchanged.** Over-budget nodes stay in the tail; we
  only *prefer* not to start on them. If all eligible nodes are over-budget,
  we still try them in declaration order (today's behavior) rather than 503.
- **Content-start semantics are unchanged.** Cost selection happens at
  `primary_route` decision time (pre-stream, synchronous — same place
  `format_route_header` already computes). No mid-stream re-routing.

### 5.3 Settings (opt-in, default-off)

```
# proposed additions to config/settings.py — NOT committed by this doc
token_budget_aware_routing: bool = Field(default=False,
    validation_alias="CLAUDEY_TOKEN_BUDGET_AWARE_ROUTING")
cost_overlay_path: str = Field(default="",
    validation_alias="CLAUDEY_COST_OVERLAY_PATH")
budget_reserve_tokens: int = Field(default=512,
    validation_alias="CLAUDEY_BUDGET_RESERVE_TOKENS")
```

Default `False` ⇒ today's declaration-order behavior, bit-identical. Flipping
the toggle is the **only** activation; the `[1m]` suffix is consumed *only when
the toggle is on* (so existing suffix behavior — stripped, metadata discarded —
is unchanged when off).

### 5.4 Telemetry (reuse the route header)

`x-claudey-route` (P3-D2) already exposes `provider/model; why=<reason>`.
Extend `format_route_header`'s `why` vocabulary with `budget=<tier>` /
`budget=unknown` so budget-aware decisions are debuggable without a new
header. The `route_trace` payload gains a `budget_tier` field (string, optional)
on each node tried, consumed by the existing trace sink — no new sink.

## 6. Test strategy (when implemented)

- **Unit** — `resolve_budget_tier` precedence (overlay > env > suffix > unknown);
  suffix parsing reuses the `_CONTEXT_WINDOW_SUFFIX_RE` tests (already covered
  in `tests/core/test_gateway_model_ids.py`).
- **Unit** — a pure `_rank_by_budget(nodes, estimate, tiers, lkgp)` function
  (extracted from `_ordered_nodes`) with table-driven cases proving the
  invariants: health-wins-over-cost, LKG-P-first-within-class, over-budget
  appended last, unknown never first when eligible exists, default-off =
  declaration order.
- **Property-ish** — with the toggle off, `rank(nodes, ...)` returns nodes in
  the pre-change order for any health/estimate input (regression guard).
- **Integration** — `FallbackExecutor` stream test: a chain
  `[free/cheap[1m], paid/big[200k]]`, a 10k-token request, both healthy ⇒
  primary = free/cheap (budget-eligible + cheapest); a 150k-token request ⇒
  primary = paid/big (only budget-eligible); free/cheap down ⇒ paid/big
  primary regardless (health-wins-over-cost).
- **Fail-fast / validation** — overlay JSON schema validated at load; bad
  overlay logs a structured error and degrades to suffix-only (never raises
  into the hot path).

## 7. Risks

| Risk | Mitigation |
|------|------------|
| **Free-tier catalog volatility** (FCM removes models on 404/410 — plan risk line). Cost metadata pinned to a model id goes stale. | Overlay is **read-only and best-effort**; unknown budget never blocks. Health/lockout already absorbs dead-model noise. Never hard-pin free model ids as guarantees in docs. |
| **Estimate is coarse** (chars/token heuristic). A fat payload could overflow a node we marked budget-eligible. | The `RESERVE` margin + the existing `context_window_exceeded_provider_failure` kind (failover-eligible) make the overflow path the same as today: fail-over to the next node. Cost selection is *preference*, not a correctness guarantee. |
| **Overlay maintenance burden.** | Overlay is optional and power-user-only; the `[1m]` suffix is the zero-config path. No overlay ⇒ no maintenance. |
| **Demoting LKG-P surprises users.** | LKG-P-first-within-class invariant (§5.2) keeps the warm path sticky; cost only re-ranks *equal-cost-stratum* nodes. |
| **Adding fields to `ProviderModelInfo` breaks contract tests.** | Sidecar overlay avoids widening the dataclass entirely (§5.1). |
| **Suffix is already stripped upstream (v5.7.6).** | Stripping happens on the *advertised gateway id*. Selection reads the *resolved ref* (`ResolvedModel.provider_model_ref`), where the suffix is still intact in the tier setting. Only the *toggle-on* path reads it; toggle-off path is untouched. |

## 8. Versioning & rollout

- **This doc = P2-C3 design deliverable.** No production file changes; no
  semver bump for the doc itself (docs are non-production per CLAUDE.md).
- **Implementation (future MINOR):** touches `application/failover.py`,
  `application/cost_tiers.py` (new), `config/settings.py` (new opt-in env),
  `.env.example`. On `main`, that commit bumps `[project].version` MINOR +
  `uv lock` + admin `index.html ?v=` sync, per the versioning rules. **Not**
  in this doc's commit.
- Default-off preserves back-compat; flipping the toggle is the only migration
  step. No store migration, no breaking wire change.

## 9. Why this shape (alternatives considered)

- **Re-rank in `routing.resolve_chain`?** Rejected: `resolve_chain` is shared
  with catalog enumeration and admin UI, which must show *declared* order.
  Selection-time re-rank belongs in the executor, next to health/LKG-P logic
  that already re-orders there.
- **Extend `ProviderModelInfo` with cost fields?** Rejected: contract tests
  enumerate `ProviderModelInfo` shape across every provider; widening it is a
  blast radius a design-doc-gated MINOR shouldn't take. Sidecar overlay keeps
  the frozen dataclass stable.
- **Precise tokenization at selection time?** Rejected (KISS): a tokenizer in
  the hot path is real cost+complexity; bounded estimate + fail-through is
  correct and cheaper.
- **A new response header for budget?** Rejected: reuse `x-claudey-route`'s
  `why=` vocabulary (P3-D2 already shipped) — DRY, no new header, no new trace
  sink.
