# Sprint 4 Report — Iteration 001 (Provider family boundaries, H2)

Branch: `feat/phase-a-free-providers` · Date: 2026-08-13 · Generator report (evaluator re-verifies everything).

## Summary

`claudey.providers.google_openai` renamed to `claudey.providers.gemini_family` via `git mv` (4 files, 0 content change — history follows), all importers updated, the facade boundary amended (second sanctioned contract edit), ARCHITECTURE.md link updated, and the Sprint-3 LOW-1 carry-over (docstring reword) fixed. Pure rename — zero behavior change.

## Files Changed

| File (path:line) | Change |
|---|---|
| `src/claudey/providers/google_openai/` → `src/claudey/providers/gemini_family/` | `git mv` of all 4 files (`__init__.py`, `provider.py`, `reasoning.py`, `thought_signatures.py`); git detects 100% renames, 0 content lines changed |
| `src/claudey/providers/gemini/client.py:6` | Import `claudey.providers.google_openai` → `claudey.providers.gemini_family` |
| `src/claudey/providers/vertex/client.py:12` | Import `claudey.providers.google_openai` → `claudey.providers.gemini_family` |
| `tests/providers/test_gemini.py:12` | Import `claudey.providers.google_openai` → `claudey.providers.gemini_family` |
| `tests/contracts/test_import_boundaries.py:53` | **Sanctioned contract edit #2**: `"claudey.providers.gemini_family"` added to `FACADE_ONLY_BOUNDARIES` with a Sprint 4 (H2) comment |
| `tests/contracts/test_import_boundaries.py:209,212` | Mechanical path updates for the moved package in `test_google_reasoning_wire_fields_have_one_owner` (owner + roots list) |
| `ARCHITECTURE.md:676` | Link `providers/google_openai/` → `providers/gemini_family/` (link-validity contract test green) |
| `tests/providers/test_retryability_matrix.py:4` | **LOW-1 carry-over**: docstring reworded to "the pre-merge stream-recovery classifier" — `is_retryable_stream_error` grep gate back to 0 |

Note on plan item 2 ("internal `gemini_family/reasoning.py:13` cross-import"): the grep shows `reasoning.py` never imported `google_openai` (its only claudey imports are `core.*` and `claudey.providers.openai_chat` — line 13 stays valid). No edit needed; verified by grep rather than assumed. Module docstrings inside the package ("Google OpenAI-compatible endpoints") describe the wire API family, not the package name, and remain accurate since `GoogleOpenAIProvider` is intentionally not renamed — no docstring edit required.

## Verification (contract order)

| Step | Command | Outcome |
|---|---|---|
| Grep gate 1 | `grep -rn "google_openai" src tests smoke ARCHITECTURE.md` | **0 hits** (exit 1) |
| Grep gate 2 | `grep -rn "google_openai"` repo-wide (`--include` py/md/yml/toml/json/ts/tsx, excluding `docs/plans/refactor/`) | **0 hits** — complete migration |
| Grep gate 3 (carry-over) | `grep -rn "is_retryable_stream_error" src tests smoke` | **0 hits** |
| Format/lint | `uv run ruff format && uv run ruff check --fix` | 504 files unchanged; all checks passed |
| Type check | `uv run ty check` | All checks passed |
| Targeted tests | `uv run pytest tests/contracts/test_import_boundaries.py -n0 tests/providers/test_gemini.py tests/providers/test_vertex.py tests/contracts/test_architecture_contracts.py -q` | **84 passed** in 4.57s (boundary contract 21/21 incl. the new facade rule; ARCHITECTURE.md link test green) |
| Full suite + coverage | `uv run pytest --cov=claudey --cov-report=term-missing -q` | **3142 passed, 73 skipped**; TOTAL **19707 stmts / 1868 miss / 91%** |

## Coverage Delta vs Baseline

Baseline (Sprint 0, re-verified Sprint 3): 91%. This sprint: **91%** — identical statement/miss counts (19707/1868), zero regression.

## Rebuttals

None — all plan actions executed as specified.

## Frozen Invariants

Pure rename: no wire, env, admin payload, retry-budget, or wording constants touched. Diff is 11 insertions / 7 deletions across 6 files plus 4 pure renames; the only non-mechanical edit is the sanctioned facade amendment.

## Residual Risks

- None known. The facade guard is enforced by `test_external_consumers_use_owned_package_facades` (scanner-based); the full suite is green.
