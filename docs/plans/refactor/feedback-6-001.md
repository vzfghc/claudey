# Evaluation — Sprint 6 — Iteration 001

**Branch:** `feat/phase-a-free-providers` · **Sprint:** 6 — markdown inline token-walk dedup (M1b) · **Date:** 2026-08-13 · **Mode:** code-only
**Baseline:** `eb4f16dd` (Sprint 5 iter 3) → `49b1ee70` + `29809644` (HEAD)

## Scores

| Criterion | Score | Weight | Weighted | Band justification |
|-----------|-------|--------|----------|--------------------|
| C1 CI gate green | 9/10 | 0.30 | 2.70 | All 7 `ci.sh` checks green on evaluator's first run (logos, icons, suppressions, ruff-format, ruff-check, ty, pytest). Deduct 1: `git status --short` still shows stray harness artifacts at root (`admin-ui-check.png` modified, 23 untracked: `.playwright-mcp/`, `budget-*.png`, `collapsed-*.png`, etc. — Sprint 8 scope, not introduced by this diff). Committed sprint state itself is clean. |
| C2 Behavior preservation | 10/10 | 0.25 | 2.50 | Full suite 3169 passed / 73 skipped, coverage 91% (≥80% and ≥baseline), wire/env/payload/CLI/retry/wording diff clean, byte-identity proved non-circular via isolated Sprint-5 worktree (9 samples incl. nested emphasis, code escaping, link URL escaping, table, entities all identical). |
| C3 Principle adherence | 10/10 | 0.20 | 2.00 | Single token-walk skeleton via `InlineRenderProfile` hooks; platform escape/emit stays in platform modules; no new cross-layer edges, no suppressions, no `TYPE_CHECKING`, no local-import cycle dodge. |
| C4 Dead-code & hygiene | 7/10 | 0.10 | 0.70 | Neutral sprint per rubric §5: no hygiene deletions required; no junk added. Sprint 8 inventory probes (`beam/`, `HANS_*`, `nvidia_nim` literals) correctly deferred — hits are pre-existing, not introduced. |
| C5 Code health | 9/10 | 0.15 | 1.35 | Walker 83 L, frozen `slots=True`, list-accumulation + `join`, no mutation; longest new functions 15–17 L (<50). Deduct 1: initial `49b1ee70` introduced `+=` increments in `markdown_walk.py` (`index += 1` / `link_index += 1`), fixed within iteration by `29809644` (`index = index + 1`). No file >800 L. |
| **TOTAL** | | | **9.25/10** | **PASS** (threshold 7.0) |

## Verdict: PASS — recommend proceeding to Sprint 7 (literals/naming/file sizes)

## Scope Discipline — PASS
- `git diff --stat eb4f16dd..HEAD` = 5 files, all in-scope (rendering modules + walker + golden tests + `gan-harness/generator-state.md`):
  - `src/claudey/messaging/rendering/discord_markdown.py` (68 lines removed → delegation)
  - `src/claudey/messaging/rendering/telegram_markdown.py` (70 lines removed → delegation)
  - `src/claudey/messaging/rendering/markdown_walk.py` (new, 83 L)
  - `tests/messaging/test_markdown_golden.py` (new, 22 golden tests)
  - `gan-harness/generator-state.md` (harness state)
- No out-of-scope files touched, no test edits that change behavior, no version bump (feature branch — correct), no wire/env/CLI changes.

## Critical Issues (must fix)
None.

## Major Issues (should fix)
None.

## Minor Issues (nice to fix)
1. **[LOW] `markdown_walk.py:27,34` increment follow-up created two commits.** The `+=` → `= ... + 1` fix was correct but landed as `29809644` on top of `49b1ee70`. Squash or keep — no action needed for gate, but note for hygiene: prefer single-commit fix before pushing.
2. **[LOW] `telegram_markdown.py:61-79` / `discord_markdown.py:64-86` duplicated `render_inline_table_plain` + list/blockquote scaffolding.** Out of scope for Sprint 6 (only inline walk was target), but Sprint 5 overlap remains. Do not expand Sprint 6 to dedup it; consider noting as Sprint 7-adjacent if file-size split touches rendering.
3. **[LOW] Golden test `test_markdown_rendering_byte_identical` bundles both platforms in one parametrized test.** Works, but a failure message prints both diffs. Splitting into `test_telegram_golden` / `test_discord_golden` would isolate failures — optional, not required.
4. **[INFO] Stray artifacts at repo root persist** (`admin-ui-check.png` modified, `.playwright-mcp/`, `budget-*.png`, `collapsed-*.png`, `docs/plans/refactor/*.md` untracked). Owned by Sprint 8 — no deduction beyond C1 note; ensure Sprint 8 deletes them per plan §8.2.

## What Improved Since Last Iteration (Sprint 5 → 6)
- Extracted shared `markdown_walk.py:21` `render_inline_tokens()` + `InlineRenderProfile` (frozen, slots) — eliminates structural duplicate `render_inline` loops at `telegram_markdown.py:80-119` / `discord_markdown.py` counterpart.
- Platform modules now 2-line delegation (`render_inline` → `render_inline_tokens(profile)`) with platform escape rules (`escape_md_v2` vs `escape_discord`) retained in place.
- Added 22 real characterization tests covering headings, bold/italic/strikethrough, nested emphasis, inline/block code escaping, links (URL escaping diverges correctly), images (with/without alt), bullet/ordered lists, blockquote, HTML entities, tables (single + multi-row), line breaks, multi-paragraph, mixed structures — parametrized, deterministic, byte-exact.
- Walker uses `list[str]` accumulation + `"".join` — no `+=` string loops in final HEAD (verified `grep -F '+='` → 0 hits).

## What Regressed Since Last Iteration
None — byte output identical for all sampled cases; full suite +2 tests (3147 → 3169 baseline is pre-existing growth + 22 golden; no failures).

## Specific Suggestions for Next Iteration (Sprint 7)
1. Keep Sprint 7 strictly to `config/constants.py` map + `HANS_*` → `CLAUDEY_*` renames + `openai_chat/provider.py` split — do not re-touch rendering.
2. When adding `NIM_WHISPER_DEVICE` constant, grep `"nvidia_nim"` after and document prose/docstring hits that intentionally remain (e.g. `api/usage_aggregate.py:7` prose).
3. For `openai_chat/provider.py` split, freeze public surface (`OpenAIChatProvider` method names/signatures) and add a one-line import-boundary smoke import of vendor subclasses in the PR description.

## Verification Commands Run (and outcomes)

| Command | Outcome |
|---------|---------|
| `git log --oneline -10` | `29809644` (walker `+=` fix) on top of `49b1ee70` (sprint 6) on top of `eb4f16dd` (sprint 5) — as expected |
| `git diff --stat eb4f16dd..HEAD` | 5 files, 308 ins / 177 del — scope clean |
| `uv run pytest -v -k golden` | 22 passed |
| `uv run ruff format --check . && uv run ruff check .` | 508 files already formatted, All checks passed |
| `uv run ty check` | All checks passed |
| `uv run pytest tests/contracts/test_import_boundaries.py -n0 -q` | 21 passed in 4.92s |
| `grep -rn "def render_inline" src/claudey/messaging/rendering/` | 2 delegation `render_inline` (telegram/discord) + 1 walker `render_inline_tokens` + 2 `render_inline_table_plain`/`render_inline_plain` helpers (distinct names, not the deduped walk) — gate PASS |
| `grep -F '+=' src/claudey/messaging/rendering/markdown_walk.py` | 0 hits (fixed by 29809644) |
| `grep -En "_string_attr\|escape_md_v2\|escape_discord" src/claudey/messaging/rendering/markdown_walk.py` | 0 hits — walker uses `profile.escape_*` only |
| Isolated worktree byte-identity check (`/tmp/claudey-sprint5` at `eb4f16dd` vs HEAD) | 9 hardest cases (`headings`, `***nested***`, fenced code, link URL escaping, bullet list, table, entities, image alt, ordered list) — all byte-identical (see log snippet below) |
| `uv run pytest -q` (full suite) | 3169 passed, 73 skipped, 2 warnings in 89.62s (target run) / 3169 passed in 89.03s via `ci.sh` — matches baseline 3147+22 |
| `uv run pytest --cov=claudey --cov-report=term-missing -q` | TOTAL 19666 1836 91% — ≥80% and ≥Sprint-0 baseline → no C2 cap |
| `./scripts/ci.sh` (all 7 checks) | provider logos ✓, app icon assets ✓, Ban suppressions ✓, ruff format ✓, ruff check ✓, ty ✓, pytest 3169/73 ✓ — "All selected CI checks passed." |
| Adversarial greps (`from claudey.application` in providers, `from claudey.providers` in config/application, `# type: ignore`, `TYPE_CHECKING`, `google_openai`, `HANS_CONFIG_DIRNAME`, `"nvidia_nim"`, `beam`) | All hits are pre-existing Sprint 4/7/8-owned items — none introduced by Sprint 6 diff (verified via `git diff --name-only eb4f16dd..HEAD` only rendering files) |
| `wc -l` touched files | `markdown_walk.py` 83 L, `telegram_markdown.py` ~271 L (down from 327), `discord_markdown.py` ~275 L (down from 318) — all <800; `test_markdown_golden.py` 180 L |
| `ast` function length check | New walker funcs 6–17 L; platform `render_markdown_*` 208/218 L pre-existing (not new code, not >50 L guideline breach) |

**Byte-identity spot-check log (Sprint 5 output, isolated worktree):**
```
'# Heading 1\n## Heading 2'  TG '*Heading 1*\n*Heading 2*'  DC '**Heading 1**\n**Heading 2**'
'***nested***'  TG '_*nested*_'  DC '***nested***'
'```python\nprint(`x`)\path\n```'  TG '```\nprint(\`x\`)\\path\n```'  DC same
'[text](https://example.com/a_(b))'  TG '[text](https://example.com/a_(b\))'  DC '[text](https://example.com/a_(b))'
'- first\n- second'  TG '\- first\n\n\- second'  DC '- first\n\n- second'
'| A | B |\n|---|---|\n| 1 | `two` |'  TG '```\n| A   | B   |\n| --- | --- |\n| 1   | two |\n```'  DC same
'AT&amp;T &lt;tag&gt; &#35;1'  TG 'AT&T <tag\> \#1'  DC 'AT&T <tag\> #1'
'![alt *text*](https://img.example/a.png)'  TG 'alt \*text\* (https://img.example/a.png)'  DC same
'3. third\n4. fourth'  TG '3\. third\n\n4\. fourth'  DC '3. third\n\n4\. fourth'
```
All match `tests/messaging/test_markdown_golden.py` expected values — golden tests are non-circular.

## Positive Findings (do not churn)
- `InlineRenderProfile` is frozen/slots, callable-based — minimal, not a framework; no platform conditionals inside walker.
- `markdown_walk.py:81-83` `_string_attr` correctly guards `token.attrGet` return type (`str` else `""`) — edge-case correct.
- `discord_markdown.py:81` `escape_url=lambda value: value` identity correctly preserves Discord's no-escape URL semantics vs Telegram's `escape_md_v2_link_url`.
- `telegram_markdown.py:14-17` / `discord_markdown.py:15-17` table/strikethrough parser setup untouched — behavior preserved.
- `test_markdown_golden.py` IDs are descriptive, assertions print `Expected`/`Got` repr for both platforms — debuggable.
- Two-commit `+=` fix shows generator self-corrected without evaluator feedback — good hygiene signal.

## Methodology Notes
- Golden tests landed in same commit as extraction (`49b1ee70`) — normally circular, but evaluator independently reconstructed Sprint 5 output via `git worktree add /tmp/claudey-sprint5 eb4f16dd` and confirmed byte identity without trusting the report.
- Evaluator did not edit code; all checks run on committed HEAD (`29809644`).
- Screenshots not applicable (code-only eval).

## Recommendation
**PASS (9.25/10) — proceed to Sprint 7.** No iteration 2 needed. One optional squash of `29809644` into `49b1ee70` before merge to `main` if the team prefers a single Sprint-6 commit, but not required for correctness.
