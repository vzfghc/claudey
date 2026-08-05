# Evaluation — Iteration 002 (Sprint 3: Intuitive UX)

## Hard Gates — ALL PASS

| Gate | Result | Evidence |
|------|--------|----------|
| 1. Imports | PASS | `uv run python -c "import claudey"` → OK (`src/claudey/__init__.py`); `import free_claude_code` → ModuleNotFoundError |
| 2. Version | PASS | `hans-server --version` → `claudey 5.2.0`; `claudey --version` → `claudey 5.2.0`; pyproject `5.2.0`, uv.lock in sync (editable claudey 5.2.0); bump 5.1.0→5.2.0 committed in same commit as prod changes (db0eb944) |
| 3. Grep audit | PASS | Exactly 1 hit across src/ scripts/ README AGENTS CLAUDE .env.example .github/: `LEGACY_REPO_DIRNAME = "free-claude-code"` (paths.py:7) — the documented carve-out, and it is the *correct* legacy path (fix from feedback-001 applied). Remaining `FCC` hits (env_migrations.py, env_files.py, settings.py AliasChoices, admin.js map) are the legacy env-fallback carve-out |
| 4. CI | PASS | `ruff format --check`: 468 files already formatted; `ruff check`: All checks passed; `ty check`: All checks passed; `pytest -x -q`: **2711 passed, 62 skipped, 0 failed** (66s) — 7 new tests vs Sprint 1 (2704) |
| 5. UI serves | PASS | /admin HTTP 200, `<title>Claudey Admin</title>`, all assets 200, zero console errors in headless Chromium |

## Sprint 3 AC Verification — 34/34 browser checks pass

Ran `gan-harness/sprint3-verify.mjs` (headless Chromium against the live server) plus independent manual browser tests:

- **Onboarding empty state**: hidden when a key is configured; renders 3 steps with SVG icons (check/key/terminal, zero emoji) when no keys; copy button flips to "Copied!" + success toast; dismiss button persists flag in localStorage; flag auto-cleared when any key exists (card returns when all keys removed). Copy uses `navigator.clipboard` with a `execCommand` textarea fallback.
- **Provider cards**: 30 cards rendered, each with logo (`/admin/assets/logos/<providerId>.svg`), status pill (Configured green / Not configured neutral / Error red), Configure button that scrolls to and focuses `field-NVIDIA_NIM_API_KEY` with a 2.2s glow highlight.
- **Server status pill**: "Running on :8082 v5.2.0" with ok-tint bg `rgba(5,150,105,0.08)`, green dot; static "Claudey Admin" fallback in code if the endpoint fails; pulse animation disabled under `prefers-reduced-motion` (verified: `animation-name: none`).
- **Model Config**: 5 role cards (Fallback/Fable/Opus/Sonnet/Haiku) with sticky headers (`position: sticky; top: 16px`), plain-language descriptions ("Default used by Claude Code's /model picker…"), per-field Reset (marks dirty — verified "1 unsaved change"), "Uses provider default" placeholder + hint line.
- **Keyboard**: `Cmd/Ctrl+Enter` applies when dirty (verified toast), `Cmd/Ctrl+S` validates; `aria-keyshortcuts="Control+Enter Meta+Enter"` / `"Control+S Meta+S"` present on Apply/Validate; `defaultPrevented`/`isComposing` guards so combobox typing still works.
- **Toasts**: fixed top-right container, `aria-live="polite"`, 4s auto-dismiss, click-to-dismiss, ok/error/warn styling, inline SVG icons.
- **Messaging**: `role="radiogroup"` + per-segment `role="radio"` + `aria-checked` + roving tabindex; ArrowLeft/Right + Home/End navigation (verified selection syncs the hidden select); "Voice notes" subheader present.
- **Error path**: invalid key → Apply stays enabled, toast "Applied"; validation is shape-only ("Config shape is valid"); API-error pill/toast path implemented (`setCardPill` error class, `showToast` from `showMessage`).

## Design Audit (computed styles, headless Chromium)

- Body `rgb(250,249,247)` = #FAF9F7 warm paper, `color-scheme: light`; cards white with 1px hairline `#E7E5E4`, radius 10px (within 6/10/14 rule); no `backdrop-filter`, no `linear-gradient` anywhere, no purple/indigo tokens, no emoji in admin.js (0 unicode-emoji matches).
- Brand mark is the Anthropic starburst SVG + wordmark (sidebar + `<title>`).
- Card hover lift verified in CSS: `translateY(-2px)` + `--shadow-sm` + border-color change; disabled under reduced-motion.
- Sticky action bar (position: fixed), mono font for commands (`.command-pill code`).
- Muted `#78716C` on white = ~4.7:1 contrast (≥4.5 AC).
- No horizontal overflow at 375px; provider grid collapses to single column.

## Scores

| Criterion | Score | Weight | Weighted |
|-----------|-------|--------|----------|
| Design Quality | 8.5/10 | 0.3 | 2.55 |
| Originality | 9.0/10 | 0.2 | 1.80 |
| Craft | 8.0/10 | 0.3 | 2.40 |
| Functionality | 9.0/10 | 0.2 | 1.80 |
| **TOTAL** | | | **8.55/10** |

## Verdict: PASS (threshold 7.0) — 8.55/10

Trajectory: 6.05 (S1) → 7.45 (S2) → 8.55 (S3). Every Sprint 3 feature (#8–#13) is implemented, committed (db0eb944), and verified live in a real browser. This is the first iteration that scores above the "junior developer" band: the app genuinely reads as a product.

## Critical Issues (must fix)

None — no hard-gate failures, no broken features.

## Major Issues (should fix in Sprint 4)

1. **Missing `beforeunload` dirty guard** — spec Edge Cases ("Dirty state: … refresh without applying shows a beforeunload guard") and Craft rubric both require it; `admin.js` has zero `beforeunload`/`pagehide` handlers. The dirty indicator exists but a refresh silently discards unsaved edits. → Add `window.addEventListener("beforeunload", e => { if (dirty) { e.preventDefault(); e.returnValue = ""; } })` and test it (the existing apply path reloads the page on restart-required changes, so guard against firing during that reload — e.g., set a flag before `location.reload()`).
2. **Touch targets are 36px, spec requires ≥40px** — `.primary-button/.secondary-button/.ghost-button` all use `min-height: 36px` (admin.css:376). Verified: Configure/Test buttons measure 36px at 375px viewport. → Bump to `min-height: 40px` (or add a `@media (pointer: coarse)` override) — one-line change, keeps the 6/10/14 radius aesthetic.
3. **Sidebar does not collapse to an icon rail below 900px** — spec: "below 900px, sidebar collapses to icon rail with labels hidden". Implemented behavior: sidebar becomes a full-width horizontal top bar (position relative, labels visible) at ≤900px. It is functional and arguably more usable than an icon rail, but it deviates from the explicit AC. → Either document the top-bar choice in the spec as an accepted alternative, or implement the icon-rail collapse. Do not leave it silently divergent.

## Minor Issues (nice to fix)

1. **Sprint 4 WIP is uncommitted in the working tree** — `scripts/ci.sh` (new `icons` check), `scripts/generate_icons.py`, `dispatcher.py` (+131 lines, likely `claudey doctor`), install scripts, and 41 CSS lines are modified but not committed. The committed tree (db0eb944) is consistent, but `./scripts/ci.sh` as run from the working tree exercises different code than what's committed. → Commit Sprint 4 work incrementally with the version bump per repo rules; don't let WIP accumulate.
2. **`claudey` with no args exits 0** (feedback-001 note, still open) — conventional CLIs exit 2 on missing subcommand; trivial fix in dispatcher.
3. **Validate is shape-only** — "Config shape is valid" never touches the provider API, so the "Validating…" pulse and error pill only fire via Test/Refresh. Fine as designed, but the spec's error-state AC ("invalid key → provider card shows error pill + toast") is only reachable through Test — consider wording the Validate button as "Validate config" (shape) vs "Test" (live) so users aren't surprised.

## What Improved Since Last Iteration (Sprint 2)

- LEGACY_REPO_DIRNAME fixed to the true legacy path `free-claude-code` (feedback-001 critical item resolved, with the Anthropic logo fix).
- Full Sprint 3 feature set landed and is verified working in a real browser: onboarding (show/dismiss/reappear/copy), provider card upgrade, status pill with version, role-card model config, shortcuts + toasts, radiogroup segmented control.
- CI fully green (2711 passed) with the two stale admin tests replaced by real pill-contract tests.
- No glassmorphism/purple-gradient/emoji violations; theme is unambiguously light and warm.

## What Regressed Since Last Iteration

- None found. (Sprint 2 surfaces — light theme, logos, installers, desktop tray — all still intact; grep audit still zero old-brand hits.)

## Specific Suggestions for Next Iteration (Sprint 4)

1. Do the three Major fixes above first — they are each <10 lines and directly close rubric items (beforeunload guard, touch targets, sidebar responsiveness documentation).
2. For `claudey doctor` (#16): print version, module path, admin URL, port, per-provider key presence, config path — the `/admin/api/status` payload already has everything needed; reuse it.
3. For dark theme (#15): the spec's token-swap trick means a `@media (prefers-color-scheme: dark)` block reusing the original Sprint 1 palette values is low-risk — but only if the Sprint 3 additions (toasts, onboarding card, role cards, segmented control) get dark overrides too; test the full view set, not just providers.
4. If `--legacy-fcc` shims (#14) land, add the grep-audit carve-out line to the harness gate so the audit stays green by construction.

## Screenshots / Evidence

- Screenshots captured (headless Chromium, 1440x900 and 375x812): providers view, forced onboarding state, model config, messaging, mobile providers, toast, error-pill state — stored under /tmp/eval-shots/ (image rendering unavailable in this session; all assertions were verified via DOM/computed-style checks instead).
- Computed-style audit: body #FAF9F7, color-scheme light, card radius 10px + 1px hairline, sticky role headers top:16px, toast aria-live polite, no horizontal overflow at 375px, reduced-motion disables pill pulse and hover lift.
- CI evidence: ruff format 468 files OK; ruff check OK; ty check OK; pytest "2711 passed, 62 skipped, 2 warnings in 66.13s" (2 warnings = pre-existing pty DeprecationWarnings).
- Browser checks: `gan-harness/sprint3-verify.mjs` → 34/34 PASS; independent error-path/dirty-state/apply tests via Playwright all behaved correctly.
