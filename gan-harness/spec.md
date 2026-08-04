# Product Specification: Claudey

> Generated from brief: "Rebrand this fork from 'free-claude-code' to 'claudey', 'fcc' to 'hans' (e.g. 'hans-server', 'hans-claude', or if possible just 'claudey'). Make the UI more intuitive, light themed, with AI/provider logos from LobeHub. Create PRD and planning."

## Vision

**Claudey** is the user's personal fork of free-claude-code: a local proxy that launches Claude Code, Codex, and Pi through any of 30+ OpenAI-compatible providers. The rebrand makes it feel like *the user's own product*, not a repackaged clone: a warm, light, tactile admin console where the brand is "Claudey" (a friendly nod to Claude), the commands are short (`hans-server`, `hans-claude`, or the single `claudey` command), and every provider is instantly recognizable by its real logo from LobeHub's icon set. First-time users can go from zero to a running agent in under a minute without reading docs.

## Naming Map (authoritative — the Generator must follow this exactly)

| Old | New | Where |
|---|---|---|
| `free-claude-code` (project/PyPI name) | `claudey` | `pyproject.toml`, docs, version string |
| `free_claude_code` (Python module) | `claudey` | `src/` dir, all imports, `known-first-party`, wheel `force-include` path, pytest `pythonpath` |
| `fcc-server` | `hans-server` | `[project.scripts]` |
| `fcc-claude` | `hans-claude` | `[project.scripts]` |
| `fcc-codex` | `hans-codex` | `[project.scripts]` |
| `fcc-pi` | `hans-pi` | `[project.scripts]` |
| `fcc-desktop` | `hans-desktop` | `[project.gui-scripts]` |
| (new) unified binary | `claudey` (`claudey server`, `claudey claude`, `claudey codex`, `claudey pi`, `claudey desktop`, `claudey --version`) | `[project.scripts]` |
| `FCC_ENV_FILE` | `HANS_ENV_FILE` (legacy `FCC_*` still honored) | `admin.js`, `config/env_migrations.py` |
| `FCC_SMOKE_TARGETS` | `HANS_SMOKE_TARGETS` | `pyproject.toml` markers, smoke lib |
| `FCC_MACOS_BUNDLE_ID` | `HANS_MACOS_BUNDLE_ID` | installers |
| `FCC_COMMANDS` / `FCC_MACOS_OWNER_FILE` | `HANS_COMMANDS` / `.claudey-owner` | installers |
| `io.github.alishahryar1.free-claude-code` | `io.github.<fork-owner>.claudey` | installers, desktop |
| `assets/free-claude-code-wordmark-{light,dark}.svg` | `assets/claudey-wordmark-{light,dark}.svg` | README |
| "Free Claude Code" / "FC" (UI, tray) | "Claudey" + starburst mark | `admin_static/*`, `cli/desktop*` |
| version `4.16.6` | `5.0.0` (MAJOR — breaking rename; bump + `uv lock` in the same commit as the rename, per CLAUDE.md) | `pyproject.toml` |

**Decision on "hans" vs "claudey":** Both. `hans-*` binaries are the primary installed commands (user's explicit ask). `claudey` is a thin dispatcher over the same entrypoint functions so "if possible, just claudey" is also true. Legacy `fcc-*` names become optional warning shims (Sprint 4).

## Design Direction

- **Color palette** (light theme, warm paper + Anthropic coral):
  - `--bg: #FAF9F7` (warm paper), `--panel: #FFFFFF`, `--panel-strong: #F5F3F0`, `--card: #FFFFFF`, `--card-hover: #F5F3F0`
  - `--input: #FFFFFF`, `--input-focus: #FFFDF9`
  - `--text: #1C1917` (stone-900 ink), `--text-strong: #0C0A09`, `--muted: #78716C`, `--line: #E7E5E4`, `--line-strong: #D6D3D1`
  - `--accent: #D97757` (Anthropic "book cloth" coral), `--accent-dark: #C05E3D`, `--accent-muted: rgba(217,119,87,0.10)`, `--accent-border: rgba(217,119,87,0.35)`
  - Status: `--ok: #059669`, `--warn: #B45309`, `--error: #B91C1C`, `--info: #2563EB`, each with matching `-bg`/`-border` tints
  - Shadows: `--shadow-sm: 0 1px 2px rgba(28,25,23,0.06)`, `--shadow: 0 8px 24px rgba(28,25,23,0.10)`, `--glow-accent: 0 0 0 3px rgba(217,119,87,0.18)` (focus ring)
  - **Implementation trick:** keep every existing CSS variable name (`--bg`, `--panel`, `--accent`, `--ok-bg`…) and only change their values plus `color-scheme: dark → light`. This flips the whole theme with near-zero JS/HTML churn and preserves all status/validation classes.
- **Typography**: existing system-ui stack for UI; add `--font-mono: ui-monospace, "SF Mono", "JetBrains Mono", Menlo, monospace` for env-file paths, commands, and keys. Brand wordmark: lowercase `claudey`, weight 700, tracking `-0.02em`.
- **Layout philosophy**: keep the proven 260px sidebar + content + sticky action-bar shell. Refine, don't rebuild: tighter spacing, hairline borders instead of dark-panel contrast, one clear primary action per view.
- **Visual identity**: brand mark = LobeHub **Anthropic** starburst (coral `#D97757`) inside a white rounded square with hairline border, next to the `claudey` wordmark. Every provider card shows its real LobeHub logo. No gradients except a single subtle warm-to-white sidebar wash (`linear-gradient(180deg, #FFFDFB, #FAF9F7)`) — no purple/blue gradient abuse anywhere.
- **Inspiration**: Linear's light mode (restraint, hairline borders, keyboard-first), Claude.ai settings (coral accent, friendly copy), LobeChat provider settings page (logo grids), Vercel dashboard (status pills, compact density).

### Anti-AI-slop directives (hard requirements)
1. **No purple/indigo/blue gradient buttons or headers.** The accent is coral, period.
2. **No glassmorphism, no backdrop-blur, no "modern SaaS" 24px-radius cards.** Radii stay 6/10/14px.
3. **No emoji as icons.** Provider identity comes from LobeHub SVGs; UI icons are inline SVG strokes (reuse existing patterns).
4. **No stock illustrations or photos in the onboarding/empty states.** Use clean inline SVG diagrams and real product commands.
5. **No dark-theme-only design.** The app must be fully legible in light; dark mode is a later optional extra, not a crutch.
6. **No lorem-ipsum copy.** Every empty state and tooltip must contain real, actionable guidance with real commands (`hans-server`, `hans-claude`).

## Features (prioritized)

### Must-Have (Sprint 1–2)

1. **Package + module rename** (`free-claude-code` → `claudey`, `free_claude_code` → `claudey`)
   - AC: `src/free_claude_code/` becomes `src/claudey/` via `git mv`; every import updated; `pyproject.toml` `[tool.hatch]` force-include path → `claudey/config/env.example`; ruff `known-first-party = ["claudey", "smoke"]`; pytest `pythonpath = ["src"]` unchanged; ty config updated; version → `5.0.0`; `uv lock` re-run.
   - AC: `uv run python -c "import claudey"` works; `uv run python -c "import free_claude_code"` fails.

2. **Binary rename** (`fcc-*` → `hans-*`)
   - AC: `hans-server --version` prints `claudey 5.0.0`; `hans-claude`, `hans-codex`, `hans-pi` launch their clients; `hans-desktop` launches the tray app.
   - AC: internal references updated — error hint in `launchers/claude.py` ("Start it in another terminal with: hans-server"), docstrings, installer prompts ("Install or verify Claude Code for hans-claude?"), `smoke/lib/*`, `tests/cli/*`, `tests/scripts/*`, `.github/workflows/validate-bug-report-version.yml`.

3. **Unified `claudey` command**
   - AC: `claudey` with no args prints a short usage tree (server/claude/codex/pi/desktop); `claudey server [--version]`, `claudey claude [args…]` etc. forward to the same entrypoint functions with argv passthrough; `claudey --version` prints `claudey 5.0.0`.
   - AC: implemented as a single new module `claudey/cli/dispatcher.py` (~100 lines) — no duplication of launcher logic.

4. **Env var migration** (`FCC_*` → `HANS_*`)
   - AC: canonical names `HANS_ENV_FILE`, `HANS_SMOKE_TARGETS`, `HANS_MACOS_BUNDLE_ID`, `HANS_COMMANDS`; legacy `FCC_*` names still read (documented in `config/env_migrations.py` mechanism; admin.js reads `HANS_ENV_FILE` and falls back to `FCC_ENV_FILE`).
   - AC: a test asserts both spellings resolve to the same value.

5. **Light theme redesign** (design tokens)
   - AC: `admin.css` `:root` updated per Design Direction (values swapped, `color-scheme: light`); all views, form controls, pills, toasts, and the action bar are legible and harmonious in light; focus rings use `--glow-accent`; scrollbar recolored.
   - AC: no contrast < 4.5:1 for body text (spot-check muted `#78716C` on white — use `#706B66` if borderline).

6. **LobeHub provider + brand logos**
   - AC: `admin_static/logos/` contains one SVG per `PROVIDER_CATALOG` key (derive ids from `PROVIDER_CATALOG.keys()`: nvidia_nim, openai, azure_openai, openrouter, gemini, vertex, deepseek, mistral, mistral_codestral, opencode_zen, opencode_go, vercel_ai_gateway, bedrock, huggingface, cohere, github_models, wafer, kimi, kimi_code, kilo, minimax, cerebras, groq, sambanova, fireworks, cloudflare, zai, ollama_cloud, lm_studio, llamacpp, ollama) + `anthropic.svg` for the brand mark.
   - AC: logos sourced from LobeHub (check first for a locally installed `@lobehub/icons` copy; else fetch from `lobehub.com/icons` / `github.com/lobehub/lobe-icons` raw SVGs); a `scripts/fetch_provider_logos.py` refresh script documents the source URL map; any provider without a clean source gets a hand-drawn monochrome letter-chip fallback (still served as SVG) — every card renders *something* recognizable.
   - AC: provider cards render logo + name + status; connected-account cards render the account's provider logo.

7. **Brand surfaces** (UI + desktop + docs)
   - AC: `index.html` title → `Claudey Admin`, brand mark → Anthropic starburst + `claudey` wordmark, `<title>` and favicon updated; `admin.js` copy strings updated (e.g., "Disconnect this ChatGPT account from Claudey?").
   - AC: desktop tray/app name → **Claudey**; `desktop_assets.py` icon → starburst mark; `desktop.py` menu strings and window titles updated; macOS bundle id per Naming Map.
   - AC: README fully rebranded (wordmark SVGs regenerated as `claudey-wordmark-*.svg`, badges point to the fork, all `fcc-*`/FCC references replaced); **AGENTS.md and CLAUDE.md updated identically** (repo rule); ARCHITECTURE.md, CONTRIBUTING.md refreshed.
   - AC: `scripts/install.sh|ps1` and `scripts/uninstall.sh|ps1` renamed commands/prompts/owner-file/bundle-id per Naming Map.

### Should-Have (Sprint 3–4)

8. **Onboarding empty state** — when no provider keys are configured, the Providers view shows a 3-step guide card: (1) Pick a provider from the grid, (2) Paste your API key and Apply, (3) Run `hans-claude` (with a copy-to-clipboard button). Dismissible once any key is configured; returns when all keys are removed. AC: copy button writes to clipboard and shows "Copied" state; steps use inline SVG illustrations, not emoji.

9. **Provider card upgrade** — each card: LobeHub logo, display name, meta line (base URL or model hint), status pill (Configured / Not configured / Validating… / Error), and a "Configure" action that scrolls to and focuses the provider's form. Cards use `--card` with hairline border and `--card-hover` lift (`transform: translateY(-1px)` + shadow-sm).

10. **Server status pill** — topbar gains a persistent pill: green "Running on port 8082" (or "Stopped") with the version. AC: fetched once via existing admin endpoints on load; static fallback "Claudey Admin" if the endpoint is unavailable; pill shows a subtle pulse animation while health-checking (pure CSS, respects `prefers-reduced-motion`).

11. **Model Config clarity** — role-grouped cards (Fable / Opus / Sonnet / Haiku / Fallback) with plain-language descriptions ("Used by Claude Code's `/model` picker default"), provider-aware placeholders, and a "Reset to provider default" affordance per field. AC: group headers are sticky within the view; empty fields show clear "uses provider default" hint text.

12. **Keyboard shortcuts + toasts** — `Cmd/Ctrl+Enter` triggers Apply when dirty (with `aria-keyshortcuts` on the Apply button); `Cmd/Ctrl+S` triggers Validate. Validation and apply results surface as toasts (success/error/warn styled from status tokens) in addition to the inline message area. AC: shortcuts ignored when focus is in a text input unless explicitly documented (Apply still works — keep it simple: always active).

13. **Messaging view polish** — platform choice (discord/telegram) renders as a segmented control; voice-transcription settings grouped with a clear "Voice notes" subheader; platform logos from LobeHub where available. AC: segmented control is keyboard-accessible (arrow keys + radiogroup semantics).

### Nice-to-Have (Sprint 5+)

14. **Legacy `fcc-*` shims** — optional installer flag (`--legacy-fcc`) installs `fcc-*` scripts that print `fcc-server is deprecated: use hans-server` to stderr and exit 2; helps migration without permanently confusing the brand.
15. **Dark theme (optional)** — `@media (prefers-color-scheme: dark)` token overrides reusing the original dark palette values; no structural changes.
16. **`claudey doctor`** — quick diagnostics subcommand: prints version, module path, admin URL, port, which providers have keys, and config file path.
17. **App icon assets** — generate `assets/claudey-icon.png` (512px) and macOS `.icns`/Windows `.ico` from the starburst mark for installer and desktop use.

## Technical Stack

- **Backend**: Python 3.14, FastAPI (existing), uvicorn, pydantic-settings, httpx — unchanged. No new runtime deps if avoidable.
- **Frontend**: vanilla HTML/CSS/JS served from `admin_static/` — no build step, no framework. The rename touches `admin.js` only for strings/env-var names; the theme is a CSS-token swap.
- **Icons**: LobeHub brand icons, vendored as static SVGs (`admin_static/logos/`), sourced from `@lobehub/icons` (npm) or `lobehub.com/icons` / `github.com/lobehub/lobe-icons` raw files; refresh script `scripts/fetch_provider_logos.py`; letter-chip SVG fallbacks.
- **CLI**: `[project.scripts]` entries + new `claudey/cli/dispatcher.py` thin wrapper.
- **Tooling**: uv (`uv lock` after pyproject changes), ruff (format + lint), ty, pytest with pytest-xdist; `scripts/ci.sh` must stay green; smoke suite renamed consistently.
- **Key constraint**: do not touch the provider/config/core logic beyond renames and string updates — this is a rebrand + UI sprint, not a rewrite.

## Evaluation Criteria

See `gan-harness/eval-rubric.md` for the executable rubric. Summary of what "good" means here:

- **The rename is total.** A fresh `grep -ri "free-claude-code\|free_claude_code\|fcc-"` over `src/`, `scripts/`, `tests/`, `smoke/`, `.github/`, README/AGENTS/CLAUDE/CONTRIBUTING/ARCHITECTURE surfaces zero hits outside the documented legacy-shim and `FCC_*`-fallback carve-outs. `import claudey` works; `import free_claude_code` fails; `hans-server --version` → `claudey 5.0.0`.
- **The UI is unambiguously light and warm.** Paper background, coral accent, hairline borders, no purple gradients, no glassmorphism, no emoji icons; status colors remain distinct.
- **Provider logos are real and complete.** Every provider card in the grid shows its LobeHub logo (or a tasteful letter-chip fallback), and the brand mark is the Anthropic starburst.
- **It feels like a product, not a theme swap.** Onboarding empty state, status pill, keyboard shortcuts, and model-config clarity make the admin genuinely more intuitive; all copy reads like it was written for Claudey, not find-replaced.

## Sprint Plan

### Sprint 1: The Great Rename
- Goals: zero remaining `free_claude_code`/`fcc-*` in code and tooling; version 5.0.0; all tests/smoke green.
- Features: #1, #2, #3, #4 (env migration), version bump + `uv lock`.
- Definition of done: `git mv` rename complete; `uv run ./scripts/ci.sh` green (ruff format, ruff check, ty, pytest); smoke lib/child_process + cli tests updated and passing; `hans-server --version` prints `claudey 5.0.0`; `claudey server` works; `FCC_*` fallback test exists and passes.

### Sprint 2: Brand & Light
- Goals: the app visibly becomes *Claudey* — light theme, starburst mark, LobeHub logos, installers/docs rebranded.
- Features: #5, #6, #7.
- Definition of done: admin UI fully light-themed with token swap (no stray dark values); logos dir has 30+ SVGs + anthropic.svg; README/AGENTS/CLAUDE/installers carry zero old-brand strings; desktop tray shows "Claudey"; `uv run ./scripts/ci.sh` still green.

### Sprint 3: Intuitive UX
- Goals: first-run clarity and daily-driver polish.
- Features: #8, #9, #10, #11, #12, #13.
- Definition of done: onboarding empty state appears with no keys and disappears with a key; provider cards show logos + status + focus-on-configure; status pill renders; Cmd/Ctrl+Enter applies; messaging segmented control works; all interactive elements keyboard-accessible; `uv run ./scripts/ci.sh` green; new UI tests (if any) pass.

### Sprint 4: Polish & Legacy
- Goals: legacy escape hatch, optional extras, final QA.
- Features: #14, #15, #16, #17 (as time allows; #14 recommended).
- Definition of done: `--legacy-fcc` installer flag works (shims print deprecation, exit 2); dark theme optional extra is consistent; `claudey doctor` outputs clean diagnostics; final `grep` audit clean; full CI + smoke suite green; commit per project rules with version bump on production changes.

## Edge Cases & States (must be handled)
- **Empty state**: no keys configured → onboarding card; grid still lists all providers as "Not configured".
- **Error state**: invalid key → provider card shows error pill + toast; Apply stays enabled for retry; error message is human-readable, not a stack trace.
- **Loading state**: health check and validation show "Validating…" with pulse; no layout shift (skeleton via existing card structure).
- **Dirty state**: any form change enables Apply and flips the dirty indicator; refresh without applying shows a `beforeunload` guard.
- **Responsive**: below 900px, sidebar collapses to icon rail with labels hidden; action bar wraps; provider grid becomes single column; touch targets ≥ 40px.
- **Reduced motion**: `prefers-reduced-motion: reduce` disables pulse/translate animations.
- **Legacy env**: existing user `.env` files with `FCC_*` names keep working (fallback), with a one-time log note suggesting the `HANS_*` name.
