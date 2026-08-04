# Evaluation Rubric: Claudey Rebrand

> Consumed by the Evaluator agent. Score each category 0–10, apply weights, sum to 100. Report per-criterion evidence (commands run, files inspected, greps executed).

## 0. Hard Gate — Blockers (any fail ⇒ overall score 0)

- [ ] `uv run python -c "import claudey"` succeeds; `uv run python -c "import free_claude_code"` fails.
- [ ] `hans-server --version` prints `claudey 5.0.0` (not `free-claude-code …`).
- [ ] `uv run ./scripts/ci.sh` passes (ruff format, ruff check, ty, pytest) with the rebranded tree.
- [ ] No `free-claude-code` / `free_claude_code` / `fcc-` strings remain in user-facing surfaces: `src/`, `scripts/`, `README.md`, `AGENTS.md`, `CLAUDE.md`, `.env.example`, `.github/` (legacy `FCC_*` env fallback carve-out allowed only in env-migration code; `--legacy-fcc` shims allowed only if clearly deprecated).
- [ ] Admin UI renders in the browser at the documented local address (light theme, no broken assets).

## 1. Design Quality (weight 0.3)

Score the admin UI as a designed artifact, not a palette swap.

- [ ] Light theme is warm/paper (`#FAF9F7`-family), coral accent `#D97757`-family, hairline borders; `color-scheme: light` set.
- [ ] No purple/indigo/blue gradient buttons, no glassmorphism, no >14px radii on cards, no emoji icons, no stock illustrations. (Each violation −2.)
- [ ] Status colors (ok/warn/error/info) remain clearly distinguishable in light mode.
- [ ] Brand mark = Anthropic starburst (LobeHub) + lowercase `claudey` wordmark in sidebar and `<title>`.
- [ ] Typography hierarchy consistent; mono font used for paths/commands/keys; body text contrast ≥ 4.5:1.
- [ ] Spacing/alignment: cards, grids, and the sticky action bar are aligned on a consistent grid; no orphaned or misaligned elements at 1280px and 375px widths.

## 2. Originality (weight 0.2)

- [ ] The product reads as *Claudey*, not a find-replace job: copy in empty states, tooltips, error messages, and the onboarding flow is written for the new brand with real commands (`hans-server`, `hans-claude`, `claudey`).
- [ ] Onboarding empty state exists when no keys configured and is a genuinely helpful 3-step guide with copy-to-clipboard; disappears once a key is applied. (None ⇒ 0 for this criterion.)
- [ ] The `claudey` unified command exists and is ergonomic (`claudey server|claude|codex|pi|desktop|--version`), not a script that merely re-exes itself awkwardly.
- [ ] Visual identity is distinctive: starburst mark + warm paper + coral is recognizable as "the Claudey admin," not generic SaaS.
- [ ] No dark-theme-only leftovers (e.g., unreadable text, hardcoded `#0f1118` backgrounds) in the light UI.

## 3. Craft (weight 0.3)

Polish and robustness of the implementation.

- [ ] Every provider card in the grid shows its provider logo (LobeHub SVG or tasteful letter-chip fallback); connected accounts show provider logos too. Count cards vs logos: ≥95% coverage, zero broken-image icons.
- [ ] `scripts/fetch_provider_logos.py` (or equivalent) documents the LobeHub source map and can re-fetch; no external asset fetched at runtime (all vendored in `admin_static/logos/`).
- [ ] Env migration: `HANS_ENV_FILE`/`HANS_SMOKE_TARGETS` work, `FCC_*` legacy fallback works, and a test asserts both spellings resolve identically.
- [ ] Server status pill renders (running/stopped + port) with a graceful fallback if the endpoint is unavailable; pulse animation respects `prefers-reduced-motion`.
- [ ] Keyboard: Cmd/Ctrl+Enter applies when dirty; Cmd/Ctrl+S validates; Apply disabled/aria-keyshortcuts consistent; messaging segmented control is a keyboard-accessible radiogroup.
- [ ] States: loading ("Validating…" no layout shift), error (human-readable, card-level), dirty (beforeunload guard), empty (onboarding), responsive <900px (collapsible sidebar), touch targets ≥40px.
- [ ] Desktop tray shows "Claudey" with starburst icon; macOS bundle id updated; installers use `hans-*` names and `HANS_COMMANDS`.
- [ ] Docs: README wordmarks rebranded, badges → fork; AGENTS.md ≡ CLAUDE.md (identical files, repo rule).
- [ ] No mutation/no-dead-code regressions; code stays within repo conventions (small files, no magic numbers).

## 4. Functionality (weight 0.2)

Critical user flows must survive the rebrand intact.

- [ ] Flow A: `hans-server` starts; admin UI loads; a provider key is added and Applied; validation reports success; `hans-claude` connects through the proxy (or equivalent smoke check).
- [ ] Flow B: `claudey server` and `claudey claude` behave identically to `hans-server`/`hans-claude` for basic invocations and `--version`.
- [ ] Flow C: fresh checkout install path — installer script references resolve (`hans-claude` prompt, `HANS_MACOS_BUNDLE_ID`, `.claudey-owner`), dry-run passes.
- [ ] Flow D: existing `.env` with `FCC_*` names still works after upgrade (legacy fallback).
- [ ] Versioning: `pyproject.toml` is `5.0.0` and `uv.lock` is in sync; production changes are committed with the version bump per repo rules.
- [ ] Tests updated, not deleted: rebranded names covered in `tests/cli/*`, `tests/scripts/*`, `smoke/*`; overall coverage still ≥80%.

## Scoring

```
score = 0.3·Design + 0.2·Originality + 0.3·Craft + 0.2·Functionality
```

Per-category grade: 9–10 exceptional, 7–8 solid with minor gaps, 5–6 major gaps, <5 fails the intent of the brief. Any Hard-Gate fail ⇒ 0 overall. Final report must include: evidence per criterion (grep outputs, screenshots/descriptions of UI states, CI log summary), the category scores, the weighted total, and a prioritized fix list.
