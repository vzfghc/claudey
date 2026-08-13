# Dead Code Inventory — Phase 1 Analysis

Date: 2026-08-13
Branch: feat/phase-a-free-providers
Scope: Python (`src/claudey`), admin-ui (`src/claudey/api/admin_static/admin-ui`), retired assets
Mode: ANALYSIS ONLY — no files modified. Vulture was skipped (not resolvable via `uv run` without adding a dependency; per constraint, no deps were added).

---

## 1. Python (`src/claudey`)

### 1.1 Tooling results — CLEAN

| Check | Result |
|---|---|
| `uv run ruff check --select F401,F841` | All checks passed — zero unused imports/variables |
| `# type: ignore` / `# ty: ignore` | 0 occurrences |
| `from __future__ import annotations` | 0 occurrences |
| vulture | SKIPPED (not resolvable without adding a dependency) |
| Unreachable modules (import-graph scan) | none — every module has a real importer or pyproject entrypoint |

The Python side is in notably good shape: unused-import bans are enforced by CI, and error classification, retry, and redaction are already centralized (`providers/failure_policy.py`, `providers/admission.py`, `core/anthropic/errors.py`, `core/trace.py`) rather than copy-pasted per provider.

### 1.2 Retired directory — HIGH confidence removal

| Path | Why dead | Suggested action |
|---|---|---|
| `src/claudey/api/admin_static/beam/` (entire project: `build.mjs`, `package.json`, `package-lock.json`, `tsconfig.json`, `src/`, `node_modules/` 54 MB on disk) | Retired standalone React micro-frontend for the provider-beam diagram. Zero references in Python or elsewhere. Its declared output `admin_static/beam.bundle.js` no longer exists. Feature was reverted from the React app in commit `756bf5c8` ("revert(admin-ui): remove provider beam from React app") but the standalone project was never deleted. | `git rm -r src/claudey/api/admin_static/beam/` + delete `node_modules/` |

### 1.3 Duplication clusters

#### Cluster A — Queued-messenger pattern: `discord_io.py` + `telegram_io.py` (MED confidence)
- `src/claudey/messaging/platforms/discord_io.py` (167 lines) and `src/claudey/messaging/platforms/telegram_io.py` (287 lines) both implement the same queue-and-flush messenger interface with 10 identical method names:
  `send_message`, `edit_message`, `delete_message`, `delete_messages`, `queue_send_message`, `queue_edit_message`, `queue_delete_messages`, `fire_and_forget`, `close`, `__init__`.
- The queue/edit/delete bookkeeping (timers, retries, message-id tracking) is near-identical; only the platform send/edit/delete primitives differ.
- Suggested action: extract a shared `QueuedMessenger` base class (queueing, edit batching, delete coalescing, fire-and-forget) into `messaging/platforms/` (e.g. `base_messenger.py`); keep platform-specific primitives in each `*_io.py`.
- Caveat: telegram_io is ~120 lines larger — verify the delta is genuine Telegram behavior (caption editing, media) before extraction, or the base will need hooks.

#### Cluster B — Inbound audio/reply helpers: `discord_inbound.py` + `telegram_inbound.py` (LOW confidence)
- `src/claudey/messaging/platforms/discord_inbound.py` and `src/claudey/messaging/platforms/telegram_inbound.py` both define `_download_to` (audio download) and `_reply_text` (quick reply) with near-identical bodies.
- Suggested action: consolidate into one shared inbound helper module (e.g. `inbound_utils.py`). LOW — only two small helpers; extraction may not repay the churn.

### 1.4 Already-consolidated (no action, monitor for drift)
- Provider retry: all thin providers delegate to `ProviderAdmissionController.run_with_retry` (`src/claudey/providers/admission.py`).
- Error classification: single owner `src/claudey/providers/failure_policy.py`; no per-provider copies.
- OpenAI-compatible providers: `cloudflare`, `github_models`, `mistral`, `vertex`, `kilo`, `lmstudio`, `open_router`, `deepseek`, `nvidia_nim` are all thin wrappers over `OpenAIChatProvider` (`src/claudey/providers/openai_chat/`). No copy-paste clients found (cloudflare vs github_models differ legitimately: URL construction, model listing, capabilities).
- Reasoning layers: `config/reasoning.py` (user preference) -> `application/reasoning.py` (resolution) -> `core/reasoning.py` (domain policy) — distinct roles, not duplication.
- Stream recovery split: `providers/stream_recovery.py` (holdback/failure decisions) vs `core/anthropic/streaming/recovery.py` (wire-body repair) — distinct, no overlap.

### 1.5 Process-level finding (not dead code, but related)
- `src/claudey/api/admin_static/admin_ui_dist/` is committed build output (`git ls-files` tracks `index.html`, `assets/index-CLI79gPV.js`, `assets/index-CPu4SDQ7.css`). Stale hashed assets accumulate across commits (working tree already deletes `index-DZY5IEv8.css`, `index-LQllRiI5.js`). Suggest adding `admin_ui_dist/` to `.gitignore` (or pruning old hashed assets on each build) — deployment must keep the index.html `?v=` sync with `pyproject.toml` version (per memory: admin index.html ?v= must sync with pyproject bump).

---

## 2. admin-ui (`src/claudey/api/admin_static/admin-ui`)

Typecheck: `npm run typecheck` (`tsc --noEmit -p tsconfig.json`) — PASSES clean. No `@ts-ignore` / `@ts-expect-error` in source.

### 2.1 Unused shadcn components (HIGH confidence removal)
| File | Why unused |
|---|---|
| `src/claudey/api/admin_static/admin-ui/src/components/ui/shadcn/tabs.tsx` | 0 importers anywhere (its only radix dependency `@radix-ui/react-tabs` is likewise used by nothing else) |
| `src/claudey/api/admin_static/admin-ui/src/components/ui/shadcn/separator.tsx` | 0 importers; `@radix-ui/react-separator` used only by this file |

Note: `skeleton.tsx`, `switch.tsx`, `checkbox.tsx`, `table.tsx`, `textarea.tsx`, `select.tsx`, `label.tsx`, `input.tsx`, `dialog.tsx`, `card.tsx`, `badge.tsx`, `tooltip.tsx`, `button.tsx`, `sonner.tsx` all have >= 1 real importer — keep.

### 2.2 Unused exports in `src/claudey/api/admin_static/admin-ui/src/api/client.ts` (HIGH)
9 functions with zero callers outside their own file (the backing admin endpoints still exist — see False-Positive candidates):
- `fetchDashboard` (line 60), `fetchUsage` (line 64), `fetchCombos` (line 76), `fetchCustomProviders` (line 80), `fetchProviderAuth` (line 84), `refreshLocalStatus` (line 112), `startAuthLogin` (line 116), `cancelAuthLogin` (line 123), `disconnectProvider` (line 127)

### 2.3 Unused types in `src/claudey/api/admin_static/admin-ui/src/api/types.ts` (HIGH)
10 types with zero references outside `api/types.ts`:
- `TokenTotals` (line 8), `UsageWindows` (line 14), `UsageProviderRow` (line 18), `ConfigFieldType` (line 68), `ConfigOption` (line 78), `ProviderKind` (line 107), `ConfigPaths` (line 121), `AuthStatus` (line 138), `LocalStatusEntry` (line 155), `LocalStatusResponse` (line 163)

### 2.4 Unused exports in `src/claudey/api/admin_static/admin-ui/src/lib/config.ts` (HIGH)
- `MASKED_SECRET` (line 9) — 0 references outside its file
- `REASONING_OPTION_ORDER` (line 11) — 0 references outside its file

### 2.5 Unused npm dependencies (HIGH — remove from package.json)
| Package | Evidence |
|---|---|
| `@tremor/react` | Only mention in all of `src/` is a stale comment in `usage-view.tsx:37`; no real import. Tremor chart was replaced by the shadcn chart in GAN iteration 003 (`d8300da1`) |
| `motion` | No `from "motion"` / `motion/react` import anywhere (grep hits were the `use-reduced-motion` hook name) |
| `@radix-ui/react-scroll-area` | 0 references in `src/` (no ScrollArea usage) |

Used deps verified: `sonner` (toast in 4 dialogs + Toaster in app.tsx), `recharts` (usage-trend-chart), `lucide-react` (16 files), `clsx`/`tailwind-merge`/`class-variance-authority` (shadcn primitives), `@radix-ui/react-dialog/select/switch/checkbox/label/tooltip/tabs` (each used by exactly one shadcn component).

### 2.6 Dead CSS tokens in `src/claudey/api/admin_static/admin-ui/src/styles/tokens.css` (MED)
7 tokens defined but never referenced via `var(--…)` in any TS/TSX or globals.css:
- `--duration-10`, `--duration-4`, `--line`, `--panel`, `--text-primary`, `--text-secondary`, `--text-strong`
- Keep: `--sidebar-w` (set programmatically in `sidebar.tsx:147,177`), `--sidebar-budget-opacity` (set programmatically in sidebar-budget), `--radix-*` vars (radix injects them).

### 2.7 Chart-stack overlap (LOW confidence consolidation)
- `usage-trend-chart.tsx` imports recharts primitives directly (`Area, AreaChart, CartesianGrid, XAxis, YAxis`) AND the shadcn `chart.tsx` wrapper (`ChartContainer, ChartTooltip, ChartTooltipContent`), while `provider-bar-list.tsx` uses the shadcn `bar-list.tsx`.
- Three rendering stacks coexist in the usage view (recharts direct + shadcn chart + shadcn bar-list). Suggested: standardize on the shadcn wrappers; remove direct recharts imports. LOW — cosmetic, works today.

### 2.8 Minor (LOW)
- `button.tsx: ButtonProps` type export is never imported elsewhere (it is used internally as the component props type — idiomatic; leave unless a lint rule flags it).

---

## 3. Repo-root dev artifacts (untracked clutter, HIGH cleanup)
- 9 untracked screenshot PNGs at repo root: `beam-drag.png`, `beam-verified.png`, `budget-final-expanded.png`, `budget-redesign.png`, `collapsed-check.png`, `collapsed-icons-fixed.png`, `provider-key-dialog.png`, `sidebar-hover-fixed.png`, `sidebar-three-fixes.png`, `usage-chart-fixed.png`, `usage-full.png`, `admin-rendered.jpeg`
- `model-config-skeleton.yml`, `.playwright-mcp/`
- Not tracked in git (safe to delete or move to a scratch dir / `assets/`). Not source code.

---

## 4. False-positive candidates (DO NOT remove — live interfaces)

| Item | Why it looks dead but is live |
|---|---|
| `src/claudey/cli/desktop*.py` (entrypoint, tray, assets) | No in-tree importers beyond dispatcher, but wired to `hans-desktop` via `[project.gui-scripts]` in `pyproject.toml` |
| `src/claudey/cli/dispatcher.py`, `entrypoints.py`, `launchers/*` | Imported via pyproject `[project.scripts]` (`claudey`, `hans-server`, `hans-claude`, `hans-codex`, `hans-pi`) |
| `src/claudey/config/env_migrations.py`, `env_template.py`, `secret_crypto.py` | Used by `cli/commands.py` / runtime bootstrap, not by string-match on full path |
| `src/claudey/providers/deepseek/compat.py` | Named "compat" (looks like a shim) but is the live DeepSeek request policy, imported by `deepseek/client.py:16` |
| `src/claudey/runtime/asgi.py`, `core/openai_responses/**`, `messaging/**` | Imported via relative imports (`from .asgi import …`); import-graph scan undercounts relative imports |
| Admin endpoints in `src/claudey/api/admin_routes.py` (dashboard, usage, auth login/cancel, local-status, custom providers, combos) | The admin-ui client wrappers for these are dead (2.2), but the HTTP endpoints are public admin API — other consumers (tests, desktop tray, curl) may use them; verify consumers before touching endpoints |
| `--sidebar-w`, `--sidebar-budget-opacity`, `--radix-*` CSS vars | Set at runtime via `document.documentElement.style.setProperty` / injected by radix |
| `admin_ui_dist/` committed assets | Served offline at `/admin/ui` — current files must stay; only stale hashed predecessors are dead |

---

## 5. Summary counts

| Category | Count | Confidence |
|---|---|---|
| Dead Python imports/variables (F401/F841) | 0 | — |
| `# type: ignore` / `# ty: ignore` | 0 | — |
| `from __future__ import annotations` | 0 | — |
| Unreachable Python modules | 0 | — |
| Retired projects (beam/) | 1 | HIGH |
| Python duplication clusters | 2 (A: discord_io/telegram_io MED, B: inbound helpers LOW) | MED/LOW |
| Unused admin-ui components | 2 (tabs, separator) | HIGH |
| Unused admin-ui exports (client.ts) | 9 functions | HIGH |
| Unused admin-ui types (types.ts) | 10 | HIGH |
| Unused admin-ui lib exports (config.ts) | 2 | HIGH |
| Unused npm dependencies | 3 (tremor, motion, radix-scroll-area) | HIGH |
| Dead CSS tokens | 7 | MED |
| Dead/overlapping chart stacks | 1 (chart-stack overlap) | LOW |
| False-positive candidates (kept) | 11 groups | — |

TOTAL actionable dead code: 33 items (1 retired dir, 2 components, 9 client fns, 10 types, 2 consts, 3 deps, 7 tokens) + 2 duplication clusters. Python core is clean; the dead weight is concentrated in the admin-ui client surface and the retired beam project.
