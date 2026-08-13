# Codebase Map — claudey v5.26.0 (Phase 1 refactor analysis)

All counts verified by reading files / `rg` line-counts. Total Python surface: **265 files, ~41,415 lines** under `src/claudey/`, plus **195 test files (~66,900 lines)** under `tests/` and **38 smoke files** under `smoke/`.

## 1. Package Tree (`src/claudey`)

```
src/claudey/                     265 files, ~41,415 lines
├── api/                          29 files, ~4,949 L   FastAPI HTTP adapter + admin API + React admin UI
│   ├── app.py:121                create_app() factory; middleware, exception handlers (app.py:37-121)
│   ├── routes.py:221             proxy routes (/v1/messages, /v1/responses, /v1/models)
│   ├── admin_routes.py:640       /admin API + static React UI serving (admin_routes.py:173-205)
│   ├── handlers/                 4 files / 675 L      messages.py:383, responses.py:198, token_count.py:87
│   ├── web_tools/                6 files / 782 L      outbound web-fetch/search tools (egress, parsers, streaming)
│   ├── admin_dashboard.py, usage_aggregate.py, deepseek_billing.py:511, model_catalog.py, response_streams.py:390
│   ├── dependencies.py:78        FastAPI Depends: get_services/get_settings/resolve_provider/require_proxy_auth
│   ├── ports.py:55               ApiServices boundary (requests/admin/tasks)
│   └── admin_static/             admin-ui/ (React source), admin_ui_dist/ (committed build), logos/
├── application/                  10 files / ~1,291 L  Use cases + ports (hexagonal middle layer)
│   ├── ports.py:79               ProviderPort, RequestRuntimeLease, RequestRuntimePort, TaskController
│   ├── routing.py:326            model-ref → provider routing, combos
│   ├── failover.py:314, execution.py:168, usage_recorder.py:181, reasoning.py:99
│   └── errors.py:41, connected_accounts.py:63, model_metadata.py:19
├── cli/                          23 files / ~2,392 L  Entry points + launchers
│   ├── dispatcher.py:200         `claudey` umbrella command; _ENTRYPOINTS map (dispatcher.py:23-29)
│   ├── entrypoints.py:25         hans-server (serve), local_http.py:51
│   ├── launchers/                claude.py:64, codex.py:219, pi.py:169, codex_model_catalog.py:192
│   ├── managed/                  session.py:293, manager.py:207, claude.py:216 (managed child processes)
│   ├── desktop.py:139, desktop_tray.py:62, desktop_entrypoint.py:26, process_registry.py:76
│   └── commands.py:223           `doctor`, config commands; imports runtime.bootstrap (commands.py:21)
├── config/                       23 files / ~4,362 L  Settings + provider catalog + admin config
│   ├── settings.py:526           flat pydantic-settings env schema (Settings), per-provider sections
│   ├── provider_catalog.py:470   PROVIDER_CATALOG: id → ProviderDescriptor (auth kind, config attrs)
│   ├── admin/                    6 files / ~1,670 L   manifest.py:800 (admin UI field spec), persistence.py, sources.py, values.py, validation.py, status.py
│   ├── custom_providers.py:317   admin-defined provider records
│   ├── combos.py:302, model_refs.py:149, env_files.py:94, env_migrations.py:191, paths.py:55
│   └── nim.py:118, reasoning.py:24, logging_config.py:196, server_urls.py:26
├── core/                         52 files / ~6,566 L  SDK-free protocol logic (leaf layer)
│   ├── anthropic/                19 files / 3,102 L   Messages wire types + SSE ledger
│   │   ├── conversion.py:780     AnthropicToOpenAIConverter (largest protocol file)
│   │   ├── streaming/ledger.py:554, recovery.py:211, emitter.py:62
│   │   └── models.py:183, tools.py:212, tokens.py:118, thinking.py:140, errors.py:97
│   ├── openai_responses/         22 files / 2,399 L   Responses protocol: input.py:415, provider_stream.py:249, streaming/assembler.py:380
│   ├── failures.py, diagnostics.py:301, trace.py:197, rate_limit.py, interprocess_lock.py, secret_crypto.py, gateway_model_ids.py, version.py
├── messaging/                    53 files / ~9,292 L  Chat-platform messaging + agent-session trees (largest by files)
│   ├── workflow.py:714           message intake → session dispatch pipeline
│   ├── trees/                    12 files / 2,286 L   message tree model: manager.py:587, runtime.py:487, graph.py:250
│   ├── platforms/                10 files / 2,077 L   telegram.py:300, discord.py:319, factory.py:109, voice_flow.py:388
│   ├── node_runner.py:408, limiter.py:349, voice.py:376, turn_intake.py:241
│   ├── session/                  4 files / 463 L      persistence, store, managed_message_log
│   ├── rendering/                4 files / 748 L      telegram/discord markdown converters
│   └── transcript/               5 files / 593 L      subagent transcript buffers
├── providers/                    67 files / ~10,938 L Provider adapters (largest by lines)
│   ├── base.py:117               BaseProvider, ProviderConfig (shared contracts)
│   ├── admission.py:758          rate-limit/concurrency gate; failure_policy.py:447; stream_recovery.py:200
│   ├── openai_chat/              11 files / 2,818 L   generic OpenAI-compat engine: provider.py:1,059 (largest file in repo), profiles.py:465, tool_calls.py:449
│   ├── openai_codex/             4 files / 1,366 L    auth.py:635 (OAuth), login.py:265, provider.py:455
│   ├── nvidia_nim/               6 files / 1,527 L    native_tool_stream.py:766, tool_schema.py:255
│   ├── deepseek/                 compat.py:450, client.py:55
│   ├── anthropic/                3 files / 258 L      auth.py:61, messages.py:197 (Anthropic wire passthrough)
│   ├── google_openai/            provider.py:77, reasoning.py:146, thought_signatures.py:117
│   ├── runtime/                  6 files / 665 L      factory.py:267 (create_provider), discovery.py:161, model_cache.py
│   └── vendor stubs (2-3 files each): vertex, gemini, mistral, kilo, lmstudio, cloudflare, github_models, open_router
├── runtime/                      6 files / ~1,274 L  Composition root + lifecycle
│   ├── bootstrap.py:111          build_asgi_app() — the single production composition root
│   ├── application.py:546        ApplicationRuntime: startup/shutdown, admin ops
│   ├── provider_manager.py:503   generation-based ProviderRuntimeManager
│   └── asgi.py:64, codex_catalog.py:49
```

## 2. Key Abstractions & Data Flow

**Bootstrapping chain** (config → runtime → API):
1. `Settings` (pydantic BaseSettings, env-var driven) — `config/settings.py:21`; reads `.env` via `config/env_files.py`; `get_settings()` lru_cache at settings.py:3.
2. `build_asgi_app(settings)` — `runtime/bootstrap.py:39`: wires `OpenAIAuthManager`, `AnthropicAuthManager`, partialed `create_provider` with injected `openai` factory (bootstrap.py:52-58), `ProviderRuntimeManager`, `ApplicationRuntime`, then `create_app(ApiServices)` (bootstrap.py:81-86).
3. `create_app(services)` — `api/app.py:37`: pure FastAPI factory; `ApiServices` dataclass `api/ports.py:49-55` (requests: `RequestRuntimePort`, admin: `AdminRuntimePort`, tasks: `TaskController`).

**Request path** (`/v1/messages`):
`api/routes.py:38-67` → `services.requests.acquire()` returns `RequestRuntimeLease` (protocol `application/ports.py:38-51`, one provider generation per response) → `MessagesHandler` (`api/handlers/messages.py:383`) → `resolve_provider` (`api/dependencies.py:26-44`) → `ProviderPort.stream_response` (`application/ports.py:24-32`) → provider adapter → `core/anthropic` conversion/SSE ledger → response stream bound to lease release (`routes.py:67`).

**Provider construction**: `create_provider` (`providers/runtime/factory.py:185-225`) — catalog lookup → `build_provider_config` → `ProviderAdmissionController` → factory dispatch. Integrity assertion at factory.py:172-182 enforces every catalog id has exactly one construction owner (openai_chat profile | special factory | injected | connected account). Custom providers built at factory.py:228-267.

**Core protocol layer**: `core/anthropic/__init__.py` re-exports wire models (`MessagesRequest`, content blocks), `AnthropicToOpenAIConverter` (conversion.py), SSE aggregation; `core/openai_responses/__init__.py` exports `OpenAIResponsesAdapter`, `build_responses_provider_request`, `ResponsesProviderStream`. Failure semantics centralized SDK-free in `core/failures.py` + `core/anthropic/errors.py` / `core/openai_responses/errors.py` (per CLAUDE.md: providers own retries; core owns canonical payloads).

**Admin runtime ops**: `AdminRuntimePort` (`api/ports.py:15-46`) implemented by `ApplicationRuntime` (`runtime/application.py:108`) → admin config persisted via `config/admin/persistence.py` (prepare/commit), `config/admin/manifest.py` is the UI field spec driving `config/admin/values.py`.

**Messaging**: `messaging/workflow.py` orchestrates from platform events (`platforms/telegram.py`/`discord.py`) → `turn_intake.py` → `node_runner.py` → message trees (`messaging/trees/`) with managed CLI sessions (`cli/managed/`); rendering via `messaging/rendering/`.

**CLI entry points** (pyproject.toml:33-41): `claudey` → `cli.dispatcher:main`; `hans-server` → `cli.entrypoints:serve`; `hans-claude`/`hans-codex`/`hans-pi` → `cli/launchers/*`; `hans-desktop` → gui-script `cli/desktop_entrypoint:launch`.

## 3. Dependency Hotspots

Adjacency (verified by grepping `^from claudey.<pkg>` in every file):

| Package | core | config | application | providers | messaging | api | cli | runtime |
|---|---|---|---|---|---|---|---|---|
| **core/** | — | — | — | — | — | — | — | — |
| **config/** | yes (secret_crypto) | — | — | **yes** (custom_provider_check.py:16,20) | — | — | — | — |
| **application/** | yes | yes | — | **yes** (failover.py:27 → providers.health) | — | — | — | — |
| **providers/** | yes | yes (factory.py) | **yes** (~24 files: errors, model_metadata, connected_accounts) | — | — | — | — | — |
| **messaging/** | yes (trace, rate_limit, diagnostics) | — | — | — | — | — | — | — |
| **api/** | yes | yes | yes | — | — | — | — | — |
| **cli/** | yes | yes | — | — | — | — | — | **yes** (commands.py:21 → runtime.bootstrap) |
| **runtime/** | yes | yes | yes | yes | yes (application.py:41-47) | yes (bootstrap.py:7-8) | **yes** (codex_catalog.py:7 → cli.launchers) | — |

**Cycles / layering violations:**
- **providers ↔ application**: providers→application is pervasive (24 files); application→providers in `application/failover.py:27` (`providers.health.HealthRegistry`). Both directions = true cycle.
- **providers ↔ config**: providers/runtime/factory.py→config.* (expected), but **config→providers** in `config/custom_provider_check.py:16,20` (imports `providers.anthropic.messages` + `providers.openai_chat.base_url`) — config is a lower layer importing upward.
- **cli ↔ runtime**: cli/commands.py→runtime.bootstrap (down) and runtime/codex_catalog.py→cli.launchers.codex_model_catalog (up) — cycle between the two packages.
- **Cross-provider imports**: hub-and-spoke, all through `providers/openai_chat/` + shared infra (`admission`, `failure_policy`, `http`, `model_listing`, `stream_recovery`). 17 vendor files import openai_chat; no vendor imports another vendor's private module directly (google_openai is base for gemini/vertex). Exception noted: `google_openai/reasoning.py:13` imports `providers.openai_chat` (shared engine, not a vendor-vendor edge).

**Clean layers**: `core/` imports nothing outside core (verified — zero matches); `messaging/` depends only on core; `api/` imports no cli/messaging/providers/runtime (pure adapter).

## 4. Test Map

**Organization** — `tests/`: 195 files, ~66,900 lines. Mirrors package layout with a contracts/ twist:
- `tests/contracts/` (9 files): cross-cutting invariants — `test_import_boundaries.py:793` (import graph gates), `test_architecture_contracts.py`, `test_smoke_tiers.py`, `test_provider_catalog_order.py`, `test_stream_contracts.py`, `test_uv_policy.py`, `test_feature_manifest.py`.
- Per-package: `tests/core/` (incl. `anthropic/`, `openai_responses/`), `tests/providers/` (largest — one test file per vendor, e.g. `test_deepseek.py:1411`, plus `request_factory.py`, `support.py`, `provider_request_mocks.py`), `tests/api/`, `tests/messaging/`, `tests/application/`, `tests/runtime/`, `tests/cli/`, `tests/config/`, `tests/scripts/`.
- Unit + integration mixed within each dir; no separate unit/integration split. Live E2E lives in `smoke/`, NOT in `tests/`.

**Framework/config** (pyproject.toml:123-138): pytest 9.1.1, `pythonpath=["src"]`, `addopts="-n auto"` (pytest-xdist), `testpaths=["tests"]`. Markers: `live`, `interactive`, `provider`, `messaging`, `cli`, `clients`, `voice`, `contract`, `smoke_target`, `xdist_group`. Dev deps also include pytest-cov, mutmut (mutation testing, scope: providers/ + application/ only, pyproject.toml:85-89), schemathesis.

**`tests/conftest.py:229`**: env isolation (`.env` disabled, conftest.py:14-29), health-registry reset fixture, loguru→caplog propagation, shared provider fixtures (`nim_provider`, `open_router_provider`, `lmstudio_provider`, `llamacpp_provider`), messaging mocks (`mock_cli_session`, `mock_platform`, `mock_session_store`, `incoming_message_factory`).

**`smoke/`** (38 files): local-only live E2E, gated by `HANS_LIVE_SMOKE=1`, NOT run by default pytest. `smoke/prereq/` = liveness checks (server, auth, CLI, provider pings, local /models); `smoke/product/` = end-to-end scenarios; `smoke/features.py` = source-of-truth feature map (feature→subfeature→scenario→env→behavior→failure class); `smoke/capabilities.py`, `smoke/lib/` harness (server, http, child_process, claude_cli_matrix, report).

**`scripts/ci.sh`** (7 sequential checks, `--only/--skip/--dry-run` supported):
1. `logos` — `scripts/fetch_provider_logos.py --check` (admin_static logos synced)
2. `icons` — `scripts/generate_icons.py --check` (app icon SVG + PNG sizes)
3. `suppressions` — grep bans `# type: ignore`, `# ty: ignore`, `from __future__ import annotations`
4. `ruff-format` — `uv run ruff format` (repairs locally; GitHub CI runs `--check` only)
5. `ruff-check` — `uv run ruff check --fix` (GitHub: check only)
6. `ty` — `uv run ty check`
7. `pytest` — `uv run pytest -v --tb=short`

## 5. Admin-UI Map

**Location**: `src/claudey/api/admin_static/admin-ui/` (Vite 8 + React 19 + Tailwind 4 + shadcn/ui + tremor, package.json:2-42). 49 files under `src/`.

**Build tooling** (package.json:7-12): `dev` (vite), `build` (`vite build && node build.mjs`), `preview`, `typecheck` (`tsc --noEmit -p tsconfig.json`). `build.mjs` wipes and copies `dist/` → `../admin_ui_dist` (committed, served offline). `vite.config.ts`: `base: "/admin/"`, `@` alias → src, tailwindcss plugin, no sourcemaps.

**Dist relationship**: `admin_ui_dist/` is **tracked in git** (3 files: `index.html`, `assets/index-CPu4SDQ7.css`, `assets/index-CLI79gPV.js` — old hashed assets deleted in git status, new ones pending commit). Served by `admin_routes.py`: `/admin` (admin_routes.py:173-177, loopback-only via `require_loopback_admin` :150-159, `__ASSET_VERSION__` placeholder substituted at serve time :167), `/admin/ui` legacy 308 redirect (:180-184), `/admin/assets/{filename}` (path-traversal-guarded FileResponse :187-195), `/admin/assets/logos/` (:198-205).

**Component tree** (`src/`):
```
main.tsx → app.tsx (view switcher, hash routing, theme; app.tsx:65-120)
├── components/shared/layout/   sidebar.tsx, sidebar-budget.tsx
├── components/app/views/       usage-view, providers-view, model-config-view, messaging-view, placeholder-view
├── components/app/usage/       usage-hero, usage-heatmap, usage-daily-table, usage-trend-chart, provider-bar-list
├── components/app/providers/   provider-card, combo-dialog, custom-provider-dialog, provider-key-dialog
├── components/app/config/      model-combobox
├── components/shared/form/     config-field, config-section, config-action-bar
├── components/ui/shadcn/       20 primitives (button, card, dialog, tabs, table, select, bar-list, chart, ...)
├── hooks/                      use-json.ts (fetch-by-path), use-config-form.ts, use-count-up.ts, use-reduced-motion.ts
├── api/                        client.ts (typed fetch wrapper, cache:"no-store", api/client.ts:27-50), types.ts
└── lib/                        config.ts, utils.ts (cn)
```

**State/data-fetching**: no react-query/SWR — plain `fetch` via `api/client.ts` (GET/POST helpers per endpoint, client.ts:60-80) consumed by `useJson`/`useConfigForm` hooks with AbortSignal support; local state only. Views poll on mount/navigation.

## 6. Size Hotspots

**10 largest Python files (src/):**
| # | File | Lines |
|---|---|---|
| 1 | `src/claudey/providers/openai_chat/provider.py` | 1,059 |
| 2 | `src/claudey/config/admin/manifest.py` | 800 |
| 3 | `src/claudey/core/anthropic/conversion.py` | 780 |
| 4 | `src/claudey/providers/nvidia_nim/native_tool_stream.py` | 766 |
| 5 | `src/claudey/providers/admission.py` | 758 |
| 6 | `src/claudey/messaging/workflow.py` | 714 |
| 7 | `src/claudey/api/admin_routes.py` | 640 |
| 8 | `src/claudey/providers/openai_codex/auth.py` | 635 |
| 9 | `src/claudey/messaging/trees/manager.py` | 587 |
| 10 | `src/claudey/core/anthropic/streaming/ledger.py` | 554 |

**>800 lines**: only `openai_chat/provider.py` (1,059). `config/admin/manifest.py` is exactly 800. Runners-up at 766-780 (conversion.py, native_tool_stream.py) are over the 800 guideline if counted with comments/docstrings.

**God-modules / catch-alls to flag for refactor**:
- `providers/openai_chat/provider.py` (1,059) — generic engine for ~15 vendors; also imports admission/failure_policy/http/model_listing/stream_recovery (provider.py:36-52), so it doubles as integration point.
- `config/admin/manifest.py` (800) — admin UI field/validation manifest, likely generated or near-generated structure.
- `messaging/workflow.py` (714) — orchestrator spanning intake→dispatch→trees.
- `api/admin_routes.py` (640) — router + payload models + auth guard + static serving in one file.
- `messaging/trees/manager.py` (587) — tree lifecycle manager.
- `core/anthropic/conversion.py` (780) — Anthropic→OpenAI conversion incl. tool-turn boundary heuristics.
- Also notable: `api/deepseek_billing.py` (511), `runtime/application.py` (546), `config/settings.py` (526, flat 500-line env schema), `providers/deepseek/compat.py` (450, compat shim).

**Largest test files** (test-suite debt mirrors src hotspots): `tests/messaging/test_handler.py` (2,499), `tests/scripts/test_installers.py` (1,941), `tests/providers/test_streaming_errors.py` (1,895), `tests/providers/test_converter.py` (1,616), `tests/providers/test_deepseek.py` (1,411), `tests/config/test_config.py` (1,200), `tests/providers/test_nvidia_nim.py` (1,267), `tests/api/test_deepseek_billing.py` (1,088), `tests/core/openai_responses/test_sse.py` (1,027), `tests/api/test_openai_responses.py` + `tests/runtime/test_application_runtime.py` (1,003 each), `tests/api/test_admin.py` (2,009).

## Refactor-relevant observations (facts only)
- Layering is mostly clean: `core/` is a leaf, `api/` is a pure adapter, `messaging/` depends only on core. The three cycles (providers↔application, providers↔config, cli↔runtime) are the structural debt, plus 7 files over 700 lines.
- `tests/contracts/test_import_boundaries.py` (793 L) already encodes import-graph rules — any repackaging must update it.
- `config/admin/manifest.py` and `settings.py` both carry the full provider surface; `providers/runtime/factory.py:172-182` has a hard consistency assertion across catalog/construction — provider refactors must keep exactly-one-owner invariant.
