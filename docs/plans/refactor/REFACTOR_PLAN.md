# Refactor Plan — claudey v5.26.0 (Phase-A foundation sprints)

Branch: `feat/phase-a-free-providers` · Date: 2026-08-13 · Inputs: `docs/plans/refactor/architecture-assessment.md`, `docs/plans/refactor/codebase-map.md`, `docs/plans/refactor/dead-code-inventory.md`

This plan is the executable contract for the GAN Generator. The Evaluator scores against `docs/plans/refactor/RUBRIC.md`. The analysis documents (assessment/codebase-map/inventory) are **dated snapshots of the before-state — do not edit them**; they document history. The living docs are `ARCHITECTURE.md`, `docs/design-system.md`, `docs/frontend-scaffold-plan.md`.

---

## 1. Goals & Non-Goals

### Goals
1. **Behavior-preserving refactor**: zero user-visible change. Wire protocol, env vars, admin API payloads, CLI surface, provider retry budgets/backoff, and user-facing failure wording are frozen (see §10 invariants).
2. **Make the import-boundary contract green first** and keep it green: `tests/contracts/test_import_boundaries.py` currently has **2 failures, 19 passes** on this branch. The foundation sprint fixes both.
3. **Resolve the assessment's principle violations** (C1-C3 critical, H1-H4 high, M2/M4/M5 medium) without introducing new ones.
4. **Eliminate dead code and repo junk** per the dead-code inventory: retire `admin_static/beam/`, delete root artifacts, settle `admin_ui_dist` tracking, tidy `docs/`, remove admin-ui dead exports/types/components/deps/CSS tokens.
5. **Every sprint ends green on `./scripts/ci.sh`** (all 7 checks: logos, icons, suppressions, ruff-format, ruff-check, ty, pytest).
6. **Code health floor**: no file >800 lines after splits; functions <50 lines; zero `# type: ignore` / `# ty: ignore` / `from __future__ import annotations`; list accumulation not `+=` in loops; platform-agnostic constant names.

### Non-Goals
- **No visual redesign** of the admin-ui. The in-flight Phase-3 redesign (commit `ebca06ce` area) is untouched; this refactor only *removes* dead admin-ui code and never edits component behavior, layout, or styles.
- **No restructure of the 8 top-level packages** — the layout is sound and contract-enforced. All moves are surgical relocations.
- **No new features, no dependency additions, no `uv.lock`/`pyproject.toml` dependency changes.**
- **No renaming of user-facing env vars** (`HANS_ENV_FILE`, `HANS_PI_*`, `HANS_CODEX_API_KEY`, `HANS_OPEN_BROWSER`, `HANS_SMOKE_*` are frozen aliases — renaming is a MAJOR bump). Only internal Python identifiers in `config/paths.py` are renamed (M4).
- **No touching smoke/ files** unless a moved symbol is imported there (grep first).
- **No version bump** — see §4.

---

## 2. Verified Baseline (run once at Sprint 0 start, record in report)

```bash
uv run pytest tests/contracts/test_import_boundaries.py -n0
# EXPECTED NOW: 2 failed, 19 passed
#  - test_package_dependencies_follow_declarative_policy  (config→providers, application→providers.health, config→core.secret_crypto edges)
#  - test_external_consumers_use_owned_package_facades    (config/custom_provider_check.py:20 reaches behind providers.openai_chat facade)
uv run pytest --cov=claudey --cov-report=term-missing -q   # record the Total line as the coverage baseline
git status --porcelain                                     # record: expected untracked junk only (root screenshots, .playwright-mcp/, model-config-skeleton.yml)
```

Contract policy map (source of truth, `tests/contracts/test_import_boundaries.py:13-30`): `config: set()`, `core: set()`, `application: {config, core}`, `messaging: {core}`, `providers: {application, config, core}`, `api: {application, config, core}`, `cli: {config, core}`, `runtime: {api, application, cli, config, core, messaging, providers}`. Facade-only boundaries (:42-46): `claudey.core.openai_responses`, `claudey.messaging.trees`, `claudey.providers.openai_chat`. Sanctioned exception: `cli.commands → runtime.bootstrap` (:32-40).

**Generator may edit `test_import_boundaries.py` in exactly two sanctioned ways** (both specified below): the `config: {"core"}` amendment (Sprint 0) and the `gemini_family` facade addition (Sprint 4). All other test edits are mechanical import-site updates for moved symbols.

---

## 3. Versioning Note

**No version bump in this refactor.** The work lands on the feature branch `feat/phase-a-free-providers`, not `main`; the CLAUDE.md versioning rule applies to commits on `main`. Do not touch `pyproject.toml` `[project].version` (currently 5.26.0) and do not change the `?v=` cache-buster in `admin_ui_dist/index.html` (it must stay equal to the pyproject version — verify, don't change). When this branch is later merged to `main`, the merge commit should carry a PATCH bump (`5.26.0 → 5.26.1`, refactor with no user-visible change) — that is a note for the orchestrator, not an action here.

---

## 4. Sprint Contract (per sprint, generator side)

For every Python sprint, the generator executes in this exact order and reports each step's outcome:

1. **Read** the sprint scope below plus the relevant feedback file(s) `docs/plans/refactor/feedback-<sprint>-NNN.md` (latest iteration only) — every issue in the latest feedback must be addressed (fix, or record an explicit rebuttal with evidence in the report; never silently skip).
2. **Implement** the sprint actions (§7). Pure `git mv` for file relocations.
3. **Format/lint repair**: `uv run ruff format && uv run ruff check --fix`
4. **Type check**: `uv run ty check`
5. **Targeted tests**: `uv run pytest <affected test files>` (see "Affected tests" per sprint) plus `uv run pytest tests/contracts/test_import_boundaries.py -n0`
6. **Report** to `docs/plans/refactor/` as `sprint-report-<sprint>-NNN.md`: files changed (path:line), verification command outputs, coverage delta vs baseline, rebuttals (if any), residual risks. Then the Evaluator runs the full gate (`./scripts/ci.sh` + rubric) and writes `feedback-<sprint>-NNN.md`.

Maximum 5 generator-evaluator iterations per sprint. If 2 consecutive iterations produce no score gain, stop and escalate to the orchestrator (do not burn iterations).

## 5. Admin-UI Sprint Mechanics

Only Sprint 8 touches admin-ui source. Rules:
- Work dir: `src/claudey/api/admin_static/admin-ui/`. Run `npm install` first only if `node_modules/` is missing.
- Gate: `npm run typecheck` (`tsc --noEmit -p tsconfig.json`) must pass after every change batch.
- `npm run build` only when `admin_ui_dist` must be re-synced (Sprint 8 step 5). Otherwise never build.
- **No visual redesign changes**: removals only; never edit component behavior, layout, styles, or copy.
- The Phase-3 WIP is in flight: before deleting anything from the inventory, **re-verify with grep** that the item still has zero importers on the current tree (the inventory is a snapshot). If the redesign adopted an item since the inventory, keep it and note the deviation in the report.
- Python CI must still pass after admin-ui work (admin-ui is not covered by pytest, but `admin_ui_dist` content is served — see Sprint 8 step 5).

---

## 6. Sprints at a Glance

| # | Name | Assessment items |
|---|---|---|
| 0 | Foundation: import-boundary contract green | C1, C2, C3 |
| 1 | Kill providers→application | H1, L3 |
| 2 | SSE parsing consolidation | H3 |
| 3 | Failure classification DRY | H4 |
| 4 | Provider family boundaries | H2 |
| 5 | Messaging dedup I (inbound glue + queued messenger) | M1a, inventory Cluster A/B |
| 6 | Messaging dedup II (markdown token-walk) | M1b |
| 7 | Literals, naming, file sizes | M2, M4, M5, L1, L2 (M3 resolved in-place) |
| 8 | Repo hygiene, dead code, docs | assessment §4 + inventory §2-3 |

Sprint 0 must land first — every later sprint is validated against the boundary test it repairs. Sprints 2-6 are independent of each other; keep the given order so feedback files stay addressable.

---

## 7. Sprint Details

### Sprint 0 — Foundation: import-boundary contract green (C1, C2, C3)

**Goal**: `uv run pytest tests/contracts/test_import_boundaries.py -n0` → 21 passed. This is the gate for the whole refactor.

**Actions:**

1. **C1 — Promote wire URL constants to `core/anthropic/`.** Create `src/claudey/core/anthropic/urls.py` containing, with docstrings:
   - `ANTHROPIC_VERSION_HEADER = "2023-06-01"` (moved from `providers/anthropic/messages.py:31`)
   - `anthropic_messages_url(base_url: str) -> str` (moved from `providers/anthropic/messages.py:34`)
   - `openai_v1_base_url(base_url: str) -> str` (moved from `providers/openai_chat/base_url.py:4-7`, the whole file)
   Rationale for hosting the OpenAI-compat URL here: `core/openai_responses` is facade-gated (`FACADE_ONLY_BOUNDARIES`), and the config-layer consumer `config/custom_provider_check.py` may not reach behind it. These are gateway wire-endpoint helpers for both protocols; `core/anthropic/urls.py` is the contract-safe home.
2. Update **all** importers of the three names (grep `anthropic_messages_url|ANTHROPIC_VERSION_HEADER|openai_v1_base_url` across `src/`, `tests/`, `smoke/`; verified: the only src importers are `config/custom_provider_check.py:16-20` and the two owner modules themselves; zero test imports). `providers/anthropic/messages.py:59,62` keeps using the names via the new core import. After the move, if `providers/openai_chat/base_url.py` has no remaining content, **delete the file** (complete migration — no shims).
3. **C2 — Move `providers/health.py` → `application/health.py`.** `git mv` the file. It is already FailureKind-pure (its only claudey import is `core.failures.FailureKind` at `health.py:17`). Update all four known import sites: `application/failover.py:27` (becomes an intra-application import), `tests/api/test_failover_executor.py:15`, `tests/conftest.py:35`, `tests/providers/test_health.py:6`; move the test file `git mv tests/providers/test_health.py tests/application/test_health.py` and update its import. Grep `providers.health` for stragglers after.
4. **C3 — Amend the declarative contract.** In `tests/contracts/test_import_boundaries.py:14`, change `"config": set(),` → `"config": {"core"},` with a comment: config→core (`custom_providers.py:20-21` → `core.secret_crypto`) is a legitimate downward edge to a true leaf; core imports nothing. This is a deliberate, documented contract amendment (not code motion). If `ARCHITECTURE.md` states config's import policy, update the statement in the same commit (keep the link-validity contract test `test_architecture_contracts.py` green).
5. Verify: boundary file 21 passed; then the full gate.

**Acceptance:**
- `uv run pytest tests/contracts/test_import_boundaries.py -n0` → 21 passed (both previously failing tests now green).
- Zero `claudey.providers` imports in `config/` (grep `config/.*from claudey\.providers` → 0 hits).
- Zero `claudey.providers` imports in `application/` (grep → 0 hits).
- `./scripts/ci.sh` green (full suite).

**Affected tests:** `tests/contracts/test_import_boundaries.py`, `tests/contracts/test_architecture_contracts.py`, `tests/application/test_health.py` (moved), `tests/api/test_failover_executor.py`, `tests/conftest.py`, any test importing the three constants (verified: none).

**Risks:** The config-policy amendment is a contract change — the Evaluator must accept it because it is pre-approved here and documented in the test itself. Moving health.py changes no behavior (pure relocation; tests pin the state machine). Deleting `base_url.py` only if zero importers remain — grep first.

---

### Sprint 1 — Kill providers→application (H1, L3)

**Goal**: no `src/claudey/providers/` module imports `claudey.application.*` (grep → 0 hits). Contract already allows it; this removes the architectural inversion.

**Actions:**

1. **H1 — Move `ProviderModelInfo` to `core/`.** Create `src/claudey/core/model_metadata.py` holding `ProviderModelInfo` (moved from `application/model_metadata.py:6-11`; a pure frozen dataclass). Grep `ProviderModelInfo` across `src/`, `tests/`, `smoke/` — known src importers: `providers/base.py:9`, `providers/model_listing.py:6`, `providers/openai_chat/provider.py:14`, `providers/vertex/client.py:8`, `providers/kilo/models.py:6`, `providers/github_models/client.py:8`, `providers/cloudflare/client.py:11`, `providers/open_router/client.py:3`, `providers/openai_codex/provider.py:13`, `providers/anthropic/messages.py:17`, `providers/runtime/model_cache.py:5`, `providers/runtime/discovery.py:9-10`, plus ~20 test files (see the grep list recorded in §7 verification). Update **all** to import from `core.model_metadata`. `ProviderModelRefreshResult` (`application/model_metadata.py:14-19`): keep in `application/` unless grep shows a provider-side importer (none known) — if providers import it, move it too. If `application/model_metadata.py` becomes empty, delete it. Update `ARCHITECTURE.md:618` (the "owns the immutable ..." line) in the same commit.
2. **L3 — Move `ApplicationUnavailableError` to `core/errors.py`.** Grep all importers: `providers/runtime/discovery.py:9`, `tests/runtime/test_provider_manager.py:7`, `tests/providers/test_cloudflare.py:10`, `tests/api/test_dependencies.py:13`. Move the class from `application/errors.py` to a new `src/claudey/core/errors.py`; `application/errors.py` keeps its other classes (`InvalidRequestError`, `UnknownProviderError`, etc. — do not move them unless grep shows provider-side importers; if some are provider-imported, move those too). Update all importers; no shim.
3. Grep `from claudey.application` in `src/claudey/providers/` — target 0 hits.

**Acceptance:** grep checks above at 0; boundary test green; full `./scripts/ci.sh` green; `ARCHITECTURE.md` link test green.

**Affected tests:** all `ProviderModelInfo`/`ApplicationUnavailableError` importers (list above), `tests/runtime/test_provider_manager.py`, `tests/api/test_dependencies.py`, plus `tests/application/` if `model_metadata.py` is deleted.

**Risks:** mechanical but wide (30+ files). The import-boundary test is the regression gate — it fails on any stale import (bare-owner names, ancestor facades, cycles). Use `git mv` for the dataclass file moves so history follows.

---

### Sprint 2 — SSE parsing consolidation (H3)

**Goal**: one incremental SSE parser in `core/anthropic/`; zero `+=` string buffers in the four flagged accumulators.

**Actions:**

1. Read the three current loops and extract their exact shared semantics first: `core/openai_responses/anthropic_sse.py:21-34` (`buffer += chunk.decode(...)` / `buffer += str(chunk)`), `core/anthropic/sse_aggregation.py:90-95` (`buffer += chunk`), `application/usage_recorder.py:162-167` (`buffer += chunk`). Note the input-type difference (bytes vs str) per site.
2. Create `src/claudey/core/anthropic/sse_parser.py` with an incremental parser (e.g. an async iterator over `AsyncIterable[bytes | str]` that splits on `\n\n` event boundaries and yields parsed event strings/objects), implemented with list-of-chunks accumulation + `"".join` — no `+=`. It must handle: one event per chunk, many events per chunk, events split across chunk boundaries, empty chunks, trailing partial event without `\n\n` (semantics must match what each consumer does with a trailing partial today — read the three sites).
3. Replace the three loops with the parser. Each consumer's event interpretation (`parse_sse_text` etc.) is unchanged — only the buffering/splitting is shared.
4. Convert the string-accumulator buffers to chunk lists: `core/anthropic/streaming/ledger.py:117` (`task_arg_buffer`), `providers/openai_chat/tool_calls.py:278` (`pre_start_args`), `core/anthropic/thinking.py:44`, `core/anthropic/tools.py:98` — append to a list, `"".join` at use site.
5. Add one unit test for the parser covering the boundary cases in step 2.

**Acceptance:** identical yield order and event content (existing stream tests pin this); the new parser test green; grep `+= chunk|+= args|+= arguments|buffer \+=` in the five files → 0 hits; boundary test green; full gate green.

**Affected tests:** `tests/core/openai_responses/test_sse.py`, `tests/providers/test_streaming_errors.py`, `tests/core/anthropic/` streaming tests, `tests/application/` usage-recorder tests, new parser test.

**Risks:** decode semantics differ across the three sites today (`chunk.decode(...)` vs `str(chunk)`). The parser must accept both bytes and str and preserve each site's partial-final-chunk behavior. The existing suite (1,895-line `test_streaming_errors.py` plus `test_sse.py`) is the safety net — if any event test changes, stop and reconcile semantics before proceeding.

---

### Sprint 3 — Failure classification DRY (H4)

**Goal**: one retryability classifier; zero duplicated decision tables.

**Actions:**

1. Read `providers/failure_policy.py:160-189` (`is_retryable_provider_error`) and `providers/stream_recovery.py:178-200` (`is_retryable_stream_error`). The recovery variant omits the `httpx.WriteError`/`RetryableProviderProtocolError` variants and inlines an openai bad-request branch — the two tables are NOT identical.
2. **TDD guard first (RED/GREEN)**: write a table-driven unit test that captures current behavior — for each exception family in both functions' families (all `httpx.*` + `openai.*` + protocol error types appearing in either function), assert the retryable decision in **both contexts** (provider-retry context and stream-recovery context). It must pass against the current code before the merge.
3. Merge into a single classifier in `providers/failure_policy.py` — e.g. one exception-family table plus a per-context membership/flag parameter (`is_retryable_error(exc, *, recovery: bool)` or equivalent) that reproduces both current decision tables exactly, including the inlined openai bad-request branch. `stream_recovery.py` imports it; delete its local copy.
4. Run the new table test + the pinned provider tests.

**Acceptance:** table test green (both contexts identical to pre-merge behavior); pinned retry tests green (below); retry budgets/backoff constants untouched (`admission.py:27-31` — 5 attempts / 2.0s / 60s / 1.0 jitter; auth-latch TTL 5s; `stream_recovery.py:15-16` holdback 0.75s / 64KiB); user-facing wording constants untouched (`failure_policy.py:32-39`); boundary test + full gate green.

**Affected tests:** new table test, `tests/providers/test_stream_recovery.py`, `test_openai_compat_5xx_retry.py`, `test_nvidia_nim_degraded_retry.py`, `test_execution_failure_boundary.py`, `test_provider_transport_logging.py`, `tests/core/test_failure_protocol_mapping.py`.

**Risks:** silently changing a retry decision is the cardinal sin here — the pre-merge table test is mandatory and must be written before the merge, not after.

---

### Sprint 4 — Provider family boundaries (H2)

**Goal**: `google_openai` renamed to a neutral family package and facade-guarded.

**Actions:**

1. `git mv src/claudey/providers/google_openai src/claudey/providers/gemini_family` (package rename; `gemini` and `vertex` subclasses + `reasoning.py`, `thought_signatures.py` move with it). Update docstrings referencing the old name.
2. Update importers: `providers/gemini/client.py:6-8`, `providers/vertex/client.py:12-13`, internal `providers/gemini_family/reasoning.py:13`, and grep `tests/`, `smoke/`, `ARCHITECTURE.md` (`:670` links `providers/google_openai/` — update the link in the same commit; the link-validity contract test will fail otherwise).
3. Add `"claudey.providers.gemini_family"` to `FACADE_ONLY_BOUNDARIES` (`tests/contracts/test_import_boundaries.py:42-46`) — the second sanctioned edit to the contract file.
4. Grep `google_openai` repo-wide → 0 hits (complete migration).

**Acceptance:** boundary test green including the new facade rule; `google_openai` grep → 0; full gate green; no behavior change (pure rename + import updates).

**Affected tests:** `tests/providers/test_gemini.py`, `test_vertex.py`, any test importing `google_openai` (grep), `tests/contracts/test_import_boundaries.py`.

**Risks:** low — mechanical. The facade test now pins that no external consumer reaches behind `gemini_family`'s facade.

---

### Sprint 5 — Messaging dedup I: inbound glue + queued messenger (M1a, inventory Clusters A/B)

**Goal**: shared inbound helpers; one queued-messenger implementation.

**Actions:**

1. **M1a — inbound glue.** Read `messaging/platforms/telegram_inbound.py:44-62` and `discord_inbound.py:45-63` (identical raw-content log-preview block, incl. `text_preview += "..."` at `telegram_inbound.py:47` / `discord_inbound.py:48`, plus the parallel `VoiceNoteRequest` construction). Extract into `messaging/platforms/inbound_utils.py` (list accumulation, no `+=`); both modules consume it. Fold in inventory Cluster B (`_download_to` / `_reply_text` near-identical helpers) **only if** they are trivially identical after reading — otherwise leave them and note why.
2. **Cluster A — QueuedMessenger base.** Read `messaging/platforms/discord_io.py` (167 L) and `messaging/platforms/telegram_io.py` (287 L) — both implement the same 10-method queue-and-flush interface (`send_message`, `edit_message`, `delete_message`, `delete_messages`, `queue_send_message`, `queue_edit_message`, `queue_delete_messages`, `fire_and_forget`, `close`, `__init__`). Extract the shared queue/edit-batching/delete-coalescing/timer/retry bookkeeping into `messaging/platforms/base_messenger.py`; keep only platform primitives (send/edit/delete + telegram's caption/media behavior) in each `*_io.py`. **Verify the ~120-line delta is genuine Telegram behavior before extracting** — if it is, expose it via hooks; do not flatten it into the base.

**Acceptance:** existing messaging tests green; grep shows a single `text_preview` implementation; telegram/discord platform behavior unchanged (parse modes, edit semantics); boundary test + full gate green.

**Affected tests:** `tests/messaging/` platform and inbound tests (grep `telegram_io|discord_io|telegram_inbound|discord_inbound` in tests/).

**Risks:** MED — messenger timing/retry semantics are subtle. If a test fails on message ordering or coalescing, the base's hook surface is wrong; revert the extraction, keep the duplication, and record a justified deviation rather than bending behavior.

---

### Sprint 6 — Messaging dedup II: markdown token-walk (M1b)

**Goal**: one token-walk skeleton; per-platform emit hooks.

**Actions:**

1. **Golden tests first (TDD)**: read `messaging/rendering/telegram_markdown.py` (327 L) and `discord_markdown.py` (318 L); both walk markdown-it tokens with structurally identical `render_inline` loops (`telegram_markdown.py:80-119` and the discord counterpart), differing only in escape/emit rules. If the current byte output is not fully pinned by existing tests, add golden tests first covering: headings, bold/italic, inline/block code, links, lists, spoilers, nested emphasis, HTML entities. They capture current behavior (GREEN immediately) and become the refactor's guard.
2. Extract the shared token-walk skeleton into `messaging/rendering/markdown_walk.py` (extend the existing `rendering/profiles.py:37-53` profile split if it helps) with per-platform emit hooks; both converters use it.
3. Run golden + rendering tests; byte-for-byte identical output.

**Acceptance:** golden/rendering tests green byte-for-byte; grep shows one `render_inline` walk implementation; full gate green.

**Affected tests:** existing markdown/rendering tests in `tests/messaging/` (grep `markdown`), new golden tests.

**Risks:** MED — escaping rules differ subtly per platform; the golden tests are the guard. If any golden output changes, revert and record a justified deviation.

---

### Sprint 7 — Literals, naming, file sizes (M2, M4, M5, L1, L2; M3 resolved in-place)

**Goal**: no hardcoded provider literals outside config; `HANS_*` internal names gone; `openai_chat/provider.py` <800 lines.

**Actions:**

1. **M2a — Whisper-device constant.** Add `NIM_WHISPER_DEVICE = "nvidia_nim"` to `config/constants.py`. Replace code literals at `runtime/bootstrap.py:102`, `config/settings.py:420,499`, `config/admin/manifest.py:424-425`, `config/admin/persistence.py:138`. (Prose/docstring mentions like `api/usage_aggregate.py:7` may stay; grep `"nvidia_nim"` after and confirm only constants/prose remain.)
2. **M2b/L2 — Declarative local-provider map.** In `config/constants.py` (zero-import module, no cycle risk), add a map of local provider ids → (env-var name, default path): `lmstudio → ("LM_STUDIO_BASE_URL", "/models")`, `llamacpp → ("LLAMACPP_BASE_URL", "/models")`, `ollama → ("OLLAMA_BASE_URL", "/api/tags")`. `api/admin_routes.py:58-62` (`LOCAL_PROVIDER_PATHS`) and `:392-399` (`_local_provider_url`, incl. the `if provider_id == "lmstudio"` chain at :393-398) consume the map — no string literals, no if-chains. The env-name strings must match `config/settings.py:162,168,174` exactly (reference the settings fields or the map — never re-type the literals).
3. **M3 — RESOLVED: keep `NimSettings` in `config/nim.py`. Do NOT move it.** Justification (record in ARCHITECTURE.md as one paragraph): `config/settings.py:16,332` must type its `nim` field; moving the model to `providers/nvidia_nim/` would create a config→providers edge, forbidden by the Sprint-0 policy `config: {"core"}`; `core/` is protocol-neutral and must not own vendor settings. The CLAUDE.md principle is already satisfied — `providers/base.py:20-38` `ProviderConfig` is NIM-free. This is a documented location smell, not a bleed.
4. **M4 — `HANS_*` → `CLAUDEY_*` rename, one atomic commit.** In `config/paths.py:5-8`: `HANS_CONFIG_DIRNAME → CLAUDEY_CONFIG_DIRNAME`, `HANS_ENV_FILENAME → CLAUDEY_ENV_FILENAME`, `HANS_LOGS_DIRNAME → CLAUDEY_LOGS_DIRNAME`. Values unchanged (`".claudey"`, `".env"`, `"logs"`). Update importers: `cli/dispatcher.py:181-182`, `api/deepseek_billing.py:33,73`, `api/usage_aggregate.py:26,92`. Update `ARCHITECTURE.md:225,327` prose if it names the constants. **Do NOT rename env-var aliases** (`HANS_ENV_FILE`, `HANS_PI_*`, `HANS_CODEX_API_KEY`, `HANS_OPEN_BROWSER`, `HANS_SMOKE_*` — user-facing). Optional stretch: rename the internal module-level `HANS_VERSION` in `providers/openai_codex/provider.py:48-118` — the wire-visible *value* must not change, only the identifier.
5. **M5 — Split `providers/openai_chat/provider.py` (1,059 L).** Read the file; it contains at least three separable subsystems. Extract private helpers into new modules in `providers/openai_chat/` (suggested names: `retry_body.py` for `_next_create_retry_body` + retry-policy helpers, `streaming.py` for `stream_response` internals, `listing.py` for `list_model_infos`); `provider.py` imports them. **Public surface frozen**: `OpenAIChatProvider`'s method names/signatures are identical (15 vendor subclasses + `GoogleOpenAIProvider` depend on it). Target `provider.py` <800 lines. Do not touch `admission.py:758` / `native_tool_stream.py:766` / `conversion.py:780` — they are under the cap and out of scope.
6. **L1 — optional**: consolidate `_network_error_message` (`config/custom_provider_check.py:167-185`) and `provider_error_message` (`providers/failure_policy.py:222-252`) classification sources **without changing any user-visible string** (wording constants are frozen). If the merge risks wording drift, document instead of merging.

**Acceptance:** grep `"nvidia_nim"` → no code literals outside `config/constants.py`/settings defaults; grep `HANS_CONFIG_DIRNAME|HANS_ENV_FILENAME|HANS_LOGS_DIRNAME` → 0 hits; `provider.py` <800 lines; `_local_provider_url` free of if-chains; full gate green; `ARCHITECTURE.md` link test green.

**Affected tests:** `tests/config/`, `tests/api/test_admin.py`, `tests/runtime/`, `tests/providers/` (openai_chat), grep-driven.

**Risks:** the rename must stay identifier-only (values frozen); admin payloads unchanged (map is a pure refactor of `_local_provider_url` behavior — same env names, same defaults); provider split is internal-only.

---

### Sprint 8 — Repo hygiene, dead code, docs (assessment §4 + inventory §2-3)

**Goal**: repo is clean, `beam/` gone, admin-ui dead code removed, dist settled, docs tidied. **Order matters — dist sync and commits happen after all source cleanup.**

**Actions (in order):**

1. **Delete `src/claudey/api/admin_static/beam/`.** First grep `beam` in `src/` (expect 0 code references; the feature was reverted in `756bf5c8`) and note `docs/frontend-scaffold-plan.md:28,83,130` as the only references (updated in step 6). Then `git rm -r` the tracked files (`package.json`, `build.mjs`, `tsconfig.json`, `package-lock.json`, `src/`) and `rm -rf node_modules/` (54 MB untracked). Its promised output `beam.bundle.js` no longer exists; git history preserves the subtree.
2. **Delete root junk (decision: DELETE, do not relocate).** Delete: `admin-rendered.jpeg`, `beam-drag.png`, `beam-verified.png`, `budget-final-expanded.png`, `budget-redesign.png`, `collapsed-check.png`, `collapsed-icons-fixed.png`, `provider-key-dialog.png`, `sidebar-hover-fixed.png`, `sidebar-three-fixes.png`, `usage-chart-fixed.png`, `usage-full.png`, `.playwright-mcp/` (40+ files), `model-config-skeleton.yml` (a Playwright a11y dump, not a config).
   **Justification**: all are untracked (not in git history), so deletion loses nothing historical; the UI states they document are reproducible by re-rendering the committed admin-ui source; grep confirms zero references. For future harness artifacts, `assets/screenshots/` is gitignored (step 3) as a scratch home — files may be dropped there but never tracked.
3. **`.gitignore` additions**: `.playwright-mcp/`, `assets/screenshots/`. (`node_modules/` already covers `beam/node_modules/`.)
4. **Keep `admin_ui_dist` tracked (justify in the commit message / report).** Rationale: `admin_routes.py:53-57` serves it statically as the packaged serving dir; the app must work offline/installed with no build step; the policy is already encoded in `.gitignore:26-27` and `docs/frontend-scaffold-plan.md`. **Settle current drift**: check `git status` for `admin_ui_dist` — if it still shows deleted stale hashed assets (`index-DZY5IEv8.css`, `index-LQllRiI5.js`) plus new untracked assets and a modified `index.html`, or if the tree is clean, either way the final committed state after this sprint must have exactly one current build: old hashed assets deleted and the fresh build added **in the same commit** as the source changes (complete-migration rule — no stale hashed assets in history). Verify `admin_ui_dist/index.html` `?v=` equals the pyproject version (5.26.0) — do not change it.
5. **admin-ui dead-code cleanup** (inventory §2; re-verify each with grep on the current tree first — the Phase-3 redesign may have adopted items; if so keep and note):
   - Delete `src/claudey/api/admin_static/admin-ui/src/components/ui/shadcn/tabs.tsx` and `separator.tsx` (0 importers each).
   - Remove 9 unused functions from `api/client.ts` (`fetchDashboard:60`, `fetchUsage:64`, `fetchCombos:76`, `fetchCustomProviders:80`, `fetchProviderAuth:84`, `refreshLocalStatus:112`, `startAuthLogin:116`, `cancelAuthLogin:123`, `disconnectProvider:127`). **The backing admin HTTP endpoints stay** (public admin API — see inventory §4).
   - Remove 10 unused types from `api/types.ts` (`TokenTotals:8`, `UsageWindows:14`, `UsageProviderRow:18`, `ConfigFieldType:68`, `ConfigOption:78`, `ProviderKind:107`, `ConfigPaths:121`, `AuthStatus:138`, `LocalStatusEntry:155`, `LocalStatusResponse:163`).
   - Remove `MASKED_SECRET` (`lib/config.ts:9`) and `REASONING_OPTION_ORDER` (`lib/config.ts:11`).
   - Remove 5 npm deps from `package.json`: `@tremor/react`, `motion`, `@radix-ui/react-scroll-area` (inventory §2.5) plus `@radix-ui/react-tabs`, `@radix-ui/react-separator` (only used by the deleted components). Update the stale tremor comment at `usage-view.tsx:37` and the package description (`package.json:6`).
   - Remove 7 dead tokens from `styles/tokens.css`: `--duration-10`, `--duration-4`, `--line`, `--panel`, `--text-primary`, `--text-secondary`, `--text-strong`. Keep `--sidebar-w`, `--sidebar-budget-opacity`, `--radix-*` (set at runtime / injected).
   - Optional (skip if nontrivial): chart-stack overlap in `usage-trend-chart.tsx` (inventory §2.7) — cosmetic; the Phase-3 redesign may rework it.
   - `npm run typecheck` must pass. No visual redesign changes.
6. **Docs tidy.** Proposed structure:
   ```
   docs/
   ├── ARCHITECTURE.md           (contract-tested — never moved; links must stay valid)
   ├── design-system.md          (living design doc — keep at root)
   ├── frontend-scaffold-plan.md (admin_ui_dist policy contract — keep; update beam refs :28,:83,:130)
   ├── firecrawl-animation-reference.md → move to docs/reference/firecrawl-animation.md
   ├── reference/                (new: evergreen references)
   └── plans/                    (one-off plans; refactor/ holds this plan + rubric + feedback-*)
   ```
   Before the move, grep `ARCHITECTURE.md` and other docs for links to `firecrawl-animation-reference.md` and update them in the same commit; `tests/contracts/test_architecture_contracts.py` (ARCHITECTURE.md presence/link validity at :10-15) must stay green. Add a one-line status header to `docs/plans/refactor/REFACTOR_PLAN.md` and `RUBRIC.md` marking them as the live refactor contract (they already have one).
7. **L4 closure (verify, expect no action)**: `providers/mistral/reasoning.py` is imported by the mistral wrapper (live — keep); `messaging/safe_diagnostics.py` has a real importer per the import-graph scan (live — keep). Record the verification in the report.
8. **Final**: `./scripts/ci.sh` green; `npm run typecheck` green; `git status --porcelain` shows no untracked junk (only expected ignores).

**Acceptance:** beam/ absent from `git ls-files`; zero root screenshots/.playwright-mcp/model-config-skeleton.yml; `.gitignore` updated; `admin_ui_dist` contains exactly one current build committed atomically with source; admin-ui typecheck green; inventory §2 items removed (or noted deviations); docs structure per step 6; `./scripts/ci.sh` + full gate green.

**Affected tests:** `tests/contracts/test_architecture_contracts.py` (docs links), `tests/api/test_admin.py` (dist serving), full suite (regression).

**Risks:** the admin-ui WIP is in flight — never delete an item the redesign adopted (re-verify by grep; inventory is a snapshot). Dist drift recurs when builds land without commits — the atomic commit in step 4 prevents this class.

---

## 8. Definition of Done

### Per sprint
1. All sprint actions executed; acceptance criteria (per-sprint, §7) met.
2. `uv run pytest tests/contracts/test_import_boundaries.py -n0` green (21 passed, with the two sanctioned contract edits).
3. `./scripts/ci.sh` fully green (all 7 checks).
4. Admin-ui sprints additionally: `npm run typecheck` green; no visual changes.
5. Coverage ≥ 80% and ≥ baseline (baseline recorded in Sprint 0).
6. Feedback loop closed: all items in the latest `feedback-<sprint>-NNN.md` fixed or explicitly rebutted with evidence.

### Whole refactor
1. All 9 sprints green as above.
2. Zero `claudey.providers` imports in `config/` and `application/`; zero `claudey.application` imports in `providers/`; no new cross-layer edges.
3. `google_openai` gone; `gemini_family` facade-guarded.
4. No file >800 lines under `src/claudey/`; no function >50 lines (new or touched); zero suppressions; no `+=` string accumulation in the flagged loops.
5. No `HANS_CONFIG_DIRNAME|HANS_ENV_FILENAME|HANS_LOGS_DIRNAME` identifiers; no hardcoded `"nvidia_nim"` code literals.
6. `beam/` deleted; root junk gone; `.gitignore` covers `.playwright-mcp/` and `assets/screenshots/`; `admin_ui_dist` single-build committed.
7. Zero user-visible change (§10 invariants all verified unchanged).
8. Working tree clean of untracked junk.

---

## 9. Sprint-to-Rubric Mapping

| Sprint | Primary rubric criteria |
|---|---|
| 0 | C1 (CI gate), C3 (principle adherence) |
| 1 | C3, C5 (code health) |
| 2 | C3, C5 |
| 3 | C3, C5, C2 (behavior preservation — retry matrix) |
| 4 | C3 |
| 5, 6 | C3, C2 (byte-for-byte rendering/messaging) |
| 7 | C5, C2 (rename/wiring) |
| 8 | C4 (dead-code & hygiene) + C2 (admin payloads) |

---

## 10. Frozen Invariants (never change in this refactor)

| Surface | Guarded by |
|---|---|
| Anthropic wire: `/v1/messages` request/response + SSE event stream, event ordering, stop-reason mapping | `tests/core/`, `tests/api/test_execution_failure_contract.py`, `test_ordinary_error_phases.py` |
| OpenAI Responses wire: `/v1/responses` events, `openai_error_payload` | `tests/core/openai_responses/`, `test_providers_do_not_own_wire_error_type_literals` |
| Env vars: every alias in `config/settings.py` + `.env.example` (wheel force-include) | `test_root_env_example_is_the_single_template_source`, `test_architecture_contracts.py:30-47` |
| `.claudey` config dir paths and values | `config/paths.py` values — only identifiers rename (Sprint 7) |
| Admin API payloads (`load_config_response`, `provider_config_status`, `dashboard_payload`, `usage_payload`, `billing_payload`), `Cache-Control: no-store`, `/admin/ui` serving + `?v=` | `tests/api/test_admin.py`, `test_app_lifespan_and_errors.py` |
| Provider retry budgets/backoff (admission 5/2.0s/60s/1.0, auth-latch 5s, holdback 0.75s/64KiB, `max_retries=0` SDK policy, NIM retry-body degradation) | `tests/providers/test_stream_recovery.py`, `test_nvidia_nim_degraded_retry.py`, `test_openai_compat_5xx_retry.py` |
| User-facing failure wording (`failure_policy.py:32-39`, `_stable_upstream`, `_AUTHENTICATION_MESSAGE` etc.) | `tests/providers/`, `tests/api/` wording assertions |
| CLI surface: `claudey`/`hans-*` entry points, exit codes (127/126/1), launcher env contracts, managed-session lifecycle, `doctor` output | `tests/cli/`, `tests/runtime/` |
| Messaging: telegram/discord parse modes + escaping, message-log persistence format, tree serialization, usage-log JSONL schema (`TOKEN_FIELDS`, `USAGE_LOG_FILENAME`) | `tests/messaging/`, `tests/application/`, `tests/api/test_usage*` |
| `admin_ui_dist` served bytes (only ever replaced by a fresh full build, atomically) | `tests/api/test_admin.py` |
| Provider registration: `config/provider_catalog.py` PROVIDER_CATALOG + exactly-one-construction-owner assertion (`providers/runtime/factory.py:172-182`) | `tests/contracts/test_provider_catalog_order.py` |

---

## Addendum (2026-08-13, orchestrator)

- `ovhcloud` and `llm7` were removed from the provider catalog (user directive). Affected: catalog entries, openai_chat profiles, README table/count (now 37), .env.example comments, logo set, and `llm7` test-string data (re-targeted to `routeway`).
- The pre-existing `test_catalog_publication_tracks_warm_refresh_and_direct_cache` failure is RESOLVED by the removal (the test needed no changes). `./scripts/ci.sh` is fully green (3100 passed). The sanctioned exception in `feedback-0-001.md` no longer applies — evaluators must expect a fully green gate from Sprint 1 onward.
- Coverage baseline remains 90% (Sprint 0 report).
