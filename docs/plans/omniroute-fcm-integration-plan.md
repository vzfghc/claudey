# Implementation Plan — OmniRoute + free-coding-models integration into Claudey

> Status: **Proposed** · Branch: `main` → feature branch(es) · Baseline: v5.21.0
> Source assessment: `diegosouzapw/OmniRoute` (v3.8.49) + `vava-nessa/free-coding-models` (v0.5.69)
> Planning follows `ARCHITECTURE.md` extension checklists ("Adding A Provider", "Add An Admin Setting").

## 0. Calibrated findings — what actually needs building

Assessment of both repos against Claudey's current state (`src/claudey/`, v5.21.0):

| OmniRoute / FCM idea | Already in Claudey? | Where |
|---|---|---|
| Failure-kind taxonomy (`rate_limit`/`quota_exhausted`/`auth_error`…) | **Yes** (protocol-neutral) | `core/failures.py` `FailureKind` |
| Per-provider retry session w/ budget | **Yes** | `providers/admission.py` `ProviderRetrySession`, `_RecoveryEpisode` |
| Shared half-open probe, anti-thundering-herd | **Yes** | `providers/admission.py` (`_RecoveryEpisode`, probe gate) |
| Honor upstream `Retry-After` | **Yes** | `providers/admission.py` `_retry_after_seconds` |
| Sliding-window rate + concurrency bulkhead | **Yes** | `core/rate_limit.py`, `providers/admission.py` |
| Cross-provider **failover chains** + global fallback | **NO — zero hits for failover/pool/cascade** | — |
| Exact-**model lockout** (bad model ≠ bad provider) | **No** | — |
| Provider **health state machine** (Healthy/down/recovery/auth-err/locked) | **No** (admission state is per-retry-episode only) | — |
| Per-model **token-budget / cost-aware** routing | **No** — verified `messaging/limiter.py` is rate + task-compaction/dedup only | `messaging/limiter.py` |
| Background **credential-health** scheduler + TTL cache | **No** (model-list disk cache only) | `providers/runtime/discovery.py` |
| 6 free providers (OVHcloud, Scaleway, DashScope, LLM7, Routeway, Novita) | **No** | `config/provider_catalog.py` |
| GLM/Mistral/Codestral request-shape normalizers | Reasonable default; **audit needed** | `providers/openai_chat/request_policy.py`, `extra_body.py` |
| Custom-provider key **encryption at rest** | **No — plaintext** in `custom-providers.json` | `config/custom_providers.py` |
| Per-request **decision telemetry** (route, attempt, latency) | Trace exists; **route-decision lacks attempt/fallback fields** | `application/execution.py`, `core/trace.py` |
| Nightly **adversarial batteries** (mutation, schema fuzz) | **No** — `tests.yml` gates are unit/integration only | `.github/workflows/tests.yml` |

**Conclusion:** OmniRoute is a sibling (it ports free-claude-code's `stream_recovery.py` — the module Claudey inherits). Its resilience *ring* is already Claudey's `admission.py`. The genuine, high-value build is **cross-provider failover with a provider health state machine** (Phase B), plus **cheap provider breadth** (Phase A) and smaller hardening items (Phases C–D).

### 0.5 Reconciliation against the deeper OmniRoute/FCM review

A second, fit-ranked review of OmniRoute internals (combo resolver, provider `assessment/` health, `src/mitm/`, nightly CI) added deltas. **Verified before adopting:** `messaging/limiter.py` is rate-limiting + task compaction/dedup only — it contains **no token-budget or cost-aware logic**, so review item #3 is genuinely new work, not an extension.

| Review item | Plan state | Resolution |
|---|---|---|
| #1 Combo fallback chains — persisted, UI-editable, `enabled`+priority flags | **Adopted as design** | Phase B ships **persisted combos** (atomic JSON store mirroring `custom-providers.json`, admin CRUD, per-node `enabled` + `priority`). Named combos are referenced from tier settings. Env comma-chains remain supported as the inline/back-compat form. |
| #2 Provider health / self-heal state machine (Healthy/down/recovery/auth-err/locked) | Adopted | **Core of Phase B** (`providers/health.py`), fed by already-classified `ExecutionFailure.kind`. |
| #3 Per-model token-budget routing (`MODEL_HAIKU` cost-aware) | Missing | Added as Phase C candidate — new work, bigger lift than "well-aligned extension". |
| #4 Route explainability (`x-claudey-route` + fail-why) | Aligned | = Phase D #2; extended to render in `admin_routes.get_admin_dashboard`. |
| #5 Guard-only truncation slice (opt-in, default-off) | Partial | Compression arsenal excluded; optional session-dedup / verbose-tool-log truncation card added, non-default and non-blocking (tool-fidelity provenance risks). |
| #6 Nightly adversarial batteries (mutmut + Schemathesis) | Missing | Added as cross-cutting card — matches the "maximum test coverage" directive. |
| #7 Day-0 self-heal (startup picks a healthy chain node) | Missing | Folded into Phase B (`health.py` startup validation pass). |

**Do-not-copy (explicit exclusions):** transparent MITM (`src/mitm/` — root-CA install/DNS hijack/TLS termination on Claude-Code traffic: invasive, contradicts claudey's explicit-proxy contract), the 12-engine compression arsenal, a second Next.js/Electron dashboard, and ~1.5GB polyglot monorepo scale (claudey's modular Python layout is the right size).

---

## Phase A — Six free OpenAI-compatible providers (P2 from assessment)

> **Semver:** MINOR (`5.21.0` → `5.22.0`) — backward-compatible new providers.
> **Effort:** one focused PR, low risk, purely additive.

### A.1 Providers to add (source: FCM `sources.js`, base URLs end in `/v1` so `openai_v1_base_url` appends nothing)

| provider_id | display | default base URL | env/credential | Auth model |
|---|---|---|---|---|
| `ovhcloud` | OVHcloud AI Endpoints | `https://oai.endpoints.kepler.ai.cloud.ovh.net/v1` | `OVH_AI_ENDPOINTS_ACCESS_TOKEN` (optional) | keyless sandbox; 400 RPM with key |
| `scaleway` | Scaleway | `https://api.scaleway.ai/v1` | `SCALEWAY_API_KEY` | 1M free tokens |
| `qwen` | Qwen (Alibaba DashScope) | `https://dashscope-intl.aliyuncs.com/compatible-mode/v1` | `DASHSCOPE_API_KEY` | 1M tokens/model, 90 days, SG |
| `llm7` | LLM7 | `https://api.llm7.io/v1` | `LLM7_API_KEY` (optional) | free shared tier, keyless OK |
| `routeway` | Routeway | `https://api.routeway.ai/v1` | `ROUTEWAY_API_KEY` | zero-price `:free` models |
| `novita` | Novita AI | `https://api.novita.ai/openai/v1` | `NOVITA_API_KEY` | zero-price chat models only |

### A.2 File changes (all follow ARCHITECTURE.md "Adding A Provider")

1. **`src/claudey/config/provider_catalog.py`** — add 6 `ProviderDescriptor`s + base-URL constants. Keyless handling mirrors the existing pattern:
   - `llm7` / `ovhcloud`: `static_credential` (like `ollama`/`lmstudio`) so the factory never requires a key; `credential_attr` optional so a user *may* supply a key. Verify `factory.py` treats `static_credential` + optional attr correctly before finalizing.
   - `qwen`,`scaleway`,`routeway`,`novita`: standard `credential_env` + `credential_attr` + `credential_url`.
2. **`src/claudey/config/settings.py`** — 6 fields with `validation_alias` = the env names above, all defaulting to `""`.
3. **`.env.example`** — 6 commented sections with signup URLs (FCM `provider-metadata.js` signup URLs are verified).
4. **`src/claudey/providers/openai_chat/profiles.py`** — 6 `OpenAIChatProfile`s. Start from an existing minimal profile (e.g. `kimi`/`wafer`); confirm reasoning-replay mode per provider during design. `routeway` uses `:free` model ids — no special casing needed, ids pass through as model names.
5. **`src/claudey/providers/runtime/factory.py`** — register the 6 ids.
6. **Tests (TDD, RED first):** one file per provider under `tests/providers/` mirroring `test_kimi.py`/`test_wafer.py` (use `tests/providers/request_factory.py`, `support.py`). Cover: payload rendering, base-URL suffix policy, keyless auth (no `Authorization` header for llm7/ovhcloud-no-key), reasoning handling.
7. **Contract test** addition: `tests/contracts/test_import_boundaries.py` / catalog enumeration test that asserts new ids appear in `PROVIDER_CATALOG` + `SUPPORTED_PROVIDER_IDS`.
8. **Smoke (optional, live):** `smoke/product/test_provider_product_live.py` — add llm7/ovhcloud keyless smoke entries (no key required).

### A.3 Definition of done
- All 6 providers selectable in Admin UI; `/v1/models` advertises discovered models.
- `tests/providers/test_{scaleway,qwen,llm7,routeway,novita,ovhcloud}.py` green; contract + boundary tests green; `./scripts/ci.sh` clean.
- README provider table updated.

---

## Phase B — Persisted combos + provider health state machine (P0, centerpiece)

> **Semver:** MINOR (`5.22.0`) — new config capability + persistence.
> **Effort:** the architectural change; 3–4 focused PRs (B-1 store, B-2 routing/failover, B-3 health, B-4 admin UI).

### B.1 Design decision — persisted combos (adopted)

Combos are **named, persisted, admin-managed fallback chains** — OmniRoute's actual product shape (review #1). Persistence follows the existing atomic-JSON-store idiom proved by `config/custom_providers.py` (custodial records, tmp+`os.replace` writes, in-process cache, env-overridable path).

**New store — `config/combos.py` (mirrors `config/custom_providers.py`):**

```python
@dataclass(frozen=True, slots=True)
class ComboNode:
    provider_model_ref: str   # "provider/model" from catalog or custom providers
    enabled: bool = True
    priority: int = 0         # lower = tried first (OmniRoute "priority" strategy)

@dataclass(frozen=True, slots=True)
class ComboRecord:
    combo_id: str             # "combo_<slug>", unique like custom_* ids
    display_name: str
    nodes: tuple[ComboNode, ...]
    enabled: bool = True
    created_at: str
```

- File: `combos.json` under the config dir, overridable via `CLAUDEY_COMBOS_PATH` (same test-redirection trick as `CLAUDEY_CUSTOM_PROVIDERS_PATH`).
- No secrets stored (routing metadata only) — no encryption concern here.
- Store API: `list_combos()`, `get_combo(id)`, `create/update/delete` with atomic writes, plus a `combo_ids()` live view used by routing (parallel to `custom_provider_ids()`).

**Tier-setting grammar (union, back-compatible):**

```
MODEL_OPUS="nvidia_nim/nvidia/...ref..."            # 1-node chain (today's behavior)
MODEL_OPUS="refA,refB,refC"                          # inline chain (env-only form)
MODEL_OPUS="@combo:flagship"                         # persisted combo reference (new)
GLOBAL_FALLBACK_MODEL="open_router/openrouter/free"  # appended last to every chain
```

- `@combo:<id>` resolves to the combo's nodes filtered to `enabled` and sorted by `priority` (then by insertion order for ties). Unknown/disabled combo ids fail **config validation** early (day-0), not at request time.
- Reasoning preference still resolves from the *primary* node and travels with the chain (chains share the tier's `reasoning_*` setting).

### B.2 Design

**Routing** (`config/model_refs.py`, `application/routing.py`):
- `configured_chat_model_refs()` → also emit every node of every chain (inline + combo) so **model discovery warms all referenced providers** (`providers/runtime/discovery.py` `referenced_provider_ids`, `warm_referenced_model_cache`).
- `ModelRouter` gains `resolve_chain(claude_model_name) -> ChainResolution` = ordered `tuple[ResolvedModel, ...]` + the reasoning policy. `resolve()` (primary-only) stays for `/v1/messages/count_tokens` and non-failover callers.

**Failover executor** (`application/failover.py`, new):
- Wraps the existing `ProviderExecutor`. For each node in the chain, in order:
  1. Consult **health registry** (B.3) — skip nodes currently marked down / locked / auth-err.
  2. Execute via `ProviderExecutor`. The node's own `admission.py` retry ring runs first (unchanged).
  3. Inspect the finalized `ExecutionFailure`. **Failover-eligible kinds:** `RATE_LIMIT`, `OVERLOADED`, `TIMEOUT`, `UPSTREAM`, `UNAVAILABLE` (gated on `retryable=True`). **Not eligible** (stop, surface the failure — burning a fallback won't help): `AUTHENTICATION`, `PERMISSION`, `INVALID_REQUEST`, `CONTEXT_WINDOW_EXCEEDED`.
  4. On eligible failure → `trace` a `failover` event (`node_tried`, `reason`, `attempt`), advance to next node. On success → record LKG-P (B.3) and stream.

**Streaming semantics** (matches OmniRoute `STREAM_EARLY_EOF` nuance):
- Failover is only legal **before any user-visible content chunk** is emitted (`message_start`/`content_block_start`). Once content is out, we cannot un-send — no failover.
- Early-EOF after content: keep the existing bounded same-node retry (`providers/stream_recovery.py`); only if retries exhaust **and** we are still pre-content do we advance the chain.
- `response_model` in SSE stays the gateway model (`ResolvedModel.original_model`) for every node — providers must never leak the private upstream id (existing contract in `application/execution.py` extends unchanged).

**Count-tokens route:** `POST /v1/messages/count_tokens` uses the primary node only (no failover on a count request).

### B.3 Health registry + reputation state — `providers/health.py` (new)

Per-provider state machine (**Healthy / down / recovery / auth-err / locked**, review #2) fed by the already-classified `ExecutionFailure.kind` — models a provider as down or recovering so chain traversal and a future admin health view mirror OmniRoute's `assessment/` layer. In-memory + TTL, per process; never persisted.

- **Last-known-good path (LKG-P):** per chain identity (combo_id or tier), remember the most recent node that completed successfully; on the next request, prefer LKG-P as primary, else configured order (OmniRoute's default strategy). Map with monotonic timestamps; bounded size.
- **Exact-model lockout:** key = `(provider_id, provider_model)`. A model-level 404 / `mode denied` / repeated 429 sets a TTL (e.g. 60s, escalate with `BACKOFF_STEPS`-style steps) during which chain traversal **skips** that node without trying it. This is OmniRoute's `exactModelLock` — a bad model must not poison a whole provider.
- **Day-0 self-heal (review #7):** on startup, run one validation probe per referenced provider (reuse `custom_provider_check.py` logic); mark unverified providers down so chain traversal and `warm_referenced_model_cache` skip them instead of failing later.
- Feedback points: websocket at `application/execution.py` (final failure), `stream_recovery.py` (early-EOF), and the API handlers.

### B.4 File changes

| File | Change |
|---|---|
| `config/combos.py` (new) | `ComboNode`/`ComboRecord` records + atomic JSON store + `combo_ids()` + validation |
| `config/model_refs.py` | inline-chain + `@combo:` parsing; `configured_chat_model_chains()`; expand `configured_chat_model_refs` |
| `config/settings.py` | `global_fallback_model: str \| None`, alias `GLOBAL_FALLBACK_MODEL`; validators: refs well-formed, combo ids exist, no dup adjacent nodes |
| `application/routing.py` | `resolve_chain()` (inline + combo sources); keep `resolve()` |
| `application/failover.py` (new) | chain traversal + eligibility + streaming-window guard |
| `application/execution.py` | expose final-failure hook to health registry; add chain/attempt fields to `route_trace` |
| `providers/health.py` (new) | provider state machine + LKG-P map + model-lock table + TTL + day-0 validation pass |
| `api/admin_routes.py` | combos CRUD + validate endpoints (`/admin/api/combos[...]`) |
| `config/admin/` | manifest entries so Admin UI renders the combos surface |
| `api/handlers/messages.py`, `responses.py` | swap `ProviderExecutor` → `FallbackExecutor` for Messages/Responses |
| `api/handlers/token_count.py` | unchanged (primary only) |
| `providers/runtime/discovery.py` | warm all chain-referenced providers; consult day-0 health marks |

### B.5 Tests (TDD)

- **Store unit** — `tests/config/test_combos.py` (mirror custom-provider store tests): CRUD atomicity, id uniqueness, corrupted-file tolerance, `CLAUDEY_COMBOS_PATH` redirection.
- **Resolution unit** — `tests/config/test_model_refs_chains.py`: inline parse, `@combo:` reference, disabled-combo rejection, priority ordering, single-ref back-compat, global fallback appended last.
- **Integration** — `tests/api/test_failover_executor.py` (mirror `test_execution_failure_contract.py`): provider A exhausts with `RATE_LIMIT` (retryable) → B receives request; `AUTHENTICATION` → no failover, single failure surfaced; pre-content vs post-content window guards; LKG-P preference; model-lock skip; health-registry state transitions. Inject failure via existing mock/transport seams (`tests/providers/support.py`, `provider_request_mocks.py`).
- **Admin** — `tests/api/test_combos_admin.py`: CRUD endpoints, validate action, secret-masking invariant (no secrets in combos).
- **Contract** — `tests/contracts/test_stream_contracts.py`: response model stays gateway model across nodes; trace emits `failover` events.
- **Smoke (live, optional)** — two free providers in one combo (e.g. `llm7` + `nvidia_nim/...`).

### B.6 Definition of done
- A persisted combo with ≥2 healthy nodes fails over end-to-end: primary 429s out → second node serves → user sees no error; auth failure does **not** trigger fallback.
- Combos are create/edit/delete-able in Admin UI with immediate effect (no restart), and `/v1/messages` + `/v1/responses` both fail over; `/count_tokens` does not.
- Health registry drives chain skips; day-0 probe marks dead providers without failing startup; `@combo:` references resolve and are validated at config time.
- All CI gates green (ruff, ty, pytest 80%+); README "Optional Model-Tier Routing" documents combos, `@combo:` syntax, and `GLOBAL_FALLBACK_MODEL`.

---

## Phase C — Resilience & routing gap-filling (smaller cards)

> **Semver:** PATCH each (behavior-hardening, no new user-visible config unless noted).

1. **Kind-aware quarantine on permanent auth/permission failures** — `admission.py` already refuses to retry non-retryable kinds. Add an explicit per-provider "auth failed" latch (quarantine for a short TTL) so a bad key is not hammered from parallel sessions. Small change in `admission.py` + tests.
2. **Audit request-shape normalizers against FCM `schema-normalizer.js` rules** — verify `openai_chat/request_policy.py` + `extra_body.py` handle: GLM `temperature` range, orphan `tool`-role message drop, stripping `parallel_tool_calls`/`n`/`top_k`/`logprobs`/`echo`/`user`/`metadata`/`store` where upstreams reject them. Likely already covered by `extra_body_validator`; **add regression tests** only where gaps appear (do not add normalizers that are not needed).
3. **Per-model token-budget / cost-aware routing (review #3)** — new work, not extension: `messaging/limiter.py` contains task-compaction dedup but no cost logic. Candidate shape: per-model cost/context metadata (partially in `ProviderModelInfo`/benchmarks overlays) + a "budget tier" selector that prefers the cheapest healthy node satisfying a token budget. Separate design doc; do not start before Phase B lands.
4. **Background credential-health scheduler (optional)** — reuse `custom_provider_check.py` probe logic on an interval + TTL cache feeding `health.py` marks. Defer unless Phase B fleet data shows value.
5. **Guard-only truncation slice (review #5, opt-in/default-off)** — session dedup + verbose-tool-log truncation at the commit boundary with exclusions, never lossy rewrite of tool/agent protocol content. Non-default; kept out of the MVP.

---

## Phase D — Security + telemetry (P3)

> **Semver:** MINOR if config added (`CLAUDEY_PROVIDER_ENCRYPTION_KEY`); else PATCH.

1. **Encrypt custom-provider keys at rest** — today `config/custom_providers.py` persists `api_key` in **plaintext** in `~/.claudey/custom-providers.json`. Port OmniRoute's `enc:v1:` AES-256-GCM envelope (IV 16B, key 32B via `scryptSync` static salt, pinned 16B GCM auth tag) with a Claudey key env var. Read-path back-compat: detect plaintext, transparently upgrade on next write. Sensitivity: this touches stored secrets → security-reviewer + full test matrix (`tests/config/test_custom_providers.py`).
2. **Route explainability telemetry (review #4)** — extend the existing `trace_event` route payload (`application/execution.py`) with `chain`, `node_index`, `failover_reason`, `nodes_tried`; expose an `x-claudey-route: <provider>/<model>` (+ fail-why) response header for CLI debugging, and render a route column in `admin_routes.get_admin_dashboard`. Toggleable by settings; keep the `[1m]`-style suffix pattern intact.

---

## Cross-cutting

### Test strategy
- TDD RED→GREEN per phase; 80%+ coverage (repo standard). New modules (`combos.py`, `failover.py`, `health.py`) get dedicated unit + integration tests; provider additions mirror existing provider test files.
- `tests/contracts/` additions: catalog enumeration for new providers; stream-identity across failover.
- Live smoke only where a provider is keyless (llm7, ovhcloud) so CI smoke never requires new secrets.

### Nightly adversarial batteries (review #6)
- Add a `nightly` GitHub job (not on the merge gate) running **mutmut mutation** on `providers/` + `application/` and **Schemathesis** (OpenAPI fuzz) on `admin_routes.py` + `api/handlers/`. Matches the "maximum test coverage" directive; failures are informational/filed, never block merges. Requires adding `mutmut`/`schemathesis` as dev extras + one workflow file.

### CI / gates
- `./scripts/ci.sh` (ruff format+check, `ty`, pytest) before push; `tests.yml` enforces on push/PR/merge_group. No new public runtime dependencies unless design proves one necessary (Phase D will decide stdlib-vs-`cryptography` explicitly).

### Versioning
- Phase A: MINOR. Phase B: MINOR. Phase C: PATCH each. Phase D: PATCH (or MINOR if the new env var is user-facing). Bump `pyproject.toml` + `uv lock` + admin `index.html ?v=` sync in the same commit (per CLAUDE.md / memory).

### Risks
- **Free-tier volatility:** FCM removes models on 404/410 (e.g. `zai-glm-4.7` on Cerebras shutdowns 2026-08-17). Mitigation: model discovery is live; Phase B health/lockout absorbs dead-model noise; do not hard-pin free model ids in docs as guarantees.
- **Failover window complexity:** mid-stream failover is out of scope by design; document that post-first-content failures surface as stream errors (matches current behavior).
- **Combos persistence:** same failure modes as `custom-providers.json` (corruption, concurrent writes) — reuse its atomic-write + tolerant-read guarantees; config validation rejects bad `@combo:` refs at day-0.
- **Token-budget routing (#3):** depends on reliable per-model cost metadata; treat as separate design, land after Phase B.
- **Encryption migration (Phase D):** must never break existing plaintext stores; keep read path tolerant and write path upgrading.
- **DashScope / Routeway suffixes:** verify exact base URL + `/v1` suffix during design; `openai_v1_base_url` appends `/v1` when absent — set constants that end in the correct path.

### Suggested execution order
1. **Phase A** (bounded, additive, validates the provider idiom) → **2. Phase B** (centerpiece: persisted combos + health state machine) → **3. Phase C** → **4. Phase D** → nightlies (cross-cutting) can start in parallel with Phase A.

---

## Task list (draft)

- [x] P2-A1 Add `ovhcloud` provider (catalog, settings, env, profile, factory, tests)
- [x] P2-A2 Add `scaleway` provider (same)
- [x] P2-A3 Add `qwen` (DashScope) provider (same)
- [x] P2-A4 Add `llm7` keyless provider (same; verify static_credential + optional key)
- [x] P2-A5 Add `routeway` provider (same)
- [x] P2-A6 Add `novita` provider (same)
- [x] P2-A7 Contract/boundary tests + README table + smoke (keyless only)
- [x] P0-B1 `config/combos.py` store + records + validation + `combo_ids()`
- [x] P0-B2 Chain grammar: inline + `@combo:` parsing in `model_refs.py` + settings validators
- [x] P0-B3 `routing.py` `resolve_chain()` + discovery warming for all nodes
- [x] P0-B4 `health.py` provider state machine + LKG-P + model-lock TTL + day-0 validation pass
- [x] P0-B5 `failover.py` executor + eligibility + streaming-window guard
- [x] P0-B6 Wire Messages/Responses handlers; trace + decision fields
- [x] P0-B7 Combos admin CRUD endpoints + Admin UI panel + tests
- [ ] P0-B8 Integration/contract tests + README docs
- [x] P1-C1 Auth-failure quarantine latch
- [x] P1-C2 FCM normalizer audit + regression tests
- [ ] P2-C3 Token-budget / cost-aware routing design doc (after Phase B)
- [ ] P3-C4 Background credential-health scheduler (deferred)
- [ ] P3-C5 Guard-only truncation slice (opt-in, non-default)
- [ ] P3-D1 Encrypt custom-provider keys at rest (+ migration)
- [ ] P3-D2 Route explainability telemetry + dashboard column
- [ ] QA-N1 Nightly mutmut + Schemathesis job (parallel)