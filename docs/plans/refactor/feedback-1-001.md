# Evaluation — Sprint 1, Iteration 001

Branch: `feat/phase-a-free-providers` · Commit under review: `6ab7502d` · 2026-08-13 · Evaluator: GAN harness evaluator

## Scores

| Criterion | Score | Weight | Weighted |
|-----------|-------|--------|----------|
| C1 CI gate green | 10/10 | 0.30 | 3.0 |
| C2 Behavior preservation | 10/10 | 0.25 | 2.5 |
| C3 Principle adherence | 9/10 | 0.20 | 1.8 |
| C4 Dead-code & hygiene | 7/10 | 0.10 | 0.7 |
| C5 Code health | 9/10 | 0.15 | 1.35 |
| **TOTAL** | | | **9.35/10** |

## Verdict: PASS (threshold 7.0)

## Verification Commands and Outcomes

| Command | Outcome |
|---|---|
| `uv run pytest tests/contracts/test_import_boundaries.py -n0` | **21 passed** |
| `./scripts/ci.sh` (full, all 7 checks: logos, icons, suppressions, ruff-format, ruff-check, ty, pytest) | exit 0; **3100 passed, 73 skipped**; final line "All selected CI checks passed." |
| `git status --porcelain` after ci.sh | No modified tracked files — ci.sh repaired nothing → committed state genuinely check-clean (no misreported-green evidence) |
| `uv run ruff format --check` | 501 files already formatted |
| `uv run ruff check` | All checks passed |
| `uv run pytest --cov=claudey --cov-report=term-missing -q` | **TOTAL 19678 stmts / 1872 miss / 90%** — equals Sprint-0 baseline 90%, ≥80% gate |
| `uv run pytest tests/contracts/test_architecture_contracts.py -n0` | 5 passed (ARCHITECTURE.md link-validity green) |

## Adversarial Probes (iteration-1, all run by the evaluator)

1. `grep -rn "application\.model_metadata\|application\.errors"` across src/, tests/, smoke/, scripts/ → **0 hits**.
2. `grep -rn "from claudey\.application" src/claudey/providers/` → **exactly 2 hits**, both the sanctioned out-of-scope residual: `src/claudey/providers/openai_codex/auth.py:18` and `src/claudey/providers/anthropic/auth.py:5` (both `from claudey.application.connected_accounts import`). No others. Per the orchestrator's scope amendment, accepted as a documented residual → C3 capped at 9.
3. `src/claudey/application/model_metadata.py` and `src/claudey/application/errors.py` → **deleted** (git rename `{application => core}/`, no shim files, no re-export modules; `application/__init__.py` has zero re-exports).
4. `src/claudey/core/model_metadata.py` and `src/claudey/core/errors.py` → exist. `grep` for anthropic/openai/httpx SDK imports in `src/claudey/core/` → 0 hits (only claudey's own `core/anthropic/` package internals, e.g. `anthropic_error_payload`, `anthropic_request_snapshot` — protocol-neutral, contract-safe). **Core remains SDK-free.**
5. `grep -rn "from \.model_metadata\|from \.\.model_metadata"` → 0 hits (relative-import fix in `application/ports.py:9` verified correct).
6. `grep "from claudey.application"` in smoke/ → 0 hits.

## Issues

### Critical
None.

### Major
None.

### Minor
1. **[LOW, C5]** `src/claudey/core/errors.py:1` — module docstring still reads "Deterministic application and readiness errors." The module is now owned by `core/` (its sibling `core/model_metadata.py:1` was updated to "Provider-neutral model metadata shared across the application and providers."). Stale ownership wording. Fix directive: reword to e.g. "Deterministic request and readiness errors shared across the application and providers." (docstring-only change; no behavior impact).

## Positive Findings (do not churn these)

- **Complete migration, no shims**: both `application/model_metadata.py` and `application/errors.py` deleted; zero stale importers; zero re-export modules. `git show 6ab7502d` confirms rename-based history (`{application => core}`).
- **Verbatim class bodies (C2)**: `core/errors.py` is a 100% similarity rename (all four classes — `ApplicationError`, `InvalidRequestError`, `UnknownProviderError` + `for_provider` wording, `ApplicationUnavailableError` — byte-identical); `core/model_metadata.py` differs only in the module docstring — `ProviderModelInfo`/`ProviderModelRefreshResult` keep `frozen=True, slots=True`, same fields, same defaults, same class docstrings.
- **L3 grep decision correct**: the plan sanctioned moving provider-imported error classes, and the generator's grep-based extension (4 classes, not 1) matches the current tree (`openai_codex/provider.py:12`, `deepseek/compat.py:8`, `openai_chat/request_policy.py:10`, `openai_chat/profiles.py:8`, `google_openai/reasoning.py:6`, `runtime/factory.py`). Same for `ProviderModelRefreshResult` (`runtime/discovery.py` imports it).
- **Diff audit clean (C2)**: all non-import src changes are the one documented docstring line; all test changes are import-site rewrites — zero assertion added/removed/relaxed; no pyproject.toml / .env.example / .github / admin_ui_dist / smoke/ files touched (frozen surfaces untouched).
- **ARCHITECTURE.md prose-only**: package descriptions (`:48-52`, `:61-65`) and model-metadata owner paragraph (`:623-626`) updated consistently with the move; link-validity contract test green (5 passed).
- **Spot-checked 5 of 71 rewritten import sites** — all correct: `src/claudey/api/request_errors.py:18`, `src/claudey/application/ports.py:9` (relative→absolute fix), `src/claudey/providers/base.py:9`, `src/claudey/providers/runtime/discovery.py:12-15`, `src/claudey/providers/runtime/factory.py:16-20`; plus the out-of-plan live consumer `scripts/hans_schemathesis_app.py` (1-line mechanical update, correct).
- **No new junk added** by this commit (C4 neutral).

## Criterion Band Citations

- **C1 = 10**: all 7 checks pass on the evaluator's first run (rubric §2 "10" band); ci.sh repaired nothing (tree clean of tracked modifications); independent `ruff format --check` / `ruff check` confirm the committed state is check-clean.
- **C2 = 10**: full suite green (3100 passed); coverage 90% = baseline, ≥80% (rubric §3 "10" band); protocol/env/payload/CLI/retry/wording diff audit clean; no user-visible string changed; no test weakened.
- **C3 = 9**: all in-scope violations (H1, L3) resolved with complete migration and zero new violations (rubric §4 "10" band conditions met) — capped at 9 per the orchestrator's scope amendment: the only remaining `providers→application` edge is the two `connected_accounts` auth imports, documented in the report with grep evidence and outside Sprint 1's plan actions.
- **C4 = 7**: neutral sprint (rubric §5: earlier sprints score neutrally); commit adds no junk; pre-existing untracked root artifacts (`.playwright-mcp/`, screenshots, `model-config-skeleton.yml`) are Sprint 8 scope, not this commit's.
- **C5 = 9**: all health checks pass (no suppressions, no `+=` loops, no magic numbers, frozen dataclasses preserved, files small/cohesive) with one LOW nit — stale module docstring at `core/errors.py:1` (rubric §6 "8-9" band).

## What to Keep Doing
- Grep-first decisions (L3/H1 class-set expansion) documented with evidence.
- Complete-migration discipline: delete the old owner, no shims, update live out-of-plan consumers.
- Docstring/prose kept in sync with module ownership (ARCHITECTURE.md + model_metadata.py) — apply the same to core/errors.py.

## Next-Iteration Directive (only if a further iteration is run)
- Fix the LOW docstring nit at `src/claudey/core/errors.py:1` (docstring-only). No other action required for Sprint 1; this iteration passes.
