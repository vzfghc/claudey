# Evaluation — Iteration 001 (Sprint 1: The Great Rename)

## Hard Gates — ALL PASS

| Gate | Result | Evidence |
|------|--------|----------|
| 1. CLI | PASS | `import claudey` ok; `import free_claude_code` → ModuleNotFoundError; `hans-server --version`, `claudey --version`, `claudey server --version` all print `claudey 5.0.0`; bare `claudey` prints usage tree (server/claude/codex/pi/desktop) |
| 2. Grep audit | PASS | 0 hits for `free-claude-code`, `free_claude_code`, `Free Claude Code`, `fcc-` across src/, scripts/, README, AGENTS, CLAUDE, .env.example, .github/, tests/, smoke/. The only `FCC` hits in src/ (9) are documented legacy env fallbacks (env_files.py, env_migrations.py, settings.py `AliasChoices`, admin.js mapping) — category (a) allowed. tests/smoke `FCC` hits = fallback tests + `smoke/lib/config.py` fallback mechanism + JSON fixture strings (false positives) |
| 3. CI | PASS | ruff format: 467 files ok; ruff check: passed; ty check: passed; pytest: **2704 passed, 62 skipped, 0 failed** (57.4s); new tests tests/cli/test_dispatcher.py + tests/config/test_env_migrations.py: 27 passed |
| 4. Docs identity | PASS | `diff AGENTS.md CLAUDE.md` → IDENTICAL; README old-brand count: 0 |
| 5. UI | PASS | /admin HTTP 200, `<title>Claudey Admin</title>`, brand heading "Claudey" present, admin.css + admin.js both 200 (no broken assets); brand-mark still "FC" (documented Sprint 2 item) |

Additional verified: pyproject `name = "claudey"`, `version = "5.0.0"` bumped in the same commit as the rename (08d5942, 482 files, repo rule satisfied); uv.lock in sync (editable claudey 5.0.0); `[project.scripts]` = claudey + hans-server/claude/codex/pi, `[project.gui-scripts]` = hans-desktop; running server process is the rebranded `.venv/bin/hans-server`; `hans-claude --version` → 2.1.220, `hans-pi --version` → 0.80.10 (launchers forward correctly).

## Scores

| Criterion | Score | Weight | Weighted |
|-----------|-------|--------|----------|
| Design Quality | 2.5/10 | 0.3 | 0.75 |
| Originality | 6.0/10 | 0.2 | 1.20 |
| Craft | 8.0/10 | 0.3 | 2.40 |
| Functionality | 8.5/10 | 0.2 | 1.70 |
| **TOTAL** | | | **6.05/10** |

## Verdict: PASS (all 5 hard gates green; Sprint 1 scope complete)

The 6.05 weighted total is below the 7.0 threshold by construction: 30% of the weight (Design) is Sprint 2 scope and was explicitly deferred per spec (`admin.css` still `color-scheme: dark`, brand mark "FC"). Design must be re-scored at the end of Sprint 2. All Sprint 1 gates and Definition-of-Done items (rename total, version 5.0.0, CI green, fallback test passing, `hans-server --version` → `claudey 5.0.0`) are met. Do NOT interpret this score as Sprint 1 failure — every earnable criterion for this sprint scored 8+.

## Critical Issues (must fix before Sprint 2)

None — no hard-gate failures.

## Major Issues (should fix before Sprint 2)

1. **Legacy env-path regression**: `src/claudey/config/paths.py:7` — `LEGACY_REPO_DIRNAME = "claudey"` makes the legacy lookup resolve `~/claudey/.env`, not the true pre-rename location `~/free_claude_code/.env`. An existing user upgrading from the old checkout path silently loses the fallback lookup (Flow D of the rubric is only half-tested — dual-spelling test covers env names, not the repo-dir path). → Fix: set `LEGACY_REPO_DIRNAME = "free_claude_code"` and document it as a carve-out in the grep audit (a path string is not user-facing brand copy; the audit currently allows exactly this class of carve-out). The generator's stated reason ("keep clean under the hard-gate grep") inverted the priority — correctness beats grep cosmetics.

## Minor Issues (nice to fix)

1. `claudey` with no args exits 0; conventional CLIs exit 2 on missing subcommand (spec doesn't mandate it, but `echo $?` shows 0 which can mask script misuse).
2. `curl /api/health` → 404 and `/api/status` → Not Found — endpoint naming unknown; the Sprint 2 status pill (feature #10) will need a real health endpoint, so document which admin endpoints exist now.
3. `smoke/product/test_api_product_live.py` and smoke suite still have `FCC` fallback strings — fine per carve-out, but ensure Sprint 2 smoke additions use `HANS_*` names so the fallback layer stays legacy-only.
4. Hardcoded dark value check: admin.css still contains a `#0f1118`-family background hit — sweep it during the Sprint 2 token swap, not before.

## What Improved Since Last Iteration

- N/A — first iteration.

## Specific Suggestions for Next Iteration (Sprint 2)

1. **Light theme first, logos second.** Do the CSS token swap (feature #5) before the logo work — it's the highest-weight item (0.3) and the "implementation trick" in the spec makes it low-risk. Keep every variable name, swap values + `color-scheme: light`, and verify `--muted #78716C` contrast (spec already flags `#706B66` as the fallback if borderline).
2. **Brand mark + title** (feature #7): replace the `FC` in `brand-mark` with the LobeHub Anthropic starburst SVG (`admin_static/logos/anthropic.svg`) + lowercase `claudey` wordmark. This single change moves Design from 2.5 toward earnable and is the highest-leverage visual edit.
3. **Fix the LEGACY_REPO_DIRNAME regression** (above) in the same sprint, plus any other correctness-vs-grep tradeoffs — grep cleanliness must never cause behavior regressions.

## Screenshots / Evidence

- No browser screenshots captured (no Playwright MCP in this environment); UI verified via curl: HTTP 200 on /admin, /admin/assets/admin.css, /admin/assets/admin.js; `<title>Claudey Admin</title>`; brand-mark div contains `FC`; admin.js line 372 contains rebranded copy "Disconnect this ChatGPT account from Claudey?"; line 45 contains `FCC_ENV_FILE: "HANS_ENV_FILE"` migration map.
- CI evidence: `ruff format --check` → "467 files already formatted"; `ruff check` → "All checks passed!"; `ty check` → "All checks passed!"; `pytest -x -q` → "2704 passed, 62 skipped, 2 warnings in 57.44s" (2 warnings = pre-existing pty DeprecationWarnings in installer tests).
