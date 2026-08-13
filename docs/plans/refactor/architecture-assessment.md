# Claudey Architecture Assessment — Phase 1 (analysis)

Scope: `src/claudey` (8 top-level packages, 266 .py files, ~53k raw lines), `src/claudey/api/admin_static/admin-ui` (React, mid-Phase-3), tracked build output `admin_ui_dist`, `tests/` (195 files), `smoke/` (28 files), repo root hygiene. Branch `feat/phase-a-free-providers` at v5.26.0 (pyproject.toml:7). All findings are from static analysis (Read/Grep); no source was modified.

---

## 1. Current-state module map

The package graph is governed by a **declarative import contract** in `tests/contracts/test_import_boundaries.py:13-30`:

| Package | Allowed deps | Size | Role |
|---|---|---|---|
| `core` | none (leaf) | 52 files / 6.9k lines | Protocol-neutral engine |
| `config` | **none (leaf per policy)** | 24 files | Settings, catalog, admin config |
| `application` | config, core | 10 files | Use cases, routing, failover |
| `messaging` | core | 54 files / 9.3k lines | Trees, sessions, platforms |
| `providers` | application, config, core | 66 files / 10.9k lines | Upstream adapters + shared infra |
| `api` | application, config, core | 27 files + admin_static | HTTP adapter (FastAPI) |
| `cli` | config, core | 23 files | Entry points, launchers, managed sessions |
| `runtime` | everything (composition root) | 6 files | Bootstrap, lifecycle owner |

One sanctioned exception: `cli.commands → runtime.bootstrap` (test_import_boundaries.py:32-40). The graph is statically acyclic (test_import_boundaries.py:314-321).

### core/ — protocol-neutral engine
- `core/anthropic/` (15 modules): protocol models (`models.py` — MessagesRequest, ThinkingConfig), wire error payloads (`errors.py`), SSE parsing/aggregation (`stream_contracts.py`, `sse_aggregation.py`), streaming ledger + recovery (`streaming/ledger.py` 554 lines, `streaming/recovery.py`), Anthropic→OpenAI conversion (`conversion.py` 780 lines), token counting (`tokens.py`), heuristic tool parsing (`tools.py`, `thinking.py`), tool-name codec (`openai_tool_names.py`), request serialization/snapshot. Facade: `core/anthropic/__init__.py` (102 lines, explicit `__all__`).
- `core/openai_responses/` (18 modules): `/v1/responses` wire adapter — `models.py` (OpenAIResponsesRequest), `errors.py` (openai_error_payload), `streaming/` (assembler 380, event_builders, error_mapping, blocks), `provider_input.py` (internal→provider payload), `input.py` (wire→internal). Reuses `core/anthropic` types (e.g. `provider_stream.py:6-7`, `provider_input.py:6-9`) — intra-core, healthy.
- `core/failures.py` — `ExecutionFailure` + `FailureKind` (canonical, SDK-free; 50 lines).
- `core/diagnostics.py` — credential redaction (`redact_sensitive_error_text`, `_SECRET_TEXT_REPLACEMENTS` at :16-45), bounded upstream detail extraction; SDK-free.
- `core/reasoning.py` — `ReasoningControl/ReasoningEffort/ReasoningPolicy` (resolved policy).
- `core/rate_limit.py` (StrictSlidingWindowLimiter), `core/trace.py` (structured event tracing), `core/secret_crypto.py`, `core/gateway_model_ids.py`, `core/interprocess_lock.py`, `core/async_iterators.py`, `core/version.py`.

### providers/ — upstream adapters (largest package)
- **Shared infra**: `base.py` (BaseProvider ABC, `ProviderConfig` frozen dataclass — base fields only, :20-38), `admission.py` (ProviderAdmissionController, coordinated retry sessions; 758 lines), `failure_policy.py` (SDK classification — imports `openai` + `httpx`; 447 lines), `stream_recovery.py` (holdback buffer + recovery decisions), `http.py`, `health.py` (provider reputation state machine), `model_listing.py`, `stream_recovery.py`.
- **Family base**: `openai_chat/` (10 modules; `provider.py` = OpenAIChatProvider, 1059 lines) — facade-protected by test (FACADE_ONLY_BOUNDARIES, test_import_boundaries.py:42-46). `google_openai/` — `GoogleOpenAIProvider(OpenAIChatProvider)` subclass used as Gemini-family base.
- **Registered providers** (thin wrappers over openai_chat, e.g. `open_router/client.py` = 53-line profile + subclass): mistral, deepseek, nvidia_nim, kilo, github_models, cloudflare, lmstudio; **subclass family**: `gemini/client.py:28` `GeminiProvider(GoogleOpenAIProvider)`, `vertex/client.py:40` `VertexProvider(GoogleOpenAIProvider)`; **standalone**: `anthropic/` (native /v1/messages provider), `openai_codex/` (own provider 455 lines + auth 635 lines).
- `providers/runtime/` — factory (profile map :150-159), discovery, model_cache, config. Instantiation via `providers/runtime/factory.py` reading `config/provider_catalog.py` PROVIDER_CATALOG (the single registry of provider IDs).

### application/ — use-case layer
`ports.py` (ProviderPort/RequestRuntimeLease/TaskController protocols), `routing.py` (ModelRouter), `execution.py` (ProviderExecutor/TokenCounter), `failover.py` (FallbackExecutor + route headers), `reasoning.py` (ReasoningPreference→ReasoningPolicy bridge — the "resolve reasoning once at application boundary" point), `model_metadata.py` (ProviderModelInfo dataclass), `connected_accounts.py`, `usage_recorder.py`, `errors.py`.

### api/ — HTTP adapter
`app.py` (factory + exception handlers; wire-protocol dispatch on `request.url.path` at :104-111), `routes.py` + `handlers/{messages,responses,token_count}.py`, `request_errors.py`/`response_streams.py` (wire error shaping), `web_tools/` (server tools), `admin_routes.py` (640 lines; serves `admin_ui_dist` at :53-57), `admin_dashboard.py`, `deepseek_billing.py`, `usage_aggregate.py`, `model_catalog.py`, `ports.py` (ApiServices). **Healthy finding: api has zero imports of `providers`** — it goes through `application.ports` and runtime leases.
`admin_static/`: `admin-ui/` (React 19 Vite app, 49 ts/tsx, mid-Phase-3 WIP), `admin_ui_dist/` (tracked build: index.html + hashed assets), `beam/` (reverted micro-frontend — see §4), `logos/` (provider SVGs, checked by CI `logos` check).

### config/
`settings.py` (flat pydantic-settings schema; every env var aliased here), `provider_catalog.py` (ProviderDescriptor registry), `model_refs.py`, `combos.py`, `custom_providers.py`, `admin/` (persistence, sources, validation, values, manifest, status), `nim.py` (NimSettings), `reasoning.py` (ReasoningPreference), `env_files.py`/`env_template.py`/`env_migrations.py`, `paths.py`, `server_urls.py`, `constants.py`, `custom_provider_check.py` (violation — see §2).

### messaging/
Facade is minimal (`__init__.py` exports 5 symbols; enforced by test_import_boundaries.py:571-589). Subdomains: `trees/` (graph/repository/processor/runtime — internal, facade-gated :592-602), `session/` (managed Claude persistence), `transcript/`, `rendering/` (discord_markdown 318 / telegram_markdown 327 / profiles), `platforms/` (telegram 300, discord 319, io/inbound, outbox, voice_flow 388, ports, factory), `workflow.py` (714), `node_runner.py` (408), `limiter.py`, `voice.py`, `transcription.py`, `event_parser.py`, `commands.py`. Only imports `core` — clean.

### cli/
`dispatcher.py` (unified `claudey` command), `entrypoints.py` (hans-server), `commands.py`, `local_http.py` (single owner of urllib proxy machinery — enforced by test :229-251), `proxy_auth.py`, `claude_env.py`, `process_registry.py`, `launchers/{claude,codex,pi}.py` (share `common.py` preflight/binary-resolution helpers — good DRY), `launchers/codex_model_catalog.py`, `managed/` (manager, session, claude, diagnostics), `desktop*`.

### runtime/
`application.py` (lifecycle owner, imports cli/messaging/application/config/core — sanctioned top layer), `provider_manager.py` (ProviderRuntimeManager), `bootstrap.py` (composition root, `build_asgi_app`), `codex_catalog.py` (imports `api.model_catalog` — top layer reaching into the API adapter; contract-sanctioned but see §2 item L5), `asgi.py`.

---

## 2. Principle-violation inventory (ranked)

### CRITICAL

**C1. config imports provider internals — breaks the leaf-package contract.**
`src/claudey/config/custom_provider_check.py:16-20`:
```python
from claudey.providers.anthropic.messages import (ANTHROPIC_VERSION_HEADER, anthropic_messages_url)
from claudey.providers.openai_chat.base_url import openai_v1_base_url
```
Declared policy is `config: set()` (test_import_boundaries.py:14), so `test_package_dependencies_follow_declarative_policy` (test_import_boundaries.py:125-182) flags this edge. This is also the "api/config importing provider internals" pattern the refactor brief calls out, and it creates a config↔providers cycle risk (providers→config is a legal edge, so the config→providers edge makes the dependency graph bidirectional across layers). Fix: move the URL/header constants (`anthropic_messages_url`, `ANTHROPIC_VERSION_HEADER`, `openai_v1_base_url`) into `core/anthropic/` (they are pure protocol constants — exactly what "shared Anthropic protocol logic in core/anthropic" means) and have the probe consume them from there; or relocate the probe itself into `application/` (which may import providers).

**C2. application imports providers — breaks the `{config, core}` boundary.**
`src/claudey/application/failover.py:27`: `from claudey.providers.health import HealthRegistry, health_registry`. Declared policy is `application: {config, core}` (test_import_boundaries.py:16). This inverts the layer: providers may depend on application, application may not depend on providers. Fix: move the health state machine (`providers/health.py`, 257 lines, imports only `core.failures` at :17 — already SDK-free) to `core/` or `application/`, since it operates purely on canonical `FailureKind`s.

**C3. config imports core — third live boundary break.**
`src/claudey/config/custom_providers.py:20-21`: `from claudey.core.secret_crypto import ...`. Again illegal under `config: set()`. Note: unlike C1/C2 this is a *downward* dependency, so the pragmatic fix is to amend the declared policy to `config: {"core"}` (core is a true leaf) — a deliberate, documented contract amendment rather than code motion.

Implication: **the repo's own import-boundary test is currently red on this branch** (consistent with the documented 3 deferred failures in project memory). These three edges must be the first sprint's target, because every later refactor step is validated by this test. Verify with `uv run pytest tests/contracts/test_import_boundaries.py -n0` before starting.

### HIGH

**H1. providers→application dependency for a trivial dataclass.**
`ProviderModelInfo` lives in `application/model_metadata.py`, and ~15 provider modules import it: `providers/base.py:9`, `providers/model_listing.py:6`, `providers/openai_chat/provider.py:14`, `providers/vertex/client.py:8`, `providers/kilo/models.py:6`, `providers/github_models/client.py:8`, `providers/cloudflare/client.py:11`, `providers/open_router/client.py:3`, `providers/openai_codex/provider.py:13`, `providers/anthropic/messages.py:17`, `providers/runtime/model_cache.py:5`, `providers/runtime/discovery.py:9-10`. Contract-sanctioned (providers may import application) but architecturally inverted: the provider layer depends on the use-case layer for a plain dataclass. Move `ProviderModelInfo` to `core/` (or `providers/base.py`) and have `application` import it from there.

**H2. Cross-provider utils imports (letter of the rule).**
- `providers/gemini/client.py:6-8` and `providers/vertex/client.py:12-13` import `claudey.providers.google_openai` (`GoogleOpenAIProvider` — gemini/client.py:8, vertex/client.py:13).
- Nine providers import `claudey.providers.openai_chat` (facade-protected by contract, so this one is at least test-blessed).

CLAUDE.md says "Do not have one provider import from another provider's utils." The reality: `openai_chat` and `google_openai` function as *family base libraries*, not registered providers (neither appears in `config/provider_catalog.py`; the factory registers only concrete IDs, `providers/runtime/factory.py:150-159`). Recommendation: either (a) codify this by renaming `providers/google_openai/` → a neutral `providers/gemini_family/` (or move its Gemini wire helpers — `reasoning.py`, `thought_signatures.py` — into `core/`, mirroring the `core/anthropic` pattern) and add `claudey.providers.google_openai` to FACADE_ONLY_BOUNDARIES; or (b) leave in place and document the family-base designation in ARCHITECTURE.md. Option (a) is the CLAUDE.md-consistent target.

**H3. Triple-duplicated incremental SSE "\n\n" split loops + `+=` string buffers.**
The same pattern exists in three places:
- `core/openai_responses/anthropic_sse.py:21-34` (`buffer += chunk.decode(...)` / `buffer += str(chunk)`)
- `core/anthropic/sse_aggregation.py:90-95` (`buffer += chunk`)
- `application/usage_recorder.py:162-167` (`buffer += chunk`)

Plus string-append accumulator state: `core/anthropic/streaming/ledger.py:117` (`state.task_arg_buffer += args`), `providers/openai_chat/tool_calls.py:278` (`state.pre_start_args += arguments`), `core/anthropic/thinking.py:44`, `core/anthropic/tools.py:98`. Violates both the DRY principle and the performance rule ("list accumulation for strings, not `+=` in loops"). Practical impact is bounded (the `\n\n` split keeps buffers small), hence HIGH as a consolidation item, not a hot-path emergency. Extract one incremental SSE parser in `core/anthropic/` (e.g. alongside `stream_contracts.py`'s `parse_sse_text`) and reuse it in all three consumers; convert the accumulator buffers to list-of-chunks + `"".join`.

**H4. Duplicated retryability classifiers.**
`providers/failure_policy.py:160-189` (`is_retryable_provider_error`) and `providers/stream_recovery.py:178-200` (`is_retryable_stream_error`) are near-identical retryable checks with slightly different exception sets (the recovery one omits `httpx.WriteError`/`RetryableProviderProtocolError` variants and inlines the `openai` bad-request branch). Two decision tables for one concept = drift risk. Merge into one classifier in `failure_policy.py` with an explicit set of exception families, and let `stream_recovery.py` import it.

### MEDIUM

**M1. Parallel platform adapters with duplicated glue.**
`messaging/platforms/telegram_inbound.py:44-62` vs `discord_inbound.py:45-63` — identical raw-content log-preview block (including `text_preview += "..."` at telegram_inbound.py:47 / discord_inbound.py:48); both files also build parallel `VoiceNoteRequest`s. `messaging/rendering/telegram_markdown.py` (327 lines) and `discord_markdown.py` (318 lines) both walk markdown-it tokens with structurally identical `render_inline` loops (e.g. telegram_markdown.py:80-119 vs discord_markdown.py counterpart), differing only in escape/emit rules. Extract a shared token-walk skeleton + per-platform emit hooks (a `RenderingProfile`-style split already exists at `rendering/profiles.py:37-53`); extract the log-preview/voice-request glue into a platform-neutral helper.

**M2. Hardcoded literals where settings/constants exist.**
- `api/admin_routes.py:58-62` `LOCAL_PROVIDER_PATHS = {"lmstudio": "/models", "llamacpp": "/models", "ollama": "/api/tags"}` and `api/admin_routes.py:392-399` `_local_provider_url` hardcode env names `"LM_STUDIO_BASE_URL"`, `"LLAMACPP_BASE_URL"`, `"OLLAMA_BASE_URL"` — these already exist as settings fields (`config/settings.py:162,168,174`) and `.env.example` entries (:138,142,146). The env-name strings are duplicated outside `config/`.
- `runtime/bootstrap.py:102` `settings.whisper_device == "nvidia_nim"` — literal repeated in `config/settings.py:420,499`, `config/admin/manifest.py:424-425`, `config/admin/persistence.py:138` (`"nvidia_nim"` also appears in the usage-log docstring `api/usage_aggregate.py:7`). Introduce a named constant (e.g. `NIM_WHISPER_DEVICE = "nvidia_nim"` in `config/constants.py`).

**M3. Provider-specific settings model living in config.**
`config/nim.py` (`NimSettings`, 118 lines) is NVIDIA-NIM-specific; consumed by `providers/nvidia_nim/request_options.py:6` and `client.py:11`. CLAUDE.md's example of provider-constructor config is literally `nim_settings` — the base `ProviderConfig` is correctly clean (`providers/base.py:20-38` has no NIM fields), so this is a location smell, not a bleed. Move `NimSettings` to `providers/nvidia_nim/settings.py` (config keeps only the field on `Settings`). Pure relocation, contract-neutral (config→config internal).

**M4. `HANS_*` naming leftovers (platform-agnostic naming).**
`config/paths.py:5-8` (`HANS_CONFIG_DIRNAME = ".claudey"`, `HANS_LOGS_DIRNAME`, `AUTH_DIRNAME`), consumed by `api/deepseek_billing.py:33` and `api/usage_aggregate.py:26`. The rebrand to `.claudey` is complete; rename constants to `CLAUDEY_*`/`LOGS_DIRNAME`. LOW behavioral risk (internal names only), but a flag-level rename across the repo (config, api, cli) must be one atomic commit.

**M5. File-size guideline breaches.**
`providers/openai_chat/provider.py` = 1059 lines (guideline max 800); `providers/admission.py` = 758, `providers/nvidia_nim/native_tool_stream.py` = 766 (at the cap). `core/anthropic/conversion.py` = 780. Split `openai_chat/provider.py` (streaming execution vs model listing vs request-body retry policy are separable concerns — the file already contains at least three distinct subsystems per the `_next_create_retry_body`/`stream_response`/`list_model_infos` surface).

### LOW

**L1.** `config/custom_provider_check.py:167-185` `_network_error_message` — string-matching on error text (`"econnrefused"`, `"certificate verify"`) for user messages; a parallel classifier exists in `providers/failure_policy.py:222-252` (`provider_error_message`). Consolidate wording sources.
**L2.** `api/admin_routes.py:393-398` string-compare chain `if provider_id == "lmstudio"` — derive from a single declarative map (see M2).
**L3.** `providers/runtime/discovery.py:9` imports `application.errors` (`ApplicationUnavailableError`) — same upward pattern as H1, one more instance to fix when `ProviderModelInfo` moves.
**L4.** Dead-code candidates: `admin_static/beam/` (see §4); verify `providers/mistral/reasoning.py` (404 lines) and `messaging/safe_diagnostics.py` (15 lines) still have live consumers before the cleanup sprint (mistral/reasoning is imported by the mistral wrapper; safe_diagnostics was not observed in the messaging facade — confirm).
**L5.** `runtime/codex_catalog.py:5` imports `api.model_catalog` — top layer reaching into the HTTP adapter; contract-sanctioned but means `api` is not a pure leaf. Prefer moving `build_models_list_response` into `application/` (or runtime-owned) so `api` stays adapter-only.

Positive verification (no violations found): zero `# type: ignore`/`# ty: ignore`/`from __future__ import annotations`/`TYPE_CHECKING` in `src/claudey`; `core/` is SDK-free (`test_core_does_not_import_provider_transport_sdks`, test_import_boundaries.py:487-499); providers do not own wire error type literals (test_import_boundaries.py:502-524); no model-name branching (`startswith("claude-"/"gpt-"/...)` — zero hits); messaging imports only core; api imports no providers.

---

## 3. Refactor direction

Target state (dependency order, foundations first — each sprint ends green on `scripts/ci.sh`):

**Sprint 0 — Make the contract green (foundation).** Fix C1/C2/C3. For C1: promote `anthropic_messages_url` + `ANTHROPIC_VERSION_HEADER` (from `providers/anthropic/messages.py`) and `openai_v1_base_url` (from `providers/openai_chat/base_url.py`, already a 7-line pure function) into `core/anthropic/`; repoint `custom_provider_check.py`. For C2: move `providers/health.py` to `application/` (it is already FailureKind-pure). For C3: amend `ALLOWED_PACKAGE_DEPENDENCIES["config"] = {"core"}` with a comment, or relocate `secret_crypto` consumers. This unblocks every subsequent sprint's verification via `test_import_boundaries.py`.

**Sprint 1 — Kill providers→application (H1/L3).** Move `ProviderModelInfo` from `application/model_metadata.py` to `core/` (or `providers/base.py`); update ~15 import sites; `application` imports it from the new owner (complete migration per CLAUDE.md — no shims). Also move `build_models_list_response` out of `api/` if L5 is accepted.

**Sprint 2 — SSE parsing consolidation (H3).** One incremental-SSE parser in `core/anthropic/` (iterator over `AsyncIterable[bytes|str]` that splits on `\n\n` and yields parsed events, list-based accumulation); replace the three loops in `anthropic_sse.py`, `sse_aggregation.py`, `usage_recorder.py`; convert ledger/tool-call buffers to chunk lists. Behavior-neutral (identical yield semantics), strongly covered by existing stream tests.

**Sprint 3 — Failure classification DRY (H4).** Merge `is_retryable_provider_error`/`is_retryable_stream_error` into one classifier in `failure_policy.py`; `stream_recovery.py` imports it. Guard with a table-driven unit test over the exception-family matrix (retryable/not for each httpx+openai type) so the merge cannot silently change retry decisions.

**Sprint 4 — Provider family boundaries (H2).** Rename `providers/google_openai/` → neutral family package (e.g. `providers/gemini_family/` or relocate wire helpers to `core/gemini/`) and add it to `FACADE_ONLY_BOUNDARIES`; update gemini/vertex imports. Purely mechanical import updates, no behavior change; the facade test then guards it.

**Sprint 5 — Messaging platform dedup (M1).** Shared log-preview + voice-request builder in `messaging/platforms/` (or `messaging/`); extract markdown token-walk core with per-platform emit hooks; verify telegram/discord rendering byte-for-byte against existing rendering tests.

**Sprint 6 — Literals, naming, file sizes (M2/M3/M4/M5).** Whisper-device constant; single local-provider-path/env map (in `config/`, referenced by `admin_routes`); move `NimSettings` to `providers/nvidia_nim/`; `HANS_*` → `CLAUDEY_*` rename in one commit; split `openai_chat/provider.py` along the three subsystem seams.

**Sprint 7 — Dead code + hygiene (see §4):** remove `admin_static/beam/`, root junk; settle `admin_ui_dist` policy; commit the Phase-3 build atomically with the admin-ui work.

Each sprint is independently shippable (PATCH-level per the semver rules, except Sprint 6's `HANS_*` rename which stays PATCH since the constant names are internal).

---

## 4. Repo hygiene & folder reorg

### Root junk inventory (all untracked)
- **13 screenshots at repo root**: `admin-rendered.jpeg`, `beam-drag.png`, `beam-verified.png`, `budget-final-expanded.png`, `budget-redesign.png`, `collapsed-check.png`, `collapsed-icons-fixed.png`, `provider-key-dialog.png`, `sidebar-hover-fixed.png`, `sidebar-three-fixes.png`, `usage-chart-fixed.png`, `usage-full.png` — GAN-harness verification artifacts of the admin-ui Phase-3 work.
- **`.playwright-mcp/`** — 40+ files of Playwright MCP debug output (console logs, page YAML a11y snapshots, PNGs) dated 2026-08-09 → 08-12.
- **`model-config-skeleton.yml`** — confirmed Playwright a11y-tree dump (its content is a `generic [ref=e1]`-style snapshot of the admin nav, not a config skeleton).

**Recommendation**: delete all three. The screenshots' information (UI state at a commit) is reproducible by re-rendering the admin-ui; if the harness needs a permanent home, create `assets/screenshots/` and gitignore it — do not track them. Nothing in the repo references any of these files (verified by grep).

### .gitignore additions
```
.playwright-mcp/
assets/screenshots/
```
Also consider `src/claudey/api/admin_static/beam/node_modules/` — already covered by the existing `node_modules/` rule (:23).

### admin_ui_dist tracking decision
Keep **tracked**. Rationale: `admin_routes.py:53-57` serves it statically as the packaged serving dir, the app must work offline/installed (no build step at install time), and the `.gitignore` comment (:26) plus the architecture contract (`docs/frontend-scaffold-plan.md`) already encode this policy. But the current tree is mid-build and inconsistent: `index-DZY5IEv8.css`/`index-LQllRiI5.js` deleted (git D), `index-CPu4SDQ7.css`/`index-CLI79gPV.js` untracked (git ??), `index.html` modified (M). The Phase-3 PR must commit the old-asset deletions and the new build in the same commit (complete migration rule — no stale hashed assets in history). Optional hardening: add a CI check (like `logos`/`icons`) that fails when `admin_ui_dist` is out of sync with a fresh `npm run build` — prevents the current drift class from recurring.

### admin_static/beam — dead code
The "provider beam" was removed from the React app in commit `756bf5c8 revert(admin-ui): remove provider beam from React app`. `beam/` still tracks `package.json`, `build.mjs`, `tsconfig.json`, `package-lock.json` (670 lines), `src/main.tsx` (495 lines), `src/components/animated-beam.tsx` (199 lines), `src/beam.css` (221 lines), `src/lib/utils.ts`; its promised output `beam.bundle.js` no longer exists; nothing imports the beam build; only `docs/frontend-scaffold-plan.md:28` references it. Delete `admin_static/beam/` (git history preserves it). Safe move: pure deletion of an unused subtree.

### src/claudey subpackage layout
No restructuring of the 8 top-level packages is warranted — the layout is sound and contract-enforced. Proposed moves are surgical and all pure relocations:
- **Safe (relocation only, zero behavior change)**: `NimSettings` config/nim.py → `providers/nvidia_nim/settings.py` (M3); `health.py` providers/ → application/ (C2 fix); `openai_v1_base_url` + `anthropic_messages_url`/`ANTHROPIC_VERSION_HEADER` → `core/anthropic/` (C1 fix); `ProviderModelInfo` → core/ (H1); `google_openai/` rename (H2).
- **Risky (behavior-affecting — must not be lumped into relocation sprints)**: any change to `admin_ui_dist` content (served bytes), `providers/failure_policy.py` wording constants (user-visible messages, `_AUTHENTICATION_MESSAGE` etc.), retry budgets in `admission.py:27-31`, `stream_recovery.py:15-16` holdback constants, CLI exit codes, `.env.example` (it is force-included into the wheel — `pyproject.toml:59-60`, contract-tested at test_architecture_contracts.py:30-47), or provider registration in `provider_catalog.py`.

---

## 5. Risks & invariants

### Must not change in a behavior-preserving refactor

**Wire protocol (Anthropic)** — `/v1/messages` request/response shape and SSE event stream (`core/anthropic/streaming/` emitter + `format_sse_event`; error payloads in `core/anthropic/errors.py` — `anthropic_error_payload`, `anthropic_error_type_for_failure`; `app.py:104-111` picks wire format by path). SSE event ordering and stop-reason mapping (`map_stop_reason`).

**Wire protocol (OpenAI Responses)** — `/v1/responses` events and `openai_error_payload` (`core/openai_responses/`); `test_providers_do_not_own_wire_error_type_literals` (test_import_boundaries.py:502-524) already pins that providers never emit these.

**Env vars** — every alias in `config/settings.py` + `.env.example` (source of truth; wheel force-include; `test_root_env_example_is_the_single_template_source`). Renames are MAJOR bumps. The `.claudey` config dir (`config/paths.py:5`) is user-visible state — unchanged.

**Admin API responses** — `admin_routes.py` payload shapes: `load_config_response` (`config/admin/values.py`), `provider_config_status`, `dashboard_payload`, `usage_payload`, `billing_payload`, `Cache-Control: no-store` middleware, `/admin/ui` static serving with `asset_version` (`core/version.py`). The `?v=` cache-buster sync between `admin_ui_dist/index.html` and pyproject bumps is a known trap (memory: claudey-tokentracker).

**Provider behavior** — retry budgets and backoff (`providers/admission.py:27-31`: 5 attempts, 2.0s base, 60s max, 1.0 jitter; auth-latch TTL 5s :31); stream holdback 0.75s / 64KiB (`providers/stream_recovery.py:15-16`); user-facing failure wording (`failure_policy.py:32-39`, `_stable_upstream` :361-364); output-token-cap learning (`openai_chat/provider.py:106-108`); NIM retry-body degradation (`providers/nvidia_nim/retry.py`); `max_retries=0` SDK policy (`openai_chat/provider.py:124`).

**CLI surface** — `claudey` + `hans-*` entry points (pyproject:33-41), exit codes (127 binary-missing, 126 incompatible, 1 preflight failure — `launchers/common.py:52-58`, `launchers/pi.py:40-45`), launcher env contracts (`HANS_PI_API_KEY`, `HANS_PI_BASE_URL`, `proxy_auth_token`), managed-session lifecycle and process registry, `doctor` output.

**Messaging** — Telegram/Discord platform semantics (parse modes, markdown escaping), managed message-log persistence format (`messaging/session/persistence.py`), tree serialization (`messaging/trees/snapshot.py`), usage-log JSONL schema (`application/usage_recorder.py` `TOKEN_FIELDS`/`USAGE_LOG_FILENAME`, consumed by `api/usage_aggregate.py:25`).

### Safety net
- **`tests/contracts/test_import_boundaries.py`** — static import-graph contract (package deps, acyclicity, facade-only boundaries, no wire literals in providers, no SDKs in core, single owners for urllib/optional deps). The single most valuable guard for this refactor; Sprint 0 must restore it to green.
- **`tests/contracts/test_architecture_contracts.py`** — ARCHITECTURE.md presence/link validity, env.example single-source, pyproject first-party config.
- **`tests/core/test_failure_protocol_mapping.py`**, `test_protocol_model_ownership.py`, `test_failures.py`, `test_diagnostics.py` — pin the FailureKind→wire mapping and redaction; **`tests/api/test_execution_failure_contract.py`**, `test_ordinary_error_phases.py` — pin wire error phases; **`tests/providers/`** — `test_stream_recovery.py`, `test_nvidia_nim_degraded_retry.py`, `test_openai_compat_5xx_retry.py`, `test_execution_failure_boundary.py`, `test_provider_transport_logging.py` pin the retry/classification matrix (Sprint 3's merge is safe only while these stay green).
- **`smoke/`** — live prereq + product E2E (28 files) with the feature inventory in `smoke/features.py`; `scripts/ci.sh` runs 7 checks (logos, icons, suppressions, ruff-format, ruff-check, ty, pytest); mutmut is configured for providers+application (`pyproject.toml:85-89`).
- For pure relocations (Sprint 0/1/4): the import-boundary test *is* the regression test — it fails on stale imports (bare-owner names, ancestor facades, cycles), so "update all imports, delete shims, test passes" is the complete-migration gate.

Residual risks: none for the analysis itself beyond the inability to execute pytest in this session — the C1/C2/C3 finding should be confirmed by running `uv run pytest tests/contracts/test_import_boundaries.py -n0` on the branch before Sprint 0 planning; and the admin-ui Phase-3 WIP (uncommitted `admin-ui/` changes + untracked `admin_ui_dist` build) must land atomically before hygiene cleanup so the screenshots' information is preserved in the commit history.

Note: the admin-ui Phase-3 WIP was committed as `ebca06ce` on 2026-08-13 before this assessment was finalized — that condition is now satisfied.
