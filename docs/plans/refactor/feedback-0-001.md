# Feedback — Sprint 0, Iteration 001 (Foundation: import-boundary contract green)

Branch: `feat/phase-a-free-providers` · Evaluated commit: `0db4fb43` (work) + `e195e202` (state doc) · Date: 2026-08-13

## Scores

| Criterion | Score | Weight | Weighted |
|-----------|-------|--------|----------|
| C1 CI gate green | 10/10 | 0.30 | 3.0 |
| C2 Behavior preservation | 10/10 | 0.25 | 2.5 |
| C3 Principle adherence | 10/10 | 0.20 | 2.0 |
| C4 Dead-code & hygiene | 7/10 | 0.10 | 0.7 |
| C5 Code health | 10/10 | 0.15 | 1.5 |
| **TOTAL** | | | **9.7/10** |

**Verdict: PASS** (threshold 7.0). Sprint 0 lands green; this is a genuine iteration-1 pass — the diff is small (14 files, +115/−33), every probe came back empty, and the report's gate outcomes reproduce.

## Criterion Citations

- **C1 = 10** (band: "all 7 checks pass on the evaluator's first run; git status clean"). Boundary test 21/21 passed on first evaluator run. `./scripts/ci.sh`: logos (40/40), icons (8/8), suppressions grep (0 hits), ruff format (503 files left unchanged — nothing to repair), ruff check (pass), ty (pass), pytest (1 failed, 3111 passed, 73 skipped). The single failure is the sanctioned pre-existing `test_catalog_publication_tracks_warm_refresh_and_direct_cache`; the orchestrator's exception applies (see below), so no cap. Committed state re-verified check-only: `ruff format --check` → "503 files already formatted", `ruff check` → pass. `git status --porcelain` after the full gate: zero tracked-file modifications → no misreported-green evidence.
- **C2 = 10** (band: "full suite green; coverage ≥80% and ≥baseline; protocol/env/payload/CLI/retry/wording diff audit clean; no user-visible string changed"). Coverage `TOTAL 19682 1872 90%` ≥ 80% and ≥ the 90% baseline. Diff audit: `health.py` move is a 100% similarity rename; `test_health.py` move is 99% with the import block only; the three promoted constants are byte-identical (`ANTHROPIC_VERSION_HEADER = "2023-06-01"`, identical function bodies in `core/anthropic/urls.py:14-31`); zero touched files in the frozen surfaces (`admission.py`, `stream_recovery.py`, `failure_policy.py`, `config/settings.py`, `.env.example`, `pyproject.toml` — version stays 5.26.0, `src/claudey/cli/` all untouched). Removed-line audit shows only moved constant definitions and docstrings — no user-visible string altered.
- **C3 = 10** (band: "all in-scope violations resolved; all grep gates at 0; zero new violations; the two sanctioned contract edits are the only edits to test_import_boundaries.py"). All greps: `from claudey.providers` in `config/` and `application/` → 0; `providers.health` in src/tests/smoke → 0; `openai_chat.base_url` → 0 (file deleted, zero importers — complete migration, no shim); no stale importers of the three constants. `tests/contracts/test_import_boundaries.py` diff = exactly the sanctioned `"config": {"core"}` amendment plus its documenting comment, nothing else (verified hunk-by-hunk). The comment's factual claims are true: `config/custom_providers.py:21` → `core.secret_crypto`, `config/custom_provider_check.py:16-19` → `core.anthropic.urls`. ARCHITECTURE.md:86 cell `none` → `core` plus rationale note at :102-106; `test_architecture_contracts.py` green. New `core/anthropic/urls.py` imports nothing (true leaf).
- **C4 = 7** (neutral non-target sprint per rubric §5). No junk added; deleting `openai_chat/base_url.py` is hygiene-positive. Pre-existing untracked root junk untouched — correct (Sprint 8 scope).
- **C5 = 10** (band: "all checks pass; moved code is clean"). New `urls.py` is 32 lines, focused, docstringed, functions 9/3 lines, no magic numbers beyond the frozen constant value, no suppressions (CI check passes), no `+=` loops, no mutation. `health.py` content untouched by the move.

## Sanctioned Exception Confirmation

- ONLY full-suite failure = `tests/runtime/test_provider_manager.py::test_catalog_publication_tracks_warm_refresh_and_direct_cache` (CI log line 6500: "1 failed, 3111 passed").
- File untouched by Sprint 0: `git diff 0db4fb43^ 0db4fb43 -- tests/runtime/test_provider_manager.py` → empty; last commit touching it is `08d59425` (rebrand, v5.0.0).
- Failure mode is a warm-refresh race (snapshot at index 1 contains `ovhcloud/warm-model` and `llm7/warm-model` extra entries) with loguru deadlock noise — a provider-runtime discovery timing issue, not an import-boundary symptom. C1/C2 not capped per orchestrator instruction.

## Issues

### Critical
None.

### High
None.

### Medium
None.

### Low
1. **Coverage numbers in the report don't reproduce exactly** — `sprint-report-0-001.md:44` records post-sprint coverage as `TOTAL 19682 1874 90%`; the evaluator's run measured `TOTAL 19682 1872 90%`. Same statement count and same 90% (gate outcome identical), so this is xdist coverage-attribution nondeterminism (the failing warm-refresh test executes slightly different lines per run), not a misreport of the gate. Severity: LOW. Criterion: C1 (report accuracy). Fix directive: in future reports, state coverage as percent + statements only, or note that missed-line counts are run-dependent; no code change needed.
2. **Facade re-export leaves one external name unresolved by the plan's importer list** — `src/claudey/providers/openai_chat/__init__.py:3,61` re-exports `openai_v1_base_url` from core, consumed by `smoke/lib/local_providers.py:8`. This is legitimate (ARCHITECTURE.md sanctions package initializers publishing supported exports; smoke needs no change) and the report documents it at `sprint-report-0-001.md:55` — recorded for awareness only, no action. Criterion: C3 (informational). Fix directive: none; when Sprint 8 considers removing the facade export, `smoke/lib/local_providers.py:8` must be repointed in the same commit.

## Positive Findings (do not churn these)

- C3 contract amendment is exactly as pre-approved: one line + documenting comment, nothing else in the contract file.
- Constant values and function bodies are byte-identical after the move; `git` rename detection confirms pure `git mv` (100% / 99% similarity).
- `base_url.py` deletion is a true complete migration with grep evidence of zero importers.
- The report's rebuttal #1 (plan's importer list was incomplete — `profiles.py:12`, `__init__.py:3`, `smoke/lib/local_providers.py:8`) is accurate and handled correctly.
- The report's rebuttal #2 (pre-existing failure) is corroborated by git history and the failure's nature.
- ARCHITECTURE.md policy cell and rationale note are truthful and link-valid (`test_architecture_contracts.py` green).

## Verification Commands Run (evaluator, all on current tree)

| Command | Outcome |
|---|---|
| `uv run pytest tests/contracts/test_import_boundaries.py -n0` | 21 passed |
| `./scripts/ci.sh` | logos 40/40; icons 8/8; suppressions 0; ruff format 503 unchanged; ruff check pass; ty pass; pytest 1 failed (sanctioned) / 3111 passed / 73 skipped; exit 1 |
| `git status --porcelain` (after ci.sh) | 0 tracked modifications; untracked = pre-existing junk + refactor docs |
| `uv run ruff format --check` / `uv run ruff check` | "503 files already formatted" / "All checks passed" |
| `uv run pytest --cov=claudey --cov-report=term-missing -q` | TOTAL 19682 1872 90%; 1 failed (sanctioned), 3111 passed |
| `grep "from claudey\.providers\|import claudey\.providers" src/claudey/config/ src/claudey/application/` | 0 hits |
| `grep "providers\.health" src/ tests/ smoke/` | 0 hits |
| `grep "openai_chat\.base_url" src/ tests/ smoke/` | 0 hits |
| `grep -rn "anthropic_messages_url\|ANTHROPIC_VERSION_HEADER\|openai_v1_base_url" src/ tests/ smoke/` | all importers point at `core/anthropic/urls.py` or the sanctioned facade re-export |
| `git diff 0db4fb43^ 0db4fb43 --stat` | 14 files, +115/−33, matches report |
| `git show 0db4fb43 -- src/claudey/{providers => application}/health.py` | similarity 100% (pure rename) |
| `git show 0db4fb43 -- tests/{providers => application}/test_health.py` | similarity 99%, import-block-only change |
| `git diff 0db4fb43^ 0db4fb43 --stat -- admission.py stream_recovery.py failure_policy.py settings.py .env.example pyproject.toml cli/` | empty (frozen surfaces untouched) |
| Probes: `google_openai` in src/tests/smoke → 5 pre-existing hits; `HANS_` → pre-existing (Sprint 7 scope); `beam` in api → pre-existing (Sprint 8 scope); none introduced by this diff | no regression |

## Specific Suggestions for Next Iteration (Sprint 1)

1. Sprint 1 is wide (30+ files of `ProviderModelInfo` import churn) — use `git mv` for `application/model_metadata.py` → `core/model_metadata.py` and record the grep list (src + ~20 test files) in the report as the plan requires.
2. Keep the boundary test as the regression gate: run it with `-n0` immediately after the last import repoint, before the full gate.
3. When you record coverage, report the percent and statement count; missed-line counts are xdist-nondeterministic.
4. The deferred `test_catalog_publication_tracks_warm_refresh_and_direct_cache` failure is a provider-runtime race — flag it to the orchestrator for triage; it will keep blocking `./scripts/ci.sh` exit 0 for every subsequent sprint.
